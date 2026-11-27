"""V2 Security Findings Scanner — derives findings from collected scan data (no binary needed)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.target_guard import GUARDED_HOOKS, filter_probe_targets

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5}

_RISKY_PORTS = {
    21: ("Cleartext FTP exposed", "medium"),
    23: ("Telnet exposed (cleartext)", "high"),
    25: ("SMTP exposed", "low"),
    53: ("DNS recursion exposure", "low"),
    139: ("SMB NetBIOS exposed", "medium"),
    445: ("SMB exposed", "medium"),
    3306: ("MySQL database exposed to network", "high"),
    3389: ("RDP exposed", "high"),
    5432: ("PostgreSQL exposed to network", "high"),
    6379: ("Redis exposed (often unauthenticated)", "high"),
    27017: ("MongoDB exposed to network", "high"),
    9200: ("Elasticsearch exposed", "high"),
    5601: ("Kibana exposed", "medium"),
    5900: ("VNC exposed", "medium"),
}

_REQUIRED_HEADERS = {
    "strict-transport-security": ("Missing HSTS header", "medium", "hdr/missing-hsts"),
    "content-security-policy": ("Missing Content-Security-Policy", "medium", "hdr/missing-csp"),
    "x-frame-options": ("Missing X-Frame-Options (clickjacking)", "low", "hdr/missing-xfo"),
    "x-content-type-options": ("Missing X-Content-Type-Options", "low", "hdr/missing-xcto"),
    "referrer-policy": ("Missing Referrer-Policy", "low", "hdr/missing-referrer"),
    "permissions-policy": ("Missing Permissions-Policy", "low", "hdr/missing-permissions"),
}

_EXPOSED_FILES = [
    ("/.env", "Exposed .env file", "high", "misc/exposed-env"),
    ("/.git/config", "Exposed .git directory", "high", "misc/exposed-git"),
    ("/.aws/credentials", "Exposed AWS credentials", "critical", "misc/exposed-aws"),
    ("/backup.zip", "Exposed backup archive", "high", "misc/exposed-backup"),
    ("/phpinfo.php", "Exposed phpinfo()", "medium", "misc/exposed-phpinfo"),
    ("/server-status", "Exposed server-status", "low", "misc/exposed-status"),
    ("/robots.txt", "robots.txt (informational)", "info", "misc/robots"),
]

_ADMIN_PANELS = [
    ("/admin", "Reachable admin panel", "low", "misc/admin-panel"),
    ("/wp-login.php", "Reachable WordPress admin", "low", "misc/wp-admin"),
    ("/phpmyadmin", "Reachable phpMyAdmin", "medium", "misc/phpmyadmin"),
    ("/administrator", "Reachable Joomla admin", "low", "misc/joomla-admin"),
]


@register_scanner(
    name="security-findings",
    category=ScannerCategory.VULNERABILITY,
    version="2.0.0",
    priority=ScannerPriority.NORMAL,
    description="Security finding generator from scan data (headers, TLS, ports, certs, paths)",
    capabilities=["security_headers", "exposed_ports", "sensitive_paths", "tls_findings"],
)
class SecurityFindingsScanner(EnhancedBaseScanner):
    name = "security-findings"
    version = "2.0.0"
    category = ScannerCategory.VULNERABILITY
    priority = ScannerPriority.NORMAL

    def validate_target(self, target: str) -> bool:
        return bool(target)

    async def scan(self, target: str, **kwargs) -> ScanResult:
        scan_results = kwargs.get("scan_results") or {}
        if not scan_results:
            return ScanResult(success=True, scanner=self.name, target=target,
                              data={"vulnerabilities": [], "count": 0})

        findings: List[Dict[str, Any]] = []
        ports_by_host = scan_results.get("ports", {}) or {}
        ssl_by_host = scan_results.get("ssl_certificates", {}) or {}
        tech_by_host = scan_results.get("technologies", {}) or {}
        dns_records = scan_results.get("dns_records", {}) or {}
        hosts = set(ports_by_host) | set(ssl_by_host) | set(tech_by_host) | {target}

        for host in sorted(hosts):
            cert = ssl_by_host.get(host)
            if isinstance(cert, dict):
                if cert.get("is_valid") is False:
                    findings.append(self._finding(host, "Invalid or untrusted TLS certificate", "high", "tls", "ssl/invalid-cert"))
                days = cert.get("days_until_expiry")
                if isinstance(days, int):
                    if days < 0:
                        findings.append(self._finding(host, "TLS certificate expired", "high", "tls", "ssl/expired"))
                    elif days < 15:
                        findings.append(self._finding(host, "TLS certificate expiring soon", "medium", "tls", "ssl/expiring"))
                if cert.get("grade") in ("D", "F"):
                    findings.append(self._finding(host, f"Weak TLS configuration (grade {cert['grade']})", "medium", "tls", "ssl/weak"))

            for port_info in ports_by_host.get(host, []) or []:
                port = port_info.get("port")
                if port in _RISKY_PORTS:
                    label, sev = _RISKY_PORTS[port]
                    svc = port_info.get("service") or "unknown"
                    findings.append(self._finding(host, f"{label} ({svc}/{port})", sev, "exposure", f"port/{port}"))

            for tech in tech_by_host.get(host, []) or []:
                name = (tech.get("name") or "").lower()
                version = tech.get("version")
                if name in ("wordpress", "drupal", "joomla") and version:
                    findings.append(self._finding(host, f"CMS detected: {tech.get('name')} {version}", "low", "tech", "cms/version-disclosed"))

        # DMARC/DKIM
        domain_records = dns_records.get(target, {})
        if not any(k == "DMARC" for k in domain_records):
            findings.append(self._finding(target, "Missing DMARC record", "high", "dns", "dns/missing-dmarc"))
        if not any(k.startswith("DKIM_") for k in domain_records):
            findings.append(self._finding(target, "Missing DKIM record", "medium", "dns", "dns/missing-dkim"))

        # HTTP misconfiguration
        try:
            await self._http_checks(scan_results, findings, kwargs.get("root_domain") or target)
        except Exception as e:
            logger.warning("HTTP misconfig checks failed: %s", e)

        findings.sort(key=lambda f: _SEVERITY_RANK.get(f.get("severity", "unknown"), 9))
        return ScanResult(success=True, scanner=self.name, target=target,
                          data={"vulnerabilities": findings, "count": len(findings)})

    def _finding(self, host, name, severity, vuln_type, template_id):
        return {"template_id": template_id, "name": name, "severity": severity,
                "vuln_type": vuln_type, "host": host, "matched_at": host,
                "description": f"{name} on {host}.", "tags": [vuln_type]}

    async def _http_checks(self, scan_results, findings, root_domain):
        tech_by_host = scan_results.get("technologies", {}) or {}
        ports_by_host = scan_results.get("ports", {}) or {}
        hosts = set(tech_by_host) | set(ports_by_host)

        sem = asyncio.Semaphore(20)

        async def _check_host(client, host):
            async with sem:
                has_web = any(p.get("port") in (80, 443, 8080, 8000, 8443) for p in ports_by_host.get(host, [])) or host in tech_by_host
                if not has_web:
                    return
                root = None
                for url in [f"https://{host}", f"http://{host}"]:
                    try:
                        root = await client.get(url)
                        break
                    except Exception:
                        continue
                if root is None:
                    return
                hdr = {k.lower(): v for k, v in root.headers.items()}
                for name, (label, sev, tid) in _REQUIRED_HEADERS.items():
                    if name not in hdr:
                        findings.append(self._finding(host, label, sev, "header", tid))
                # Path probes
                for path, label, sev, tid in _EXPOSED_FILES + _ADMIN_PANELS:
                    try:
                        r = await client.get(f"http://{host}{path}")
                        if r.status_code in (200, 403):
                            findings.append(self._finding(host, label, sev, "misc", tid))
                    except Exception:
                        pass

        probe_hosts = await filter_probe_targets(sorted(hosts), root_domain)
        async with httpx.AsyncClient(verify=False, timeout=5, follow_redirects=True, event_hooks=GUARDED_HOOKS) as client:
            await asyncio.gather(*[_check_host(client, h) for h in probe_hosts], return_exceptions=True)
