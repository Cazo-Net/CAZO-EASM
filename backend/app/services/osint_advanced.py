"""Advanced OSINT collectors — zero-key, open-source intelligence.

Extends the base OSINT engine with:
* Email / DNS security intelligence (DMARC, SPF, DKIM, MX)
* WAF / CDN detection
* Security header analysis
* Sensitive path scanning (backup files, .env, .git, admin panels)
* Web technology fingerprinting (HTML, headers, cookies, JS)
* Reverse DNS range scanning
* Risk scoring engine
"""
from __future__ import annotations

import re
import logging
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

log = logging.getLogger("osint.advanced")

_USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class EmailSecurityResult:
    """DMARC / SPF / DKIM / MX analysis for a domain."""
    mx_records: List[Dict[str, str]] = field(default_factory=list)
    dmarc_record: Optional[str] = None
    dmarc_policy: Optional[str] = None
    spf_record: Optional[str] = None
    spf_valid: Optional[bool] = None
    dkim_selectors: List[str] = field(default_factory=list)
    dkim_found: List[str] = field(default_factory=list)
    smtp_banner: Optional[str] = None
    open_relay: Optional[bool] = None
    emails_found: List[str] = field(default_factory=list)


@dataclass
class WafCdnResult:
    """WAF / CDN detection for the target."""
    cdn: Optional[str] = None
    waf: Optional[str] = None
    server: Optional[str] = None
    powered_by: Optional[str] = None
    technologies_from_headers: List[str] = field(default_factory=list)


@dataclass
class SecurityHeadersResult:
    """Security header audit."""
    hsts: Optional[str] = None
    csp: Optional[str] = None
    x_frame_options: Optional[str] = None
    x_content_type_options: Optional[str] = None
    x_xss_protection: Optional[str] = None
    referrer_policy: Optional[str] = None
    permissions_policy: Optional[str] = None
    score: int = 0
    issues: List[str] = field(default_factory=list)


@dataclass
class SensitivePathResult:
    """Discovered sensitive paths / files."""
    path: str = ""
    status: int = 0
    size: int = 0
    category: str = ""


@dataclass
class WebFingerprintResult:
    """Technology fingerprinting from HTML / headers / cookies."""
    title: Optional[str] = None
    meta_generator: Optional[str] = None
    technologies: List[str] = field(default_factory=list)
    cookies: List[str] = field(default_factory=list)
    forms: int = 0
    external_links: int = 0
    js_files: List[str] = field(default_factory=list)
    email_addresses: List[str] = field(default_factory=list)
    phone_numbers: List[str] = field(default_factory=list)
    social_links: List[str] = field(default_factory=list)


@dataclass
class RiskScoreResult:
    """Aggregated risk score for the domain."""
    score: int = 0
    grade: str = "F"
    findings: List[Dict[str, str]] = field(default_factory=list)
    exposed_services: int = 0
    missing_security_headers: int = 0
    sensitive_paths_found: int = 0
    ssl_issues: int = 0
    dns_misconfigs: int = 0


