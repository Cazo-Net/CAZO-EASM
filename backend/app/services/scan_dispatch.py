"""Hand a newly created scan to whatever executes scans.

``SCAN_EXECUTION_MODE`` picks the backend:

* ``queue`` (production default) — write a durable row to ``scan_jobs``.
  Scan workers (``python -m app.workers.scan_worker``, or the scan-engine
  container, or ``RUN_EMBEDDED_WORKER=true`` inside the API) pick it up.
  Scans survive restarts and deploys, are retried, and never run inside a
  web request.
* ``inline`` (development default) — run in the API process with FastAPI
  BackgroundTasks. Simple, but a restart loses the scan.
* ``celery`` — legacy Celery queue (needs a Celery worker and Redis).

The old "POST to the scan engine" and QStash paths are gone: the first sent a
JSON body to an endpoint that expected query parameters (every request was
rejected), and the second called back to an endpoint that did not exist. The
scan-engine container now simply runs a queue worker against the shared
database.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import BackgroundTasks

from app.config import settings, is_production

logger = logging.getLogger(__name__)

# Default engine for new scans: "v1" (legacy) or "v2" (enterprise pipeline).
SCAN_ENGINE_VERSION = os.environ.get("SCAN_ENGINE", "v2").lower()

EXECUTION_MODES = ("queue", "inline", "celery")


def execution_mode() -> str:
    mode = (getattr(settings, "SCAN_EXECUTION_MODE", "") or "").strip().lower()
    if mode in EXECUTION_MODES:
        return mode
    if settings.USE_CELERY:
        return "celery"
    return "queue" if is_production() else "inline"


def get_active_engine() -> str:
    """Return the default scanner engine version."""
    return SCAN_ENGINE_VERSION


def _load_scan(scan_id: str, db=None):
    from app.models.scan import Scan

    if db is not None:
        return db, False, db.query(Scan).filter(Scan.id == scan_id).first()
    from app.database import SessionLocal

    own = SessionLocal()
    return own, True, own.query(Scan).filter(Scan.id == scan_id).first()


def _dispatch(scan_id: str, engine: str, background_tasks: Optional[BackgroundTasks],
              triggered_by: str, db=None) -> str:
    mode = execution_mode()

    if mode == "queue":
        from app.services.job_queue import enqueue_scan

        session, owned, scan = _load_scan(scan_id, db)
        try:
            if not scan:
                raise ValueError(f"Scan not found: {scan_id}")
            enqueue_scan(session, scan, engine=engine, triggered_by=triggered_by)
        finally:
            if owned:
                session.close()
        return "queue"

    if mode == "celery":
        try:
            if engine == "v2":
                from app.tasks import execute_scan_task_v2 as task
            else:
                from app.tasks import execute_scan_task as task
            task.delay(scan_id)
            logger.info("Dispatched scan %s to Celery (%s)", scan_id, engine)
            return "celery"
        except Exception:  # noqa: BLE001
            logger.exception("Celery dispatch failed for scan %s; falling back to inline", scan_id)

    if background_tasks is None:
        raise RuntimeError("Inline scan execution needs FastAPI BackgroundTasks")

    async def _run():
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            if engine == "v2":
                from app.services.scan_service_v2 import ScanServiceV2
                await ScanServiceV2(session).execute_scan(scan_id)
            else:
                from app.services.scan_service import ScanService
                await ScanService(session).execute_scan(scan_id)
        finally:
            session.close()

    background_tasks.add_task(_run)
    logger.info("Running scan %s inline in the API process (%s)", scan_id, engine)
    return "inline"


def dispatch_scan(scan_id: str, background_tasks: Optional[BackgroundTasks] = None, *,
                  triggered_by: str = "manual", db=None) -> str:
    """Queue a scan for the v1 engine. Returns the backend used."""
    return _dispatch(scan_id, "v1", background_tasks, triggered_by, db)


def dispatch_scan_v2(scan_id: str, background_tasks: Optional[BackgroundTasks] = None, *,
                     triggered_by: str = "manual", db=None) -> str:
    """Queue a scan for the v2 engine. Returns the backend used."""
    return _dispatch(scan_id, "v2", background_tasks, triggered_by, db)
