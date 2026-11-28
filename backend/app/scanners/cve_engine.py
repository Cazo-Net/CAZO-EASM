"""CVE knowledge for both scan engines: store, NVD import and version matching.

Why this exists (the old snapshot code never matched anything):

* The old NVD importer read the CPE fields one position off, so every
  imported CVE was stored with an empty vendor and product, and lookups by
  product never found them.
* NVD describes most affected software as *ranges*
  (``versionStartIncluding`` / ``versionEndExcluding``), which were ignored;
  only exact versions were kept, and the matcher treated each bound as a
  separate "match any version above X" rule.
* One row per CVE (primary key) meant a CVE affecting several products kept
  only the last one.
* The weekly job only pulls CVEs *published* in the last 7 days, so an old
  CVE in, say, nginx 1.18 was never in the snapshot.

This module keeps one row per (CVE, product, version range) in a
``cve_match`` table, imports NVD JSON correctly, and can fetch every CVE for
a product the first time a scan sees that product (``ensure_products``), so
correlation works from the first scan without a bulk import.

Matches stay labelled *version-correlated (unverified)*: a version in range
does not prove the instance is exploitable (distro backports, config, WAF).
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from packaging.version import InvalidVersion, Version
from packaging.version import parse as parse_version

logger = logging.getLogger(__name__)

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
PRODUCT_REFRESH_S = 7 * 24 * 3600

_DB_PATH = os.environ.get(
    "CAZO_CVE_DB",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "cve_snapshot.db"),
)

# Detected name (lower-case) -> (NVD vendor, NVD product). Covers names from
# HTTP fingerprints and from service banners (port scans, nmap -sV).
PRODUCT_ALIASES: Dict[str, Tuple[str, str]] = {
    "nginx": ("f5", "nginx"),
    "apache": ("apache", "http_server"),
    "apache httpd": ("apache", "http_server"),
    "apache http server": ("apache", "http_server"),
    "httpd": ("apache", "http_server"),
    "tomcat": ("apache", "tomcat"),
    "apache tomcat": ("apache", "tomcat"),
    "apache-coyote": ("apache", "tomcat"),
    "openssh": ("openbsd", "openssh"),
    "microsoft-iis": ("microsoft", "internet_information_services"),
    "iis": ("microsoft", "internet_information_services"),
    "php": ("php", "php"),
    "openssl": ("openssl", "openssl"),
    "node.js": ("nodejs", "node.js"),
    "express": ("expressjs", "express"),
    "wordpress": ("wordpress", "wordpress"),
    "drupal": ("drupal", "drupal"),
    "joomla": ("joomla", "joomla\\!"),
    "jquery": ("jquery", "jquery"),
    "bootstrap": ("getbootstrap", "bootstrap"),
    "django": ("djangoproject", "django"),
    "laravel": ("laravel", "framework"),
    "mysql": ("oracle", "mysql"),
    "mariadb": ("mariadb", "mariadb"),
    "postgresql": ("postgresql", "postgresql"),
    "redis": ("redis", "redis"),
    "mongodb": ("mongodb", "mongodb"),
    "elasticsearch": ("elastic", "elasticsearch"),
    "kibana": ("elastic", "kibana"),
    "grafana": ("grafana", "grafana"),
    "jenkins": ("jenkins", "jenkins"),
    "gitlab": ("gitlab", "gitlab"),
    "exim": ("exim", "exim"),
    "postfix": ("postfix", "postfix"),
    "proftpd": ("proftpd", "proftpd"),
    "vsftpd": ("beasts", "vsftpd"),
    "pure-ftpd": ("pureftpd", "pure-ftpd"),
    "dovecot": ("dovecot", "dovecot"),
    "lighttpd": ("lighttpd", "lighttpd"),
    "litespeed": ("litespeedtech", "litespeed_web_server"),
    "openresty": ("openresty", "openresty"),
    "haproxy": ("haproxy", "haproxy"),
    "varnish": ("varnish-software", "varnish_cache"),
    "squid": ("squid-cache", "squid"),
    "bind": ("isc", "bind"),
    "rabbitmq": ("vmware", "rabbitmq"),
    "memcached": ("memcached", "memcached"),
    "confluence": ("atlassian", "confluence_server"),
    "jira": ("atlassian", "jira_server"),
    "weblogic": ("oracle", "weblogic_server"),
    "jetty": ("eclipse", "jetty"),
    "envoy": ("envoyproxy", "envoy"),
    "traefik": ("traefik", "traefik"),
    "caddy": ("caddyserver", "caddy"),
}

# Banner text that means a distribution patched the package without changing
# its upstream version number ("OpenSSH_8.9p1 Ubuntu-3ubuntu0.6").
_BACKPORT_RE = re.compile(r"ubuntu|debian|deb\d|el\d|centos|rhel|red hat|amzn|suse|alpine|fedora", re.I)


# NVD sometimes files one product under two vendors over time.
EXTRA_KEYS: Dict[Tuple[str, str], List[Tuple[str, str]]] = {
    ("f5", "nginx"): [("nginx", "nginx")],
    ("nodejs", "node.js"): [("nodejs", "nodejs")],
}


def product_key(name: str) -> Optional[Tuple[str, str]]:
    n = (name or "").strip().lower()
    if not n:
        return None
    if n in PRODUCT_ALIASES:
        return PRODUCT_ALIASES[n]
    for alias, key in PRODUCT_ALIASES.items():
        if n.startswith(alias + " ") or n.startswith(alias + "/"):
            return key
    return None


def product_keys(name: str) -> List[Tuple[str, str]]:
    key = product_key(name)
    return [key, *EXTRA_KEYS.get(key, [])] if key else []


def clean_version(v: str) -> Optional[Version]:
    """Upstream numeric core of a version: '8.9p1' -> 8.9, '2.4.7 (Ubuntu)' -> 2.4.7."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+){0,3})", str(v or ""))
    if not m:
        return None
    try:
        return parse_version(m.group(1))
    except InvalidVersion:
        return None


