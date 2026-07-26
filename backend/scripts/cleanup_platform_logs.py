"""Platform log retention cleanup.

Deletes old log entries based on per-category retention policies:
- api_request, notification: 90 days
- scan_event, application_error: 180 days
- unexpected, security_event, auth_event: 365 days

Run via cron or as a one-off script:
    python -m scripts.cleanup_platform_logs

Or with a specific cutoff:
    python -m scripts.cleanup_platform_logs --dry-run
"""
import argparse
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.database import write_engine

logger = logging.getLogger("cleanup_platform_logs")

# Category → retention days
RETENTION = {
    "api_request": 90,
    "notification": 90,
    "scan_event": 180,
    "application_error": 180,
    "unexpected": 365,
    "security_event": 365,
    "auth_event": 365,
}


def cleanup(dry_run: bool = False) -> dict:
    """Delete expired platform logs. Returns {category: deleted_count}."""
    results = {}
    now = datetime.now(timezone.utc)

    with write_engine.begin() as conn:
        for category, days in RETENTION.items():
            cutoff = now - timedelta(days=days)
            if dry_run:
                row = conn.execute(
                    text("SELECT COUNT(*) FROM platform_logs WHERE category = :cat AND created_at < :cutoff"),
                    {"cat": category, "cutoff": cutoff},
                ).scalar()
                results[category] = row or 0
                logger.info("[DRY RUN] %s: would delete %d rows older than %s", category, row or 0, cutoff.date())
            else:
                result = conn.execute(
                    text("DELETE FROM platform_logs WHERE category = :cat AND created_at < :cutoff"),
                    {"cat": category, "cutoff": cutoff},
                )
                deleted = result.rowcount
                results[category] = deleted
                if deleted > 0:
                    logger.info("Deleted %d %s logs older than %s", deleted, category, cutoff.date())

    return results


def main():
    parser = argparse.ArgumentParser(description="Clean up old platform logs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    results = cleanup(dry_run=args.dry_run)
    total = sum(results.values())
    mode = "DRY RUN" if args.dry_run else "DELETED"
    logger.info("%s %d total rows across %d categories", mode, total, len(results))
    for cat, count in sorted(results.items()):
        if count > 0:
            logger.info("  %s: %d rows", cat, count)


if __name__ == "__main__":
    main()
