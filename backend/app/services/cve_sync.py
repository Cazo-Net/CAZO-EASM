"""Manual NVD CVE snapshot loader (option c: run by hand, no scheduled infra).

Usage:
    python -m app.services.cve_sync --days 30 --limit 5000

Pulls CVEs published in the last N days from NVD's free CVE API 2.0, extracts
vendor/product/affected-version info from the CPE match data, and upserts them
into the local SQLite store used by app/scanners/cve_engine.py. Scans also
fetch all CVEs for a product the first time they see it. Re-run periodically
to keep the snapshot reasonably current.

Note: NVD's free API is rate-limited (~5 req/s without an API key). The loader
sleeps between pages and is resumable via --start-index.
"""
import argparse
import asyncio
import time
import httpx

from app.scanners.cve_engine import CveStore

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"


async def pull(start_date: str, end_date: str, limit: int, start_index: int, store: CveStore) -> int:
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
            added = store.add_nvd_items(vulns)
            total_added += added
            print(f"[cve_sync] idx={idx} pulled={len(vulns)} imported={added} total={total_added} db_total={store.count()}")
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
    db = CveStore(args.db) if args.db else CveStore()
    print(f"[cve_sync] db={db.db_path} existing={db.count()}")
    now = datetime.now(timezone.utc)
    # NVD limits a single pubStart/pubEnd span; chunk into <=120-day windows.
    chunk = 120
    total = 0
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