# --------------------------------------------------------------------------- #
# Email / DNS Security Intelligence
# --------------------------------------------------------------------------- #
def _collect_email_security(domain: str, status: Dict[str, str]) -> EmailSecurityResult:
    """Analyze MX, DMARC, SPF, DKIM, and SMTP for email security posture."""
    result = EmailSecurityResult()

    # --- MX Records ---
    try:
        import dns.resolver
        for rr in dns.resolver.resolve(domain, "MX", lifetime=8):
            result.mx_records.append({
                "host": rr.exchange.to_text().rstrip("."),
                "priority": str(rr.preference),
            })
        status["email-mx"] = "ok" if result.mx_records else "no_mx"
    except Exception as e:
        status["email-mx"] = f"error: {type(e).__name__}"

    # --- DMARC ---
    try:
        import dns.resolver
        forrr = dns.resolver.resolve(f"_dmarc.{domain}", "TXT", lifetime=8)
        for rr in forrr:
            txt = rr.to_text().strip('"')
            if txt.lower().startswith("v=dmarc1"):
                result.dmarc_record = txt
                # Extract policy
                m = re.search(r";\s*p\s*=\s*(\w+)", txt, re.I)
                if m:
                    result.dmarc_policy = m.group(1).lower()
                break
        status["email-dmarc"] = "ok" if result.dmarc_record else "not_found"
    except dns.resolver.NXDOMAIN:
        result.dmarc_record = None
        status["email-dmarc"] = "not_found"
    except Exception as e:
        status["email-dmarc"] = f"error: {type(e).__name__}"

    # --- SPF ---
    try:
        import dns.resolver
        forrr = dns.resolver.resolve(domain, "TXT", lifetime=8)
        for rr in forrr:
            txt = rr.to_text().strip('"')
            if txt.lower().startswith("v=spf1"):
                result.spf_record = txt
                result.spf_valid = "all" in txt.lower()
                break
        status["email-spf"] = "ok" if result.spf_record else "not_found"
    except Exception as e:
        status["email-spf"] = f"error: {type(e).__name__}"

    # --- DKIM (common selectors) ---
    dkim_selectors = ["default", "google", "selector1", "selector2", "k1", "mandrill", "everlytickey1", "dkim", "mail"]
    found = []
    try:
        import dns.resolver
        for sel in dkim_selectors:
            try:
                forrr = dns.resolver.resolve(f"{sel}._domainkey.{domain}", "TXT", lifetime=3)
                for rr in forrr:
                    txt = rr.to_text()
                    if "p=" in txt.lower():
                        found.append(sel)
                        break
            except Exception:
                pass
    except Exception:
        pass
    result.dkim_selectors = dkim_selectors
    result.dkim_found = found
    status["email-dkim"] = f"{len(found)} found" if found else "none_found"

    # --- SMTP banner ---
    import socket
    import ssl
    try:
        sock = socket.create_connection((domain, 25), timeout=5)
        banner = sock.recv(512).decode("utf-8", "ignore").strip()
        result.smtp_banner = banner[:200]
        sock.close()
        status["email-smtp"] = "ok"
    except Exception as e:
        status["email-smtp"] = f"error: {type(e).__name__}"

    return result


# --------------------------------------------------------------------------- #
# WAF / CDN Detection
# --------------------------------------------------------------------------- #
_WAF_SIGNATURES = {
    "cloudflare": ["cf-ray", "cf-cache-status", "cloudflare"],
    "akamai": ["x-akamai-transformed", "akamai"],
    "aws-cloudfront": ["x-amz-cf-id", "x-amz-cf-pop", "cloudfront"],
    "fastly": ["x-fastly-request-id", "fastly"],
    "incapsula": ["x-iinfo", "incap_ses", "incapsula"],
    "sucuri": ["x-sucuri-id", "sucuri"],
    "barracuda": ["barra_counter_session", "barracuda"],
    "f5-bigip": ["bigip", "bigipdomain", "tsa_"],
    "imperva": ["imperva", "x-cdn"],
    "radware": ["radware", "rdwr"],
    "fortinet": ["fortigate", "fortiweb"],
    "modsecurity": ["mod_security", "modsecurity"],
    "wordfence": ["wordfence", "wf_"],
    "denyall": ["denyall", "sonarwall"],
}


def _collect_waf_cdn(domain: str, status: Dict[str, str]) -> WafCdnResult:
    """Detect WAF, CDN, server, and technology from HTTP headers."""
    result = WafCdnResult()
    try:
        r = requests.get(
            f"https://{domain}",
            headers=_USER_AGENT,
            timeout=10,
            verify=False,
            allow_redirects=True,
        )
        headers = {k.lower(): v for k, v in r.headers.items()}
        result.server = headers.get("server")
        result.powered_by = headers.get("x-powered-by")

        # WAF/CDN detection
        all_headers_text = " ".join(f"{k}: {v}" for k, v in headers.items()).lower()
        for name, sigs in _WAF_SIGNATURES.items():
            if any(s in all_headers_text for s in sigs):
                if name in ("cloudflare", "akamai", "aws-cloudfront", "fastly", "incapsula"):
                    result.cdn = name
                else:
                    result.waf = name
                break

        # Extract technologies from headers
        if result.server:
            result.technologies_from_headers.append(f"server:{result.server}")
        if result.powered_by:
            result.technologies_from_headers.append(f"powered-by:{result.powered_by}")
        if headers.get("x-aspnet-version"):
            result.technologies_from_headers.append(f"aspnet:{headers['x-aspnet-version']}")
        if headers.get("x-generator"):
            result.technologies_from_headers.append(f"generator:{headers['x-generator']}")

        status["waf-cdn"] = "ok"
    except Exception as e:
        status["waf-cdn"] = f"error: {type(e).__name__}"

    return result


