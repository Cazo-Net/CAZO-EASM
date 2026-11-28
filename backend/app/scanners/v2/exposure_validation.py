"""Exposure Validation Scanner — validates real-world exploitability of discovered assets.

Checks for:
- Exposed sensitive files (.env, .git, backup files, config dumps)
- Misconfigured HTTP security headers (CSP, HSTS, X-Frame-Options, etc.)
- Debug/admin endpoints exposed in production
- Information disclosure (server headers, version leaks, error pages)
- SSL/TLS misconfigurations (weak ciphers, expired certs)
- Common default credentials on admin panels
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import ssl
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import dns.resolver
import httpx

from app.core.target_guard import GUARDED_HOOKS

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

# ── Sensitive paths to probe ────────────────────────────────────────────────

_SENSITIVE_PATHS: list[dict[str, Any]] = [
    # Environment & config
    {"path": "/.env", "severity": "critical", "category": "environment_file"},
    {"path": "/.env.local", "severity": "critical", "category": "environment_file"},
    {"path": "/.env.production", "severity": "critical", "category": "environment_file"},
    {"path": "/.env.backup", "severity": "critical", "category": "environment_file"},
    {"path": "/config.json", "severity": "high", "category": "config_file"},
    {"path": "/config.yml", "severity": "high", "category": "config_file"},
    {"path": "/config.yaml", "severity": "high", "category": "config_file"},
    {"path": "/config.php", "severity": "high", "category": "config_file"},
    {"path": "/settings.json", "severity": "high", "category": "config_file"},
    {"path": "/wp-config.php.bak", "severity": "critical", "category": "config_file"},
    {"path": "/.htaccess", "severity": "medium", "category": "config_file"},

    # Git
    {"path": "/.git/config", "severity": "critical", "category": "source_control"},
    {"path": "/.git/HEAD", "severity": "high", "category": "source_control"},
    {"path": "/.gitignore", "severity": "low", "category": "source_control"},

    # Backup files
    {"path": "/backup.sql", "severity": "critical", "category": "backup_file"},
    {"path": "/backup.zip", "severity": "high", "category": "backup_file"},
    {"path": "/db.sql", "severity": "critical", "category": "backup_file"},
    {"path": "/database.sql", "severity": "critical", "category": "backup_file"},
    {"path": "/dump.sql", "severity": "critical", "category": "backup_file"},
    {"path": "/site.tar.gz", "severity": "high", "category": "backup_file"},
    {"path": "/www.zip", "severity": "high", "category": "backup_file"},
    {"path": "/public.zip", "severity": "high", "category": "backup_file"},

    # Debug & admin
    {"path": "/debug", "severity": "medium", "category": "debug_endpoint"},
    {"path": "/debug/vars", "severity": "high", "category": "debug_endpoint"},
    {"path": "/debug/pprof/", "severity": "high", "category": "debug_endpoint"},
    {"path": "/actuator", "severity": "medium", "category": "debug_endpoint"},
    {"path": "/actuator/env", "severity": "critical", "category": "debug_endpoint"},
    {"path": "/actuator/health", "severity": "low", "category": "debug_endpoint"},
    {"path": "/phpinfo.php", "severity": "high", "category": "debug_endpoint"},
    {"path": "/info.php", "severity": "medium", "category": "debug_endpoint"},
    {"path": "/server-status", "severity": "medium", "category": "debug_endpoint"},
    {"path": "/server-info", "severity": "medium", "category": "debug_endpoint"},

    # Admin panels
    {"path": "/admin", "severity": "medium", "category": "admin_panel"},
    {"path": "/admin/login", "severity": "low", "category": "admin_panel"},
    {"path": "/wp-admin/", "severity": "low", "category": "admin_panel"},
    {"path": "/wp-login.php", "severity": "low", "category": "admin_panel"},
    {"path": "/administrator/", "severity": "low", "category": "admin_panel"},
    {"path": "/cpanel", "severity": "medium", "category": "admin_panel"},
    {"path": "/plesk", "severity": "medium", "category": "admin_panel"},

    # API endpoints
    {"path": "/api/v1/users", "severity": "medium", "category": "api_exposure"},
    {"path": "/graphql", "severity": "low", "category": "api_exposure"},
    {"path": "/swagger-ui.html", "severity": "medium", "category": "api_exposure"},
    {"path": "/swagger.json", "severity": "medium", "category": "api_exposure"},
    {"path": "/openapi.json", "severity": "medium", "category": "api_exposure"},
    {"path": "/api-docs", "severity": "medium", "category": "api_exposure"},
]

# ── Security headers to check ───────────────────────────────────────────────

_REQUIRED_SECURITY_HEADERS: dict[str, dict[str, Any]] = {
    "strict-transport-security": {
        "severity": "high",
        "description": "HSTS header missing — allows HTTP downgrade attacks",
    },
    "content-security-policy": {
        "severity": "high",
        "description": "CSP header missing — vulnerable to XSS and injection",
    },
    "x-content-type-options": {
        "severity": "medium",
        "description": "X-Content-Type-Options missing — MIME sniffing risk",
    },
    "x-frame-options": {
        "severity": "medium",
        "description": "X-Frame-Options missing — clickjacking risk",
    },
    "x-xss-protection": {
        "severity": "low",
        "description": "X-XSS-Protection missing (legacy but still useful)",
    },
    "referrer-policy": {
        "severity": "low",
        "description": "Referrer-Policy missing — may leak sensitive URLs",
    },
    "permissions-policy": {
        "severity": "low",
        "description": "Permissions-Policy missing — browser features unrestricted",
    },
}

# ── Information disclosure patterns ─────────────────────────────────────────

_SERVER_HEADER_PATTERNS: list[dict[str, Any]] = [
    {"pattern": r"Apache/(\d+\.\d+\.\d+)", "name": "Apache", "severity": "medium"},
    {"pattern": r"nginx/(\d+\.\d+\.\d+)", "name": "Nginx", "severity": "medium"},
    {"pattern": r"Microsoft-IIS/(\d+\.\d+)", "name": "IIS", "severity": "medium"},
    {"pattern": r"OpenSSH/(\d+\.\d+)", "name": "OpenSSH", "severity": "medium"},
    {"pattern": r"PHP/(\d+\.\d+\.\d+)", "name": "PHP", "severity": "high"},
    {"pattern": r"Express", "name": "Express.js", "severity": "low"},
]

_ERROR_PAGE_SIGNATURES: list[dict[str, Any]] = [
    {"pattern": r"Traceback \(most recent call last\)", "name": "Python stack trace", "severity": "high"},
    {"pattern": r"Fatal error:.*in.*on line \d+", "name": "PHP fatal error", "severity": "high"},
    {"pattern": r"org\.springframework\.", "name": "Spring stack trace", "severity": "high"},
    {"pattern": r"java\.lang\.\w+Exception", "name": "Java exception", "severity": "high"},
    {"pattern": r"Syntax error.*line \d+", "name": "Generic syntax error", "severity": "medium"},
]


class TakeoverSignature:
    """How to confirm a dangling CNAME at one service is really claimable."""

    def __init__(self, service: str, suffixes: tuple, fingerprints: tuple = (),
                 nxdomain_means_unclaimed: bool = False, severity: str = "high"):
        self.service = service
        self.suffixes = suffixes
        self.fingerprints = fingerprints
        self.nxdomain_means_unclaimed = nxdomain_means_unclaimed
        self.severity = severity


# Signals per service follow the community-maintained "can-i-take-over-xyz"
# list. Services whose takeover is no longer possible (CloudFront, generic
# AWS hostnames) or that give no reliable signal are left out on purpose.
TAKEOVER_SIGNATURES: list[TakeoverSignature] = [
    TakeoverSignature("GitHub Pages", ("github.io",), ("there isn't a github pages site here",)),
    TakeoverSignature("Heroku", ("herokuapp.com", "herokudns.com", "herokussl.com"),
                      ("no such app", "herokucdn.com/error-pages/no-such-app.html")),
    TakeoverSignature("AWS S3", ("s3.amazonaws.com", ".s3-website", ".s3."),
                      ("nosuchbucket", "the specified bucket does not exist")),
    TakeoverSignature("Azure", ("azurewebsites.net", "cloudapp.net", "cloudapp.azure.com",
                                "trafficmanager.net", "blob.core.windows.net", "azure-api.net",
                                "azureedge.net", "azurecontainer.io", "azurefd.net", "azurestaticapps.net"),
                      nxdomain_means_unclaimed=True),
    TakeoverSignature("Fastly", ("fastly.net",), ("fastly error: unknown domain",), severity="medium"),
    TakeoverSignature("Shopify", ("myshopify.com", "shops.myshopify.com"),
                      ("sorry, this shop is currently unavailable",), severity="medium"),
    TakeoverSignature("Ghost", ("ghost.io",), ("the thing you were looking for is no longer here",)),
    TakeoverSignature("Surge.sh", ("surge.sh",), ("project not found",), severity="medium"),
    TakeoverSignature("Bitbucket", ("bitbucket.io",), ("repository not found",)),
    TakeoverSignature("Pantheon", ("pantheonsite.io",),
                      ("the gods are wise, but do not know of the site which you seek",)),
    TakeoverSignature("Help Juice", ("helpjuice.com",), ("we could not find what you're looking for",),
                      severity="medium"),
    TakeoverSignature("Help Scout", ("helpscoutdocs.com",), ("no settings were found for this company",),
                      severity="medium"),
    TakeoverSignature("ReadMe", ("readme.io",), ("project doesnt exist... yet!",), severity="medium"),
    TakeoverSignature("Tumblr", ("domains.tumblr.com",),
                      ("whatever you were looking for doesn't currently exist at this address",),
                      severity="medium"),
    TakeoverSignature("WordPress.com", ("wordpress.com",), ("do you want to register",), severity="medium"),
    TakeoverSignature("Webflow", ("proxy.webflow.com", "proxy-ssl.webflow.com"),
                      ("the page you are looking for doesn't exist or has been moved",), severity="medium"),
    TakeoverSignature("ngrok", ("ngrok.io", "ngrok.app", "ngrok-free.app"),
                      ("err_ngrok_3200",), severity="high"),
    TakeoverSignature("Uberflip", ("read.uberflip.com",), ("non-hub domain, the url you've accessed",),
                      severity="medium"),
    TakeoverSignature("Agile CRM", ("agilecrm.com",), ("sorry, this page is no longer available",),
                      severity="medium"),
]


def takeover_signature_for(cname: str) -> "TakeoverSignature | None":
    """The service a CNAME target belongs to, if takeovers there are checkable.

    A suffix starting with "." matches anywhere in the name (regional S3
    endpoints); any other suffix must match whole labels at the end.
    """
    c = (cname or "").lower().rstrip(".")
    for sig in TAKEOVER_SIGNATURES:
        for suf in sig.suffixes:
            if suf.startswith("."):
                if suf in c:
                    return sig
            elif c == suf or c.endswith("." + suf):
                return sig
    return None


@register_scanner(
    name="exposure-validation",
    category=ScannerCategory.VULNERABILITY_ASSESSMENT,
    version="1.0.0",
    description="Validates exposure: sensitive files, security headers, info disclosure, debug endpoints",
    priority=ScannerPriority.HIGH,
    dependencies=["tech-intel", "dns-intel"],
    capabilities=[
        "sensitive_file_detection",
        "security_header_audit",
        "information_disclosure",
        "debug_endpoint_detection",
        "admin_panel_detection",
        "cors_misconfiguration",
        "open_redirect_detection",
        "subdomain_takeover_validation",
        "ssrf_surface_mapping",
        "ssl_tls_validation",
    ],
)
class ExposureValidator(EnhancedBaseScanner):
    """Validates real-world exposure and misconfigurations for a target domain."""

    name = "exposure-validation"
    version = "1.0.0"
    category = ScannerCategory.VULNERABILITY_ASSESSMENT
    priority = ScannerPriority.HIGH
    description = "Validates exposure: sensitive files, security headers, info disclosure, debug endpoints"
    dependencies = ["tech-intel", "dns-intel"]
    capabilities = [
        "sensitive_file_detection",
        "security_header_audit",
        "information_disclosure",
        "debug_endpoint_detection",
        "admin_panel_detection",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.timeout = self.config.get("timeout", 30)
        self._max_concurrent = self.config.get("max_concurrent", 10)
        self._sensitive_paths = self.config.get("sensitive_paths", _SENSITIVE_PATHS)
        self._verify_ssl = self.config.get("verify_ssl", False)
        # Path probing and the header audit are done (with content
        # validation, per web service) by the web-exposure scanner. These
        # unvalidated versions flagged every 200/301/403 and duplicated it.
        self._probe_paths = bool(self.config.get("exposure_validation_probe_paths", False))
        self._check_headers = bool(self.config.get("exposure_validation_check_headers", False))
        # Takeover checks walk every in-scope subdomain; give them room.
        self.timeout = max(float(self.timeout), 180.0)
        self.max_retries = 0

    def validate_target(self, target: str) -> bool:
        return bool(target and "." in target)

    async def scan(self, target: str, **kwargs) -> ScanResult:
        start = time.time()
        errors: list[str] = []
        warnings: list[str] = []

        # Collect data from kwargs (prior scan results)
        open_ports: list[int] = kwargs.get("open_ports", [])
        technologies: list[dict[str, Any]] = kwargs.get("technologies", [])
        subdomains: list[str] = kwargs.get("subdomains", [])

        # Build list of hosts to probe
        hosts_to_probe: list[str] = [target]
        for sub in subdomains[:20]:  # Limit to 20 subdomains
            if sub not in hosts_to_probe:
                hosts_to_probe.append(sub)

        from app.core.target_guard import filter_probe_targets

        hosts_to_probe = await filter_probe_targets(hosts_to_probe, kwargs.get("root_domain") or target)

        # Determine which ports have HTTP services
        http_ports: list[int] = []
        for port in open_ports:
            if port in (80, 443, 8080, 8443, 8000, 3000, 5000, 9000, 9443):
                http_ports.append(port)
        if not http_ports:
            http_ports = [80, 443]

        # Build URL list
        urls_to_probe: list[str] = []
        for host in (hosts_to_probe if self._probe_paths else []):
            for port in http_ports:
                scheme = "https" if port in (443, 8443, 9443) else "http"
                port_suffix = "" if port in (80, 443) else f":{port}"
                base_url = f"{scheme}://{host}{port_suffix}"
                for path_entry in self._sensitive_paths:
                    urls_to_probe.append(f"{base_url}{path_entry['path']}")

        # Probe all URLs concurrently
        findings: list[dict[str, Any]] = []
        sem = asyncio.Semaphore(self._max_concurrent)

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True, event_hooks=GUARDED_HOOKS,
            verify=self._verify_ssl,
            headers={"User-Agent": "CAZO-EASM/2.0 (Security Scanner)"},
        ) as client:
            tasks = [self._probe_url(client, sem, url) for url in urls_to_probe]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict) and r.get("found"):
                    findings.append(r)

        # The remaining check groups are independent of each other: run them
        # together instead of one after another. Results are appended in the
        # same order as before, so de-duplication keeps the same winner.
        async def _none() -> list[dict[str, Any]]:
            return []

        groups = [
            ("security_headers", self._check_security_headers(target) if self._check_headers else _none()),
            ("info_disclosure", self._check_info_disclosure(target)),
            ("cors", self._check_cors_misconfiguration(target, subdomains)),
            ("open_redirect", self._check_open_redirects(target)),
            ("subdomain_takeover", self._check_subdomain_takeover(subdomains[:200])),
            ("ssrf_surface", self._check_ssrf_surface(target)),
            ("ssl_tls", self._check_ssl_tls(target) if (443 in open_ports or 8443 in open_ports) else _none()),
        ]
        group_results = await asyncio.gather(*(c for _, c in groups), return_exceptions=True)
        for (group_name, _), group_result in zip(groups, group_results):
            if isinstance(group_result, BaseException):
                errors.append(f"{group_name}: {group_result}")
                continue
            findings.extend(group_result or [])

        # Deduplicate findings
        seen: set[str] = set()
        unique_findings: list[dict[str, Any]] = []
        for f in findings:
            key = f"{f.get('category', '')}:{f.get('url', f.get('header', ''))}"
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in unique_findings:
            sev = f.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        duration_ms = (time.time() - start) * 1000

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "findings": unique_findings,
                "summary": {
                    "total_findings": len(unique_findings),
                    "severity_breakdown": severity_counts,
                    "hosts_probed": len(hosts_to_probe),
                    "urls_probed": len(urls_to_probe),
                    "categories": list({f.get("category", "unknown") for f in unique_findings}),
                },
            },
            warnings=warnings,
            errors=errors,
            duration_ms=duration_ms,
            metadata={
                "open_ports_scanned": http_ports,
                "subdomains_probed": len(hosts_to_probe) - 1,
                "technologies_used": [t.get("name", "unknown") for t in technologies[:10]],
            },
        )

    async def _probe_url(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        url: str,
    ) -> dict[str, Any]:
        """Probe a single URL and return a finding if something is exposed."""
        async with sem:
            try:
                resp = await client.get(url, timeout=10)
                if resp.status_code in (200, 301, 302, 401, 403):
                    # Parse the URL to extract path info
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    path = parsed.path

                    # Match against sensitive path categories
                    for path_entry in self._sensitive_paths:
                        if path == path_entry["path"] or path.endswith(path_entry["path"]):
                            # Determine if it's a real finding
                            is_false_positive = False

                            # 403 on admin panels is expected
                            if resp.status_code == 403 and path_entry["category"] == "admin_panel":
                                is_false_positive = True

                            # 401 on admin login is expected
                            if resp.status_code == 401 and "login" in path:
                                is_false_positive = True

                            # .gitignore 404 is normal
                            if resp.status_code == 404 and path == "/.gitignore":
                                is_false_positive = True

                            if not is_false_positive:
                                body_preview = resp.text[:500] if resp.status_code == 200 else ""
                                return {
                                    "found": True,
                                    "url": url,
                                    "path": path,
                                    "category": path_entry["category"],
                                    "severity": path_entry["severity"],
                                    "status_code": resp.status_code,
                                    "content_length": len(resp.content),
                                    "body_preview": body_preview[:200],
                                    "description": f"Sensitive {path_entry['category']} accessible at {path}",
                                }
            except Exception:
                pass
            return {"found": False}

    async def _check_security_headers(self, target: str) -> list[dict[str, Any]]:
        """Check for missing or weak security headers."""
        findings: list[dict[str, Any]] = []
        urls = [f"https://{target}", f"http://{target}"]

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True, event_hooks=GUARDED_HOOKS,
            verify=False,
            headers={"User-Agent": "CAZO-EASM/2.0 (Security Scanner)"},
        ) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    headers = {k.lower(): v for k, v in resp.headers.items()}

                    for header_name, info in _REQUIRED_SECURITY_HEADERS.items():
                        if header_name not in headers:
                            findings.append({
                                "found": True,
                                "url": url,
                                "header": header_name,
                                "category": "missing_security_header",
                                "severity": info["severity"],
                                "description": info["description"],
                            })
                        elif header_name == "strict-transport-security":
                            # Check for weak HSTS
                            max_age_match = re.search(r"max-age=(\d+)", headers.get(header_name, ""))
                            if max_age_match:
                                max_age = int(max_age_match.group(1))
                                if max_age < 31536000:  # Less than 1 year
                                    findings.append({
                                        "found": True,
                                        "url": url,
                                        "header": header_name,
                                        "category": "weak_security_header",
                                        "severity": "medium",
                                        "description": f"HSTS max-age={max_age} is weak (should be >= 31536000)",
                                    })

                    # Check for dangerous headers
                    if "access-control-allow-origin" in headers:
                        acao = headers["access-control-allow-origin"]
                        if acao == "*":
                            findings.append({
                                "found": True,
                                "url": url,
                                "header": "access-control-allow-origin",
                                "category": "weak_security_header",
                                "severity": "medium",
                                "description": "CORS wildcard (*) allows any origin",
                            })

                    break  # Only need one successful response

                except Exception:
                    continue

        return findings

    async def _check_info_disclosure(self, target: str) -> list[dict[str, Any]]:
        """Check for information disclosure in HTTP responses."""
        findings: list[dict[str, Any]] = []
        urls = [f"https://{target}", f"http://{target}"]

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True, event_hooks=GUARDED_HOOKS,
            verify=False,
            headers={"User-Agent": "CAZO-EASM/2.0 (Security Scanner)"},
        ) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    server_header = resp.headers.get("server", "")
                    x_powered = resp.headers.get("x-powered-by", "")

                    # Check server header for version disclosure
                    for pattern_info in _SERVER_HEADER_PATTERNS:
                        match = re.search(pattern_info["pattern"], server_header, re.IGNORECASE)
                        if match:
                            version = match.group(1) if match.lastindex else ""
                            findings.append({
                                "found": True,
                                "url": url,
                                "header": "server",
                                "category": "info_disclosure",
                                "severity": pattern_info["severity"],
                                "description": f"Server header discloses {pattern_info['name']} {version}",
                                "value": server_header,
                            })

                    # Check X-Powered-By
                    if x_powered:
                        findings.append({
                            "found": True,
                            "url": url,
                            "header": "x-powered-by",
                            "category": "info_disclosure",
                            "severity": "medium",
                            "description": f"X-Powered-By header discloses technology: {x_powered}",
                            "value": x_powered,
                        })

                    # Check for error disclosure in response body
                    body = resp.text[:5000]
                    for error_sig in _ERROR_PAGE_SIGNATURES:
                        if re.search(error_sig["pattern"], body, re.IGNORECASE):
                            findings.append({
                                "found": True,
                                "url": url,
                                "category": "info_disclosure",
                                "severity": error_sig["severity"],
                                "description": f"Response contains {error_sig['name']}",
                            })
                            break

                    break  # Only need one successful response

                except Exception:
                    continue

        return findings

    async def _check_ssl_tls(self, target: str) -> list[dict[str, Any]]:
        """Check SSL/TLS configuration for weaknesses."""
        findings: list[dict[str, Any]] = []

        try:
            # Create SSL context and check
            ctx = ssl.create_default_context()
            loop = asyncio.get_event_loop()

            def _check_ssl_sync() -> dict[str, Any] | None:
                import socket
                try:
                    with socket.create_connection((target, 443), timeout=10) as sock:
                        with ctx.wrap_socket(sock, server_hostname=target) as ssock:
                            cert = ssock.getpeercert()
                            cipher = ssock.cipher()
                            version = ssock.version()

                            result: dict[str, Any] = {
                                "protocol_version": version,
                                "cipher_name": cipher[0] if cipher else "unknown",
                                "cipher_bits": cipher[2] if cipher and len(cipher) > 2 else 0,
                            }

                            # Check certificate expiry
                            import datetime
                            not_after = cert.get("notAfter", "")
                            if not_after:
                                # Parse SSL date format: "Dec 31 23:59:59 2024 GMT"
                                try:
                                    expiry = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                                    now = datetime.datetime.utcnow()
                                    days_left = (expiry - now).days
                                    result["days_until_expiry"] = days_left
                                    if days_left < 0:
                                        result["expired"] = True
                                    elif days_left < 30:
                                        result["expiring_soon"] = True
                                except ValueError:
                                    pass

                            # Check for weak protocols
                            if version in ("TLSv1", "TLSv1.1", "SSLv3"):
                                result["weak_protocol"] = True

                            # Check cert subject
                            subject = cert.get("subject", ())
                            for rdn in subject:
                                for attr in rdn:
                                    if attr[0] == "commonName":
                                        result["cn"] = attr[1]

                            return result
                except Exception as e:
                    return {"error": str(e)}

            result = await loop.run_in_executor(None, _check_ssl_sync)

            if result and not result.get("error"):
                if result.get("expired"):
                    findings.append({
                        "found": True,
                        "category": "ssl_tls",
                        "severity": "critical",
                        "description": f"SSL certificate for {target} is EXPIRED",
                        "details": result,
                    })
                elif result.get("expiring_soon"):
                    findings.append({
                        "found": True,
                        "category": "ssl_tls",
                        "severity": "high",
                        "description": f"SSL certificate for {target} expires in {result.get('days_until_expiry', '?')} days",
                        "details": result,
                    })

                if result.get("weak_protocol"):
                    findings.append({
                        "found": True,
                        "category": "ssl_tls",
                        "severity": "high",
                        "description": f"Weak TLS protocol: {result.get('protocol_version')}",
                        "details": result,
                    })

        except Exception as e:
            logger.debug("SSL check failed for %s: %s", target, e)

        return findings

    # ── CORS misconfiguration ────────────────────────────────────────────────

    async def _check_cors_misconfiguration(
        self, target: str, subdomains: list[str]
    ) -> list[dict[str, Any]]:
        """Deep CORS checks: wildcard, null origin, reflected origin, trusted subdomains."""
        findings: list[dict[str, Any]] = []
        test_origins = [
            f"https://{target}",
            "https://evil.com",
            "null",
            f"https://{target}.evil.com",
            f"https://evil.{target}",
        ]

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True, event_hooks=GUARDED_HOOKS,
            verify=False,
            headers={"User-Agent": "CAZO-EASM/2.0 (Security Scanner)"},
        ) as client:
            for scheme in ("https", "http"):
                url = f"{scheme}://{target}"
                try:
                    for origin in test_origins:
                        headers = {"Origin": origin}
                        resp = await client.get(url, headers=headers)
                        acao = resp.headers.get("access-control-allow-origin", "")
                        acac = resp.headers.get("access-control-allow-credentials", "")

                        if not acao:
                            continue

                        # Wildcard
                        if acao == "*":
                            findings.append({
                                "found": True,
                                "url": url,
                                "category": "cors_misconfiguration",
                                "severity": "high",
                                "description": f"CORS allows all origins (wildcard) with Origin: {origin}",
                                "details": {"acao": acao, "acac": acac, "test_origin": origin},
                            })
                            break  # Wildcard covers everything

                        # Null origin allowed
                        if origin == "null" and acao == "null":
                            findings.append({
                                "found": True,
                                "url": url,
                                "category": "cors_misconfiguration",
                                "severity": "high",
                                "description": "CORS accepts null origin — exploitable via sandboxed iframe",
                                "details": {"acao": acao, "acac": acac},
                            })

                        # Reflected origin (any origin is reflected back)
                        if acao == origin and origin not in (f"https://{target}", f"http://{target}"):
                            sev = "critical" if acac == "true" else "high"
                            findings.append({
                                "found": True,
                                "url": url,
                                "category": "cors_misconfiguration",
                                "severity": sev,
                                "description": f"CORS reflects arbitrary origin with credentials: Origin={origin}",
                                "details": {"acao": acao, "acac": acac, "test_origin": origin},
                            })

                    break  # One scheme is enough

                except Exception:
                    continue

        return findings

    # ── Open redirect ────────────────────────────────────────────────────────

    async def _check_open_redirects(self, target: str) -> list[dict[str, Any]]:
        """Test common URL parameters for open redirect vulnerabilities."""
        findings: list[dict[str, Any]] = []
        redirect_params = ["url", "next", "redirect", "return", "continue", "goto", "redir", "dest", "destination"]
        evil_url = "https://evil.com"

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "CAZO-EASM/2.0 (Security Scanner)"},
        ) as client:
            for scheme in ("https", "http"):
                base = f"{scheme}://{target}"
                for param in redirect_params:
                    test_url = f"{base}/?{param}={evil_url}"
                    try:
                        resp = await client.get(test_url)
                        location = resp.headers.get("location", "")
                        if resp.status_code in (301, 302, 303, 307, 308):
                            if evil_url in location:
                                findings.append({
                                    "found": True,
                                    "url": test_url,
                                    "category": "open_redirect",
                                    "severity": "high",
                                    "description": f"Open redirect via parameter '{param}' — redirects to {evil_url}",
                                    "details": {"param": param, "redirect_to": location, "status": resp.status_code},
                                })
                                break  # Found one, no need to test more params on this scheme
                    except Exception:
                        continue

        return findings

    # ── Subdomain takeover ───────────────────────────────────────────────────

    async def _check_subdomain_takeover(
        self, subdomains: list[str]
    ) -> list[dict[str, Any]]:
        """Detect dangling CNAMEs pointing to unclaimed third-party services.

        A CNAME to a hosting service is only reported when the takeover is
        confirmed by that service's own "unclaimed" signal: its specific
        error page, or (for services that hand out names on request) the
        CNAME target no longer existing. A generic 404 is not evidence; the
        old check treated any "404 not found" or "page not found" text as
        proof, which flagged ordinary CDN 404s as high-severity takeovers.
        """
        import dns.resolver

        def _resolve_cname(s: str) -> str | None:
            try:
                answers = dns.resolver.resolve(s, "CNAME", lifetime=4.0)
                for rdata in answers:
                    return str(rdata.target).rstrip(".")
            except Exception:
                pass
            return None

        def _target_missing(name: str) -> bool:
            try:
                dns.resolver.resolve(name, "A", lifetime=4.0)
                return False
            except dns.resolver.NXDOMAIN:
                return True
            except Exception:
                return False  # timeouts etc. are not proof

        # Look the names up together (bounded), not one after another: with
        # 200 names and slow authoritative servers the serial loop alone
        # could take minutes.
        sem = asyncio.Semaphore(25)

        async def _one(sub: str) -> dict[str, Any] | None:
            async with sem:
                try:
                    cname = await asyncio.to_thread(_resolve_cname, sub)
                    if not cname:
                        return None
                    sig = takeover_signature_for(cname)
                    if sig is None:
                        return None
                    evidence: list[str] = [f"{sub} CNAME {cname} ({sig.service})"]
                    confirmed = False
                    if sig.nxdomain_means_unclaimed and await asyncio.to_thread(_target_missing, cname):
                        confirmed = True
                        evidence.append(f"{cname} does not exist (NXDOMAIN), so the name can be registered by anyone")
                    if not confirmed and sig.fingerprints:
                        page = await self._fetch_takeover_page(sub)
                        hit = next((fp for fp in sig.fingerprints if page and fp.lower() in page), None)
                        if hit:
                            confirmed = True
                            evidence.append(f"https://{sub} shows the {sig.service} 'unclaimed' page: \"{hit}\"")
                    if not confirmed:
                        return None
                    return {
                        "found": True,
                        "category": "subdomain_takeover",
                        "severity": sig.severity,
                        "url": f"https://{sub}",
                        "description": (
                            f"Subdomain takeover possible: {sub} points to {sig.service} ({cname}), "
                            f"but nothing is claimed there. Anyone who registers it on {sig.service} "
                            "can serve content (phishing, cookie theft) on your domain. "
                            f"Fix: remove the DNS record for {sub}, or claim the resource on {sig.service}."
                        ),
                        "details": {
                            "subdomain": sub,
                            "cname": cname,
                            "service": sig.service,
                            "unclaimed": True,
                            "evidence": evidence,
                        },
                    }
                except Exception as e:
                    logger.debug("Takeover check failed for %s: %s", sub, e)
                return None

        return [f for f in await asyncio.gather(*(_one(sub) for sub in subdomains)) if f]

    async def _fetch_takeover_page(self, hostname: str) -> str:
        """Lower-cased start of the page served on ``hostname`` ('' on failure)."""
        for scheme in ("https", "http"):
            try:
                async with httpx.AsyncClient(
                    timeout=8, follow_redirects=True, event_hooks=GUARDED_HOOKS, verify=False,
                    headers={"User-Agent": "CAZO-EASM/2.0"},
                ) as client:
                    resp = await client.get(f"{scheme}://{hostname}")
                    return resp.text[:5000].lower()
            except Exception:  # noqa: BLE001
                continue
        return ""

    # ── SSRF surface mapping ─────────────────────────────────────────────────

    async def _check_ssrf_surface(self, target: str) -> list[dict[str, Any]]:
        """Identify potential SSRF entry points: URL fetchers, webhooks, import endpoints."""
        findings: list[dict[str, Any]] = []

        # Common SSRF-vulnerable paths
        ssrf_paths = [
            "/api/fetch",
            "/api/proxy",
            "/api/webhook",
            "/api/import",
            "/api/load-url",
            "/fetch",
            "/proxy",
            "/webhook",
            "/import",
            "/load",
            "/preview",
            "/pdf",
            "/screenshot",
            "/api/pdf",
            "/api/screenshot",
            "/api/og",
            "/api/metadata",
            "/api/link-preview",
            "/api/unfurl",
            "/api/archive",
            "/api/render",
            "/healthcheck",
            "/webhook/test",
            "/api/webhook/test",
        ]

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "CAZO-EASM/2.0 (Security Scanner)"},
        ) as client:
            for scheme in ("https", "http"):
                base = f"{scheme}://{target}"
                for path in ssrf_paths:
                    url = f"{base}{path}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code not in (404, 405, 502):
                            # Path exists — potential SSRF surface
                            body = resp.text[:2000].lower()
                            is_ssrf_risk = False

                            # Check if the response indicates URL processing
                            ssrf_indicators = [
                                "fetching",
                                "loading url",
                                "requesting",
                                "invalid url",
                                "url parameter",
                                "missing url",
                                "no url provided",
                                "target url",
                                "proxy",
                                "upstream",
                                "connection refused",
                            ]
                            if any(ind in body for ind in ssrf_indicators):
                                is_ssrf_risk = True

                            if resp.status_code == 200 or is_ssrf_risk:
                                severity = "high" if is_ssrf_risk else "low"
                                findings.append({
                                    "found": True,
                                    "url": url,
                                    "category": "ssrf_surface",
                                    "severity": severity,
                                    "description": f"Potential SSRF endpoint: {path} (HTTP {resp.status_code})",
                                    "details": {
                                        "path": path,
                                        "status_code": resp.status_code,
                                        "url_processing_detected": is_ssrf_risk,
                                        "content_type": resp.headers.get("content-type", ""),
                                    },
                                })
                    except Exception:
                        continue

                break  # One scheme is enough

        return findings
