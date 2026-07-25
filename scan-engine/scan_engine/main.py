"""Scan Engine Service — minimal FastAPI app for running scans.

This service runs as a separate always-on process (e.g., on Railway).
It polls a database-backed job queue, executes scans using the same
scanner modules as the main backend, and writes results directly to
the shared Postgres database.
"""
import os
import sys
import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Header
from sqlalchemy import text
from sqlalchemy.orm import Session

# The backend directory is mounted at /app/backend inside the container.
# We add it to sys.path so we can import scanner modules, models, and config.
_BACKEND_DIR = os.environ.get("BACKEND_DIR", "/app/backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.config import settings
from app.database import get_db, SessionLocal, init_db

logger = logging.getLogger("scan-engine")

# ── Config ─────────────────────────────────────────────────────────

SCAN_ENGINE_SECRET = os.environ.get("SCAN_ENGINE_SECRET", "")
WORKER_ID = os.environ.get("WORKER_ID", f"worker-{os.getpid()}")
MAX_CONCURRENT_SCANS = int(os.environ.get("MAX_CONCURRENT_SCANS", "3"))

# Timeout per scan type in minutes
SCAN_TIMEOUTS = {
    "quick": 5,
    "full": 20,
    "custom": 45,
}

if not SCAN_ENGINE_SECRET:
    logger.warning("SCAN_ENGINE_SECRET not set — service will reject all authenticated requests")


# ── Auth ───────────────────────────────────────────────────────────

def verify_secret(authorization: str = Header(None)):
    """Verify the shared secret from the Vercel API."""
    if not SCAN_ENGINE_SECRET:
        raise HTTPException(status_code=500, detail="SCAN_ENGINE_SECRET not configured")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.replace("Bearer ", "").strip()
    if not secrets.compare_digest(token, SCAN_ENGINE_SECRET):
        raise HTTPException(status_code=401, detail="Invalid secret")


# ── Job Queue ──────────────────────────────────────────────────────

def get_running_job_count(db: Session) -> int:
    """Count currently running jobs for concurrency control."""
    result = db.execute(
        text("SELECT COUNT(*) FROM scan_jobs WHERE status = 'running'")
    ).scalar()
    return result or 0


def acquire_next_job(db: Session) -> dict | None:
    """Pick up the next pending job using SELECT FOR UPDATE SKIP LOCKED.

    This guarantees exactly-once execution even with multiple scan engine
    replicas running concurrently. SKIP LOCKED causes the database to skip
    any row that another transaction has locked, so two workers never
    pick up the same job.
    """
    # Check concurrency limit first
    if get_running_job_count(db) >= MAX_CONCURRENT_SCANS:
        return None

    result = db.execute(
        text("""
            SELECT id, scan_id, domain, scan_type, scan_options, org_id, attempt
            FROM scan_jobs
            WHERE status = 'pending'
              AND attempt < max_attempts
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
    ).mappings().first()

    if not result:
        return None

    job_id = result["id"]
    db.execute(
        text("""
            UPDATE scan_jobs
            SET status = 'running',
                started_at = NOW(),
                worker_id = :worker_id
            WHERE id = :job_id
        """),
        {"worker_id": WORKER_ID, "job_id": job_id},
    )
    db.commit()

    return dict(result)


def complete_job(db: Session, job_id: str, success: bool, error_message: str = None):
    """Mark a job as completed or failed."""
    status = "completed" if success else "failed"
    db.execute(
        text("""
            UPDATE scan_jobs
            SET status = :status,
                completed_at = NOW(),
                error_message = :error_message
            WHERE id = :job_id
        """),
        {"status": status, "error_message": error_message, "job_id": job_id},
    )
    db.commit()


def reap_stuck_jobs(db: Session) -> int:
    """Recover jobs stuck in 'running' status past their timeout.

    Called on startup and periodically. Resets retryable jobs to 'pending'
    and marks exhausted jobs as 'failed'. Also updates the parent scans
    table so the UI doesn't show stale "running" status.
    Returns total jobs reaped.
    """
    total_reaped = 0
    for scan_type, timeout_minutes in SCAN_TIMEOUTS.items():
        result = db.execute(
            text("""
                UPDATE scan_jobs
                SET status = CASE
                    WHEN attempt < max_attempts - 1 THEN 'pending'
                    ELSE 'failed'
                END,
                    attempt = CASE
                        WHEN attempt < max_attempts - 1 THEN attempt + 1
                        ELSE attempt
                    END,
                    error_message = CASE
                        WHEN attempt >= max_attempts - 1 THEN 'Timed out after max retries'
                        ELSE 'Timed out, retrying (attempt ' || (attempt + 1) || ')'
                    END,
                    worker_id = NULL,
                    started_at = NULL
                WHERE status = 'running'
                  AND scan_type = :scan_type
                  AND started_at < NOW() - INTERVAL '1 minute' * :timeout_minutes
                RETURNING id, scan_id, domain, attempt, status
            """),
            {"scan_type": scan_type, "timeout_minutes": timeout_minutes},
        )
        recovered = result.fetchall()
        for row in recovered:
            job_id, scan_id, domain, attempt, new_status = row[0], row[1], row[2], row[3], row[4]
            logger.warning(
                "Reaped stuck job %s (scan %s, domain %s, attempt %d) -> %s",
                job_id, scan_id, domain, attempt, new_status,
            )
            # Sync parent scan status when job is permanently failed
            if new_status == "failed" and scan_id:
                db.execute(
                    text("""
                        UPDATE scans
                        SET status = 'failed',
                            error_message = :error_message,
                            completed_at = NOW()
                        WHERE id = :scan_id
                          AND status = 'running'
                    """),
                    {"scan_id": scan_id, "error_message": f"Timed out after max retries (scan type: {scan_type})"},
                )
        total_reaped += len(recovered)
    db.commit()
    return total_reaped


# ── Scan Execution ─────────────────────────────────────────────────

async def run_scan_job(job: dict):
    """Execute a scan job end-to-end. Runs as an asyncio task."""
    from app.scanners.runner import ScanRunner
    from app.services.scan_service import ScanService

    scan_id = job["scan_id"]
    domain = job["domain"]
    scan_type = job["scan_type"]
    scan_options = job.get("scan_options", {})
    if isinstance(scan_options, str):
        import json
        scan_options = json.loads(scan_options)
    job_id = job["id"]

    db = SessionLocal()
    try:
        # Update scan status to running
        db.execute(
            text("UPDATE scans SET status = 'running', started_at = NOW() WHERE id = :scan_id"),
            {"scan_id": scan_id},
        )
        db.commit()

        runner = ScanRunner()

        async def progress_callback(pct, message):
            db.execute(
                text("UPDATE scans SET progress = :pct WHERE id = :scan_id"),
                {"pct": pct, "scan_id": scan_id},
            )
            db.commit()

        if scan_type == "quick":
            results = await runner.run_quick_scan(domain, progress_callback=progress_callback)
        else:
            results = await runner.run_full_scan(
                domain,
                progress_callback=progress_callback,
                options=scan_options,
            )

        # Store results to database
        service = ScanService(db)
        await service.store_results(scan_id, results)

        # Mark the scan as completed
        db.execute(
            text("UPDATE scans SET status = 'completed', progress = 100, completed_at = NOW() WHERE id = :scan_id"),
            {"scan_id": scan_id},
        )
        db.commit()

        complete_job(db, job_id, success=True)
        logger.info("Scan %s completed for domain %s", scan_id, domain)

    except Exception as exc:
        logger.error("Scan %s failed: %s", scan_id, exc)
        complete_job(db, job_id, success=False, error_message=str(exc))
        db.execute(
            text("UPDATE scans SET status = 'failed', error_message = :err WHERE id = :scan_id"),
            {"err": str(exc), "scan_id": scan_id},
        )
        db.commit()
    finally:
        db.close()


# ── Background Worker Loop ─────────────────────────────────────────

async def worker_loop():
    """Continuously poll for jobs and execute them."""
    logger.info("Worker loop started (id=%s, max_concurrent=%d)", WORKER_ID, MAX_CONCURRENT_SCANS)

    # Run reaper on startup
    db = SessionLocal()
    try:
        reaped = reap_stuck_jobs(db)
        if reaped:
            logger.info("Reaper recovered %d stuck jobs on startup", reaped)
    finally:
        db.close()

    while True:
        db = SessionLocal()
        try:
            job = acquire_next_job(db)
            if job:
                logger.info(
                    "Acquired job %s: scan %s (%s) for %s",
                    job["id"], job["scan_id"], job["scan_type"], job["domain"],
                )
                asyncio.create_task(run_scan_job(job))
            else:
                await asyncio.sleep(5)
        except Exception as exc:
            logger.error("Worker loop error: %s", exc)
            await asyncio.sleep(10)
        finally:
            db.close()


# ── App Lifecycle ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the worker loop on application startup."""
    init_db()
    worker_task = asyncio.create_task(worker_loop())
    logger.info("Scan engine service started")
    yield
    worker_task.cancel()
    logger.info("Scan engine service stopping")


app = FastAPI(
    title="CAZO Scan Engine",
    version="1.0.0",
    lifespan=lifespan,
)


# ── API Endpoints ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check for Railway / load balancer."""
    return {"status": "healthy", "worker_id": WORKER_ID}


@app.post("/jobs")
async def create_job(
    scan_id: str,
    domain: str,
    scan_type: str = "full",
    scan_options: dict = None,
    org_id: str = "",
    _secret: str = Depends(verify_secret),
    db: Session = Depends(get_db),
):
    """Accept a scan job from the Vercel API.

    Inserts a row into the job queue. The worker loop picks it up.
    """
    import json as _json

    db.execute(
        text("""
            INSERT INTO scan_jobs (scan_id, domain, scan_type, scan_options, org_id)
            VALUES (:scan_id, :domain, :scan_type, :scan_options, :org_id)
            RETURNING id
        """),
        {
            "scan_id": scan_id,
            "domain": domain,
            "scan_type": scan_type,
            "scan_options": _json.dumps(scan_options or {}),
            "org_id": org_id,
        },
    )
    db.commit()
    return {"status": "accepted", "scan_id": scan_id}


@app.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    _secret: str = Depends(verify_secret),
    db: Session = Depends(get_db),
):
    """Check job status."""
    result = db.execute(
        text("SELECT * FROM scan_jobs WHERE id = :job_id"),
        {"job_id": job_id},
    ).mappings().first()
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(result)


@app.post("/reaper")
async def trigger_reaper(
    _secret: str = Depends(verify_secret),
    db: Session = Depends(get_db),
):
    """Manually trigger the reaper (for admin use)."""
    reaped = reap_stuck_jobs(db)
    return {"status": "reaper completed", "jobs_reaped": reaped}