# --------------------------------------------------------------------------- #
# Security Header Analysis
# --------------------------------------------------------------------------- #
def _collect_security_headers(domain: str, status: Dict[str, str]) -> SecurityHeadersResult:
    """Audit HTTP security headers and compute a score."""
    result = SecurityHeadersResult()
    try:
        r = requests.get(
            f"https://{domain}",
            headers=_USER_AGENT,
            timeout=10,
            verify=False,
            allow_redirects=True,
        )
        headers = {k.lower(): v for k, v in r.headers.items()}
        result.hsts = headers.get("strict-transport-security")
        result.csp = headers.get("content-security-policy")
        result.x_frame_options = headers.get("x-frame-options")
        result.x_content_type_options = headers.get("x-content-type-options")
        result.x_xss_protection = headers.get("x-xss-protection")
        result.referrer_policy = headers.get("referrer-policy")
        result.permissions_policy = headers.get("permissions-policy") or headers.get("x-permitted-cross-domain-policies")

        score = 0
        issues = []
        if result.hsts:
            score += 20
        else:
            issues.append("Missing HSTS header")
        if result.csp:
            score += 20
        else:
            issues.append("Missing Content-Security-Policy header")
        if result.x_frame_options:
            score += 15
        else:
            issues.append("Missing X-Frame-Options (clickjacking risk)")
        if result.x_content_type_options:
            score += 10
        else:
            issues.append("Missing X-Content-Type-Options")
        if result.referrer_policy:
            score += 10
        else:
            issues.append("Missing Referrer-Policy")
        if result.permissions_policy:
            score += 10
        else:
            issues.append("Missing Permissions-Policy")
        if result.x_xss_protection:
            score += 5
        else:
            issues.append("Missing X-XSS-Protection")

        # Bonus for good CSP
        if result.csp and "unsafe-inline" not in result.csp and "unsafe-eval" not in result.csp:
            score += 10
        elif result.csp:
            issues.append("CSP contains unsafe-inline or unsafe-eval")

        result.score = min(score, 100)
        result.issues = issues
        status["security-headers"] = f"score:{result.score}"
    except Exception as e:
        status["security-headers"] = f"error: {type(e).__name__}"

    return result


# --------------------------------------------------------------------------- #
# Sensitive Path Scanner
# --------------------------------------------------------------------------- #
_SENSITIVE_PATHS = [
    ("/.env", "Environment variables"),
    ("/.git/HEAD", "Git repository"),
    ("/.git/config", "Git config"),
    ("/.svn/entries", "SVN repository"),
    ("/.DS_Store", "macOS metadata"),
    ("/robots.txt", "Robots file"),
    ("/sitemap.xml", "Sitemap"),
    ("/.htaccess", "Apache config"),
    ("/web.config", "IIS config"),
    ("/wp-config.php.bak", "WordPress config backup"),
    ("/wp-login.php", "WordPress login"),
    ("/administrator/", "Admin panel"),
    ("/admin/", "Admin panel"),
    ("/phpmyadmin/", "phpMyAdmin"),
    ("/server-status", "Apache status"),
    ("/server-info", "Apache info"),
    ("/.well-known/security.txt", "Security contact"),
    ("/crossdomain.xml", "Cross-domain policy"),
    ("/clientaccesspolicy.xml", "Silverlight policy"),
    ("/elmah.axd", "ELMAH error log"),
    ("/trace.axd", "ASP.NET trace"),
    ("/config.php", "PHP config"),
    ("/database.yml", "Rails config"),
    ("/dump.sql", "SQL dump"),
    ("/backup.zip", "Backup archive"),
    ("/db.sql", "Database dump"),
    ("/debug/", "Debug endpoint"),
    ("/api/swagger.json", "Swagger API"),
    ("/api/docs", "API docs"),
    ("/graphql", "GraphQL endpoint"),
    ("/.aws/credentials", "AWS credentials"),
    ("/actuator", "Spring Boot Actuator"),
    ("/actuator/env", "Spring Boot env"),
    ("/console", "Debug console"),
    ("/.ssh/id_rsa", "SSH private key"),
]


