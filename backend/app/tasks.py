"""Celery tasks."""

import asyncio
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.scan_service import ScanService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, name="app.tasks.execute_scan")
def execute_scan_task(self, scan_id: str):
    """Run a full scan in a Celery worker."""
    logger.info("Starting scan task for scan_id=%s", scan_id)
    db = SessionLocal()
    try:
        service = ScanService(db)
        asyncio.run(service.execute_scan(scan_id))
        logger.info("Scan task completed for scan_id=%s", scan_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scan task failed for scan_id=%s", scan_id)
        raise self.retry(exc=exc)
    finally:
        db.close()
