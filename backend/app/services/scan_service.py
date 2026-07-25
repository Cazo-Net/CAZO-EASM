from sqlalchemy.orm import Session
from app.models.scan import Scan
from app.models.asset import Subdomain
from app.models.dns import DNSRecord
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.whois import WhoisRecord
from app.models.technology import Technology
from app.models.risk import RiskScore
from app.models.vulnerability import Vulnerability
from app.scanners.runner import ScanRunner
from app.database import SessionLocal
from app.core.scope import check_target_authorized
from app.services.audit import log_event
from app.services.notification_service import dispatch_notification
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class ScanService:
    """Service for managing scans."""
    
    def __init__(self, db: Session):
        self.db = db
        self.runner = ScanRunner()

    def _resolve_org(self, db: Session, scan: Scan) -> Optional[str]:
        """Resolve the owning organization for a scan (via its creator)."""
        if getattr(scan, "organization_id", None):
            return scan.organization_id
        user = db.query(__import__("app.models.user", fromlist=["User"]).User).filter_by(
            id=scan.created_by
        ).first()
        return user.organization_id if user else None

    def _resolve_scan_options(self, scan: Scan) -> dict:
        """Resolve runner options from scan_type profile + stored scan_options."""
        from app.config import settings

        scan_type = scan.scan_type or "full"

        # Parse stored scan_options if present
        stored_options = None
        if scan.scan_options:
            try:
                stored_options = json.loads(scan.scan_options)
            except (json.JSONDecodeError, TypeError):
                stored_options = None

        if scan_type == "quick":
            return {
                "scan_size": "small",
                "max_subdomains": settings.SCAN_SMALL_MAX_SUBDOMAINS,
                "port_mode": "quick",
                "include_nuclei": False,
                "subdomain_tools": ["default"],
            }
        elif scan_type == "custom" and stored_options:
            return stored_options
        else:
            # "full" or "custom" with no stored_options → defaults
            return {
                "scan_size": "large",
                "max_subdomains": settings.SCAN_LARGE_MAX_SUBDOMAINS,
                "port_mode": "full",
                "include_nuclei": True,
                "subdomain_tools": ["default", "subfinder", "amass"],
            }
    
    async def create_scan(
        self,
        domain: str,
        user_id: str,
        scan_type: str = "full",
        scan_options: Optional[dict] = None,
        project_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Scan:
        """Create a new scan.

        Enforces the authorized-scope policy: discovery is only permitted for
        targets matching an active AuthorizedScope of the owning organization.
        Raises ``PermissionError`` when the target is not authorized; the API
        layer translates this to HTTP 403 and records a failed audit event.
        """
        if organization_id:
            match = check_target_authorized(self.db, organization_id, domain)
            if not match.authorized:
                log_event(
                    self.db,
                    action="scan.create.denied",
                    organization_id=organization_id,
                    actor_id=user_id,
                    target_type="domain",
                    target_id=domain,
                    status="denied",
                    detail={"reason": match.reason},
                    request_id=request_id,
                )
                raise PermissionError(
                    f"Target '{domain}' is not within an authorized scope for this "
                    f"organization. {match.reason}"
                )
        else:
            # Users without an organization cannot create scans — they must
            # belong to an org with configured scopes to be authorized.
            raise PermissionError(
                "You must belong to an organization with configured authorized "
                "scopes to create a scan."
            )

        # Store scan_options as JSON string if provided
        scan_options_json = json.dumps(scan_options) if scan_options else None

        scan = Scan(
            domain=domain,
            scan_type=scan_type,
            scan_options=scan_options_json,
            created_by=user_id,
            project_id=project_id,
            organization_id=organization_id,
            status="pending"
        )
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)

        if organization_id:
            log_event(
                self.db,
                action="scan.create",
                organization_id=organization_id,
                actor_id=user_id,
                target_type="scan",
                target_id=scan.id,
                status="success",
                detail={"domain": domain, "scan_type": scan_type},
                request_id=request_id,
            )
        return scan
    
    async def execute_scan(self, scan_id: str) -> Scan:
        """Execute a scan asynchronously. Creates its own DB session for background task."""
        db = SessionLocal()
        try:
            # Retry the lookup briefly: under SQLite the scan row committed by the
            # API request's session may not be immediately visible to this new
            # connection (cross-connection visibility race). In production
            # (PostgreSQL) this is a no-op.
            scan = None
            for _ in range(10):
                scan = db.query(Scan).filter(Scan.id == scan_id).first()
                if scan:
                    break
                import asyncio
                await asyncio.sleep(0.1)
            if not scan:
                raise ValueError(f"Scan not found: {scan_id}")
            
            scan.status = "running"
            scan.started_at = datetime.now(timezone.utc)
            db.commit()
            
            # Resolve scan options from profile + stored options
            options = self._resolve_scan_options(scan)
            
            async def progress_callback(progress: int, message: str):
                try:
                    scan.progress = progress
                    db.commit()
                except Exception:
                    db.rollback()
            
            # Route to quick or full scan based on scan_type
            scan_type = scan.scan_type or "full"
            if scan_type == "quick":
                results = await self.runner.run_quick_scan(
                    domain=scan.domain,
                    progress_callback=progress_callback,
                )
            else:
                results = await self.runner.run_full_scan(
                    domain=scan.domain,
                    progress_callback=progress_callback,
                    options=options,
                )
            
            await self._store_results(db, scan, results)
            
            scan.status = "completed"
            scan.progress = 100
            scan.completed_at = datetime.now(timezone.utc)
            if results.get("scanner_status"):
                scan.scanner_status = results["scanner_status"]
            db.commit()
            
            # Generate notifications
            try:
                self._generate_notifications(db, scan, results)
            except Exception as e:
                logger.error(f"Failed to generate notifications: {e}")
            
            return scan
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            try:
                scan = db.query(Scan).filter(Scan.id == scan_id).first()
                if scan:
                    scan.status = "failed"
                    scan.error_message = str(e)
                    scan.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    try:
                        dispatch_notification(
                            db=db,
                            organization_id=scan.organization_id,
                            user_id=scan.created_by,
                            notification_type="scan_failed",
                            title=f"Scan failed: {scan.domain}",
                            message=f"Scan for {scan.domain} failed. {e}",
                            related_entity_type="scan",
                            related_entity_id=scan.id,
                            data={"scan_id": scan.id, "domain": scan.domain, "error": str(e)},
                            skip_dedup=True,
                        )
                    except Exception as notify_err:
                        logger.warning("Failed to send scan failure notification: %s", notify_err)
            except Exception as rollback_err:
                logger.error("Failed to rollback after scan error: %s", rollback_err)
            raise
        finally:
            db.close()
    
    async def store_results(self, scan_id: str, results: Dict[str, Any]):
        """Public entry point for storing results — used by the scan engine.

        Looks up the Scan object from the DB and delegates to the internal
        ``_store_results`` helper so that callers only need to supply a scan ID.
        """
        scan = self.db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            raise ValueError(f"Scan not found: {scan_id}")
        await self._store_results(self.db, scan, results)

    async def _store_results(self, db: Session, scan: Scan, results: Dict[str, Any]):
        """Store scan results in database — batch inserts for performance."""
        domain = results.get("domain")
        
        subdomain_objects = []
        subdomain_map = {}
        os_detection = results.get("os_detection", {})
        host_scripts = results.get("host_scripts", {})
        for hostname in results.get("subdomains", []):
            subdomain = Subdomain(
                scan_id=scan.id,
                hostname=hostname,
                ip_addresses=self._extract_ips(results.get("dns_records", {}).get(hostname, {})),
                is_alive=True,
                os_detection=os_detection.get(hostname),
                host_scripts=host_scripts.get(hostname),
            )
            subdomain_objects.append(subdomain)
            subdomain_map[hostname] = subdomain
        db.add_all(subdomain_objects)
        db.flush()  # one flush for all subdomains
        
        dns_records = []
        for hostname, records in results.get("dns_records", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain:
                continue
            for record_type, record_list in records.items():
                for record in record_list:
                    dns_records.append(DNSRecord(
                        subdomain_id=subdomain.id,
                        record_type=record_type,
                        value=str(record.get("value", "")),
                        ttl=record.get("ttl"),
                    ))
        if dns_records:
            db.add_all(dns_records)
        
        ssl_objects = []
        for hostname, cert in results.get("ssl_certificates", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain or not cert:
                continue
            ssl_objects.append(SSLCertificate(
                subdomain_id=subdomain.id,
                issuer=cert.get("issuer"),
                subject=cert.get("subject"),
                serial_number=cert.get("serial_number"),
                not_before=datetime.fromisoformat(cert["not_before"]) if cert.get("not_before") else None,
                not_after=datetime.fromisoformat(cert["not_after"]) if cert.get("not_after") else None,
                is_valid=cert.get("is_valid", True),
                grade=cert.get("grade"),
                protocol=cert.get("version"),
                cipher_suite=cert.get("cipher_suite"),
                san=cert.get("san_names", []) or [],
            ))
        if ssl_objects:
            db.add_all(ssl_objects)
        
        port_objects = []
        for hostname, port_list in results.get("ports", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain:
                continue
            for port_info in port_list:
                port_objects.append(Port(
                    subdomain_id=subdomain.id,
                    port_number=port_info.get("port"),
                    state=port_info.get("state", "open"),
                    service=port_info.get("service"),
                    version=port_info.get("version"),
                    banner=port_info.get("product"),
                ))
        if port_objects:
            db.add_all(port_objects)
        
        tech_objects = []
        for hostname, tech_list in results.get("technologies", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain:
                continue
            for tech in tech_list:
                tech_objects.append(Technology(
                    subdomain_id=subdomain.id,
                    name=tech.get("name"),
                    category=tech.get("category"),
                    version=tech.get("version"),
                    confidence=tech.get("confidence", 100),
                ))
        if tech_objects:
            db.add_all(tech_objects)
        
        vuln_payload = results.get("vulnerabilities", [])
        vuln_list = vuln_payload if isinstance(vuln_payload, list) else list(vuln_payload.values())
        vuln_objects = []
        for vuln in vuln_list:
            host = vuln.get("host") or vuln.get("matched_at") or domain
            subdomain = subdomain_map.get(host)
            vuln_objects.append(Vulnerability(
                scan_id=scan.id,
                subdomain_id=subdomain.id if subdomain else None,
                template_id=vuln.get("template_id", ""),
                name=vuln.get("name", ""),
                severity=vuln.get("severity", "unknown"),
                vuln_type=vuln.get("type") or vuln.get("vuln_type") or "",
                host=vuln.get("host", host),
                matched_at=vuln.get("matched_at", ""),
                description=vuln.get("description", ""),
                reference=vuln.get("reference", []),
                tags=vuln.get("tags", []),
                curl_command=vuln.get("curl_command", ""),
                extracted_results=vuln.get("extracted_results", []),
            ))
        if vuln_objects:
            db.add_all(vuln_objects)
        
        whois_data = results.get("whois")
        if whois_data:
            db.add(WhoisRecord(
                domain=domain,
                scan_id=scan.id,
                registrar=whois_data.get("registrar"),
                creation_date=datetime.fromisoformat(whois_data["creation_date"]) if whois_data.get("creation_date") else None,
                expiration_date=datetime.fromisoformat(whois_data["expiration_date"]) if whois_data.get("expiration_date") else None,
                name_servers=whois_data.get("name_servers", []),
                registrant_name=whois_data.get("registrant_name"),
                registrant_org=whois_data.get("registrant_org"),
                registrant_country=whois_data.get("registrant_country"),
            ))
        
        risk_data = results.get("risk_score", {})
        if risk_data:
            db.add(RiskScore(
                scan_id=scan.id,
                overall_score=risk_data.get("overall", 0),
                breakdown=risk_data.get("breakdown", {}),
                factors=risk_data.get("factors", []),
            ))

        db.commit()  # single commit for all results

        # Build the canonical, cross-scan asset inventory + relationships.
        try:
            from app.repositories.assets import backfill_from_scan

            backfill_from_scan(db, scan)
        except Exception as exc:  # noqa: BLE001
            logger.error("Asset backfill failed for scan %s: %s", scan.id, exc)

        # Record the change timeline vs the previous completed scan.
        try:
            from app.services.change_detector import detect_changes

            if organization_id := self._resolve_org(db, scan):
                detect_changes(db, organization_id, scan.id)
        except Exception as exc:  # noqa: BLE001
            logger.error("Change detection failed for scan %s: %s", scan.id, exc)
    
    def _extract_ips(self, dns_records: Dict) -> list:
        """Extract IP addresses from DNS records."""
        ips = []
        for record_type in ["A", "AAAA"]:
            for record in dns_records.get(record_type, []):
                value = record.get("value")
                if value and isinstance(value, str):
                    ips.append(value)
        return list(set(ips))

    def _generate_notifications(self, db: Session, scan: Scan, results: Dict[str, Any]):
        """Generate notifications based on scan results, respecting user preferences.

        All notifications go through dispatch_notification() which handles
        preference checks, deduplication, org scoping, and email delivery.
        """
        user_id = scan.created_by
        domain = scan.domain
        scan_id = scan.id
        org_id = scan.organization_id

        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        prefs = user.preferences if user and user.preferences else {}

        # Scan completed — respects scan_complete_alerts preference
        if prefs.get("scan_complete_alerts", True):
            subdomains = results.get("subdomains", [])
            vuln_payload = results.get("vulnerabilities", [])
            vulns = vuln_payload if isinstance(vuln_payload, list) else list(vuln_payload.values())
            dispatch_notification(
                db=db,
                organization_id=org_id,
                user_id=user_id,
                notification_type="scan_completed",
                title=f"Scan completed: {domain}",
                message=f"Scan completed for {domain}. Found {len(subdomains)} subdomains. {len(vulns)} vulnerabilities detected.",
                related_entity_type="scan",
                related_entity_id=scan_id,
                data={"scan_id": scan_id, "domain": domain, "subdomains_count": len(subdomains), "vulns_count": len(vulns)},
                skip_dedup=True,
            )

        # New assets discovered — respects scan_complete_alerts preference
        if prefs.get("scan_complete_alerts", True):
            subdomains = results.get("subdomains", [])
            if subdomains:
                dispatch_notification(
                    db=db,
                    organization_id=org_id,
                    user_id=user_id,
                    notification_type="new_shadow_asset",
                    title=f"New assets discovered: {domain}",
                    message=f"Found {len(subdomains)} new subdomains for {domain}: {', '.join(subdomains[:5])}{'...' if len(subdomains) > 5 else ''}",
                    related_entity_type="asset",
                    related_entity_id=None,
                    data={"scan_id": scan_id, "domain": domain, "subdomains": subdomains, "asset_count": len(subdomains)},
                )

        # SSL expiring soon — respects ssl_expiry_alerts preference
        if prefs.get("ssl_expiry_alerts", True):
            for hostname, cert in results.get("ssl_certificates", {}).items():
                if not cert or not cert.get("not_after"):
                    continue
                try:
                    not_after = datetime.fromisoformat(cert["not_after"])
                    if not_after.tzinfo is None:
                        not_after = not_after.replace(tzinfo=timezone.utc)
                    days_left = (not_after - datetime.now(timezone.utc)).days
                    if 0 < days_left <= 30:
                        dispatch_notification(
                            db=db,
                            organization_id=org_id,
                            user_id=user_id,
                            notification_type="ssl_expiring",
                            title=f"SSL certificate expiring: {hostname}",
                            message=f"SSL certificate for {hostname} expires in {days_left} days.",
                            related_entity_type="certificate",
                            related_entity_id=None,
                            data={"hostname": hostname, "days_left": days_left, "scan_id": scan_id},
                        )
                except (ValueError, TypeError):
                    pass

        # Risk score changed
        risk_data = results.get("risk_score", {})
        if risk_data:
            new_score = risk_data.get("overall", 0)
            prev_scan = (
                db.query(Scan)
                .filter(Scan.created_by == user_id, Scan.id != scan_id, Scan.status == "completed")
                .order_by(Scan.created_at.desc())
                .first()
            )
            if prev_scan:
                prev_risk = db.query(RiskScore).filter(RiskScore.scan_id == prev_scan.id).first()
                if prev_risk:
                    direction = "increased" if new_score > prev_risk.overall_score else "decreased"
                    dispatch_notification(
                        db=db,
                        organization_id=org_id,
                        user_id=user_id,
                        notification_type="scan_completed",
                        title=f"Risk score {direction}: {domain}",
                        message=f"Risk score for {domain} {direction} from {prev_risk.overall_score} to {new_score}.",
                        related_entity_type="scan",
                        related_entity_id=scan_id,
                        data={"scan_id": scan_id, "domain": domain, "old_score": prev_risk.overall_score, "new_score": new_score},
                        skip_dedup=True,
                    )

        # New findings (critical + high) and CVE matches
        if prefs.get("scan_complete_alerts", True):
            vuln_payload = results.get("vulnerabilities", [])
            vulns = vuln_payload if isinstance(vuln_payload, list) else list(vuln_payload.values())
            for vuln in vulns:
                severity = vuln.get("severity", "")
                # CVE correlation findings
                if vuln.get("vuln_type") == "cve-correlation" or vuln.get("cve_id"):
                    dispatch_notification(
                        db=db,
                        organization_id=org_id,
                        user_id=user_id,
                        notification_type="new_cve_match",
                        title=f"CVE match: {vuln.get('cve_id', 'Unknown')}",
                        message=f"Version-correlated (unverified) CVE {vuln.get('cve_id', 'Unknown')} on {vuln.get('name', domain)}.",
                        related_entity_type="finding",
                        related_entity_id=None,
                        data={
                            "scan_id": scan_id,
                            "domain": domain,
                            "cve_id": vuln.get("cve_id", ""),
                            "tech_name": vuln.get("name", ""),
                            "severity": severity,
                        },
                    )
                elif severity in ("critical", "high"):
                    notif_type = f"new_finding_{severity.lower()}"
                    dispatch_notification(
                        db=db,
                        organization_id=org_id,
                        user_id=user_id,
                        notification_type=notif_type,
                        title=f"New {severity} finding: {vuln.get('name', 'Unknown')}",
                        message=f"A {severity} vulnerability was found on {domain}: {vuln.get('name', 'Unknown')}",
                        related_entity_type="finding",
                        related_entity_id=None,
                        data={"scan_id": scan_id, "domain": domain, "vuln_name": vuln.get("name", "Unknown"), "severity": severity},
                    )

        # DNS changes
        for hostname in results.get("dns_records", {}):
            dispatch_notification(
                db=db,
                organization_id=org_id,
                user_id=user_id,
                notification_type="scan_completed",
                title=f"DNS changed: {hostname}",
                message=f"DNS records for {hostname} have changed.",
                related_entity_type="asset",
                related_entity_id=None,
                data={"hostname": hostname, "scan_id": scan_id},
                skip_dedup=True,
            )

        # Technology changes
        for hostname in results.get("technologies", {}):
            dispatch_notification(
                db=db,
                organization_id=org_id,
                user_id=user_id,
                notification_type="scan_completed",
                title=f"Technology changed: {hostname}",
                message=f"Detected technology changes for {hostname}.",
                related_entity_type="asset",
                related_entity_id=None,
                data={"hostname": hostname, "scan_id": scan_id},
                skip_dedup=True,
            )
    
    async def get_scan_with_results(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Get scan with all results."""
        scan = self.db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            return None
        
        # Get subdomains
        subdomains = self.db.query(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        
        # Get risk score
        risk_score = self.db.query(RiskScore).filter(RiskScore.scan_id == scan_id).first()
        
        return {
            "scan": scan,
            "subdomains": subdomains,
            "risk_score": risk_score,
            "subdomains_count": len(subdomains),
        }