@dataclass
class VersionRange:
    exact: Optional[str] = None
    start_incl: Optional[str] = None
    start_excl: Optional[str] = None
    end_incl: Optional[str] = None
    end_excl: Optional[str] = None

    def contains(self, version: str) -> bool:
        v = clean_version(version)
        if v is None:
            return False
        if self.exact:
            e = clean_version(self.exact)
            return e is not None and v == e
        bounds = [self.start_incl, self.start_excl, self.end_incl, self.end_excl]
        if not any(bounds):
            return False  # "all versions" is too vague to report as a match
        checks = (
            (self.start_incl, lambda b: v >= b),
            (self.start_excl, lambda b: v > b),
            (self.end_incl, lambda b: v <= b),
            (self.end_excl, lambda b: v < b),
        )
        for raw, ok in checks:
            if raw:
                b = clean_version(raw)
                if b is None or not ok(b):
                    return False
        return True

    def describe(self) -> str:
        if self.exact:
            return f"= {self.exact}"
        parts = []
        if self.start_incl:
            parts.append(f">= {self.start_incl}")
        if self.start_excl:
            parts.append(f"> {self.start_excl}")
        if self.end_incl:
            parts.append(f"<= {self.end_incl}")
        if self.end_excl:
            parts.append(f"< {self.end_excl}")
        return ", ".join(parts)


def _cvss(metrics: Dict[str, Any]) -> Tuple[str, Optional[float]]:
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for entry in (metrics or {}).get(key, []) or []:
            data = entry.get("cvssData", {}) or {}
            sev = (data.get("baseSeverity") or entry.get("baseSeverity") or "").lower()
            if sev:
                return sev, data.get("baseScore")
    return "unknown", None


