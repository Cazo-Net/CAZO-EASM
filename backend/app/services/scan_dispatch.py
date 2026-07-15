"""Dispatch scans either to Celery (production) or FastAPI BackgroundTasks (dev).

Keeps the API layer agnostic to the execution backend.
"""

import logging
from typing import Optional

from fastapi import BackgroundTasks

from app.config import settings

logger = logging.getLogger(__name__)


def dispatch_scan(scan_id: str, background_tasks: Optional[BackgroundTasks] = None) -> None:
    """Queue a scan for execution.

    Uses Celery when USE_CELERY is enabled; otherwise falls back to in-process
    FastAPI background tasks (suitable for local development only).
    """
    if settings.USE_CELERY:
        try:
            from app.tasks import execute_scan_task

            execute_scan_task.delay(scan_id)
            logger.info("Dispatched scan %s to Celery", scan_id)
            return
        except Exception:  # noqa: BLE001
            logger.exception("Failed to dispatch scan %s to Celery; falling back", scan_id)

    if background_tasks is not None:
        from app.database import SessionLocal
        from app.services.scan_service import ScanService

        async def _run():
            db = SessionLocal()
            try:
                await ScanService(db).execute_scan(scan_id)
            finally:
                db.close()

        background_tasks.add_task(_run)
        logger.info("Dispatched scan %s to background task", scan_id)
    else:
        raise RuntimeError("No execution backend available for scan dispatch")