def _collect_sensitive_paths(domain: str, status: Dict[str, str]) -> List[SensitivePathResult]:
    """Probe common sensitive paths and files."""
    found: List[SensitivePathResult] = []

    def _check(path: str, category: str) -> Optional[SensitivePathResult]:
        try:
            url = f"https://{domain}{path}"
            r = requests.get(url, headers=_USER_AGENT, timeout=5, verify=False, allow_redirects=False)
            if r.status_code in (200, 301, 302, 403) and r.status_code != 404:
                # Filter out generic error pages
                body = r.text[:500] if r.status_code == 200 else ""
                if r.status_code == 403 or (
                    len(body) > 10 and not re.search(r"(404|not found|page not found|does not exist)", body, re.I)
                ):
                    return SensitivePathResult(
                        path=path, status=r.status_code,
                        size=len(r.content), category=category,
                    )
        except Exception:
            pass
        return None

    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_check, p, c): p for p, c in _SENSITIVE_PATHS}
        for f in cf.as_completed(futures):
            try:
                result = f.result(timeout=8)
                if result:
                    found.append(result)
            except Exception:
                pass

    status["sensitive-paths"] = f"{len(found)} found" if found else "none"
    return found


# --------------------------------------------------------------------------- #
# Web Technology Fingerprinting
# --------------------------------------------------------------------------- #
_TECH_SIGNATURES = {
    # CMS
    "wordpress": [r"wp-content", r"wp-includes", r"wordpress"],
    "drupal": [r"drupal", r"sites/default/files"],
    "joomla": [r"joomla", r"/media/jui/"],
    "ghost": [r"ghost/", r"ghost-platform"],
    # Frameworks
    "react": [r"react", r"__NEXT_DATA__", r"_next/"],
    "nextjs": [r"__next", r"_next/static"],
    "vue.js": [r"vue\.js", r"vue\.min\.js", r"__vue__"],
    "angular": [r"ng-version", r"angular", r"ng-app"],
    "svelte": [r"svelte", r"__svelte"],
    "django": [r"csrfmiddlewaretoken", r"django"],
    "flask": [r"werkzeug"],
    "laravel": [r"laravel", r"laravel_session"],
    "rails": [r"csrf-token", r"ruby-on-rails"],
    "express": [r"express", r"x-powered-by: Express"],
    "aspnet": [r"asp\.net", r"__viewstate", r"__eventvalidation"],
    # JS Libraries
    "jquery": [r"jquery", r"jquery\.min\.js"],
    "bootstrap": [r"bootstrap\.min\.css", r"bootstrap\.min\.js"],
    "tailwindcss": [r"tailwindcss", r"tailwind\.min\.css"],
    "font-awesome": [r"font-awesome", r"fontawesome"],
    # Analytics
    "google-analytics": [r"google-analytics\.com/analytics", r"gtag", r"ga\("],
    "google-tag-manager": [r"googletagmanager\.com"],
    "hotjar": [r"hotjar\.com", r"hj\("],
    "mixpanel": [r"mixpanel\.com"],
    "segment": [r"segment\.com/analytics", r"analytics\.js"],
    # CDNs
    "cloudflare": [r"cloudflare", r"cf-ray"],
    "cloudfront": [r"cloudfront\.net"],
    "fastly": [r"fastly"],
    # E-commerce
    "shopify": [r"shopify", r"cdn\.shopify\.com"],
    "woocommerce": [r"woocommerce", r"wc-"],
    "magento": [r"magento", r"Mage\.Cookies"],
    # Others
    "google-fonts": [r"fonts\.googleapis\.com"],
    "stripe": [r"stripe\.com/js", r"Stripe\("],
    "recaptcha": [r"recaptcha", r"google\.com/recaptcha"],
    "hCaptcha": [r"hcaptcha", r"hcaptcha\.com"],
    "intercom": [r"intercom", r"intercomcdn"],
    "sentry": [r"sentry\.io", r"Sentry\.init"],
    "newrelic": [r"newrelic", r"nr-data\.net"],
    "datadog": [r"datadoghq", r"DD_RUM"],
}


