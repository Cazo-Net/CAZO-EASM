"""OSINT result types and email security (DMARC, SPF, DKIM, MX) from public DNS.

The live web checks that used to live here (HTTP headers, sensitive paths,
page fingerprinting, SMTP banner) contacted the target and were removed: the
OSINT lookup is passive, and those checks are the scan engines' job. Their
result types stay so the API shape is stable (they are now always empty).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("osint.advanced")


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
    """Analyze MX, DMARC, SPF and DKIM from public DNS (no connection to the target)."""
    result = EmailSecurityResult()

    # --- MX Records ---
    try:
        import dns.resolver
        for rr in dns.resolver.resolve(domain, "MX", lifetime=15):
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
        forrr = dns.resolver.resolve(f"_dmarc.{domain}", "TXT", lifetime=15)
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
        forrr = dns.resolver.resolve(domain, "TXT", lifetime=15)
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
                forrr = dns.resolver.resolve(f"{sel}._domainkey.{domain}", "TXT", lifetime=5)
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

    return result
