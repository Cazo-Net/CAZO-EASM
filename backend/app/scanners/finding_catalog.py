"""One vocabulary for findings, shared by both scan engines.

The standard engine and Scanner v2 grew separate checkers that report the
same issue under different ids, titles and severities. A missing HSTS header
was ``hdr/missing-hsts`` (medium) in one engine and
``headers/missing-hsts`` in the other; a missing CSP was medium in one and
low in the other. Across scans and engines that read as different issues and
made scores disagree.

``polish_findings`` gives every known issue:

* one stable ``template_id`` (so the same issue de-duplicates across scans
  and engines),
* one title and severity, with the reason for the severity in the catalog,
* a remediation step and references (CWE / vendor docs),

and then merges findings that describe the same issue at the same place,
keeping the highest severity, every source and all evidence.

Unknown findings pass through untouched apart from the merge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit

_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5}


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    title: str
    severity: str
    category: str
    remediation: str
    why: str  # why this severity (kept here so reviewers can argue with it)
    aliases: Tuple[str, ...] = ()
    references: Tuple[str, ...] = ()
    cwe: Optional[str] = None
    per_host: bool = True  # one finding per host, whatever URL it was seen on
    tags: Tuple[str, ...] = field(default_factory=tuple)


_MDN = "https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/"

CATALOG: List[CatalogEntry] = [
    CatalogEntry(
        "header/missing-hsts", "HSTS header missing", "medium", "security_headers",
        "Send Strict-Transport-Security: max-age=31536000; includeSubDomains on every HTTPS response.",
        "Without HSTS a network attacker can downgrade the first visit to plain HTTP.",
        aliases=("hdr/missing-hsts", "headers/missing-hsts",
                 "exposure-validation/security_headers/strict-transport-security"),
        references=(_MDN + "Strict-Transport-Security",), cwe="CWE-319",
    ),
    CatalogEntry(
        "header/missing-csp", "Content-Security-Policy header missing", "low", "security_headers",
        "Define a Content-Security-Policy that limits script sources (start in report-only mode).",
        "Not exploitable on its own; it removes a layer of defence against XSS.",
        aliases=("hdr/missing-csp", "headers/missing-csp",
                 "exposure-validation/security_headers/content-security-policy"),
        references=(_MDN + "Content-Security-Policy",), cwe="CWE-1021",
    ),
    CatalogEntry(
        "header/missing-clickjacking-protection", "No clickjacking protection", "low", "security_headers",
        "Send X-Frame-Options: DENY (or SAMEORIGIN), or CSP frame-ancestors 'none'.",
        "Pages can be framed by other sites; matters most for pages with state-changing buttons.",
        aliases=("hdr/missing-xfo", "headers/missing-clickjacking-protection",
                 "exposure-validation/security_headers/x-frame-options"),
        references=(_MDN + "X-Frame-Options",), cwe="CWE-1021",
    ),
    CatalogEntry(
        "header/missing-xcto", "X-Content-Type-Options header missing", "low", "security_headers",
        "Send X-Content-Type-Options: nosniff.",
        "Browsers may MIME-sniff uploaded or user-controlled content into script.",
        aliases=("hdr/missing-xcto", "headers/missing-xcto",
                 "exposure-validation/security_headers/x-content-type-options"),
        references=(_MDN + "X-Content-Type-Options",), cwe="CWE-430",
    ),
    CatalogEntry(
        "header/missing-referrer-policy", "Referrer-Policy header missing", "info", "security_headers",
        "Send Referrer-Policy: strict-origin-when-cross-origin (or stricter).",
        "Modern browsers already default to strict-origin-when-cross-origin.",
        aliases=("hdr/missing-referrer", "headers/missing-referrer-policy",
                 "exposure-validation/security_headers/referrer-policy"),
        references=(_MDN + "Referrer-Policy",),
    ),
    CatalogEntry(
        "header/missing-permissions-policy", "Permissions-Policy header missing", "info", "security_headers",
        "Send a Permissions-Policy that disables browser features the site does not use.",
        "Hardening only; nothing is exposed by its absence.",
        aliases=("hdr/missing-permissions", "headers/missing-permissions-policy",
                 "exposure-validation/security_headers/permissions-policy"),
        references=(_MDN + "Permissions-Policy",),
    ),
    CatalogEntry(
        "header/version-disclosure", "Software version disclosed in headers", "low", "information_disclosure",
        "Remove version numbers from Server and X-Powered-By headers (e.g. nginx server_tokens off).",
        "Helps attackers pick exploits; the real risk is the outdated software itself.",
        aliases=("headers/version-disclosure", "exposure-validation/info_disclosure/server",
                 "exposure-validation/info_disclosure/x-powered-by"),
        cwe="CWE-200",
    ),
    CatalogEntry(
        "dns/subdomain-takeover", "Subdomain takeover possible", "", "subdomain_takeover",
        "Delete the DNS record that points at the unclaimed service, or claim the resource there.",
        "Severity depends on the service (kept from the check): an attacker can serve pages on your domain.",
        aliases=("exposure-validation/subdomain_takeover",),
        references=("https://github.com/EdOverflow/can-i-take-over-xyz",), cwe="CWE-350",
    ),
    CatalogEntry(
        "email/missing-dmarc", "No DMARC policy", "medium", "email_security",
        "Publish a DMARC record (start with p=none and rua reporting, then move to quarantine/reject).",
        "Anyone can send mail that claims to come from this domain and receivers get no policy.",
        aliases=("dns/missing-dmarc",), references=("https://dmarc.org/overview/",), cwe="CWE-290",
    ),
    CatalogEntry(
        "email/missing-spf", "No SPF record", "medium", "email_security",
        "Publish an SPF TXT record listing the servers allowed to send mail for the domain, ending in -all or ~all.",
        "Without SPF, receivers cannot tell which servers may send this domain's mail.",
        aliases=("dns/missing-spf",), cwe="CWE-290",
    ),
    CatalogEntry(
        "email/no-dkim-at-common-selectors", "No DKIM key found at common selectors", "info", "email_security",
        "If the domain sends mail, sign it with DKIM and publish the key; check your mail provider's selector.",
        "DKIM selectors are arbitrary names, so not finding one at common names is not proof it is missing.",
        aliases=("dns/missing-dkim",),
    ),
]

_BY_ALIAS: Dict[str, CatalogEntry] = {}
for _e in CATALOG:
    _BY_ALIAS[_e.id] = _e
    for _a in _e.aliases:
        _BY_ALIAS[_a] = _e


def lookup(template_id: str) -> Optional[CatalogEntry]:
    return _BY_ALIAS.get(template_id or "")


def _location(f: Dict[str, Any], per_host: bool) -> str:
    """Where a finding is, for de-duplication: the host, or host + path."""
    host = (f.get("host") or "").lower()
    if per_host:
        return host
    at = str(f.get("matched_at") or "")
    if at.startswith("http"):
        parts = urlsplit(at)
        return f"{(parts.hostname or host).lower()}{parts.path.rstrip('/') or '/'}"
    return at.lower().rstrip("/") or host


def _as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def apply_catalog(f: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``f`` in the catalog's words (unchanged if unknown)."""
    entry = lookup(f.get("template_id", ""))
    out = dict(f)
    if entry is None:
        return out
    original_id = f.get("template_id")
    out["template_id"] = entry.id
    out["name"] = entry.title
    if entry.severity:
        out["severity"] = entry.severity
    out["vuln_type"] = entry.category
    out["remediation"] = entry.remediation
    desc = (f.get("description") or "").strip()
    if entry.severity:
        # Catalog-owned wording: what was seen, why it matters, how to fix.
        # (Entries without a fixed severity, like takeovers, keep the
        # check's own, more specific text.)
        seen = desc.split(" Fix: ")[0].strip()
        if not seen or seen == f.get("name"):
            seen = f"{entry.title} on {f.get('host') or 'this host'}."
        if not seen.endswith((".", "!", "?")):
            seen += "."
        desc = f"{seen} Why it matters: {entry.why} Fix: {entry.remediation}"
    elif "Fix:" not in desc:
        desc = f"{desc} Fix: {entry.remediation}".strip()
    out["description"] = desc
    refs = _as_list(f.get("reference"))
    out["reference"] = list(dict.fromkeys([*refs, *entry.references]))
    tags = [t for t in _as_list(f.get("tags")) if isinstance(t, str)]
    extra = [entry.category] + ([entry.cwe] if entry.cwe else []) + list(entry.tags)
    out["tags"] = list(dict.fromkeys([*tags, *extra]))
    if original_id and original_id != entry.id:
        out.setdefault("aliases", [])
        out["aliases"] = list(dict.fromkeys([*out["aliases"], original_id]))
    return out


