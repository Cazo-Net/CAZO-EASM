from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import json

from app.models.scan import Scan
from app.models.asset import Subdomain
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.dns import DNSRecord
from app.models.technology import Technology
from app.models.vulnerability import Vulnerability
from app.models.risk import RiskScore
from app.models.report import Report
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.project import Project


class ContextBuilder:
    """Builds context for AI queries from platform data."""

    def __init__(self, db: Session):
        self.db = db

    def build_full_context(
        self,
        user_id: str,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}
        ctx["timestamp"] = datetime.now(timezone.utc).isoformat()
        ctx["user_id"] = user_id

        scan_filter = []
        if org_id:
            scan_filter.append(Scan.created_by.isnot(None))
        if project_id:
            scan_filter.append(Scan.project_id == project_id)

        total_scans = self.db.query(Scan).count()
        recent_scans = self.db.query(Scan).order_by(Scan.created_at.desc()).limit(10).all()
        ctx["scans"] = {
            "total": total_scans,
            "recent": [
                {
                    "id": s.id,
                    "domain": s.domain,
                    "status": s.status,
                    "scan_type": s.scan_type,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in recent_scans
            ],
        }

        total_subdomains = self.db.query(Subdomain).count()
        alive_subdomains = self.db.query(Subdomain).filter(Subdomain.is_alive == True).count()
        ctx["subdomains"] = {
            "total": total_subdomains,
            "alive": alive_subdomains,
            "dead": total_subdomains - alive_subdomains,
        }

        total_ports = self.db.query(Port).count()
        open_ports = self.db.query(Port).filter(Port.state == "open").count()
        ctx["ports"] = {
            "total": total_ports,
            "open": open_ports,
        }

        total_ssl = self.db.query(SSLCertificate).count()
        valid_ssl = self.db.query(SSLCertificate).filter(SSLCertificate.is_valid == True).count()
        expiring_soon = self.db.query(SSLCertificate).filter(
            SSLCertificate.not_after <= datetime.now(timezone.utc) + timedelta(days=30),
            SSLCertificate.not_after > datetime.now(timezone.utc),
        ).count()
        expired_ssl = self.db.query(SSLCertificate).filter(
            SSLCertificate.not_after < datetime.now(timezone.utc)
        ).count()
        ctx["ssl_certificates"] = {
            "total": total_ssl,
            "valid": valid_ssl,
            "expiring_soon": expiring_soon,
            "expired": expired_ssl,
        }

        total_tech = self.db.query(Technology).count()
        tech_names = self.db.query(Technology.name).distinct().all()
        ctx["technologies"] = {
            "total": total_tech,
            "unique": len(tech_names),
            "names": [t[0] for t in tech_names[:30]],
        }

        total_vulns = self.db.query(Vulnerability).count()
        vuln_severity = {}
        for severity in ["critical", "high", "medium", "low"]:
            count = self.db.query(Vulnerability).filter(Vulnerability.severity == severity).count()
            vuln_severity[severity] = count
        ctx["vulnerabilities"] = {
            "total": total_vulns,
            "by_severity": vuln_severity,
        }

        latest_risk = self.db.query(RiskScore).order_by(RiskScore.calculated_at.desc()).first()
        risk_score = latest_risk.overall_score if latest_risk else None
        if risk_score is not None:
            if risk_score <= 25:
                risk_label = "Low"
            elif risk_score <= 50:
                risk_label = "Medium"
            elif risk_score <= 75:
                risk_label = "High"
            else:
                risk_label = "Critical"
        else:
            risk_label = None
        ctx["risk"] = {
            "latest_score": risk_score,
            "latest_label": risk_label,
        }

        total_reports = self.db.query(Report).count()
        ctx["reports"] = {"total": total_reports}

        total_dns = self.db.query(DNSRecord).count()
        ctx["dns_records"] = {"total": total_dns}

        ctx["organizations"] = {"count": self.db.query(Organization).count()}
        ctx["projects"] = {"count": self.db.query(Project).count()}

        return ctx

    def build_asset_context(self, scan_id: str) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}
        scan = self.db.query(Scan).filter(Scan.id == scan_id).first()
        if scan:
            ctx["scan"] = {
                "id": scan.id,
                "domain": scan.domain,
                "status": scan.status,
                "scan_type": scan.scan_type,
            }
            subdomains = self.db.query(Subdomain).filter(Subdomain.scan_id == scan_id).all()
            ctx["subdomains_count"] = len(subdomains)
            vulns = self.db.query(Vulnerability).filter(Vulnerability.scan_id == scan_id).all()
            ctx["vulnerabilities_count"] = len(vulns)
            ctx["vulnerability_severity"] = {}
            for v in vulns:
                sev = v.severity or "unknown"
                ctx["vulnerability_severity"][sev] = ctx["vulnerability_severity"].get(sev, 0) + 1

        return ctx

    def build_summary(self, context: Dict[str, Any]) -> str:
        parts = []
        if "scans" in context:
            parts.append(f"Total scans: {context['scans']['total']}")
        if "subdomains" in context:
            parts.append(f"Subdomains: {context['subdomains']['total']} ({context['subdomains']['alive']} alive)")
        if "ports" in context:
            parts.append(f"Open ports: {context['ports']['open']}")
        if "ssl_certificates" in context:
            ssl = context['ssl_certificates']
            parts.append(f"SSL: {ssl['valid']} valid, {ssl['expiring_soon']} expiring soon, {ssl['expired']} expired")
        if "vulnerabilities" in context:
            v = context['vulnerabilities']
            parts.append(f"Vulnerabilities: {v['total']} total ({v['by_severity'].get('critical', 0)} critical, {v['by_severity'].get('high', 0)} high)")
        if "technologies" in context:
            parts.append(f"Technologies: {context['technologies']['unique']} unique")
        if "risk" in context and context['risk']['latest_score'] is not None:
            parts.append(f"Latest risk score: {context['risk']['latest_score']}/100 ({context['risk']['latest_label']})")
        return "\n".join(parts)
