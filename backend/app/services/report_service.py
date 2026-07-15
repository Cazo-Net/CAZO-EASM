import os
import json
import csv
import io
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.scan import Scan
from app.models.asset import Subdomain
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.technology import Technology
from app.models.dns import DNSRecord
from app.models.whois import WhoisRecord
from app.models.vulnerability import Vulnerability
from app.models.risk import RiskScore


class ReportService:
    """Service for generating scan reports."""
    
    REPORTS_DIR = "reports"
    
    def __init__(self, db: Session):
        self.db = db
        os.makedirs(self.REPORTS_DIR, exist_ok=True)
    
    def _gather_scan_data(self, scan_id: str) -> Dict[str, Any]:
        """Gather all scan data for report generation."""
        scan = self.db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            raise ValueError(f"Scan not found: {scan_id}")
        
        subdomains = self.db.query(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        ports = self.db.query(Port).join(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        ssl_certs = self.db.query(SSLCertificate).join(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        technologies = self.db.query(Technology).join(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        dns_records = self.db.query(DNSRecord).join(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        whois = self.db.query(WhoisRecord).filter(WhoisRecord.scan_id == scan_id).first()
        vulns = self.db.query(Vulnerability).filter(Vulnerability.scan_id == scan_id).all()
        risk_score = self.db.query(RiskScore).filter(RiskScore.scan_id == scan_id).first()
        
        return {
            "scan": scan,
            "subdomains": subdomains,
            "ports": ports,
            "ssl_certificates": ssl_certs,
            "technologies": technologies,
            "dns_records": dns_records,
            "whois": whois,
            "vulnerabilities": vulns,
            "risk_score": risk_score,
        }
    
    def generate_json(self, scan_id: str) -> str:
        """Generate JSON report. Returns file path."""
        data = self._gather_scan_data(scan_id)
        
        report_data = {
            "report": {
                "type": "AttackSec Scan Report",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "format": "json",
            },
            "scan": {
                "id": data["scan"].id,
                "domain": data["scan"].domain,
                "status": data["scan"].status.value if hasattr(data["scan"].status, 'value') else data["scan"].status,
                "scan_type": data["scan"].scan_type.value if hasattr(data["scan"].scan_type, 'value') else data["scan"].scan_type,
                "started_at": data["scan"].started_at.isoformat() if data["scan"].started_at else None,
                "completed_at": data["scan"].completed_at.isoformat() if data["scan"].completed_at else None,
            },
            "summary": {
                "subdomains_count": len(data["subdomains"]),
                "ports_count": len(data["ports"]),
                "ssl_certificates_count": len(data["ssl_certificates"]),
                "technologies_count": len(data["technologies"]),
                "dns_records_count": len(data["dns_records"]),
                "vulnerabilities_count": len(data["vulnerabilities"]),
                "risk_score": data["risk_score"].overall_score if data["risk_score"] else None,
            },
            "subdomains": [
                {"hostname": s.hostname, "ip_addresses": s.ip_addresses, "is_alive": s.is_alive}
                for s in data["subdomains"]
            ],
            "ports": [
                {"hostname": p.subdomain.hostname, "port": p.port_number, "state": p.state, "service": p.service, "version": p.version}
                for p in data["ports"]
            ],
            "ssl_certificates": [
                {"hostname": c.subdomain.hostname, "issuer": c.issuer, "grade": c.grade, "not_after": c.not_after.isoformat() if c.not_after else None, "is_valid": c.is_valid}
                for c in data["ssl_certificates"]
            ],
            "technologies": [
                {"hostname": t.subdomain.hostname, "name": t.name, "category": t.category, "version": t.version}
                for t in data["technologies"]
            ],
            "vulnerabilities": [
                {"name": v.name, "severity": v.severity, "host": v.host, "description": v.description, "template_id": v.template_id}
                for v in data["vulnerabilities"]
            ],
        }
        
        if data["whois"]:
            report_data["whois"] = {
                "domain": data["whois"].domain,
                "registrar": data["whois"].registrar,
                "creation_date": data["whois"].creation_date.isoformat() if data["whois"].creation_date else None,
                "expiration_date": data["whois"].expiration_date.isoformat() if data["whois"].expiration_date else None,
                "name_servers": data["whois"].name_servers,
            }
        
        file_path = os.path.join(self.REPORTS_DIR, f"{scan_id}.json")
        with open(file_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return file_path
    
    def generate_csv(self, scan_id: str) -> str:
        """Generate CSV report. Returns file path."""
        data = self._gather_scan_data(scan_id)
        file_path = os.path.join(self.REPORTS_DIR, f"{scan_id}.csv")
        
        with open(file_path, "w", newline="") as f:
            writer = csv.writer(f)
            
            # Summary
            writer.writerow(["AttackSec Scan Report"])
            writer.writerow(["Generated", datetime.now(timezone.utc).isoformat()])
            writer.writerow(["Domain", data["scan"].domain])
            writer.writerow([])
            
            # Subdomains
            writer.writerow(["SUBDOMAINS"])
            writer.writerow(["Hostname", "IP Addresses", "Alive"])
            for s in data["subdomains"]:
                writer.writerow([s.hostname, "; ".join(s.ip_addresses or []), s.is_alive])
            writer.writerow([])
            
            # Ports
            writer.writerow(["OPEN PORTS"])
            writer.writerow(["Hostname", "Port", "State", "Service", "Version"])
            for p in data["ports"]:
                writer.writerow([p.subdomain.hostname, p.port_number, p.state, p.service, p.version])
            writer.writerow([])
            
            # SSL
            writer.writerow(["SSL CERTIFICATES"])
            writer.writerow(["Hostname", "Issuer", "Grade", "Valid", "Expires"])
            for c in data["ssl_certificates"]:
                writer.writerow([c.subdomain.hostname, c.issuer, c.grade, c.is_valid, c.not_after])
            writer.writerow([])
            
            # Technologies
            writer.writerow(["TECHNOLOGIES"])
            writer.writerow(["Hostname", "Name", "Category", "Version"])
            for t in data["technologies"]:
                writer.writerow([t.subdomain.hostname, t.name, t.category, t.version])
            writer.writerow([])
            
            # Vulnerabilities
            writer.writerow(["VULNERABILITIES"])
            writer.writerow(["Name", "Severity", "Host", "Template ID"])
            for v in data["vulnerabilities"]:
                writer.writerow([v.name, v.severity, v.host, v.template_id])
        
        return file_path
    
    def generate_pdf(self, scan_id: str) -> str:
        """Generate PDF report using ReportLab. Returns file path."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.units import inch
        
        data = self._gather_scan_data(scan_id)
        file_path = os.path.join(self.REPORTS_DIR, f"{scan_id}.pdf")
        
        doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=24, spaceAfter=20, textColor=colors.HexColor('#2563EB'))
        elements.append(Paragraph("AttackSec Scan Report", title_style))
        elements.append(Spacer(1, 12))
        
        # Scan info
        elements.append(Paragraph(f"<b>Domain:</b> {data['scan'].domain}", styles['Normal']))
        scan_status = data["scan"].status.value if hasattr(data["scan"].status, 'value') else data["scan"].status
        elements.append(Paragraph(f"<b>Status:</b> {scan_status}", styles['Normal']))
        elements.append(Paragraph(f"<b>Scan Type:</b> {data['scan'].scan_type}", styles['Normal']))
        if data["scan"].completed_at:
            elements.append(Paragraph(f"<b>Completed:</b> {data['scan'].completed_at.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Summary
        elements.append(Paragraph("Summary", styles['Heading2']))
        summary_data = [
            ["Metric", "Count"],
            ["Subdomains", str(len(data["subdomains"]))],
            ["Open Ports", str(len(data["ports"]))],
            ["SSL Certificates", str(len(data["ssl_certificates"]))],
            ["Technologies", str(len(data["technologies"]))],
            ["DNS Records", str(len(data["dns_records"]))],
            ["Vulnerabilities", str(len(data["vulnerabilities"]))],
        ]
        if data["risk_score"]:
            summary_data.append(["Risk Score", str(data["risk_score"].overall_score)])
        
        summary_table = Table(summary_data, colWidths=[200, 100])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))
        
        # Vulnerabilities
        if data["vulnerabilities"]:
            elements.append(Paragraph("Vulnerabilities", styles['Heading2']))
            vuln_data = [["Name", "Severity", "Host"]]
            for v in data["vulnerabilities"]:
                vuln_data.append([v.name[:50], v.severity, v.host[:40]])
            
            vuln_table = Table(vuln_data, colWidths=[200, 80, 180])
            vuln_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fef2f2')]),
            ]
            vuln_table.setStyle(TableStyle(vuln_style))
            elements.append(vuln_table)
            elements.append(Spacer(1, 20))
        
        # Subdomains
        if data["subdomains"]:
            elements.append(Paragraph("Subdomains", styles['Heading2']))
            sub_data = [["Hostname", "IP Addresses", "Alive"]]
            for s in data["subdomains"][:50]:
                sub_data.append([s.hostname[:40], "; ".join(s.ip_addresses or [])[:40], str(s.is_alive)])
            
            sub_table = Table(sub_data, colWidths=[200, 180, 60])
            sub_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f9ff')]),
            ]))
            elements.append(sub_table)
        
        doc.build(elements)
        return file_path
    
    def generate_report(self, scan_id: str, format: str = "json") -> str:
        """Generate report in specified format."""
        if format == "json":
            return self.generate_json(scan_id)
        elif format == "csv":
            return self.generate_csv(scan_id)
        elif format == "pdf":
            return self.generate_pdf(scan_id)
        else:
            raise ValueError(f"Unsupported format: {format}")
