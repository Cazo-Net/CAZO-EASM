"""Pure-Python CVE correlation.

Replaces nuclei's live exploit-verification templates with version-based CVE
correlation against a *local* CVE snapshot. The snapshot is populated by
``app/services/cve_sync.py`` (a manual CLI you run to pull from NVD's free
API — no scheduled infra required until a production deploy target exists).

HONEST TRADEOFF (must be surfaced to users): nuclei templates actively send
crafted requests to *confirm* a vulnerability is exploitable, which keeps false
positives low. Our approach cross-references a detected technology+version
against known CVEs — a CVE listed for a version does NOT prove the instance is
exploitable (patch level, config, and WAFs matter). Every correlation finding
is therefore explicitly labelled ``version-correlated (unverified)`` so it is
never mistaken for a confirmed exploit.
"""
import os
import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional
from packaging.version import parse as parse_version, InvalidVersion
import logging

from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

_DB_PATH = os.environ.get(
    "CAZO_CVE_DB",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "cve_snapshot.db"),
)


class CVEDatabase:
    """Thin wrapper around the local CVE SQLite snapshot."""

    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = os.path.abspath(db_path)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._lock, self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS cve (
                    cve_id TEXT PRIMARY KEY,
                    description TEXT,
                    published TEXT,
                    severity TEXT,
                    base_score REAL,
                    vendor TEXT,
                    product TEXT,
                    affected_versions TEXT   -- JSON list of version ranges/strings
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cve_vendor_product ON cve(vendor, product)"
            )

    def count(self) -> int:
        with self._lock, self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM cve").fetchone()
            return row["n"] if row else 0

    def upsert_many(self, rows: List[Dict[str, Any]]) -> int:
        """rows: list of dicts with cve_id, description, published, severity,
        base_score, vendor, product, affected_versions (list)."""
        n = 0
        with self._lock, self._conn() as conn:
            for r in rows:
                conn.execute(
                    """INSERT INTO cve (cve_id, description, published, severity, base_score, vendor, product, affected_versions)
                       VALUES (:cve_id, :description, :published, :severity, :base_score, :vendor, :product, :affected_versions)
                       ON CONFLICT(cve_id) DO UPDATE SET
                         description=excluded.description, published=excluded.published,
                         severity=excluded.severity, base_score=excluded.base_score,
                         vendor=excluded.vendor, product=excluded.product,
                         affected_versions=excluded.affected_versions""",
                    {
                        "cve_id": r["cve_id"],
                        "description": r.get("description", ""),
                        "published": r.get("published", ""),
                        "severity": r.get("severity", "unknown"),
                        "base_score": r.get("base_score"),
                        "vendor": (r.get("vendor") or "").lower(),
                        "product": (r.get("product") or "").lower(),
                        "affected_versions": json.dumps(r.get("affected_versions", [])),
                    },
                )
                n += 1
            conn.commit()
        return n

    def lookup(self, vendor: str, product: str) -> List[Dict[str, Any]]:
        vendor = (vendor or "").lower()
        product = (product or "").lower()
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cve WHERE vendor=? OR product=?",
                (vendor, product),
            ).fetchall()
            return [dict(r) for r in rows]


def _normalize_tech(name: str) -> (str, str):
    """Map a detected tech name to (vendor, product) for CVE lookup."""
    # Curated alias map; extend as needed.
    aliases = {
        "wordpress": ("wordpress", "wordpress"),
        "drupal": ("drupal", "drupal"),
        "joomla": ("joomla", "joomla"),
        "apache": ("apache", "http_server"),
        "nginx": ("nginx", "nginx"),
        "openssh": ("openbsd", "openssh"),
        "php": ("php", "php"),
        "jquery": ("jquery", "jquery"),
        "bootstrap": ("twbs", "bootstrap"),
        "openssl": ("openssl", "openssl"),
        "node.js": ("nodejs", "nodejs"),
        "express": ("expressjs", "express"),
        "laravel": ("laravel", "laravel"),
        "django": ("djangoproject", "django"),
        "spring": ("vmware", "spring_framework"),
        "tomcat": ("apache", "tomcat"),
        "mysql": ("oracle", "mysql"),
        "postgresql": ("postgresql", "postgresql"),
        "mongodb": ("mongodb", "mongodb"),
        "redis": ("redis", "redis"),
        "elasticsearch": ("elastic", "elasticsearch"),
        "apache httpd": ("apache", "http_server"),
    }
    key = (name or "").lower().strip()
    if key in aliases:
        return aliases[key]
    return (key, key)


def _sanitize_version(v: str) -> str:
    """Strip non-numeric suffixes some vendors append (e.g. OpenSSH '6.6.1p1',
    '2.4.7 ((Ubuntu))') down to a parseable numeric core for comparison."""
    import re
    v = v.strip()
    # Keep only leading "digits and dots", allowing a single trailing letter
    # (e.g. '1.2.3a' is invalid but rare). Drop 'p1', 'ubuntu2', '(Ubuntu)', etc.
    m = re.match(r"^(\d+(?:\.\d+){0,3})", v)
    return m.group(1) if m else ""


