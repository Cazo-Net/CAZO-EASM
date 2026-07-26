import os
import json
import csv
from datetime import datetime, timezone
from typing import Dict, Any
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
                "type": "CAZO EASM Scan Report",
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
            writer.writerow(["CAZO EASM Scan Report"])
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
        """Generate branded PDF report using ReportLab. Returns file path."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, KeepTogether,
        )
        from app.services.pdf_brand import (
            draw_page_header, draw_page_footer, draw_cover_page,
            SectionHeading, branded_table_style, severity_color,
            BLUE, CYAN, RED, DARK, MUTED, WHITE, LIGHT_BG, PAGE_W, PAGE_H,
        )

        data = self._gather_scan_data(scan_id)
        file_path = os.path.join(self.REPORTS_DIR, f"{scan_id}.pdf")
        report_id = scan_id[:8]

        # Scan metadata
        scan = data["scan"]
        scan_status = scan.status.value if hasattr(scan.status, "value") else scan.status
        scan_type = scan.scan_type.value if hasattr(scan.scan_type, "value") else scan.scan_type
        completed_at = scan.completed_at.strftime("%Y-%m-%d %H:%M UTC") if scan.completed_at else None

        # ── Build document ────────────────────────────────────────────
        def on_page(canvas, doc):
            """Draw header + footer on every content page (cover is page 0)."""
            draw_page_header(canvas, doc, report_id)
            draw_page_footer(canvas, doc)

        def on_cover(canvas, doc):
            """Draw the cover page."""
            draw_cover_page(
                canvas, doc,
                domain=scan.domain,
                scan_type=scan_type,
                status=scan_status,
                completed_at=completed_at,
                report_id=report_id,
            )

        doc = SimpleDocTemplate(
            file_path, pagesize=A4,
            rightMargin=50, leftMargin=50,
            topMargin=50, bottomMargin=55,
        )
        styles = getSampleStyleSheet()
        elements = []

        # ── Cover page (empty flowable triggers onFirstPage) ──────────
        elements.append(Spacer(1, PAGE_H - 60))  # push past cover
        elements.append(PageBreak())

        # ── Section: Executive Summary ─────────────────────────────────
        elements.append(SectionHeading("Executive Summary"))
        elements.append(Spacer(1, 10))

        # Summary metric cards in a 2x4 grid
        metrics = [
            ("Subdomains", str(len(data["subdomains"])), BLUE),
            ("Open Ports", str(len(data["ports"])), CYAN),
            ("SSL Certs", str(len(data["ssl_certificates"])), BLUE),
            ("Technologies", str(len(data["technologies"])), CYAN),
            ("DNS Records", str(len(data["dns_records"])), BLUE),
            ("Vulnerabilities", str(len(data["vulnerabilities"])), RED),
        ]
        if data["risk_score"]:
            score = data["risk_score"].overall_score
            score_color = RED if score >= 70 else (colors.HexColor("#F97316") if score >= 40 else CYAN)
            metrics.append(("Risk Score", str(score), score_color))

        # Build 2-column grid
        card_rows = []
        for i in range(0, len(metrics), 2):
            row = []
            for j in range(2):
                if i + j < len(metrics):
                    label, value, color = metrics[i + j]
                    cell = Paragraph(
                        f'<font size="7" color="#6B7280">{label}</font><br/>'
                        f'<font size="16" color="{color.hexval()}"><b>{value}</b></font>',
                        styles["Normal"],
                    )
                    row.append(cell)
                else:
                    row.append("")
            card_rows.append(row)

        card_table = Table(card_rows, colWidths=[230, 230], rowHeights=[45] * len(card_rows))
        card_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('BOX', (0, 0), (0, 0), 0.5, colors.HexColor("#E5E7EB")),
            ('BOX', (1, 0), (1, 0), 0.5, colors.HexColor("#E5E7EB")),
            ('BACKGROUND', (0, 0), (-1, -1), WHITE),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, LIGHT_BG]),
        ]))
        elements.append(card_table)
        elements.append(Spacer(1, 20))

        # ── Section: Vulnerabilities ───────────────────────────────────
        if data["vulnerabilities"]:
            elements.append(SectionHeading("Vulnerabilities"))
            elements.append(Spacer(1, 8))

            vuln_header = ["Name", "Severity", "Host"]
            vuln_rows = [vuln_header]
            for v in data["vulnerabilities"]:
                vuln_rows.append([
                    Paragraph(v.name[:55], styles["Normal"]),
                    Paragraph(
                        f'<font color="{severity_color(v.severity).hexval()}">'
                        f'<b>{v.severity.upper()}</b></font>',
                        styles["Normal"],
                    ),
                    Paragraph(v.host[:45], styles["Normal"]),
                ])

            vuln_table = Table(vuln_rows, colWidths=[200, 80, 180])
            vuln_style = branded_table_style(header_color=RED, alt_row=colors.HexColor("#FEF2F2"))
            vuln_table.setStyle(TableStyle(vuln_style))
            elements.append(vuln_table)
            elements.append(Spacer(1, 20))

        # ── Section: Subdomains ────────────────────────────────────────
        if data["subdomains"]:
            elements.append(SectionHeading("Subdomains"))
            elements.append(Spacer(1, 8))

            sub_header = ["Hostname", "IP Addresses", "Alive"]
            sub_rows = [sub_header]
            for s in data["subdomains"][:80]:
                sub_rows.append([
                    s.hostname[:45],
                    "; ".join(s.ip_addresses or [])[:45],
                    "Yes" if s.is_alive else "No",
                ])

            sub_table = Table(sub_rows, colWidths=[200, 180, 60])
            sub_table.setStyle(TableStyle(branded_table_style()))
            elements.append(sub_table)
            elements.append(Spacer(1, 20))

        # ── Section: Open Ports ────────────────────────────────────────
        if data["ports"]:
            elements.append(SectionHeading("Open Ports"))
            elements.append(Spacer(1, 8))

            port_header = ["Hostname", "Port", "State", "Service", "Version"]
            port_rows = [port_header]
            for p in data["ports"][:80]:
                port_rows.append([
                    p.subdomain.hostname[:35],
                    str(p.port_number),
                    p.state or "",
                    p.service or "",
                    p.version or "",
                ])

            port_table = Table(port_rows, colWidths=[140, 50, 60, 100, 110])
            port_table.setStyle(TableStyle(branded_table_style(header_color=CYAN)))
            elements.append(port_table)
            elements.append(Spacer(1, 20))

        # ── Section: Technologies ──────────────────────────────────────
        if data["technologies"]:
            elements.append(SectionHeading("Technologies"))
            elements.append(Spacer(1, 8))

            tech_header = ["Hostname", "Name", "Category", "Version"]
            tech_rows = [tech_header]
            for t in data["technologies"][:80]:
                tech_rows.append([
                    t.subdomain.hostname[:35],
                    t.name or "",
                    t.category or "",
                    t.version or "",
                ])

            tech_table = Table(tech_rows, colWidths=[140, 110, 100, 110])
            tech_table.setStyle(TableStyle(branded_table_style()))
            elements.append(tech_table)
            elements.append(Spacer(1, 20))

        # ── Section: SSL Certificates ──────────────────────────────────
        if data["ssl_certificates"]:
            elements.append(SectionHeading("SSL Certificates"))
            elements.append(Spacer(1, 8))

            ssl_header = ["Hostname", "Issuer", "Grade", "Valid", "Expires"]
            ssl_rows = [ssl_header]
            for c in data["ssl_certificates"][:50]:
                ssl_rows.append([
                    c.subdomain.hostname[:35],
                    c.issuer or "",
                    c.grade or "",
                    "Yes" if c.is_valid else "No",
                    c.not_after.strftime("%Y-%m-%d") if c.not_after else "",
                ])

            ssl_table = Table(ssl_rows, colWidths=[140, 120, 60, 50, 100])
            ssl_table.setStyle(TableStyle(branded_table_style(header_color=BLUE)))
            elements.append(ssl_table)

        doc.build(elements, onFirstPage=on_cover, onLaterPages=on_page)
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
