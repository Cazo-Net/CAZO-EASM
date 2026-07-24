"""AI Security Analyst Layer.

Provides natural language analysis of scan results:
- Explain findings in plain English
- Summarize attack surface
- Prioritize risks with reasoning
- Generate executive summaries
- Answer questions about discovered assets
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SecurityAnalyst:
    """AI-assisted security analysis of scan results."""

    def explain_findings(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate human-readable explanation of scan findings."""
        analysis = {
            "executive_summary": self._executive_summary(scan_results),
            "top_risks": self._top_risks(scan_results),
            "asset_overview": self._asset_overview(scan_results),
            "recommendations": self._recommendations(scan_results),
            "detailed_findings": self._detailed_findings(scan_results),
        }
        return analysis

    def answer_question(
        self, question: str, scan_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Answer a natural language question about the scan results."""
        q = question.lower()

        if any(w in q for w in ["highest risk", "most dangerous", "critical"]):
            return self._answer_highest_risk(scan_results)
        elif any(w in q for w in ["subdomain", "subdomains", "assets"]):
            return self._answer_subdomains(scan_results)
        elif any(w in q for w in ["certificate", "ssl", "tls"]):
            return self._answer_certificates(scan_results)
        elif any(w in q for w in ["port", "ports", "service", "services"]):
            return self._answer_ports(scan_results)
        elif any(w in q for w in ["technology", "tech", "framework"]):
            return self._answer_technologies(scan_results)
        elif any(w in q for w in ["recommend", "fix", "improve", "remediate"]):
            return self._answer_recommendations(scan_results)
        elif any(w in q for w in ["summary", "overview", "summarize"]):
            return {"answer": self._executive_summary(scan_results), "type": "summary"}
        else:
            return {
                "answer": "I can help you analyze the scan results. Try asking about: highest risk assets, subdomains, certificates, ports, technologies, or recommendations.",
                "type": "help",
            }

    def _executive_summary(self, data: Dict[str, Any]) -> str:
        """Generate executive summary."""
        subdomains = data.get("subdomains", [])
        sub_count = len(subdomains) if isinstance(subdomains, list) else 0

        ports_data = data.get("ports", {})
        open_port_count = 0
        if isinstance(ports_data, dict):
            for host, port_list in ports_data.items():
                if isinstance(port_list, list):
                    open_port_count += len(port_list)

        tech_data = data.get("technologies", {})
        tech_count = 0
        if isinstance(tech_data, dict):
            for host, techs in tech_data.items():
                if isinstance(techs, list):
                    tech_count += len(techs)

        risk = data.get("risk_score", {})
        risk_score = risk.get("risk_score", 0) if isinstance(risk, dict) else 0
        risk_label = risk.get("label", "Unknown") if isinstance(risk, dict) else "Unknown"

        findings = data.get("security_findings", [])
        finding_count = len(findings) if isinstance(findings, list) else 0

        parts = [
            f"The scan discovered {sub_count} subdomains",
            f"with {open_port_count} open ports across all hosts.",
        ]

        if tech_count:
            parts.append(f"{tech_count} technologies were identified.")

        if finding_count:
            parts.append(f"{finding_count} security findings were detected.")

        parts.append(f"Overall risk score: {risk_score}/100 ({risk_label}).")

        return " ".join(parts)

    def _top_risks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify and explain top risks."""
        risks = []

        # Check security findings
        findings = data.get("security_findings", [])
        if isinstance(findings, list):
            for f in findings[:5]:
                if isinstance(f, dict):
                    sev = f.get("severity", "info")
                    if sev in ("critical", "high"):
                        risks.append({
                            "risk": f.get("detail", f.get("type", "Unknown")),
                            "severity": sev,
                            "explanation": self._explain_finding(f),
                        })

        # Check certificates
        certs = data.get("ssl_certificates", {})
        if isinstance(certs, dict):
            for host, cert in certs.items():
                if isinstance(cert, dict):
                    if not cert.get("is_valid", True):
                        risks.append({
                            "risk": f"Expired certificate on {host}",
                            "severity": "critical",
                            "explanation": f"The SSL/TLS certificate on {host} has expired, which means encrypted connections to this host cannot be trusted. Users will see browser warnings.",
                        })
                    days = cert.get("days_until_expiry")
                    if days is not None and days < 7:
                        risks.append({
                            "risk": f"Certificate expiring soon on {host} ({days} days)",
                            "severity": "high",
                            "explanation": f"The certificate on {host} will expire in {days} days. If not renewed, encrypted connections will fail.",
                        })

        # Check open ports
        ports_data = data.get("ports", {})
        risky_ports = {3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis", 27017: "MongoDB", 3389: "RDP"}
        if isinstance(ports_data, dict):
            for host, port_list in ports_data.items():
                if isinstance(port_list, list):
                    for p in port_list:
                        port_num = p.get("port", 0) if isinstance(p, dict) else 0
                        if port_num in risky_ports:
                            risks.append({
                                "risk": f"Exposed {risky_ports[port_num]} on {host}",
                                "severity": "high",
                                "explanation": f"Port {port_num} ({risky_ports[port_num]}) is publicly accessible on {host}. This service should typically be restricted to internal networks.",
                            })

        return risks[:10]

    def _asset_overview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate asset inventory overview."""
        subdomains = data.get("subdomains", [])
        ports_data = data.get("ports", {})
        tech_data = data.get("technologies", {})

        all_hosts = set()
        all_ips = set()
        all_services = set()

        if isinstance(ports_data, dict):
            for host, port_list in ports_data.items():
                all_hosts.add(host)
                if isinstance(port_list, list):
                    for p in port_list:
                        if isinstance(p, dict):
                            all_services.add(p.get("service", "unknown"))
                            ip = p.get("ip")
                            if ip:
                                all_ips.add(ip)

        tech_categories = set()
        if isinstance(tech_data, dict):
            for host, techs in tech_data.items():
                all_hosts.add(host)
                if isinstance(techs, list):
                    for t in techs:
                        if isinstance(t, dict):
                            tech_categories.add(t.get("category", "unknown"))

        return {
            "total_subdomains": len(subdomains) if isinstance(subdomains, list) else 0,
            "total_hosts": len(all_hosts),
            "total_ips": len(all_ips),
            "total_services": len(all_services),
            "services_found": list(all_services),
            "technology_categories": list(tech_categories),
        }

    def _recommendations(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate prioritized recommendations."""
        recs = []

        # Certificate recommendations
        certs = data.get("ssl_certificates", {})
        if isinstance(certs, dict):
            for host, cert in certs.items():
                if isinstance(cert, dict):
                    if not cert.get("is_valid", True):
                        recs.append({
                            "priority": "critical",
                            "action": f"Renew the expired SSL certificate on {host}",
                            "reason": "An expired certificate prevents secure connections and causes browser warnings.",
                        })
                    days = cert.get("days_until_expiry")
                    if days is not None and days < 30:
                        recs.append({
                            "priority": "high",
                            "action": f"Schedule certificate renewal for {host} (expires in {days} days)",
                            "reason": "Proactive renewal prevents service disruption.",
                        })

        # Port recommendations
        ports_data = data.get("ports", {})
        internal_ports = {3306, 5432, 6379, 27017, 1433, 9200}
        if isinstance(ports_data, dict):
            for host, port_list in ports_data.items():
                if isinstance(port_list, list):
                    for p in port_list:
                        port_num = p.get("port", 0) if isinstance(p, dict) else 0
                        if port_num in internal_ports:
                            recs.append({
                                "priority": "high",
                                "action": f"Restrict port {port_num} access on {host} to internal networks",
                                "reason": "Database/cache ports should not be publicly accessible.",
                            })

        # Technology recommendations
        tech_data = data.get("technologies", {})
        old_techs = {"php": "5.x", "apache": "2.2", "nginx": "1.0"}
        if isinstance(tech_data, dict):
            for host, techs in tech_data.items():
                if isinstance(techs, list):
                    for t in techs:
                        if isinstance(t, dict):
                            name = t.get("name", "").lower()
                            version = t.get("version", "")
                            if name in old_techs and version:
                                recs.append({
                                    "priority": "medium",
                                    "action": f"Update {name} {version} on {host} to the latest stable version",
                                    "reason": "Outdated software may contain known vulnerabilities.",
                                })

        # Security header recommendations
        recs.append({
            "priority": "medium",
            "action": "Enable HSTS and Content Security Policy headers on all web hosts",
            "reason": "Security headers protect against common web attacks.",
        })

        return sorted(recs, key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r["priority"], 4))

    def _detailed_findings(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate detailed finding explanations."""
        findings = []
        raw = data.get("security_findings", [])
        if isinstance(raw, list):
            for f in raw:
                if isinstance(f, dict):
                    findings.append({
                        "type": f.get("type", "Unknown"),
                        "severity": f.get("severity", "info"),
                        "detail": f.get("detail", ""),
                        "explanation": self._explain_finding(f),
                        "remediation": f.get("remediation", "Review and remediate according to security best practices."),
                    })
        return findings

    def _explain_finding(self, finding: Dict[str, Any]) -> str:
        """Generate explanation for a single finding."""
        ftype = finding.get("type", "").lower()
        detail = finding.get("detail", "")

        explanations = {
            "expired_cert": f"The SSL certificate has expired. {detail}. This means encrypted connections cannot be trusted and users will see browser security warnings.",
            "weak_tls": f"The TLS configuration uses weak protocols or ciphers. {detail}. This makes the connection vulnerable to interception.",
            "missing_hsts": "The server does not send an HSTS header, which means browsers won't enforce HTTPS on future visits.",
            "missing_csp": "No Content Security Policy header is set, which increases vulnerability to XSS attacks.",
            "exposed_admin": f"An admin panel is publicly accessible. {detail}. This should be restricted to trusted IPs.",
            "exposed_db": f"A database port is publicly accessible. {detail}. This should be firewalled to internal networks only.",
        }

        for key, explanation in explanations.items():
            if key in ftype or key in detail.lower():
                return explanation

        return f"A security finding was detected: {detail}"

    def _answer_highest_risk(self, data: Dict[str, Any]) -> Dict[str, Any]:
        risks = self._top_risks(data)
        if not risks:
            return {"answer": "No critical or high-risk findings were detected in this scan.", "type": "analysis"}
        answer_parts = [f"I found {len(risks)} high-priority risks:"]
        for i, r in enumerate(risks, 1):
            answer_parts.append(f"{i}. [{r['severity'].upper()}] {r['risk']}: {r['explanation']}")
        return {"answer": "\n".join(answer_parts), "type": "analysis"}

    def _answer_subdomains(self, data: Dict[str, Any]) -> Dict[str, Any]:
        overview = self._asset_overview(data)
        return {
            "answer": f"The scan discovered {overview['total_subdomains']} subdomains across {overview['total_hosts']} hosts with {overview['total_services']} distinct services.",
            "type": "analysis",
            "data": overview,
        }

    def _answer_certificates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        certs = data.get("ssl_certificates", {})
        if not isinstance(certs, dict) or not certs:
            return {"answer": "No certificate data was collected in this scan.", "type": "analysis"}

        expired = []
        expiring = []
        for host, cert in certs.items():
            if isinstance(cert, dict):
                if not cert.get("is_valid", True):
                    expired.append(host)
                days = cert.get("days_until_expiry")
                if days is not None and days < 30:
                    expiring.append(f"{host} ({days} days)")

        parts = [f"Certificate analysis for {len(certs)} hosts:"]
        if expired:
            parts.append(f"EXPIRED: {', '.join(expired)}")
        if expiring:
            parts.append(f"EXPIRING SOON: {', '.join(expiring)}")
        if not expired and not expiring:
            parts.append("All certificates are valid and not expiring soon.")

        return {"answer": "\n".join(parts), "type": "analysis"}

    def _answer_ports(self, data: Dict[str, Any]) -> Dict[str, Any]:
        overview = self._asset_overview(data)
        return {
            "answer": f"Found {overview['total_services']} services: {', '.join(overview['services_found'][:10])}",
            "type": "analysis",
            "data": overview,
        }

    def _answer_technologies(self, data: Dict[str, Any]) -> Dict[str, Any]:
        overview = self._asset_overview(data)
        return {
            "answer": f"Detected technologies in {len(overview['technology_categories'])} categories: {', '.join(overview['technology_categories'])}",
            "type": "analysis",
            "data": overview,
        }

    def _answer_recommendations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        recs = self._recommendations(data)
        if not recs:
            return {"answer": "No specific recommendations at this time.", "type": "analysis"}
        parts = [f"Here are {len(recs)} prioritized recommendations:"]
        for i, r in enumerate(recs[:5], 1):
            parts.append(f"{i}. [{r['priority'].upper()}] {r['action']} — {r['reason']}")
        return {"answer": "\n".join(parts), "type": "analysis"}


# Singleton
analyst = SecurityAnalyst()