def _version_in_range(detected: str, ranges: List[str]) -> bool:
    """Best-effort: does `detected` fall within any listed version range/string?

    ranges entries may be: exact "1.2.3", ">=1.2.3", "<=2.0", "1.0-2.0",
    or "*" (all versions). This is heuristic — it does not parse full NVD
    version ranges perfectly, but is good enough for triage and is always
    labelled unverified.
    """
    if not detected:
        return False
    core = _sanitize_version(detected)
    if core:
        try:
            dv = parse_version(core)
        except InvalidVersion:
            dv = None
    else:
        dv = None

    for r in ranges:
        r = (r or "").strip()
        if r in ("*", "", "all", "any"):
            return True
        try:
            if r.startswith(">="):
                if dv is not None and dv >= parse_version(_sanitize_version(r[2:].strip()) or r[2:].strip()):
                    return True
            elif r.startswith("<="):
                if dv is not None and dv <= parse_version(_sanitize_version(r[2:].strip()) or r[2:].strip()):
                    return True
            elif r.startswith(">"):
                if dv is not None and dv > parse_version(_sanitize_version(r[1:].strip()) or r[1:].strip()):
                    return True
            elif r.startswith("<"):
                if dv is not None and dv < parse_version(_sanitize_version(r[1:].strip()) or r[1:].strip()):
                    return True
            elif "-" in r and all(c.isdigit() or c == "." or c == "-" for c in r):
                lo, hi = r.split("-", 1)
                if dv is not None and parse_version(lo) <= dv <= parse_version(hi):
                    return True
            else:
                if dv is not None and dv == parse_version(r):
                    return True
        except InvalidVersion:
            if r and r in detected:
                return True
    return False


def correlate(tech_list: List[Dict[str, Any]], db: Optional[CVEDatabase] = None) -> List[Dict[str, Any]]:
    """Given a list of detected technologies [{name, version, ...}], return
    CVE correlation findings (each explicitly marked unverified)."""
    db = db or CVEDatabase()
    findings: List[Dict[str, Any]] = []
    if db.count() == 0:
        return findings

    for tech in tech_list:
        name = tech.get("name")
        version = tech.get("version")
        if not name or not version:
            continue
        vendor, product = _normalize_tech(name)
        matches = db.lookup(vendor, product)
        for m in matches:
            ranges = json.loads(m.get("affected_versions") or "[]")
            if _version_in_range(version, ranges):
                findings.append({
                    "template_id": f"cve-correlation/{m['cve_id']}",
                    "name": f"{name} {version} — {m['cve_id']}",
                    "severity": m.get("severity", "unknown"),
                    "vuln_type": "cve-correlation",
                    "host": tech.get("host", ""),
                    "matched_at": tech.get("host", ""),
                    "description": (
                        f"Version-correlated (UNVERIFIED): {name} {version} matches "
                        f"{m['cve_id']}. {m.get('description', '')[:300]}"
                    ),
                    "reference": [f"https://nvd.nist.gov/vuln/detail/{m['cve_id']}"],
                    "tags": ["cve", "version-correlated", "unverified"],
                    "cve_id": m["cve_id"],
                    "evidence": f"Detected {name} {version}; CVE {m['cve_id']} affects this version range.",
                    "verified": False,
                })
    return findings


@register_scanner(
    name="cve-correlation",
    category=ScannerCategory.VULNERABILITY,
    description="Pure-Python CVE correlation against a local NVD snapshot (replaces nuclei templates).",
)
class CVECorrelationScanner(BaseScanner):
    """Version-based CVE correlation scanner (no nuclei binary).

    Cross-references detected technologies+versions (from the tech scanner)
    against the local NVD snapshot. Findings are explicitly UNVERIFIED — see
    the module docstring for the honest tradeoff vs nuclei's live templates.
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.db = CVEDatabase()

    def validate_target(self, target: str) -> bool:
        return bool(target)

    async def scan(self, target: str, scan_results: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        if self.db.count() == 0:
            # No local snapshot yet -> honest status, not a silent zero.
            return {
                "success": True,
                "target": target,
                "vulnerabilities": [],
                "count": 0,
                "scanner": "cve-correlation",
                "status": "no_cve_snapshot",
            }

        tech_by_host = (scan_results or {}).get("technologies", {}) or {}
        all_tech: List[Dict[str, Any]] = []
        for host, techs in tech_by_host.items():
            for t in techs or []:
                t = dict(t)
                t["host"] = host
                all_tech.append(t)

        findings = correlate(all_tech, self.db)
        return {
            "success": True,
            "target": target,
            "vulnerabilities": findings,
            "count": len(findings),
            "scanner": "cve-correlation",
            "status": "ok" if findings else "no_results",
            "note": "All CVE matches are version-correlated and UNVERIFIED (no live exploit confirmation).",
        }
