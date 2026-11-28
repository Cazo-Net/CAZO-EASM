"""Dark web & threat-intelligence collection from real, named sources.

Rules this module keeps:

* Every result comes from a real source and carries that source's name and a
  reference link. Nothing is generated, guessed or "filled in" when a source
  has no data or is not configured.
* A source that needs a key or subscription the operator has not supplied
  reports ``not_configured``; the UI shows that state instead of results.
* Lookups are only run for domains, and addresses on domains, that are in
  the organization's authorized scope (see :func:`authorize_monitor_value`).
  Breach data is about people, so this is not optional, even when scan scope
  enforcement is ``open``.

Sources:

=====================  ==========  ==============================================
id                     needs       gives
=====================  ==========  ==============================================
hibp_breaches          nothing     breaches of the monitored site itself (HIBP)
hibp_domain_search     HIBP key    addresses on the domain found in breaches
hibp_accounts          HIBP key    breaches containing one monitored address
urlhaus                abuse.ch    malware URLs hosted on the domain
threatfox              abuse.ch    malware IOCs (C2 etc.) that involve the domain
lookalike_dns          nothing     registered look-alike domains (live DNS)
cisa_kev               nothing     known exploited vulnerabilities catalog
first_epss             nothing     exploit-likelihood scores for CVEs
=====================  ==========  ==============================================
"""
from __future__ import annotations

import hashlib
import html
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

HIBP_BASE = "https://haveibeenpwned.com/api/v3"
URLHAUS_HOST_URL = "https://urlhaus-api.abuse.ch/v1/host/"
THREATFOX_URL = "https://threatfox-api.abuse.ch/api/v1/"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss"

USER_AGENT = "CAZO-EASM-ThreatIntel/1.0"
HTTP_TIMEOUT = 20.0
MAX_MONITORS_PER_ORG = 100
MAX_FINDINGS_PER_SOURCE = 50

