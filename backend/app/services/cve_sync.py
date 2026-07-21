"""Manual NVD CVE snapshot loader (option c: run by hand, no scheduled infra).

Usage:
    python -m app.services.cve_sync --days 30 --limit 5000

Pulls CVEs published in the last N days from NVD's free CVE API 2.0, extracts
vendor/product/affected-version info from the CPE match data, and upserts them
into the local SQLite snapshot used by cve_correlation.py. Re-run periodically
to keep the snapshot reasonably current.

Note: NVD's free API is rate-limited (~5 req/s without an API key). The loader
sleeps between pages and is resumable via --start-index.
"""
import argparse
import asyncio
import json
import os
import time
import httpx

from app.scanners.cve_correlation import CVEDatabase

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _severity_from_metrics(metrics: list) -> (str, float):
    """Pick the highest CVSS severity/score across v3x and v2."""
    best_sev, best_score = "unknown", None
    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}
    # metrics is a dict: {"cvssMetricV31": [...], "cvssMetricV30": [...], ...}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for entry in (metrics or {}).get(key, []):
            cvss = entry.get("cvssData", {})
            sev = (cvss.get("baseSeverity") or "").lower()
            score = cvss.get("baseScore")
            if rank.get(sev, 0) >= rank.get(best_sev, 0):
                best_sev, best_score = sev, score
    return best_sev, best_score


def _parse_cpe(cpe_str: str) -> (str, str):
    """cpe:2.3:a:vendor:product:version:... -> (vendor, product)."""
    parts = cpe_str.split(":")
    if len(parts) >= 5 and parts[3] in ("a", "o"):
        return parts[3], parts[4]
    return "", ""


def _affected_versions(vuln: dict) -> list:
    """Collect version strings/ranges from configurations -> cpe_match."""
    versions = []
    for conf in vuln.get("configurations", []):
        for node in conf.get("nodes", []):
            for cpe_match in node.get("cpeMatch", []):
                cpe = cpe_match.get("criteria", "")
                _, _ = _parse_cpe(cpe)
                if cpe_match.get("vulnerable"):
                    ver = cpe.split(":")[5] if len(cpe.split(":")) > 5 else "*"
                    versions.append(ver)
    # De-dupe, cap to keep storage small.
    seen = set()
    out = []
    for v in versions:
        if v not in seen:
            seen.add(v)
            out.append(v)
        if len(out) >= 50:
            break
    return out


async def pull(start_date: str, end_date: str, limit: int, start_index: int, db: CVEDatabase) -> int:
    total_added = 0
    results_per_page = 2000
    idx = start_index
    async with httpx.AsyncClient(timeout=60) as client:
        while total_added < limit:
            params = {
                "pubStartDate": start_date,
                "pubEndDate": end_date,
                "startIndex": idx,
                "resultsPerPage": results_per_page,
            }
            try:
                resp = await client.get(NVD_API, params=params)
            except Exception as e:
                print(f"[cve_sync] request failed: {e}; stopping")
                break
            if resp.status_code != 200:
                print(f"[cve_sync] NVD returned {resp.status_code}; stopping")
                break
            data = resp.json()
            vulns = data.get("vulnerabilities", [])
            if not vulns:
                break
            rows = []
            for v in vulns:
                cve = v.get("cve", {})
                cve_id = cve.get("id")
                descr = ""
                for d in cve.get("descriptions", []):
                    if d.get("lang") == "en":
                        descr = d.get("value", "")
                        break
                sev, score = _severity_from_metrics(cve.get("metrics", {}))
                published = cve.get("published", "")
                vendors = set()
                products = set()
                versions = set()

                # Schema 1.0: configurations -> cpeMatch (CPE strings).
                for conf in cve.get("configurations", []):
                    for node in conf.get("nodes", []):
                        for cpe_match in node.get("cpeMatch", []):
                            if cpe_match.get("vulnerable"):
                                vendor, product = _parse_cpe(cpe_match.get("criteria", ""))
                                if vendor:
                                    vendors.add(vendor)
                                if product:
                                    products.add(product)
                                vsplit = cpe_match.get("criteria", "").split(":")
                                if len(vsplit) > 5 and vsplit[5] not in ("*", "-"):
                                    versions.add(vsplit[5])

                # Schema 2.0: affected -> affectedData (vendor/product/versions).
                for aff in cve.get("affected", []):
                    for ad in aff.get("affectedData", []):
                        if ad.get("vendor"):
                            vendors.add(str(ad["vendor"]).lower())
                        if ad.get("product"):
                            products.add(str(ad["product"]).lower())
                        for v in ad.get("versions", []):
                            ver = v.get("version")
                            if ver and ver not in ("*", "-", "0"):
                                versions.add(ver)
                    # Legacy affected[].product string form.
                    prod = aff.get("product")
                    if prod and isinstance(prod, str):
                        products.add(prod.lower())
                # Emit one row per (vendor, product) combo (deduped by cve_id).
                vlist = sorted(versions)[:50]
                vpairs = [(v, p) for v in vendors for p in products] or [("", "")]
                for vendor, product in vpairs:
                    rows.append({
                        "cve_id": cve_id,
                        "description": descr,
                        "published": published,
                        "severity": sev,
                        "base_score": score,
                        "vendor": vendor,
                        "product": product,
                        "affected_versions": vlist,
                    })
            added = db.upsert_many(rows)
            total_added += added
            print(f"[cve_sync] idx={idx} pulled={len(vulns)} upserted_rows={added} total={total_added} db_total={db.count()}")
            idx += results_per_page
            if len(vulns) < results_per_page:
                break
            time.sleep(6)  # respect NVD free-tier rate limit
    return total_added


def _iso_days_ago(days: int) -> str:
    from datetime import datetime, timedelta, timezone
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def main():
    ap = argparse.ArgumentParser(description="Sync NVD CVEs into local snapshot")
    ap.add_argument("--days", type=int, default=30, help="Total history window to sync (chunked <=120d per NVD limit)")
    ap.add_argument("--limit", type=int, default=5000, help="Max CVE rows to add this run")
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--db", type=str, default=None)
    args = ap.parse_args()

    from datetime import datetime, timedelta, timezone
    db = CVEDatabase(args.db) if args.db else CVEDatabase()
    print(f"[cve_sync] db={db.db_path} existing={db.count()}")
    now = datetime.now(timezone.utc)
    # NVD limits a single pubStart/pubEnd span; chunk into <=120-day windows.
    chunk = 120
    total = 0
    win_end = now
    win_start = now - timedelta(days=args.days)
    cursor_end = now
    while win_start < now and total < args.limit:
        cursor_start = max(win_start, cursor_end - timedelta(days=chunk))
        n = asyncio.run(pull(
            cursor_start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            cursor_end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            args.limit - total, args.start_index, db,
        ))
        total += n
        cursor_end = cursor_start
        win_start = cursor_start
        if n == 0:
            break
    print(f"[cve_sync] done. total rows now: {db.count()} (this run added {total})")


if __name__ == "__main__":
    main()