def merge_duplicates(findings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge findings for the same issue at the same place.

    The most severe copy wins; sources, tags, references and evidence from
    the others are kept on it.
    """
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    order: List[Tuple[str, str]] = []
    ranked = sorted(
        (f for f in findings if isinstance(f, dict)),
        key=lambda f: _SEV_RANK.get(str(f.get("severity", "unknown")).lower(), 9),
    )
    for f in ranked:
        entry = lookup(f.get("template_id", ""))
        key = (f.get("template_id") or f.get("name") or "", _location(f, entry.per_host if entry else False))
        cur = merged.get(key)
        if cur is None:
            g = dict(f)
            src = g.get("source")
            g["sources"] = [src] if src else []
            merged[key] = g
            order.append(key)
            continue
        src = f.get("source")
        if src and src not in cur["sources"]:
            cur["sources"].append(src)
        for k in ("tags", "reference", "extracted_results"):
            vals = [*_as_list(cur.get(k)), *_as_list(f.get(k))]
            seen: List[Any] = []
            for v in vals:
                if v not in seen:
                    seen.append(v)
            cur[k] = seen
    out = [merged[k] for k in order]
    for g in out:
        if g["sources"]:
            g["tags"] = list(dict.fromkeys([*_as_list(g.get("tags")), *(f"found-by:{s}" for s in g["sources"])]))
    return out


def polish_findings(findings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Catalog wording + merge duplicates, most severe first."""
    return merge_duplicates(apply_catalog(f) for f in findings if isinstance(f, dict))