_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@([A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+)$")
_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


# ── Source catalogue ───────────────────────────────────────────────────


def _hibp_key() -> str:
    return (getattr(settings, "HIBP_API_KEY", "") or "").strip()


def _abusech_key() -> str:
    return (getattr(settings, "ABUSECH_AUTH_KEY", "") or "").strip()


def source_catalog() -> List[Dict[str, Any]]:
    """Every source the page can show, and whether it is usable right now."""
    hibp = bool(_hibp_key())
    abusech = bool(_abusech_key())
    return [
        {
            "id": "hibp_breaches", "name": "Have I Been Pwned — breached sites",
            "provides": "Public breaches of your own websites (was this domain itself breached?)",
            "requires": "nothing", "configured": True,
            "url": "https://haveibeenpwned.com/PwnedWebsites",
        },
        {
            "id": "hibp_domain_search", "name": "Have I Been Pwned — domain search",
            "provides": "Which addresses on your domain appear in known breaches",
            "requires": "HIBP_API_KEY (paid HIBP subscription) and the domain verified in your HIBP dashboard",
            "configured": hibp, "env": "HIBP_API_KEY",
            "url": "https://haveibeenpwned.com/API/Key",
        },
        {
            "id": "hibp_accounts", "name": "Have I Been Pwned — monitored addresses",
            "provides": "Breaches that contain a specific address you monitor",
            "requires": "HIBP_API_KEY (paid HIBP subscription)",
            "configured": hibp, "env": "HIBP_API_KEY",
            "url": "https://haveibeenpwned.com/API/Key",
        },
        {
            "id": "urlhaus", "name": "abuse.ch URLhaus",
            "provides": "Malware distribution URLs reported on your domains",
            "requires": "ABUSECH_AUTH_KEY (free abuse.ch account)",
            "configured": abusech, "env": "ABUSECH_AUTH_KEY",
            "url": "https://auth.abuse.ch/",
        },
        {
            "id": "threatfox", "name": "abuse.ch ThreatFox",
            "provides": "Malware indicators (C2 servers, payload hosts) involving your domains",
            "requires": "ABUSECH_AUTH_KEY (free abuse.ch account)",
            "configured": abusech, "env": "ABUSECH_AUTH_KEY",
            "url": "https://auth.abuse.ch/",
        },
        {
            "id": "lookalike_dns", "name": "Look-alike domain watch",
            "provides": "Typo-squat and look-alike domains that are registered right now (live DNS)",
            "requires": "nothing", "configured": True,
        },
        {
            "id": "cisa_kev", "name": "CISA Known Exploited Vulnerabilities",
            "provides": "Vulnerabilities confirmed as exploited in the wild",
            "requires": "nothing", "configured": True,
            "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        },
        {
            "id": "first_epss", "name": "FIRST EPSS",
            "provides": "Probability that a CVE is exploited in the next 30 days",
            "requires": "nothing", "configured": True,
            "url": "https://www.first.org/epss/",
        },
        {
            "id": "darkweb_forums", "name": "Dark web forums, markets & ransomware leak sites",
            "provides": "Mentions of your brand, domains or staff on criminal forums and leak sites",
            "requires": "A commercial dark web intelligence subscription (for example Flare, SpyCloud, "
                        "Recorded Future, DarkOwl). Not integrated yet.",
            "configured": False, "commercial": True,
        },
        {
            "id": "stealer_logs", "name": "Infostealer logs & paste sites",
            "provides": "Credentials for your domains captured by infostealer malware or posted to paste sites",
            "requires": "A commercial provider subscription. Not integrated yet.",
            "configured": False, "commercial": True,
        },
    ]


# ── HTTP (one place, so tests can replace it) ─────────────────────────


@dataclass
class HttpResult:
    status: int
    data: Any = None
    headers: Dict[str, str] = field(default_factory=dict)


def http_request(method: str, url: str, *, headers: Optional[dict] = None, params: Optional[dict] = None,
                 data: Optional[dict] = None, json_body: Optional[dict] = None,
                 timeout: float = HTTP_TIMEOUT) -> HttpResult:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    hdrs.update(headers or {})
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.request(method, url, headers=hdrs, params=params, data=data, json=json_body)
    try:
        body = r.json() if r.content else None
    except ValueError:
        body = None
    return HttpResult(r.status_code, body, dict(r.headers))


def _status_for(code: int) -> str:
    return {
        401: "invalid_key",
        403: "forbidden",
        429: "rate_limited",
    }.get(code, f"http_{code}")


# ── Findings ───────────────────────────────────────────────────────────


@dataclass
class Finding:
    source: str
    category: str
    subject: str
    title: str
    key: str  # stable identity within (source, category, subject)
    severity: str = "medium"
    summary: str = ""
    reference_url: Optional[str] = None
    observed_at: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        raw = "|".join([self.source, self.category, self.subject.lower(), self.key.lower()])
        return hashlib.sha256(raw.encode()).hexdigest()


def _clean_html(text: str, limit: int = 600) -> str:
    text = html.unescape(_TAG_RE.sub("", text or "")).strip()
    return text[:limit]


def _breach_severity(breach: dict) -> str:
    if breach.get("IsFabricated") or breach.get("IsSpamList"):
        return "low"
    classes = {c.lower() for c in breach.get("DataClasses") or []}
    if "passwords" in classes or "auth tokens" in classes:
        return "high"
    return "medium"


def _breach_data(breach: dict) -> Dict[str, Any]:
    return {
        "breach_name": breach.get("Name"),
        "breach_title": breach.get("Title"),
        "breached_site": breach.get("Domain"),
        "breach_date": breach.get("BreachDate"),
        "added_to_hibp": breach.get("AddedDate"),
        "accounts_in_breach": breach.get("PwnCount"),
        "data_classes": breach.get("DataClasses") or [],
        "is_verified": breach.get("IsVerified"),
        "is_fabricated": breach.get("IsFabricated"),
        "is_spam_list": breach.get("IsSpamList"),
        "is_stealer_log": breach.get("IsStealerLog"),
    }


def _hibp_ref(name: str) -> str:
    return f"https://haveibeenpwned.com/PwnedWebsites#{quote(name or '')}"


def _hibp_headers() -> dict:
    return {"hibp-api-key": _hibp_key()}


# ── Individual source checks. Each returns (findings, status). ─────────


_breach_catalog_cache: Tuple[float, Dict[str, dict]] = (0.0, {})
_cache_lock = threading.Lock()


def _hibp_breach_catalog() -> Dict[str, dict]:
    """All breaches HIBP knows about (public endpoint), cached for 6 hours."""
    global _breach_catalog_cache
    with _cache_lock:
        ts, cat = _breach_catalog_cache
        if cat and time.time() - ts < 6 * 3600:
            return cat
    r = http_request("GET", f"{HIBP_BASE}/breaches")
    if r.status != 200 or not isinstance(r.data, list):
        return cat
    cat = {b.get("Name"): b for b in r.data if b.get("Name")}
    with _cache_lock:
        _breach_catalog_cache = (time.time(), cat)
    return cat


def check_hibp_site_breaches(domain: str) -> Tuple[List[Finding], str]:
    r = http_request("GET", f"{HIBP_BASE}/breaches", params={"domain": domain})
    if r.status != 200:
        return [], _status_for(r.status)
    out = []
    for b in (r.data or [])[:MAX_FINDINGS_PER_SOURCE]:
        name = b.get("Name") or ""
        out.append(Finding(
            source="hibp", category="breach_site", subject=domain, key=name,
            title=f"{b.get('Title') or name} was breached ({b.get('BreachDate') or 'date unknown'})",
            summary=_clean_html(b.get("Description", "")),
            severity=_breach_severity(b), reference_url=_hibp_ref(name),
            observed_at=b.get("BreachDate"), data=_breach_data(b),
        ))
    return out, "ok"


def check_hibp_domain_search(domain: str) -> Tuple[List[Finding], str]:
    if not _hibp_key():
        return [], "not_configured"
    r = http_request("GET", f"{HIBP_BASE}/breacheddomain/{quote(domain)}", headers=_hibp_headers())
    if r.status == 404:
        return [], "ok"
    if r.status == 403:
        return [], "domain_not_verified_in_hibp"
    if r.status != 200 or not isinstance(r.data, dict):
        return [], _status_for(r.status)
    by_breach: Dict[str, List[str]] = {}
    for alias, breaches in r.data.items():
        for name in breaches or []:
            by_breach.setdefault(name, []).append(f"{alias}@{domain}")
    catalog = _hibp_breach_catalog() if by_breach else {}
    out = []
    for name, addrs in sorted(by_breach.items(), key=lambda kv: -len(kv[1]))[:MAX_FINDINGS_PER_SOURCE]:
        b = catalog.get(name, {"Name": name, "Title": name})
        out.append(Finding(
            source="hibp", category="breach_domain", subject=domain, key=name,
            title=f"{len(addrs)} address(es) at {domain} found in the {b.get('Title') or name} breach",
            summary=_clean_html(b.get("Description", "")),
            severity=_breach_severity(b), reference_url=_hibp_ref(name),
            observed_at=b.get("BreachDate"),
            data={**_breach_data(b), "affected_addresses": sorted(addrs)[:500],
                  "affected_count": len(addrs)},
        ))
    return out, "ok"


def check_hibp_account(email: str) -> Tuple[List[Finding], str]:
    if not _hibp_key():
        return [], "not_configured"
    r = http_request(
        "GET", f"{HIBP_BASE}/breachedaccount/{quote(email)}",
        headers=_hibp_headers(), params={"truncateResponse": "false"},
    )
    if r.status == 404:
        return [], "ok"
    if r.status != 200:
        return [], _status_for(r.status)
    out = []
    for b in (r.data or [])[:MAX_FINDINGS_PER_SOURCE]:
        name = b.get("Name") or ""
        out.append(Finding(
            source="hibp", category="breach_account", subject=email, key=name,
            title=f"{email} appears in the {b.get('Title') or name} breach",
            summary=_clean_html(b.get("Description", "")),
            severity=_breach_severity(b), reference_url=_hibp_ref(name),
            observed_at=b.get("BreachDate"), data=_breach_data(b),
        ))
    return out, "ok"


def _host_matches(host: str, domain: str) -> bool:
    host = (host or "").lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def check_urlhaus(domain: str) -> Tuple[List[Finding], str]:
    if not _abusech_key():
        return [], "not_configured"
    r = http_request("POST", URLHAUS_HOST_URL, headers={"Auth-Key": _abusech_key()}, data={"host": domain})
    if r.status != 200 or not isinstance(r.data, dict):
        return [], _status_for(r.status)
    qs = r.data.get("query_status")
    if qs in ("no_results", "invalid_host"):
        return [], "ok"
    if qs != "ok":
        return [], f"error: {qs}"
    out = []
    for u in (r.data.get("urls") or [])[:MAX_FINDINGS_PER_SOURCE]:
        online = u.get("url_status") == "online"
        out.append(Finding(
            source="urlhaus", category="malware_url", subject=domain, key=u.get("url") or "",
            title=f"{'Live' if online else 'Reported'} malware URL on {domain}: {u.get('url')}",
            summary=f"Threat: {u.get('threat') or 'unknown'}. Status: {u.get('url_status') or 'unknown'}.",
            severity="critical" if online else "medium",
            reference_url=u.get("urlhaus_reference"), observed_at=u.get("date_added"),
            data={"url": u.get("url"), "url_status": u.get("url_status"), "threat": u.get("threat"),
                  "tags": u.get("tags") or []},
        ))
    listed = {k: v for k, v in (r.data.get("blacklists") or {}).items() if v and v != "not listed"}
    if listed:
        out.append(Finding(
            source="urlhaus", category="blocklist", subject=domain, key="blocklists",
            title=f"{domain} is on a domain blocklist", severity="high",
            summary="Listed on: " + ", ".join(f"{k} ({v})" for k, v in listed.items()),
            reference_url=r.data.get("urlhaus_reference"), data={"blocklists": listed},
        ))
    return out, "ok"


def check_threatfox(domain: str) -> Tuple[List[Finding], str]:
    if not _abusech_key():
        return [], "not_configured"
    r = http_request("POST", THREATFOX_URL, headers={"Auth-Key": _abusech_key()},
                     json_body={"query": "search_ioc", "search_term": domain})
    if r.status != 200 or not isinstance(r.data, dict):
        return [], _status_for(r.status)
    qs = r.data.get("query_status")
    if qs in ("no_result", "no_results"):
        return [], "ok"
    if qs != "ok":
        return [], f"error: {qs}"
    out = []
    for ioc in r.data.get("data") or []:
        value = str(ioc.get("ioc") or "")
        host = re.sub(r"^[a-z]+://", "", value).split("/")[0].split(":")[0]
        if not _host_matches(host, domain):
            continue  # ThreatFox search is a substring match; keep only real matches
        out.append(Finding(
            source="threatfox", category="threat_ioc", subject=domain, key=str(ioc.get("id") or value),
            title=f"{ioc.get('malware_printable') or 'Malware'} indicator involving {domain}: {value}",
            summary=f"{ioc.get('threat_type_desc') or ioc.get('threat_type') or ''} "
                    f"(confidence {ioc.get('confidence_level', '?')}%)".strip(),
            severity="high",
            reference_url=f"https://threatfox.abuse.ch/ioc/{ioc.get('id')}/" if ioc.get("id") else None,
            observed_at=ioc.get("first_seen"),
            data={"ioc": value, "ioc_type": ioc.get("ioc_type"), "threat_type": ioc.get("threat_type"),
                  "malware": ioc.get("malware_printable"), "tags": ioc.get("tags") or []},
        ))
        if len(out) >= MAX_FINDINGS_PER_SOURCE:
            break
    return out, "ok"


# ── Look-alike domains ─────────────────────────────────────────────────

_HOMOGLYPHS = {"o": "0", "0": "o", "l": "1", "1": "l", "i": "1", "e": "3", "a": "4", "s": "5", "m": "rn"}
_ALT_TLDS = ["com", "net", "org", "co", "io", "info", "biz", "online", "site", "app"]


def lookalike_candidates(domain: str, limit: int = 120) -> List[Tuple[str, str]]:
    """(candidate, technique) pairs for a registrable domain like ``acme.com``."""
    parts = domain.split(".")
    if len(parts) < 2:
        return []
    name, tld = parts[0], ".".join(parts[1:])
    out: Dict[str, str] = {}

    def add(n: str, t: str, technique: str) -> None:
        if not n or n.startswith("-") or n.endswith("-") or len(n) > 63:
            return
        cand = f"{n}.{t}"
        if cand != domain and cand not in out:
            out[cand] = technique

    for i in range(len(name)):
        add(name[:i] + name[i + 1:], tld, "omission")
        add(name[:i] + name[i] + name[i:], tld, "repetition")
        if name[i] in _HOMOGLYPHS:
            add(name[:i] + _HOMOGLYPHS[name[i]] + name[i + 1:], tld, "homoglyph")
    for i in range(len(name) - 1):
        add(name[:i] + name[i + 1] + name[i] + name[i + 2:], tld, "transposition")
    for i in range(1, len(name)):
        add(name[:i] + "-" + name[i:], tld, "hyphenation")
    for t in _ALT_TLDS:
        if t != tld:
            add(name, t, "tld-swap")
    for word in ("login", "secure", "support", "account", "verify"):
        add(f"{name}-{word}", tld, "keyword")
        add(f"{word}-{name}", tld, "keyword")
    return list(out.items())[:limit]


def _resolve(name: str, rtype: str) -> Optional[List[str]]:
    """Answers for ``name``; [] when it exists without that record; None for NXDOMAIN."""
    import dns.exception
    import dns.resolver

    try:
        ans = dns.resolver.resolve(name, rtype, lifetime=4)
        return [a.to_text().rstrip(".") for a in ans]
    except dns.resolver.NXDOMAIN:
        return None
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    except Exception:  # noqa: BLE001
        return []


def check_lookalikes(domain: str, own_domains: Iterable[str] = ()) -> Tuple[List[Finding], str]:
    own = {d.lower() for d in own_domains}
    cands = [(c, t) for c, t in lookalike_candidates(domain) if c not in own]

    def probe(item):
        cand, technique = item
        a = _resolve(cand, "A")
        if a is None:
            return None
        mx = _resolve(cand, "MX")
        if not a and not mx:
            ns = _resolve(cand, "NS")
            if not ns:
                return None
        return cand, technique, a or [], mx or []

    with ThreadPoolExecutor(max_workers=16) as pool:
        hits = [h for h in pool.map(probe, cands) if h]
    out = []
    for cand, technique, ips, mx in hits[:MAX_FINDINGS_PER_SOURCE]:
        out.append(Finding(
            source="dns", category="lookalike_domain", subject=domain, key=cand,
            title=f"Look-alike domain is registered: {cand}",
            summary=("It can receive email (has MX records), so it could be used for phishing. "
                     if mx else "") + f"Technique: {technique}. Registered does not mean malicious; review it.",
            severity="medium" if mx else "low",
            reference_url=f"https://crt.sh/?q={quote(cand)}",
            data={"lookalike": cand, "technique": technique, "a_records": ips[:10], "mx_records": mx[:10]},
        ))
    return out, "ok"


# ── Scope ──────────────────────────────────────────────────────────────


def normalize_monitor_value(kind: str, raw: str) -> Tuple[Optional[str], Optional[str], str]:
    """Return (value, domain, error)."""
    from app.core.scope import is_valid_scope_value

    raw = (raw or "").strip().lower().rstrip(".")
    if kind == "email":
        m = _EMAIL_RE.match(raw)
        if not m:
            return None, None, "That is not a valid email address."
        domain = m.group(1)
    elif kind == "domain":
        raw = re.sub(r"^[a-z]+://", "", raw).split("/")[0]
        domain = raw
    else:
        return None, None, "Monitor type must be 'domain' or 'email'."
    if not is_valid_scope_value("domain", domain):
        return None, None, "That is not a valid domain."
    return raw, domain, ""


def authorize_monitor_value(db: Session, organization_id: Optional[str], kind: str, raw: str) -> Tuple[bool, str, str]:
    """(allowed, normalized_value, reason). Requires an authorized scope in every mode."""
    from app.core.scope import _target_matches_scope, get_scopes_for_org, scope_mode

    if not organization_id:
        return False, "", "You must belong to an organization."
    value, domain, err = normalize_monitor_value(kind, raw)
    if err:
        return False, "", err
    scopes = [s for s in get_scopes_for_org(db, organization_id)
              if s.scope_type in ("domain", "wildcard") and _target_matches_scope(s, domain)]
    if not scopes:
        return False, value, (f"{domain} is not in your organization's authorized scope. Breach and "
                              "dark web data is about real people, so it can only be monitored for "
                              "domains you own. Add it on the Scopes page first.")
    if scope_mode() == "verified" and not any(s.verified for s in scopes):
        return False, value, f"Verify ownership of {domain} on the Scopes page before monitoring it."
    return True, value, ""


def _own_domains(db: Session, organization_id: str) -> List[str]:
    from app.core.scope import get_scopes_for_org

    return [s.value.lower().removeprefix("*.") for s in get_scopes_for_org(db, organization_id)
            if s.scope_type in ("domain", "wildcard")]


# ── Running monitors ───────────────────────────────────────────────────


def collect_for_monitor(kind: str, value: str, own_domains: Iterable[str] = ()) -> Tuple[List[Finding], Dict[str, str]]:
    checks: List[Tuple[str, Any]] = []
    if kind == "domain":
        checks = [
            ("hibp_breaches", lambda: check_hibp_site_breaches(value)),
            ("hibp_domain_search", lambda: check_hibp_domain_search(value)),
            ("urlhaus", lambda: check_urlhaus(value)),
            ("threatfox", lambda: check_threatfox(value)),
            ("lookalike_dns", lambda: check_lookalikes(value, own_domains)),
        ]
    elif kind == "email":
        checks = [("hibp_accounts", lambda: check_hibp_account(value))]
    findings: List[Finding] = []
    status: Dict[str, str] = {}
    for sid, fn in checks:
        try:
            got, st = fn()
        except httpx.HTTPError as e:
            got, st = [], f"error: {type(e).__name__}"
        except Exception as e:  # noqa: BLE001 - one broken source must not stop the others
            logger.exception("Threat intel source %s failed for %s", sid, value)
            got, st = [], f"error: {type(e).__name__}"
        findings.extend(got)
        status[sid] = st
    return findings, status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_monitor(db: Session, monitor, notify: bool = True) -> Dict[str, Any]:
    """Check one monitor against every source and store what came back."""
    from app.models.threat_intel import ThreatIntelFinding

    ok, _, reason = authorize_monitor_value(db, monitor.organization_id, monitor.kind, monitor.value)
    if not ok:
        monitor.last_checked_at = _now()
        monitor.last_status = {"scope": "not_authorized", "reason": reason}
        db.commit()
        return {"new": 0, "total": 0, "status": monitor.last_status}

    found, status = collect_for_monitor(monitor.kind, monitor.value, _own_domains(db, monitor.organization_id))
    new_rows = []
    now = _now()
    for f in found:
        row = (db.query(ThreatIntelFinding)
               .filter(ThreatIntelFinding.organization_id == monitor.organization_id,
                       ThreatIntelFinding.fingerprint == f.fingerprint)
               .first())
        if row:
            row.last_seen = now
            row.times_seen = (row.times_seen or 1) + 1
            row.severity = f.severity
            row.data = f.data
            row.summary = f.summary
            row.title = f.title
            continue
        row = ThreatIntelFinding(
            organization_id=monitor.organization_id, monitor_id=monitor.id,
            source=f.source, category=f.category, subject=f.subject, title=f.title[:500],
            summary=f.summary, severity=f.severity, reference_url=f.reference_url,
            observed_at=(str(f.observed_at)[:40] if f.observed_at else None),
            data=f.data, fingerprint=f.fingerprint, status="open",
            first_seen=now, last_seen=now,
        )
        db.add(row)
        new_rows.append(row)
    first_check = monitor.last_checked_at is None
    monitor.last_checked_at = now
    monitor.last_status = status
    db.commit()

    # Skip alerts on a monitor's first check: everything is "new" then, and
    # the user who just added it is looking at the results already.
    if notify and new_rows and not first_check:
        _notify_new(db, monitor, new_rows)
    return {"new": len(new_rows), "total": len(found), "status": status}


def _notify_new(db: Session, monitor, rows) -> None:
    serious = [r for r in rows if r.severity in ("critical", "high")]
    if not serious or not monitor.created_by:
        return
    try:
        from app.services.notification_service import dispatch_notification

        worst = "critical" if any(r.severity == "critical" for r in serious) else "high"
        dispatch_notification(
            db=db, organization_id=monitor.organization_id, user_id=monitor.created_by,
            notification_type=f"new_finding_{worst}",
            title=f"{len(serious)} new dark web / breach finding(s) for {monitor.value}",
            message="; ".join(r.title for r in serious[:3]),
            related_entity_type="threat_intel_monitor", related_entity_id=monitor.id,
            data={"monitor_id": monitor.id, "finding_ids": [r.id for r in serious[:20]]},
        )
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("Could not send threat intel notification for %s", monitor.id, exc_info=True)


def run_due_monitors(db: Session, limit: int = 20) -> int:
    from app.models.threat_intel import ThreatIntelMonitor

    hours = max(1, int(getattr(settings, "THREAT_INTEL_CHECK_HOURS", 24) or 24))
    cutoff = _now() - timedelta(hours=hours)
    due = (db.query(ThreatIntelMonitor)
           .filter((ThreatIntelMonitor.last_checked_at.is_(None)) | (ThreatIntelMonitor.last_checked_at < cutoff))
           .order_by(ThreatIntelMonitor.last_checked_at)
           .limit(limit).all())
    ran = 0
    for m in due:
        try:
            run_monitor(db, m)
            ran += 1
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("Threat intel monitor %s failed", m.id)
    return ran


# ── Exploited-vulnerability intelligence (CISA KEV + FIRST EPSS) ──────

_kev_cache: Tuple[float, List[dict]] = (0.0, [])


def kev_catalog() -> Tuple[List[dict], str]:
    global _kev_cache
    with _cache_lock:
        ts, cat = _kev_cache
        if cat and time.time() - ts < 6 * 3600:
            return cat, "ok"
    try:
        r = http_request("GET", KEV_URL, timeout=30)
    except httpx.HTTPError as e:
        return cat, f"error: {type(e).__name__}"
    if r.status != 200 or not isinstance(r.data, dict):
        return cat, _status_for(r.status)
    cat = r.data.get("vulnerabilities") or []
    with _cache_lock:
        _kev_cache = (time.time(), cat)
    return cat, "ok"


def epss_scores(cves: Iterable[str]) -> Tuple[Dict[str, dict], str]:
    ids = sorted({c.upper() for c in cves if c})
    out: Dict[str, dict] = {}
    status = "ok"
    for i in range(0, len(ids), 100):
        try:
            r = http_request("GET", EPSS_URL, params={"cve": ",".join(ids[i:i + 100])})
        except httpx.HTTPError as e:
            return out, f"error: {type(e).__name__}"
        if r.status != 200 or not isinstance(r.data, dict):
            status = _status_for(r.status)
            continue
        for row in r.data.get("data") or []:
            try:
                out[row["cve"].upper()] = {"epss": float(row.get("epss")), "percentile": float(row.get("percentile"))}
            except (KeyError, TypeError, ValueError):
                continue
    return out, status


def _kev_item(k: dict) -> Dict[str, Any]:
    cve = k.get("cveID")
    return {
        "cve_id": cve,
        "vendor": k.get("vendorProject"),
        "product": k.get("product"),
        "name": k.get("vulnerabilityName"),
        "description": k.get("shortDescription"),
        "date_added": k.get("dateAdded"),
        "due_date": k.get("dueDate"),
        "required_action": k.get("requiredAction"),
        "ransomware_use": k.get("knownRansomwareCampaignUse"),
        "reference_url": f"https://nvd.nist.gov/vuln/detail/{cve}",
    }


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def exploited_for_org(db: Session, organization_id: str, recent_days: int = 30) -> Dict[str, Any]:
    """KEV entries that touch this organization, plus the latest additions.

    * ``confirmed``: CVEs that your own scans reported on your assets and that
      CISA lists as exploited in the wild.
    * ``possible``: KEV products that match technology names your scans
      detected. Versions are not compared, so these need a human check.
    * ``recent``: the newest KEV additions (industry-wide context).
    """
    from app.models.asset import Subdomain
    from app.models.scan import Scan
    from app.models.technology import Technology
    from app.models.vulnerability import Vulnerability

    catalog, kev_status = kev_catalog()
    by_cve = {k.get("cveID", "").upper(): k for k in catalog}

    confirmed: Dict[str, Dict[str, Any]] = {}
    vulns = (db.query(Vulnerability)
             .filter(Vulnerability.organization_id == organization_id,
                     Vulnerability.status.notin_(("resolved", "fixed", "closed", "false_positive", "accepted")))
             .limit(5000).all())
    for v in vulns:
        text = " ".join([v.template_id or "", v.name or "", " ".join(map(str, v.tags or []))])
        for cve in {c.upper() for c in _CVE_RE.findall(text)}:
            if cve in by_cve:
                item = confirmed.setdefault(cve, {**_kev_item(by_cve[cve]), "hosts": []})
                if v.host and v.host not in item["hosts"]:
                    item["hosts"].append(v.host)

    techs = (db.query(Technology.name, Technology.version, Subdomain.hostname)
             .join(Subdomain, Technology.subdomain_id == Subdomain.id)
             .join(Scan, Subdomain.scan_id == Scan.id)
             .filter(Scan.organization_id == organization_id)
             .limit(5000).all())
    tech_hosts: Dict[str, Dict[str, Any]] = {}
    for name, version, host in techs:
        key = _norm(name)
        if len(key) < 3:
            continue
        entry = tech_hosts.setdefault(key, {"name": name, "versions": set(), "hosts": set()})
        if version:
            entry["versions"].add(version)
        entry["hosts"].add(host)

    possible = []
    if tech_hosts:
        for k in catalog:
            cve = (k.get("cveID") or "").upper()
            if cve in confirmed:
                continue
            product = _norm(k.get("product"))
            vendor = _norm(k.get("vendorProject"))
            for key, entry in tech_hosts.items():
                if key == product or (key == vendor and product.startswith(key)) or f"{vendor} {product}" == key:
                    possible.append({**_kev_item(k), "technology": entry["name"],
                                     "detected_versions": sorted(entry["versions"])[:5],
                                     "hosts": sorted(entry["hosts"])[:10]})
                    break
    possible.sort(key=lambda x: x.get("date_added") or "", reverse=True)
    possible = possible[:50]

    cutoff = (datetime.now(timezone.utc) - timedelta(days=recent_days)).date().isoformat()
    recent = sorted((k for k in catalog if (k.get("dateAdded") or "") >= cutoff),
                    key=lambda k: k.get("dateAdded") or "", reverse=True)[:25]
    recent_items = [_kev_item(k) for k in recent]

    all_items = list(confirmed.values()) + possible + recent_items
    scores, epss_status = epss_scores(i["cve_id"] for i in all_items) if all_items else ({}, "ok")
    for i in all_items:
        s = scores.get((i["cve_id"] or "").upper())
        i["epss"] = s["epss"] if s else None
        i["epss_percentile"] = s["percentile"] if s else None

    return {
        "confirmed": sorted(confirmed.values(), key=lambda x: -(x.get("epss") or 0)),
        "possible": possible,
        "recent": recent_items,
        "kev_total": len(catalog),
        "sources_status": {"cisa_kev": kev_status, "first_epss": epss_status},
    }


# ── Clearly-labelled sample data (never stored, never mixed with real) ─

SAMPLE_NOTICE = ("SAMPLE DATA. These records are invented to show what the page looks like with "
                 "results. They use reserved example domains and do not describe any real "
                 "organization, person or breach.")


def sample_findings() -> List[Dict[str, Any]]:
    base = [
        ("hibp", "breach_domain", "example.com", "high",
         "3 address(es) at example.com found in the ExampleForum (sample) breach",
         "Sample: a fictional forum breach exposing email addresses and passwords.", "2025-03-14"),
        ("hibp", "breach_site", "example.com", "medium",
         "ExampleShop (sample) was breached (2024-11-02)",
         "Sample: a fictional store breach exposing names and email addresses.", "2024-11-02"),
        ("urlhaus", "malware_url", "example.net", "critical",
         "Live malware URL on example.net: http://files.example.net/invoice.zip",
         "Sample: threat malware_download. Status: online.", "2026-10-30"),
        ("dns", "lookalike_domain", "example.org", "medium",
         "Look-alike domain is registered: examp1e.org",
         "Sample: it can receive email (has MX records). Technique: homoglyph.", None),
    ]
    out = []
    for i, (src, cat, subj, sev, title, summary, observed) in enumerate(base):
        out.append({
            "id": f"sample-{i + 1}", "is_sample": True, "source": src, "category": cat,
            "subject": subj, "severity": sev, "title": title, "summary": summary,
            "observed_at": observed, "reference_url": None, "status": "open", "data": {},
        })
    return out