def parse_nvd_cve(item: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """One NVD 2.0 ``vulnerabilities[]`` item -> (cve row, match rows)."""
    cve = item.get("cve", item) or {}
    cve_id = cve.get("id", "")
    desc = next((d.get("value", "") for d in cve.get("descriptions", []) if d.get("lang") == "en"), "")
    sev, score = _cvss(cve.get("metrics", {}))
    weaknesses = sorted({
        d.get("value") for w in cve.get("weaknesses", []) or [] for d in w.get("description", []) or []
        if str(d.get("value", "")).startswith("CWE-")
    })
    row = {
        "cve_id": cve_id, "description": desc, "published": cve.get("published", ""),
        "severity": sev, "base_score": score, "cwe": ",".join(weaknesses),
    }
    matches: List[Dict[str, Any]] = []
    seen = set()
    for conf in cve.get("configurations", []) or []:
        for node in conf.get("nodes", []) or []:
            for m in node.get("cpeMatch", []) or []:
                if not m.get("vulnerable"):
                    continue
                parts = str(m.get("criteria", "")).split(":")
                # cpe:2.3:<part>:<vendor>:<product>:<version>:...
                if len(parts) < 6 or parts[2] not in ("a", "o", "h"):
                    continue
                vendor, product, version = parts[3].lower(), parts[4].lower(), parts[5]
                r = {
                    "cve_id": cve_id, "vendor": vendor, "product": product,
                    "exact": version if version not in ("*", "-", "") else None,
                    "start_incl": m.get("versionStartIncluding"),
                    "start_excl": m.get("versionStartExcluding"),
                    "end_incl": m.get("versionEndIncluding"),
                    "end_excl": m.get("versionEndExcluding"),
                }
                key = tuple(r.values())
                if key not in seen:
                    seen.add(key)
                    matches.append(r)
    return row, matches


class CveStore:
    """SQLite store: ``cve_info`` (one row per CVE), ``cve_match`` (per range)."""

    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = os.path.abspath(db_path)
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._lock, self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS cve_info (
                    cve_id TEXT PRIMARY KEY, description TEXT, published TEXT,
                    severity TEXT, base_score REAL, cwe TEXT);
                CREATE TABLE IF NOT EXISTS cve_match (
                    cve_id TEXT, vendor TEXT, product TEXT, exact TEXT,
                    start_incl TEXT, start_excl TEXT, end_incl TEXT, end_excl TEXT,
                    UNIQUE(cve_id, vendor, product, exact, start_incl, start_excl, end_incl, end_excl));
                CREATE INDEX IF NOT EXISTS idx_cve_match_vp ON cve_match(vendor, product);
                CREATE TABLE IF NOT EXISTS cve_product_sync (
                    vendor TEXT, product TEXT, synced_at REAL, status TEXT,
                    PRIMARY KEY(vendor, product));
                """
            )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def add_nvd_items(self, items: Iterable[Dict[str, Any]]) -> int:
        n = 0
        with self._lock, self._conn() as c:
            for item in items:
                row, matches = parse_nvd_cve(item)
                if not row["cve_id"]:
                    continue
                c.execute(
                    """INSERT INTO cve_info VALUES (:cve_id,:description,:published,:severity,:base_score,:cwe)
                       ON CONFLICT(cve_id) DO UPDATE SET description=excluded.description,
                       published=excluded.published, severity=excluded.severity,
                       base_score=excluded.base_score, cwe=excluded.cwe""", row)
                c.execute("DELETE FROM cve_match WHERE cve_id=?", (row["cve_id"],))
                c.executemany(
                    """INSERT OR IGNORE INTO cve_match VALUES
                       (:cve_id,:vendor,:product,:exact,:start_incl,:start_excl,:end_incl,:end_excl)""",
                    matches)
                n += 1
        return n

    def count(self) -> int:
        with self._lock, self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM cve_info").fetchone()[0]

    def product_synced(self, vendor: str, product: str, max_age: float = PRODUCT_REFRESH_S) -> bool:
        with self._lock, self._conn() as c:
            r = c.execute("SELECT synced_at, status FROM cve_product_sync WHERE vendor=? AND product=?",
                          (vendor, product)).fetchone()
        return bool(r and r["status"] == "ok" and time.time() - (r["synced_at"] or 0) < max_age)

    def mark_product(self, vendor: str, product: str, status: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO cve_product_sync VALUES (?,?,?,?)",
                      (vendor, product, time.time(), status))

    def match(self, vendor: str, product: str, version: str) -> List[Dict[str, Any]]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                """SELECT m.*, i.description, i.severity, i.base_score, i.cwe, i.published
                   FROM cve_match m JOIN cve_info i USING (cve_id)
                   WHERE m.vendor=? AND m.product=?""", (vendor, product)).fetchall()
        out: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            rng = VersionRange(r["exact"], r["start_incl"], r["start_excl"], r["end_incl"], r["end_excl"])
            if rng.contains(version) and r["cve_id"] not in out:
                d = dict(r)
                d["range"] = rng.describe()
                out[r["cve_id"]] = d
        return list(out.values())


# ── NVD import ──────────────────────────────────────────────────────────────

def _nvd_get(params: Dict[str, Any], timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    import httpx

    headers = {"User-Agent": "CAZO-EASM CVE sync"}
    key = os.environ.get("NVD_API_KEY", "")
    if key:
        headers["apiKey"] = key
    with httpx.Client(timeout=timeout) as client:
        r = client.get(NVD_API, params=params, headers=headers)
    if r.status_code != 200:
        logger.info("NVD returned %s for %s", r.status_code, params)
        return None
    return r.json()


def fetch_product(store: CveStore, vendor: str, product: str, *, deadline: float) -> str:
    """Import every NVD CVE for one product. Returns a status string."""
    idx, total, per_page = 0, None, 2000
    match = f"cpe:2.3:*:{vendor}:{product}"
    while total is None or idx < total:
        if time.monotonic() > deadline:
            return "partial: time budget"
        data = _nvd_get({"virtualMatchString": match, "startIndex": idx, "resultsPerPage": per_page})
        if data is None:
            return "error: nvd"
        total = int(data.get("totalResults") or 0)
        items = data.get("vulnerabilities") or []
        store.add_nvd_items(items)
        idx += len(items) or per_page
        if idx < total:
            time.sleep(0.7 if os.environ.get("NVD_API_KEY") else 6.0)  # NVD public rate limit
    return "ok"


def ensure_products(store: CveStore, keys: Iterable[Tuple[str, str]], budget_s: float = 90.0,
                    fetch=fetch_product) -> Dict[str, str]:
    """Make sure the store knows every CVE for these products (runs in a thread)."""
    deadline = time.monotonic() + budget_s
    status: Dict[str, str] = {}
    for vendor, product in sorted(set(keys)):
        name = f"{vendor}:{product}"
        if store.product_synced(vendor, product):
            status[name] = "cached"
            continue
        if time.monotonic() > deadline:
            status[name] = "skipped: time budget"
            continue
        try:
            st = fetch(store, vendor, product, deadline=deadline)
        except Exception as exc:  # noqa: BLE001 — offline or NVD down: correlate with what we have
            st = f"error: {type(exc).__name__}"
        if st == "ok":
            store.mark_product(vendor, product, "ok")
        status[name] = st
    return status


# ── Correlation ─────────────────────────────────────────────────────────────

def software_inventory(technologies: Dict[str, List[Dict[str, Any]]],
                       ports: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """(host, name, version, where seen) for everything with a version number."""
    items: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def _add(host, name, version, seen_on, banner=""):
        if not name or not version or clean_version(version) is None:
            return
        k = (host, name.lower(), str(version))
        if k not in items:
            items[k] = {"host": host, "name": name, "version": str(version), "seen_on": seen_on,
                        "banner": banner}

    for host, techs in (technologies or {}).items():
        for t in techs or []:
            if isinstance(t, dict):
                _add(host, t.get("name"), t.get("version"), "web fingerprint")
    for host, plist in (ports or {}).items():
        for p in plist or []:
            if not isinstance(p, dict):
                continue
            banner = str(p.get("banner") or "")
            _add(host, p.get("product"), p.get("version"), f"port {p.get('port')}/{p.get('service') or 'tcp'}",
                 banner)
    return list(items.values())


def correlate(store: CveStore, inventory: List[Dict[str, Any]], max_per_item: int = 25) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
    for it in inventory:
        keys = product_keys(it["name"])
        if not keys:
            continue
        key = keys[0]
        by_cve: Dict[str, Dict[str, Any]] = {}
        for k in keys:
            for m in store.match(k[0], k[1], it["version"]):
                by_cve.setdefault(m["cve_id"], m)
        matches = sorted(by_cve.values(),
                         key=lambda m: (rank.get(m["severity"], 9), -(m["base_score"] or 0)))
        backport = bool(_BACKPORT_RE.search(it.get("banner") or "") or _BACKPORT_RE.search(it["version"]))
        for m in matches[:max_per_item]:
            cve = m["cve_id"]
            evidence = [
                f"Detected {it['name']} {it['version']} ({it['seen_on']})",
                f"{cve} affects {key[0]}:{key[1]} {m['range']}",
            ]
            tags = ["cve", "version-correlated", "unverified"]
            note = ""
            if backport:
                tags.append("distro-backport-possible")
                note = (" The banner shows a Linux distribution package, which often carries the fix "
                        "without changing the version number; check the distribution's advisory.")
            if m.get("cwe"):
                tags += [c for c in m["cwe"].split(",") if c]
            score = f" (CVSS {m['base_score']})" if m.get("base_score") is not None else ""
            findings.append({
                "template_id": f"cve-correlation/{cve}",
                "name": f"{it['name']} {it['version']}: {cve}",
                "severity": m["severity"] if m["severity"] in rank else "unknown",
                "vuln_type": "cve-correlation",
                "host": it["host"],
                "matched_at": it["host"],
                "cve_id": cve,
                "description": (
                    f"Version-correlated (unverified): {it['name']} {it['version']} on {it['host']} is in the "
                    f"affected range of {cve}{score}. {(m.get('description') or '')[:400]}{note} "
                    f"Fix: upgrade {it['name']} to a version outside {m['range']} or apply the vendor patch."
                ),
                "reference": [f"https://nvd.nist.gov/vuln/detail/{cve}"],
                "tags": tags,
                "extracted_results": evidence,
                "verified": False,
            })
    return findings


async def correlate_scan(technologies, ports, *, store: Optional[CveStore] = None,
                         fetch_missing: bool = True, budget_s: float = 90.0) -> Tuple[List[Dict[str, Any]], str]:
    """Async entry point used by both engines. Returns (findings, status)."""
    import asyncio

    store = store or CveStore()
    if os.environ.get("CVE_NVD_FETCH", "true").lower() in ("0", "false", "no"):
        fetch_missing = False
    inventory = software_inventory(technologies or {}, ports or {})
    keys = {k for i in inventory for k in product_keys(i["name"])}
    sync = {}
    if keys and fetch_missing:
        sync = await asyncio.to_thread(ensure_products, store, keys, budget_s)
    findings = await asyncio.to_thread(correlate, store, inventory)
    fetched = sum(1 for s in sync.values() if s == "ok")
    failed = [k for k, s in sync.items() if s.startswith(("error", "partial", "skipped"))]
    status = (f"ok ({len(findings)} CVEs across {len(inventory)} versioned components, "
              f"{len(keys)} known products; {fetched} fetched from NVD"
              + (f"; NVD unavailable for {len(failed)}" if failed else "") + ")")
    return findings, status

