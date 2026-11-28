"""ScanServiceV2 — uses the v2 enterprise scanner engine.

Drop-in replacement for ScanService that routes scan execution through
the v2 pipeline framework.
"""
from sqlalchemy.orm import Session
from app.models.scan import Scan
from app.models.asset import Subdomain
from app.models.dns import DNSRecord
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.technology import Technology
from app.models.risk import RiskScore
from app.models.vulnerability import Vulnerability
from app.database import SessionLocal
from app.services.audit import log_event
from app.services.notification_service import dispatch_notification
from app.config import settings
from app.services.scan_context import ScanCancelled, queue_managed
from datetime import datetime, timezone
from typing import Dict, Any
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

# Enforce max concurrent scans — prevents scan flooding under heavy load.
# Shared across all requests within a single worker process.
_scan_semaphore = asyncio.Semaphore(getattr(settings, "MAX_CONCURRENT_SCANS", 5))


class ScanServiceV2:
    """Service for managing scans using the v2 scanner engine."""

    def __init__(self, db: Session):
        self.db = db

    def _resolve_scan_options(self, scan: Scan) -> dict:
        """Resolve scan options from profile + stored options."""
        options = {}
        if scan.scan_options_raw:
            try:
                options = json.loads(scan.scan_options_raw)
            except (json.JSONDecodeError, TypeError):
                options = {}
        return options

    async def execute_scan(self, scan_id: str) -> Scan:
        """Execute a scan using the v2 enterprise scanner pipeline."""
        async with _scan_semaphore:
            db = SessionLocal()
            try:
                scan = None
                for _ in range(10):
                    scan = db.query(Scan).filter(Scan.id == scan_id).first()
                    if scan:
                        break
                    await asyncio.sleep(0.1)
                if not scan:
                    raise ValueError(f"Scan not found: {scan_id}")
                if scan.status == "cancelled":
                    raise ScanCancelled(scan_id)

                scan.status = "running"
                scan.started_at = datetime.now(timezone.utc)
                db.commit()

                options = self._resolve_scan_options(scan)

                async def progress_callback(progress: int, message: str):
                    try:
                        scan.progress = progress
                        db.commit()
                    except Exception:
                        db.rollback()

                from app.scanners.v2_runner import V2ScanRunner
                runner = V2ScanRunner()

                scan_type = scan.scan_type or "full"
                if scan_type == "quick":
                    results = await runner.run_quick_scan(
                        domain=scan.domain,
                        progress_callback=progress_callback,
                    )
                else:
                    results = await runner.run_full_scan(
                        domain=scan.domain,
                        progress_callback=progress_callback,
                        options=options,
                    )

                await asyncio.to_thread(self._store_results_sync, db, scan, results)

                # Record in scan_history
                try:
                    from app.scanners.v2.monitoring import monitor as v2_monitor
                    await asyncio.to_thread(
                        self._record_history_and_lifecycle, v2_monitor, db, scan, results
                    )
                except Exception as e:
                    logger.warning("Failed to record scan_history: %s", e)

                # A user may have cancelled while the scan ran: keep that.
                db.refresh(scan)
                if scan.status == "cancelled":
                    return scan

                scan.status = "completed"
                scan.progress = 100
                scan.completed_at = datetime.now(timezone.utc)
                if results.get("scanner_status"):
                    scan.scanner_status = results["scanner_status"]
                db.commit()

                try:
                    self._generate_notifications(db, scan, results)
                except Exception as e:
                    logger.error(f"Failed to generate notifications: {e}")

                return scan

            except ScanCancelled:
                raise
            except Exception as e:
                logger.error(f"Scan v2 failed: {e}")
                if queue_managed.get():
                    db.rollback()
                    raise
                try:
                    scan = db.query(Scan).filter(Scan.id == scan_id).first()
                    if scan:
                        scan.status = "failed"
                        scan.error_message = str(e)
                        scan.completed_at = datetime.now(timezone.utc)
                        db.commit()
                except Exception:
                    db.rollback()
                raise
            finally:
                db.close()

    def _store_results(self, db: Session, scan: Scan, results: Dict[str, Any]) -> None:
        """Store scan results in the database."""
        domain = scan.domain

        subdomain_list = results.get("subdomains", [])
        subdomain_objects = []
        subdomain_map = {}
        for subdomain_value in subdomain_list:
            subdomain_str = subdomain_value if isinstance(subdomain_value, str) else subdomain_value.get("name", "")
            if not subdomain_str:
                continue
            existing = db.query(Subdomain).filter(
                Subdomain.scan_id == scan.id,
                Subdomain.hostname == subdomain_str,
            ).first()
            if existing:
                subdomain_map[subdomain_str] = existing
                continue
            obj = Subdomain(
                scan_id=scan.id,
                hostname=subdomain_str,
                ip_addresses=[],
                is_alive=True,
            )
            subdomain_objects.append(obj)
            subdomain_map[subdomain_str] = obj
        if subdomain_objects:
            db.add_all(subdomain_objects)
            db.flush()

        dns_records = []
        for hostname, records_dict in results.get("dns_records", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain or not isinstance(records_dict, dict):
                continue
            for record_type, values in records_dict.items():
                if not isinstance(values, list):
                    continue
                for value in values:
                    dns_records.append(DNSRecord(
                        subdomain_id=subdomain.id,
                        record_type=record_type,
                        value=str(value),
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
            if not subdomain or not isinstance(port_list, list):
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
            if not subdomain or not isinstance(tech_list, list):
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

        risk_data = results.get("risk_score", {})
        if risk_data:
            db.add(RiskScore(
                scan_id=scan.id,
                overall_score=risk_data.get("risk_score", 0),
                breakdown=risk_data.get("dimensions", {}),
                factors=risk_data.get("recommendations", []),
            ))

        vuln_payload = results.get("vulnerabilities", [])
        vuln_list = vuln_payload if isinstance(vuln_payload, list) else list(vuln_payload.values())
        vuln_objects = []
        for vuln in vuln_list:
            if not isinstance(vuln, dict):
                continue
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

        db.commit()

        try:
            from app.repositories.assets import backfill_from_scan
            backfill_from_scan(db, scan)
        except Exception as exc:
            logger.error("Asset backfill failed for scan %s: %s", scan.id, exc)

        try:
            from app.services.change_detector import detect_changes
            if organization_id := getattr(scan, "organization_id", None):
                detect_changes(db, organization_id, scan.id)
        except Exception as exc:
            logger.error("Change detection failed for scan %s: %s", scan.id, exc)

    def _generate_notifications(self, db: Session, scan: Scan, results: Dict[str, Any]) -> None:
        """Generate notifications for completed scan."""
        risk_score = results.get("risk_score", {})
        severity = risk_score.get("severity", "Low")

        # Check notification triggers
        try:
            from app.scanners.v2.monitoring import monitor as v2_monitor
            event_type = "high_risk_scan" if severity in ("High", "Critical") else "scan_completed"
            triggered = v2_monitor.check_notification_triggers(
                db, scan.domain, event_type,
                organization_id=getattr(scan, "organization_id", None),
            )
            if triggered:
                logger.info("Notification triggers fired for %s: %s", scan.domain, triggered)
        except Exception as e:
            logger.warning("Failed to check notification triggers: %s", e)

        if severity in ("High", "Critical"):
            try:
                dispatch_notification(
                    db=db,
                    user_id=scan.created_by,
                    notification_type="scan_completed_high_risk",
                    title=f"High Risk Scan Completed: {scan.domain}",
                    message=f"Scan completed with {severity} risk score ({risk_score.get('risk_score', 0)}/100)",
                    data={"scan_id": scan.id, "domain": scan.domain, "risk_score": risk_score},
                )
            except Exception as e:
                logger.error(f"Failed to dispatch notification: {e}")

        try:
            log_event(
                db=db,
                event_type="scan_completed",
                user_id=scan.created_by,
                target_id=scan.id,
                status="success",
                detail={"domain": scan.domain, "scan_type": scan.scan_type, "engine": "v2"},
            )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

    def _store_results_sync(self, db: Session, scan: Scan, results: Dict[str, Any]) -> None:
        """Synchronous version of _store_results for use with asyncio.to_thread."""
        self._store_results(db, scan, results)

    def _record_history_and_lifecycle(self, v2_monitor, db: Session, scan: Scan, results: Dict[str, Any]) -> None:
        """Record scan history and asset lifecycle in a thread-safe way."""
        scan_history_id = v2_monitor.record_scan_history(
            db,
            domain=scan.domain,
            scan_type=scan.scan_type or "full",
            status="completed",
            user_id=scan.created_by,
            organization_id=getattr(scan, "organization_id", None),
            results=results,
            duration_ms=(scan.completed_at - scan.started_at).total_seconds() * 1000
            if scan.completed_at and scan.started_at else 0,
        )
        assets = []
        for sub in results.get("subdomains", []):
            name = sub if isinstance(sub, str) else sub.get("name", "")
            if name:
                assets.append({"type": "subdomain", "value": name})
        if assets:
            v2_monitor.update_asset_lifecycle(
                db, scan.domain, assets,
                scan_history_id=scan_history_id,
                organization_id=getattr(scan, "organization_id", None),
            )
            v2_monitor.mark_removed_assets(
                db, scan.domain,
                {a["value"] for a in assets},
            )
