"""Pure-Python vulnerability/security-finding scanner.

This scanner does NOT require the external Nuclei binary. Instead it derives
real, evidence-backed findings from data already collected during a scan
(missing security headers, weak TLS, expired/invalid certificates, exposed
risky services, missing DKIM/DMARC, etc.).

It is registered under the VULNERABILITY category alongside Nuclei. The
ScanRunner prefers Nuclei when its binary is present; this scanner runs as a
complementary pass so vulnerability results are always populated, even in
environments where Nuclei (or outbound access to its template feed) is absent.
"""
from typing import Any, Dict, List, Optional

import httpx
from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
import logging

logger = logging.getLogger(__name__)


# Severity ordering used for sorting/joining.
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5}

# Ports whose exposure is commonly treated as a finding.
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
    9200: ("Elasticsearch exposed (often unauthenticated)", "high"),
    5601: ("Kibana exposed", "medium"),
    5900: ("VNC exposed", "medium"),
}

# Security headers we expect on public web services.
_SECURITY_HEADERS = {
    "strict-transport-security": ("Missing HSTS header", "medium"),
    "content-security-policy": ("Missing Content-Security-Policy", "medium"),
    "x-frame-options": ("Missing X-Frame-Options (clickjacking risk)", "low"),
    "x-content-type-options": ("Missing X-Content-Type-Options", "low"),
    "permissions-policy": ("Missing Permissions-Policy header", "low"),
    "referrer-policy": ("Missing Referrer-Policy header", "low"),
    "x-xss-protection": ("Missing X-XSS-Protection header", "low"),
    "x-permitted-cross-domain-policies": ("Missing cross-domain policies header", "info"),
    "cross-origin-opener-policy": ("Missing Cross-Origin-Opener-Policy", "info"),
    "cross-origin-resource-policy": ("Missing Cross-Origin-Resource-Policy", "info"),
}


