"""Scan Engine Service — a scan worker with the CLI scanners installed.

This container (see ``Dockerfile.scan``) ships nmap, subfinder, amass and
nuclei, and runs the same durable queue worker as
``python -m app.workers.scan_worker`` against the shared Postgres database.
The API never talks to it directly: it writes jobs to ``scan_jobs`` and any
number of scan-engine replicas pick them up.

A small HTTP app is kept for health checks (Railway / load balancers) and
for backwards-compatible job submission and inspection.
"""
import asyncio
import logging
import os
import secrets
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

# The backend package is at /app/backend inside the container.
_BACKEND_DIR = os.environ.get("BACKEND_DIR", "/app/backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.database import SessionLocal  # noqa: E402
from app.services import job_queue  # noqa: E402
from app.workers.scan_worker import ScanWorker  # noqa: E402

logger = logging.getLogger("scan-engine")

SCAN_ENGINE_SECRET = os.environ.get("SCAN_ENGINE_SECRET", "")

_worker: Optional[ScanWorker] = None


def verify_secret(authorization: str = Header(None)):
    if not SCAN_ENGINE_SECRET:
        raise HTTPException(status_code=503, detail="SCAN_ENGINE_SECRET not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization[len("Bearer "):].strip()
    if not secrets.compare_digest(token, SCAN_ENGINE_SECRET):
        raise HTTPException(status_code=401, detail="Invalid secret")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker
    from app.core.logging import configure_logging

    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    _worker = ScanWorker()
    task = asyncio.create_task(_worker.run(), name="scan-worker")
    logger.info("Scan engine started (worker %s)", _worker.worker_id)
    yield
    _worker.stop()
    try:
        await asyncio.wait_for(task, timeout=60)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task.cancel()
    logger.info("Scan engine stopped")


app = FastAPI(title="CAZO Scan Engine", version="2.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "worker_id": _worker.worker_id if _worker else None,
        "active_jobs": _worker.active_jobs if _worker else 0,
    }


class JobIn(BaseModel):
    scan_id: str = Field(..., min_length=1, max_length=36)
    engine: str = Field(default="v1", pattern="^(v1|v2)$")


@app.post("/jobs", status_code=202)
async def create_job(body: JobIn, _secret: None = Depends(verify_secret)):
    """Queue an existing scan (kept for older API versions that POST here)."""
    from app.models.scan import Scan

    def _enqueue():
        db = SessionLocal()
        try:
            scan = db.query(Scan).filter(Scan.id == body.scan_id).first()
            if not scan:
                return None
            return job_queue.enqueue_scan(db, scan, engine=body.engine, triggered_by="api").id
        finally:
            db.close()

    job_id = await asyncio.to_thread(_enqueue)
    if job_id is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"status": "accepted", "scan_id": body.scan_id, "job_id": job_id}


@app.get("/queue")
async def queue(_secret: None = Depends(verify_secret)):
    def _stats():
        db = SessionLocal()
        try:
            return job_queue.queue_stats(db)
        finally:
            db.close()

    return await asyncio.to_thread(_stats)