def _collect_web_fingerprint(domain: str, status: Dict[str, str]) -> WebFingerprintResult:
    """Fingerprint technologies from the main page HTML."""
    result = WebFingerprintResult()
    try:
        r = requests.get(
            f"https://{domain}",
            headers=_USER_AGENT,
            timeout=10,
            verify=False,
            allow_redirects=True,
        )
        html = r.text[:100_000]  # Cap at 100KB

        # Title
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            result.title = m.group(1).strip()[:200]

        # Meta generator
        m = re.search(r'<meta[^>]*name=["\']generator["\'][^>]*content=["\'](.*?)["\']', html, re.I)
        if m:
            result.meta_generator = m.group(1).strip()[:100]

        # Technology detection
        for tech, patterns in _TECH_SIGNATURES.items():
            for pat in patterns:
                if re.search(pat, html, re.I):
                    result.technologies.append(tech)
                    break

        # Cookies
        result.cookies = list(r.cookies.keys())

        # Forms
        result.forms = len(re.findall(r"<form[\s>]", html, re.I))

        # External links
        result.external_links = len(re.findall(r'href=["\']https?://(?!.*' + re.escape(domain) + r')', html, re.I))

        # JS files
        js_matches = re.findall(r'src=["\']([^"\']*\.js(?:\?[^"\']*)?)["\']', html, re.I)
        result.js_files = [j for j in js_matches if not j.startswith("data:")][:20]

        # Email addresses in HTML
        emails = set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html))
        result.email_addresses = [e for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg"))][:20]

        # Phone numbers
        phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', html)
        result.phone_numbers = list(set(phones))[:10]

        # Social links
        social_patterns = [
            r'facebook\.com/[\w.-]+', r'twitter\.com/[\w.-]+', r'x\.com/[\w.-]+',
            r'linkedin\.com/(?:company|in)/[\w.-]+', r'instagram\.com/[\w.-]+',
            r'youtube\.com/(?:c/|@)[\w.-]+', r'github\.com/[\w.-]+',
        ]
        for pat in social_patterns:
            matches = re.findall(pat, html, re.I)
            result.social_links.extend(matches)
        result.social_links = list(set(result.social_links))[:10]

        status["web-fingerprint"] = f"{len(result.technologies)} techs"
    except Exception as e:
        status["web-fingerprint"] = f"error: {type(e).__name__}"

    return result


# --------------------------------------------------------------------------- #
# Reverse DNS Range Scan
# --------------------------------------------------------------------------- #
def _collect_reverse_dns_range(
    ips: List[str], domain: str, status: Dict[str, str],
) -> List[str]:
    """For each resolved IP, do a reverse DNS and check nearby IPs."""
    import socket
    extra: List[str] = []
    seen = set()

    for ip in ips[:5]:
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            hostname = hostname.strip().lower()
            if hostname not in seen and (hostname.endswith(domain) or domain in hostname):
                extra.append(hostname)
                seen.add(hostname)
        except Exception:
            pass

        # Scan /24 subnet for same-domain hostnames
        parts = ip.split(".")
        if len(parts) == 4:
            base = ".".join(parts[:3])
            for suffix in range(1, 255):
                candidate_ip = f"{base}.{suffix}"
                if candidate_ip == ip:
                    continue
                try:
                    h, _, _ = socket.gethostbyaddr(candidate_ip)
                    h = h.strip().lower()
                    if h not in seen and (h.endswith(domain) or domain in h):
                        extra.append(h)
                        seen.add(h)
                except Exception:
                    pass

    status["reverse-dns-range"] = f"{len(extra)} found" if extra else "none"
    return extra


# --------------------------------------------------------------------------- #
# Risk Scoring Engine
# --------------------------------------------------------------------------- #
def compute_risk_score(
    domain: str,
    emails: EmailSecurityResult,
    waf: WafCdnResult,
    sec_headers: SecurityHeadersResult,
    sensitive_paths: List[SensitivePathResult],
    web_fp: WebFingerprintResult,
    subdomains_count: int,
    ports_open: int,
    vulns_count: int,
    whois: Optional[dict],
    status: Dict[str, str],
) -> RiskScoreResult:
    """Compute a risk score (0–100, higher = riskier) for the domain."""
    result = RiskScoreResult()
    score = 0
    findings = []

    # --- Exposed services ---
    result.exposed_services = ports_open
    if ports_open > 5:
        score += 15
        findings.append({"severity": "high", "detail": f"{ports_open} exposed ports detected"})
    elif ports_open > 0:
        score += 5
        findings.append({"severity": "info", "detail": f"{ports_open} open ports detected"})

    # --- Vulnerabilities ---
    if vulns_count > 5:
        score += 25
        findings.append({"severity": "critical", "detail": f"{vulns_count} known vulnerabilities found"})
    elif vulns_count > 0:
        score += 15
        findings.append({"severity": "high", "detail": f"{vulns_count} known vulnerabilities found"})

    # --- Missing security headers ---
    missing = len(sec_headers.issues)
    result.missing_security_headers = missing
    if missing > 3:
        score += 15
        findings.append({"severity": "high", "detail": f"{missing} missing security headers"})
    elif missing > 0:
        score += 5
        findings.append({"severity": "medium", "detail": f"{missing} missing security headers"})

    # --- Sensitive paths ---
    result.sensitive_paths_found = len(sensitive_paths)
    high_severity = [p for p in sensitive_paths if p.status == 200 and p.category not in ("Robots file", "Sitemap", "Security contact")]
    if high_severity:
        score += 20
        findings.append({"severity": "critical", "detail": f"{len(high_severity)} sensitive paths accessible"})

    # --- Email security ---
    if not emails.dmarc_record:
        score += 5
        findings.append({"severity": "medium", "detail": "No DMARC record — email spoofing risk"})
    elif emails.dmarc_policy in ("none", None):
        score += 3
        findings.append({"severity": "low", "detail": "DMARC policy is 'none' — monitoring only"})
    if not emails.spf_record:
        score += 3
        findings.append({"severity": "medium", "detail": "No SPF record — email spoofing risk"})
    if not emails.dkim_found:
        score += 2
        findings.append({"severity": "low", "detail": "No DKIM records found"})

    # --- WAF / CDN ---
    if not waf.cdn and not waf.waf:
        score += 5
        findings.append({"severity": "low", "detail": "No WAF or CDN detected"})

    # --- SSL / TLS ---
    import ssl as _ssl
    import socket as _socket
    try:
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        with ctx.wrap_socket(_socket.socket(), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, 443))
            cert = s.getpeercert()
            # Check expiry
            import datetime
            not_after = cert.get("notAfter", "")
            if not_after:
                from email.utils import parsedate_to_datetime
                exp = parsedate_to_datetime(not_after)
                days_left = (exp - datetime.datetime.now(exp.tzinfo)).days
                if days_left < 30:
                    score += 10
                    findings.append({"severity": "high", "detail": f"SSL cert expires in {days_left} days"})
                elif days_left < 90:
                    score += 3
                    findings.append({"severity": "medium", "detail": f"SSL cert expires in {days_left} days"})
            # Check SANs
            san_names = []
            for typ, val in cert.get("subjectAltName", []):
                if typ == "DNS":
                    san_names.append(val)
            result.ssl_issues = 0
    except Exception:
        score += 5
        findings.append({"severity": "medium", "detail": "Could not verify SSL certificate"})
        result.ssl_issues = 1

    # --- DNS misconfigurations ---
    dns_issues = 0
    if not emails.mx_records:
        dns_issues += 1
    if not emails.spf_record:
        dns_issues += 1
    result.dns_misconfigs = dns_issues
    if dns_issues > 0:
        score += dns_issues * 2

    # --- Domain age (newer = riskier) ---
    if whois and whois.get("registration_date"):
        try:
            from datetime import datetime as _dt
            reg = _dt.fromisoformat(whois["registration_date"].replace("Z", "+00:00"))
            age_days = (_dt.now(reg.tzinfo) - reg).days
            if age_days < 90:
                score += 10
                findings.append({"severity": "medium", "detail": f"Domain registered {age_days} days ago — very new"})
            elif age_days < 365:
                score += 3
                findings.append({"severity": "low", "detail": f"Domain registered {age_days} days ago — relatively new"})
        except Exception:
            pass

    # Final score
    result.score = min(score, 100)
    result.findings = findings

    # Grade
    if score <= 15:
        result.grade = "A"
    elif score <= 30:
        result.grade = "B"
    elif score <= 50:
        result.grade = "C"
    elif score <= 70:
        result.grade = "D"
    else:
        result.grade = "F"

    status["risk-score"] = f"{result.score}/100 ({result.grade})"
    return result