@register_scanner(
    name="security-findings",
    category=ScannerCategory.VULNERABILITY,
    description="Pure-Python security finding generator (headers, TLS, ports, certs).",
)
class SecurityFindingsScanner(BaseScanner):
    """Derives vulnerability findings from a scan result payload.

    Unlike Nuclei this needs no external binary. It is intended to always run
    (even when Nuclei is unavailable) so the platform surfaces real, actionable
    findings on every scan.
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.timeout = self.config.get("timeout", 120)

    def validate_target(self, target: str) -> bool:
        return bool(target)

    async def scan(self, target: str, scan_results: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Generate findings from the collected scan results.

        Args:
            target: The primary domain that was scanned.
            scan_results: The full runner result dict (subdomains, ports, ssl,
                technologies, etc.). When omitted we return an empty pass.
        """
        findings: List[Dict[str, Any]] = []

        if not scan_results:
            return {
                "success": True,
                "target": target,
                "vulnerabilities": findings,
                "count": 0,
                "scanner": "security-findings",
            }

        ports_by_host: Dict[str, List[Dict[str, Any]]] = scan_results.get("ports", {}) or {}
        ssl_by_host: Dict[str, Any] = scan_results.get("ssl_certificates", {}) or {}
        tech_by_host: Dict[str, List[Dict[str, Any]]] = scan_results.get("technologies", {}) or {}

        hosts = set(ports_by_host) | set(ssl_by_host) | set(tech_by_host) | {target}

        for host in sorted(hosts):
            # Certificate / TLS findings
            cert = ssl_by_host.get(host)
            if isinstance(cert, dict):
                if cert.get("is_valid") is False:
                    findings.append(self._finding(
                        host, "Invalid or untrusted TLS certificate",
                        "high", "tls", "ssl/invalid-cert",
                        f"Certificate for {host} failed validation.",
                    ))
                days = cert.get("days_until_expiry")
                if isinstance(days, int) and days is not None:
                    if days < 0:
                        findings.append(self._finding(
                            host, "TLS certificate expired", "high", "tls",
                            "ssl/expired",
                            f"Certificate expired {abs(days)} days ago.",
                        ))
                    elif days < 15:
                        findings.append(self._finding(
                            host, "TLS certificate expiring soon", "medium", "tls",
                            "ssl/expiring",
                            f"Certificate expires in {days} days.",
                        ))
                grade = cert.get("grade")
                if grade in ("D", "F"):
                    findings.append(self._finding(
                        host, f"Weak TLS configuration (grade {grade})", "medium",
                        "tls", "ssl/weak",
                        f"SSL Labs grade {grade} indicates weak ciphers/protocols.",
                    ))

            # Port-based findings
            for port_info in ports_by_host.get(host, []) or []:
                port = port_info.get("port")
                if port in _RISKY_PORTS:
                    label, severity = _RISKY_PORTS[port]
                    service = port_info.get("service") or "unknown"
                    findings.append(self._finding(
                        host, f"{label} ({service}/{port})", severity, "exposure",
                        f"port/{port}",
                        f"Port {port} ({service}) is reachable on {host}.",
                    ))

            # Technology-based findings (outdated / risky stacks)
            for tech in tech_by_host.get(host, []) or []:
                name = (tech.get("name") or "").lower()
                version = tech.get("version")
                if name in ("wordpress", "drupal", "joomla") and version:
                    findings.append(self._finding(
                        host, f"CMS detected: {tech.get('name')} {version}",
                        "low", "tech", "cms/version-disclosed",
                        f"Version disclosure for {tech.get('name')} {version} on {host}.",
                    ))

        # DMARC/DKIM findings for the target domain
        dns_records = scan_results.get("dns_records", {}) or {}
        domain_records = dns_records.get(target, {})
        
        has_dmarc = "DMARC" in domain_records or any(k.startswith("DKIM_") for k in domain_records)
        if not has_dmarc:
            findings.append(self._finding(
                target, "Missing DMARC record", "high", "dns", "dns/missing-dmarc",
                f"No DMARC record found for {target}. This increases risk of email spoofing.",
            ))
        
        has_dkim = any(k.startswith("DKIM_") for k in domain_records)
        if not has_dkim:
            findings.append(self._finding(
                target, "Missing DKIM record", "medium", "dns", "dns/missing-dkim",
                f"No DKIM record found for {target}. Email authenticity cannot be verified.",
            ))

        # HTTP misconfiguration checks (pure requests, no binary).
        try:
            await self._http_misconfig_checks(scan_results, findings)
        except Exception as e:
            logger.warning("misconfig checks failed: %s", e)

        findings.sort(key=lambda f: _SEVERITY_RANK.get(f.get("severity", "unknown"), 9))

        return {
            "success": True,
            "target": target,
            "vulnerabilities": findings,
            "count": len(findings),
            "scanner": "security-findings",
        }

    def _finding(
        self,
        host: str,
        name: str,
        severity: str,
        vuln_type: str,
        template_id: str,
        description: str,
    ) -> Dict[str, Any]:
        return {
            "template_id": template_id,
            "name": name,
            "severity": severity,
            "vuln_type": vuln_type,
            "host": host,
            "matched_at": host,
            "description": description,
            "reference": [],
            "tags": [vuln_type],
        }

    # ── Pure HTTP misconfiguration checks ──────────────────────────────
    # Common sensitive paths; status codes that reveal the file are flagged.
    _EXPOSED_FILES = [
        ("/.env", "env", "Exposed .env file", "high", "misc/exposed-env"),
        ("/.git/config", "git-config", "Exposed .git directory", "high", "misc/exposed-git"),
        ("/.aws/credentials", "aws", "Exposed AWS credentials", "critical", "misc/exposed-aws"),
        ("/backup.zip", "backup", "Exposed backup archive", "high", "misc/exposed-backup"),
        ("/phpinfo.php", "phpinfo", "Exposed phpinfo()", "medium", "misc/exposed-phpinfo"),
        ("/server-status", "status", "Exposed server-status", "low", "misc/exposed-status"),
        ("/robots.txt", "robots", "robots.txt (informational)", "info", "misc/robots"),
    ]
    # Default-credential-prone admin panels (we only report the path is reachable;
    # we do NOT attempt logins — that would be intrusive/illegal without auth scope).
    _ADMIN_PANELS = [
        ("/admin", "admin", "Reachable admin panel", "low", "misc/admin-panel"),
        ("/wp-login.php", "wp", "Reachable WordPress admin", "low", "misc/wp-admin"),
        ("/phpmyadmin", "pma", "Reachable phpMyAdmin", "medium", "misc/phpmyadmin"),
        ("/administrator", "joomla", "Reachable Joomla admin", "low", "misc/joomla-admin"),
    ]
    _REQUIRED_HEADERS = {
        "strict-transport-security": ("Missing HSTS header", "medium", "hdr/missing-hsts"),
        "content-security-policy": ("Missing Content-Security-Policy", "medium", "hdr/missing-csp"),
        "x-frame-options": ("Missing X-Frame-Options (clickjacking)", "low", "hdr/missing-xfo"),
        "x-content-type-options": ("Missing X-Content-Type-Options", "low", "hdr/missing-xcto"),
        "referrer-policy": ("Missing Referrer-Policy", "low", "hdr/missing-referrer"),
        "permissions-policy": ("Missing Permissions-Policy", "low", "hdr/missing-permissions"),
    }

    async def _http_misconfig_checks(self, scan_results: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
        """Probe discovered web hosts for misconfigurations over HTTP(S) — parallelized."""
        import asyncio
        tech_by_host = scan_results.get("technologies", {}) or {}
        ports_by_host = scan_results.get("ports", {}) or {}
        hosts = set(tech_by_host) | set(ports_by_host) | {scan_results.get("domain", "")}

        sem = asyncio.Semaphore(50)  # limit concurrent hosts

        async def _check_host(client, host):
            async with sem:
                has_web = any(
                    p.get("port") in (80, 443, 8080, 8000, 8443, 8888)
                    for p in ports_by_host.get(host, [])
                ) or host in tech_by_host
                if not has_web:
                    return

                base_urls = [f"https://{host}", f"http://{host}"]
                root = None
                for url in base_urls:
                    try:
                        root = await client.get(url)
                        break
                    except Exception:
                        continue
                if root is None:
                    return

                hdr = {k.lower(): v for k, v in root.headers.items()}
                for name, (label, sev, tid) in self._REQUIRED_HEADERS.items():
                    if name not in hdr:
                        findings.append(self._finding(
                            host, label, sev, "header", tid,
                            f"{label} on {host}.",
                        ))

                if "apache" in (hdr.get("server", "").lower()) and "<title>Index of" in root.text:
                    findings.append(self._finding(
                        host, "Directory listing enabled", "medium", "misc",
                        "misc/dir-listing", f"Directory listing enabled on {host}.",
                    ))

                # Path probes — parallel within this host
                async def probe(path, label, finding_name, sev, tid):
                    try:
                        r = await client.get(url.rstrip("/") + path)
                        if r.status_code in (200, 403) and not _looks_like_404(r):
                            findings.append(self._finding(
                                host, finding_name, sev, "misc", tid,
                                f"{finding_name} at {path} (HTTP {r.status_code}).",
                            ))
                    except Exception:
                        pass

                probe_tasks = [probe(p, _, fn, sev, tid) for p, _, fn, sev, tid in self._EXPOSED_FILES + self._ADMIN_PANELS]
                await asyncio.gather(*probe_tasks, return_exceptions=True)

        async with httpx.AsyncClient(verify=False, timeout=5, follow_redirects=True) as client:
            host_tasks = [_check_host(client, h) for h in sorted(h for h in hosts if h)]
            await asyncio.gather(*host_tasks, return_exceptions=True)


def _looks_like_404(r: "httpx.Response") -> bool:
    """Best-effort: skip custom 404 pages that return 200/403 for everything."""
    t = (r.text or "").lower()
    return "404" in t and "not found" in t and len(r.text) < 2000
