"""Dispatch scans to the appropriate execution backend.

Priority:
1. SCAN_ENGINE_URL set → HTTP POST to the scan engine service (production)
2. USE_CELERY=true → Celery task queue (legacy production)
3. Otherwise → FastAPI BackgroundTasks (local development)
"""

import os
import json
import logging
from typing import Optional

import httpx
from fastapi import BackgroundTasks

from app.config import settings

logger = logging.getLogger(__name__)

# The scan engine service URL. Set this in production to dispatch scans
# to the always-on scan engine container (Railway, etc.).
SCAN_ENGINE_URL = os.environ.get("SCAN_ENGINE_URL", "")
SCAN_ENGINE_SECRET = os.environ.get("SCAN_ENGINE_SECRET", "")


def dispatch_scan(scan_id: str, background_tasks: Optional[BackgroundTasks] = None) -> None:
    """Queue a scan for execution.

    Tiers:
    1. Scan engine service (HTTP POST) — preferred in production
    2. Celery — legacy production fallback
    3. FastAPI BackgroundTasks — local development only
    """
    # Tier 1: Scan engine service
    if SCAN_ENGINE_URL and SCAN_ENGINE_SECRET:
        _dispatch_to_scan_engine(scan_id)
        return

    # Tier 2: Celery
    if settings.USE_CELERY:
        try:
            from app.tasks import execute_scan_task

            execute_scan_task.delay(scan_id)
            logger.info("Dispatched scan %s to Celery", scan_id)
            return
        except Exception:  # noqa: BLE001
            logger.exception("Failed to dispatch scan %s to Celery; falling back", scan_id)

    # Tier 3: FastAPI BackgroundTasks (dev)
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


def _dispatch_to_scan_engine(scan_id: str) -> None:
    """POST scan job to the scan engine service.

    The scan engine inserts the job into the database-backed queue
    and returns HTTP 202. Results are written directly to the shared
    Postgres database by the scan engine.
    """
    from app.database import SessionLocal
    from app.models.scan import Scan

    db = SessionLocal()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            logger.error("Scan %s not found for dispatch", scan_id)
            return

        # Parse scan_options from the scan record
        scan_options = {}
        if scan.scan_options_raw:
            try:
                scan_options = json.loads(scan.scan_options_raw)
            except (json.JSONDecodeError, TypeError):
                scan_options = {}

        payload = {
            "scan_id": scan.id,
            "domain": scan.domain,
            "scan_type": scan.scan_type or "full",
            "scan_options": scan_options,
            "org_id": scan.organization_id or "",
        }

        url = f"{SCAN_ENGINE_URL.rstrip('/')}/jobs"
        headers = {"Authorization": f"Bearer {SCAN_ENGINE_SECRET}"}

        response = httpx.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()

        logger.info(
            "Dispatched scan %s to scan engine (status=%d)",
            scan_id, response.status_code,
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Scan engine rejected scan %s: %d %s",
            scan_id, exc.response.status_code, exc.response.text[:200],
        )
        raise
    except Exception as exc:
        logger.error("Failed to dispatch scan %s to scan engine: %s", scan_id, exc)
        raise
    finally:
        db.close()
