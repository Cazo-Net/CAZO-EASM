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
from app.services.notification_service import (
    notify_scan_completed, notify_scan_failed, notify_ssl_expiring,
    notify_new_assets, notify_risk_score_changed, notify_new_finding,
    notify_dns_changed, notify_technology_changed,
)
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import asyncio
import logging

logger = logging.getLogger(__name__)


class ScanService:
    """Service for managing scans."""
    
    def __init__(self, db: Session):
        self.db = db
        self.runner = ScanRunner()
    
    async def create_scan(
        self,
        domain: str,
        user_id: str,
        scan_type: str = "full",
        project_id: Optional[str] = None
    ) -> Scan:
        """Create a new scan."""
        scan = Scan(
            domain=domain,
            scan_type=scan_type,
            created_by=user_id,
            project_id=project_id,
            status="pending"
        )
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)
        return scan
    
    async def execute_scan(self, scan_id: str) -> Scan:
        """Execute a scan asynchronously. Creates its own DB session for background task."""
        db = SessionLocal()
        try:
            scan = db.query(Scan).filter(Scan.id == scan_id).first()
            if not scan:
                raise ValueError(f"Scan not found: {scan_id}")
            
            scan.status = "running"
            scan.started_at = datetime.now(timezone.utc)
            db.commit()
            
            async def progress_callback(progress: int, message: str):
                try:
                    scan.progress = progress
                    db.commit()
                except Exception:
                    db.rollback()
            
            results = await self.runner.run_full_scan(
                domain=scan.domain,
                progress_callback=progress_callback
            )
            
            await self._store_results(db, scan, results)
            
            scan.status = "completed"
            scan.progress = 100
            scan.completed_at = datetime.now(timezone.utc)
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
                        notify_scan_failed(db, scan.created_by, scan.domain, scan.id, str(e))
                    except Exception:
                        pass
            except Exception:
                db.rollback()
            raise
        finally:
            db.close()
    
    async def _store_results(self, db: Session, scan: Scan, results: Dict[str, Any]):
        """Store scan results in database."""
        domain = results.get("domain")
        
        subdomain_map = {}
        for hostname in results.get("subdomains", []):
            subdomain = Subdomain(
                scan_id=scan.id,
                hostname=hostname,
                ip_addresses=self._extract_ips(results.get("dns_records", {}).get(hostname, {})),
                is_alive=True
            )
            db.add(subdomain)
            db.flush()
            subdomain_map[hostname] = subdomain
        
        for hostname, records in results.get("dns_records", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain:
                continue
            for record_type, record_list in records.items():
                for record in record_list:
                    dns_record = DNSRecord(
                        subdomain_id=subdomain.id,
                        record_type=record_type,
                        value=str(record.get("value", "")),
                        ttl=record.get("ttl")
                    )
                    db.add(dns_record)
        
        for hostname, cert in results.get("ssl_certificates", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain or not cert:
                continue
            ssl_cert = SSLCertificate(
                subdomain_id=subdomain.id,
                issuer=cert.get("issuer"),
                subject=cert.get("subject"),
                serial_number=cert.get("serial_number"),
                not_before=datetime.fromisoformat(cert["not_before"]) if cert.get("not_before") else None,
                not_after=datetime.fromisoformat(cert["not_after"]) if cert.get("not_after") else None,
                is_valid=cert.get("is_valid", True),
                grade=cert.get("grade"),
                protocol=cert.get("version"),
                cipher_suite=cert.get("cipher_suite")
            )
            db.add(ssl_cert)
        
        for hostname, port_list in results.get("ports", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain:
                continue
            for port_info in port_list:
                port = Port(
                    subdomain_id=subdomain.id,
                    port_number=port_info.get("port"),
                    state=port_info.get("state", "open"),
                    service=port_info.get("service"),
                    version=port_info.get("version"),
                    banner=port_info.get("product")
                )
                db.add(port)
        
        for hostname, tech_list in results.get("technologies", {}).items():
            subdomain = subdomain_map.get(hostname)
            if not subdomain:
                continue
            for tech in tech_list:
                technology = Technology(
                    subdomain_id=subdomain.id,
                    name=tech.get("name"),
                    category=tech.get("category"),
                    version=tech.get("version"),
                    confidence=tech.get("confidence", 100)
                )
                db.add(technology)
        
        # Store vulnerabilities from nuclei
        for hostname, vulns in results.get("vulnerabilities", {}).items():
            subdomain = subdomain_map.get(hostname)
            for vuln in vulns:
                vulnerability = Vulnerability(
                    scan_id=scan.id,
                    subdomain_id=subdomain.id if subdomain else None,
                    template_id=vuln.get("template_id", ""),
                    name=vuln.get("name", ""),
                    severity=vuln.get("severity", "unknown"),
                    vuln_type=vuln.get("type", ""),
                    host=vuln.get("host", hostname),
                    matched_at=vuln.get("matched_at", ""),
                    description=vuln.get("description", ""),
                    reference=vuln.get("reference", []),
                    tags=vuln.get("tags", []),
                    curl_command=vuln.get("curl_command", ""),
                    extracted_results=vuln.get("extracted_results", []),
                )
                db.add(vulnerability)
        
        whois_data = results.get("whois")
        if whois_data:
            whois_record = WhoisRecord(
                domain=domain,
                scan_id=scan.id,
                registrar=whois_data.get("registrar"),
                creation_date=datetime.fromisoformat(whois_data["creation_date"]) if whois_data.get("creation_date") else None,
                expiration_date=datetime.fromisoformat(whois_data["expiration_date"]) if whois_data.get("expiration_date") else None,
                name_servers=whois_data.get("name_servers", []),
                registrant_name=whois_data.get("registrant_name"),
                registrant_org=whois_data.get("registrant_org"),
                registrant_country=whois_data.get("registrant_country")
            )
            db.add(whois_record)
        
        risk_data = results.get("risk_score", {})
        if risk_data:
            risk_score = RiskScore(
                scan_id=scan.id,
                overall_score=risk_data.get("overall", 0),
                breakdown=risk_data.get("breakdown", {}),
                factors=risk_data.get("factors", [])
            )
            db.add(risk_score)
        
        db.commit()
    
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
        """Generate notifications based on scan results, respecting user preferences."""
        user_id = scan.created_by
        domain = scan.domain
        scan_id = scan.id

        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        prefs = user.preferences if user and user.preferences else {}

        # Scan completed — respects scan_complete_alerts preference
        if prefs.get("scan_complete_alerts", True):
            subdomains = results.get("subdomains", [])
            vulns = []
            for vlist in results.get("vulnerabilities", {}).values():
                vulns.extend(vlist)
            notify_scan_completed(db, user_id, domain, scan_id, len(subdomains), len(vulns))

        # New assets discovered — respects scan_complete_alerts preference
        if prefs.get("scan_complete_alerts", True):
            subdomains = results.get("subdomains", [])
            if subdomains:
                notify_new_assets(db, user_id, domain, scan_id, subdomains)

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
                        notify_ssl_expiring(db, user_id, hostname, days_left, scan_id)
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
                    notify_risk_score_changed(db, user_id, domain, scan_id, prev_risk.overall_score, new_score)

        # New findings (critical + high)
        if prefs.get("scan_complete_alerts", True):
            for vlist in results.get("vulnerabilities", {}).values():
                for vuln in vlist:
                    severity = vuln.get("severity", "")
                    if severity in ("critical", "high"):
                        notify_new_finding(db, user_id, domain, scan_id, vuln.get("name", "Unknown"), severity)

        # DNS changes
        for hostname in results.get("dns_records", {}):
            notify_dns_changed(db, user_id, hostname, scan_id)

        # Technology changes
        for hostname in results.get("technologies", {}):
            notify_technology_changed(db, user_id, hostname, scan_id)
    
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
