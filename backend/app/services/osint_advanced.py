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
    # SPF detail
    spf_all: Optional[str] = None          # "-all" | "~all" | "?all" | "+all" | None
    spf_lookups: Optional[int] = None      # DNS-lookup mechanisms in the top-level record (RFC 7208 limit: 10)
    spf_multiple: bool = False             # more than one v=spf1 record (invalid)
    # DMARC detail
    dmarc_subdomain_policy: Optional[str] = None
    dmarc_pct: Optional[int] = None
    dmarc_rua: List[str] = field(default_factory=list)
    # Transport security / branding
    mta_sts: Optional[str] = None
    tls_rpt: Optional[str] = None
    bimi: Optional[str] = None


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
DKIM_SELECTORS = [
    "default", "google", "selector1", "selector2", "k1", "k2", "k3", "s1", "s2",
    "mandrill", "mailjet", "everlytickey1", "everlytickey2", "dkim", "mail", "smtp",
    "mxvault", "zoho", "zmail", "pm", "protonmail", "protonmail2", "sendgrid", "smtpapi",
    "amazonses", "mailgun", "mta", "fm1", "fm2", "fm3", "turbo-smtp", "sig1", "cm",
]

_SPF_LOOKUP_RE = re.compile(r"(?:^|\s)[+~?-]?(include:|a\b|a:|a/|mx\b|mx:|mx/|ptr\b|ptr:|exists:|redirect=)", re.I)


def _txt_records(name: str) -> Optional[List[str]]:
    """TXT strings for ``name`` with split chunks joined; None when the name does not exist."""
    import dns.resolver

    try:
        ans = dns.resolver.resolve(name, "TXT", lifetime=6)
    except dns.resolver.NXDOMAIN:
        return None
    except Exception:
        return []
    out = []
    for rr in ans:
        chunks = getattr(rr, "strings", None)
        if chunks:
            out.append("".join(c.decode("utf-8", "ignore") if isinstance(c, bytes) else str(c) for c in chunks))
        else:
            parts = re.findall(r'"((?:[^"\\]|\\.)*)"', rr.to_text())
            out.append("".join(parts) if parts else rr.to_text())
    return out


def _tag(record: str, tag: str) -> Optional[str]:
    m = re.search(r"(?:^|;)\s*" + re.escape(tag) + r"\s*=\s*([^;]+)", record, re.I)
    return m.group(1).strip() if m else None


def _collect_email_security(domain: str, status: Dict[str, str]) -> EmailSecurityResult:
    """MX, SPF, DMARC, DKIM, MTA-STS, TLS-RPT and BIMI from public DNS (no connection to the target)."""
    import dns.resolver

    result = EmailSecurityResult()

    try:
        for rr in dns.resolver.resolve(domain, "MX", lifetime=8):
            result.mx_records.append({"host": rr.exchange.to_text().rstrip("."), "priority": str(rr.preference)})
        status["email-mx"] = "ok" if result.mx_records else "no_mx"
    except Exception:
        status["email-mx"] = "no_mx"

    spf = [t for t in (_txt_records(domain) or []) if t.lower().startswith("v=spf1")]
    if spf:
        rec = spf[0]
        result.spf_record = rec
        result.spf_multiple = len(spf) > 1
        m = re.search(r"(?:^|\s)([+~?-]?)all\b", rec, re.I)
        result.spf_all = ((m.group(1) or "+") + "all") if m else None
        result.spf_valid = bool(m) and not result.spf_multiple
        result.spf_lookups = len(_SPF_LOOKUP_RE.findall(rec))
    status["email-spf"] = "ok" if spf else "not_found"

    dmarc = [t for t in (_txt_records(f"_dmarc.{domain}") or []) if t.lower().startswith("v=dmarc1")]
    if dmarc:
        rec = dmarc[0]
        result.dmarc_record = rec
        p = _tag(rec, "p")
        result.dmarc_policy = p.lower() if p else None
        sp = _tag(rec, "sp")
        result.dmarc_subdomain_policy = sp.lower() if sp else None
        pct = _tag(rec, "pct")
        try:
            result.dmarc_pct = int(pct) if pct is not None else 100
        except ValueError:
            result.dmarc_pct = None
        rua = _tag(rec, "rua")
        result.dmarc_rua = [u.strip() for u in rua.split(",")] if rua else []
    status["email-dmarc"] = "ok" if dmarc else "not_found"

    def _dkim(sel: str) -> Optional[str]:
        recs = _txt_records(f"{sel}._domainkey.{domain}") or []
        return sel if any("p=" in r.lower() for r in recs) else None

    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        found = [s for s in ex.map(_dkim, DKIM_SELECTORS) if s]
    result.dkim_selectors = list(DKIM_SELECTORS)
    result.dkim_found = found
    status["email-dkim"] = f"{len(found)} found" if found else "none_found"

    for attr, name, prefix in (("mta_sts", f"_mta-sts.{domain}", "v=stsv1"),
                               ("tls_rpt", f"_smtp._tls.{domain}", "v=tlsrptv1"),
                               ("bimi", f"default._bimi.{domain}", "v=bimi1")):
        recs = [t for t in (_txt_records(name) or []) if t.lower().replace(" ", "").startswith(prefix)]
        setattr(result, attr, recs[0] if recs else None)

    return result
