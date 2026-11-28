"""V2 CVE Correlation Scanner — version-based CVE matching against local NVD snapshot."""
from __future__ import annotations

import os
import json
import re
import sqlite3
import threading
import logging
from typing import Any, Dict, List, Optional

from packaging.version import parse as parse_version, InvalidVersion

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

_DB_PATH = os.environ.get(
    "CAZO_CVE_DB",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cve_snapshot.db"),
)

_ALIASES = {
    "wordpress": ("wordpress", "wordpress"), "drupal": ("drupal", "drupal"),
    "joomla": ("joomla", "joomla"), "apache": ("apache", "http_server"),
    "nginx": ("nginx", "nginx"), "openssh": ("openbsd", "openssh"),
    "php": ("php", "php"), "jquery": ("jquery", "jquery"),
    "openssl": ("openssl", "openssl"), "node.js": ("nodejs", "nodejs"),
    "laravel": ("laravel", "laravel"), "django": ("djangoproject", "django"),
    "tomcat": ("apache", "tomcat"), "mysql": ("oracle", "mysql"),
    "postgresql": ("postgresql", "postgresql"), "redis": ("redis", "redis"),
}


class CVEDatabase:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = os.path.abspath(db_path)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._lock, self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS cve (
                cve_id TEXT PRIMARY KEY, description TEXT, published TEXT,
                severity TEXT, base_score REAL, vendor TEXT, product TEXT,
                affected_versions TEXT)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cve_vendor_product ON cve(vendor, product)")

    def count(self) -> int:
        with self._lock, self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM cve").fetchone()
            return row["n"] if row else 0

    def lookup(self, vendor: str, product: str) -> List[Dict[str, Any]]:
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cve WHERE vendor=? OR product=?", (vendor.lower(), product.lower()),
            ).fetchall()
            return [dict(r) for r in rows]


def _normalize_tech(name: str):
    key = (name or "").lower().strip()
    return _ALIASES.get(key, (key, key))


def _sanitize_version(v: str) -> str:
    m = re.match(r"^(\d+(?:\.\d+){0,3})", (v or "").strip())
    return m.group(1) if m else ""


def _version_in_range(detected: str, ranges: List[str]) -> bool:
    if not detected:
        return False
    core = _sanitize_version(detected)
    try:
        dv = parse_version(core) if core else None
    except InvalidVersion:
        dv = None

    for r in ranges:
        r = (r or "").strip()
        if r in ("*", "", "all", "any"):
            return True
        try:
            if r.startswith(">=") and dv:
                if dv >= parse_version(_sanitize_version(r[2:])):
                    return True
            elif r.startswith("<=") and dv:
                if dv <= parse_version(_sanitize_version(r[2:])):
                    return True
            elif r.startswith(">") and dv:
                if dv > parse_version(_sanitize_version(r[1:])):
                    return True
            elif r.startswith("<") and dv:
                if dv < parse_version(_sanitize_version(r[1:])):
                    return True
            elif "-" in r:
                lo, hi = r.split("-", 1)
                if dv and parse_version(lo) <= dv <= parse_version(hi):
                    return True
            else:
                if dv and dv == parse_version(r):
                    return True
        except InvalidVersion:
            if r and r in detected:
                return True
    return False


@register_scanner(
    name="cve-correlation",
    category=ScannerCategory.VULNERABILITY,
    version="2.0.0",
    priority=ScannerPriority.NORMAL,
    description="Version-based CVE correlation against local NVD snapshot (unverified)",
    capabilities=["cve_correlation", "vulnerability_matching"],
)
class CVECorrelationScanner(EnhancedBaseScanner):
    name = "cve-correlation"
    version = "2.0.0"
    category = ScannerCategory.VULNERABILITY
    priority = ScannerPriority.NORMAL

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.db = CVEDatabase()
        # Room for the first-time NVD import of new products (90 s budget).
        self.timeout = max(float(self.timeout or 0), 150.0)

    def validate_target(self, target: str) -> bool:
        return bool(target)

    async def scan(self, target: str, **kwargs) -> ScanResult:
        """Same correlation as the standard engine (``app/scanners/cve_engine.py``):
        web fingerprints and service banners, NVD ranges, on-demand product import."""
        from app.scanners.cve_engine import correlate_scan

        scan_results = kwargs.get("scan_results") or {}
        findings, status = await correlate_scan(
            scan_results.get("technologies") or {}, scan_results.get("ports") or {},
            fetch_missing=bool(self.config.get("fetch_missing", True)),
        )
        return ScanResult(
            success=True, scanner=self.name, target=target,
            data={"vulnerabilities": findings, "count": len(findings), "status": status,
                  "note": "All CVE matches are version-correlated and UNVERIFIED."},
        )
