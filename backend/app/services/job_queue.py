"""Durable scan job queue backed by the ``scan_jobs`` table.

Why a database queue: the API and the workers already share Postgres, so a
table gives durable, inspectable, exactly-once job handling without adding a
broker. Workers claim rows with ``SELECT ... FOR UPDATE SKIP LOCKED``, so many
workers can poll at once and never pick the same job.

Lifecycle of a job::

    pending ──claim──▶ running ──complete──▶ completed
       ▲                  │
       │                  ├─fail (attempts left)──▶ pending (available_at = now + backoff)
       │                  ├─fail (no attempts left)─▶ failed
       └──reap (stale heartbeat, attempts left)─┘
    pending/running ──cancel──▶ cancelled

Fair share: a tenant can have at most ``SCAN_MAX_RUNNING_PER_ORG`` jobs running
at once, so one organization cannot fill every worker slot.

SQLite (development and tests) has no row locking; there the claim uses a
guarded ``UPDATE ... WHERE status = 'pending'`` and checks the row count,
which is safe for a single process.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.scan import Scan, ScanJob

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("pending", "running")


@dataclass
class ClaimedJob:
    id: str
    scan_id: str
    domain: str
    scan_type: str
    engine: str
    org_id: str
    attempt: int
    max_attempts: int
    scan_options: dict


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _max_running_per_org() -> int:
    return max(1, int(getattr(settings, "SCAN_MAX_RUNNING_PER_ORG", 2)))


def retry_backoff(attempt: int) -> timedelta:
    """Exponential backoff between attempts: 1, 2, 4, ... minutes, capped at 30."""
    base = int(getattr(settings, "SCAN_RETRY_BASE_SECONDS", 60))
    return timedelta(seconds=min(base * (2 ** max(0, attempt - 1)), 1800))


# ── Producer side ──────────────────────────────────────────────────────


def enqueue_scan(
    db: Session,
    scan: Scan,
    *,
    engine: str = "v1",
    triggered_by: str = "manual",
    priority: int = 0,
    max_attempts: Optional[int] = None,
) -> ScanJob:
    """Queue ``scan`` for execution. Idempotent: an active job is reused."""
    existing = (
        db.query(ScanJob)
        .filter(ScanJob.scan_id == scan.id, ScanJob.status.in_(ACTIVE_STATUSES))
        .first()
    )
    if existing:
        return existing

    job = ScanJob(
        scan_id=scan.id,
        domain=scan.domain,
        scan_type=scan.scan_type or "full",
        scan_options_raw=scan.scan_options_raw or "{}",
        org_id=scan.organization_id or "",
        engine=(engine or "v1").lower(),
        triggered_by=triggered_by,
        status="pending",
        priority=priority,
        attempt=0,
        max_attempts=max_attempts or int(getattr(settings, "SCAN_MAX_ATTEMPTS", 2)),
        available_at=_now(),
    )
    db.add(job)
    if scan.status not in ("pending", "queued"):
        scan.status = "pending"
    db.commit()
    db.refresh(job)
    logger.info("Queued scan %s as job %s (engine=%s, via=%s)", scan.id, job.id, job.engine, triggered_by)
    return job


def cancel_scan_jobs(db: Session, scan_id: str, reason: str = "Cancelled") -> int:
    """Cancel pending jobs for a scan. Running jobs are flagged and stop at the next heartbeat."""
    jobs = (
        db.query(ScanJob)
        .filter(ScanJob.scan_id == scan_id, ScanJob.status.in_(ACTIVE_STATUSES))
        .all()
    )
    for job in jobs:
        job.status = "cancelled"
        job.error_message = reason
        job.completed_at = _now()
    db.commit()
    return len(jobs)


# ── Consumer side ──────────────────────────────────────────────────────


def _row_to_claimed(row) -> ClaimedJob:
    opts = row["scan_options"]
    if isinstance(opts, str):
        try:
            opts = json.loads(opts) if opts else {}
        except (json.JSONDecodeError, TypeError):
            opts = {}
    return ClaimedJob(
        id=row["id"],
        scan_id=row["scan_id"],
        domain=row["domain"],
        scan_type=row["scan_type"] or "full",
        engine=(row["engine"] or "v1").lower(),
        org_id=row["org_id"] or "",
        attempt=int(row["attempt"] or 0),
        max_attempts=int(row["max_attempts"] or 1),
        scan_options=opts or {},
    )


_CLAIM_SELECT = """
    SELECT j.id, j.scan_id, j.domain, j.scan_type, j.scan_options, j.org_id,
           j.engine, j.attempt, j.max_attempts
    FROM scan_jobs j
    WHERE j.status = 'pending'
      AND j.attempt < j.max_attempts
      AND (j.available_at IS NULL OR j.available_at <= :now)
      AND (
        SELECT COUNT(*) FROM scan_jobs r
        WHERE r.status = 'running' AND r.org_id = j.org_id
      ) < :per_org
    ORDER BY j.priority DESC, j.created_at ASC
    LIMIT 1
"""


def claim_next_job(db: Session, worker_id: str) -> Optional[ClaimedJob]:
    """Atomically claim the next runnable job, or return None."""
    now = _now()
    params = {"now": now, "per_org": _max_running_per_org()}

    if _is_postgres(db):
        row = db.execute(
            text(_CLAIM_SELECT + " FOR UPDATE OF j SKIP LOCKED"), params
        ).mappings().first()
        if not row:
            db.rollback()
            return None
        db.execute(
            text(
                "UPDATE scan_jobs SET status = 'running', worker_id = :w, "
                "started_at = :now, heartbeat_at = :now, completed_at = NULL "
                "WHERE id = :id"
            ),
            {"w": worker_id, "now": now, "id": row["id"]},
        )
        db.commit()
        return _row_to_claimed(row)

    # SQLite / other: optimistic guarded update.
    for _ in range(5):
        row = db.execute(text(_CLAIM_SELECT), params).mappings().first()
        if not row:
            db.rollback()
            return None
        result = db.execute(
            text(
                "UPDATE scan_jobs SET status = 'running', worker_id = :w, "
                "started_at = :now, heartbeat_at = :now, completed_at = NULL "
                "WHERE id = :id AND status = 'pending'"
            ),
            {"w": worker_id, "now": now, "id": row["id"]},
        )
        db.commit()
        if result.rowcount == 1:
            return _row_to_claimed(row)
    return None


def heartbeat(db: Session, job_id: str, worker_id: str) -> bool:
    """Refresh the job's heartbeat. Returns False if the job was cancelled or taken over."""
    result = db.execute(
        text(
            "UPDATE scan_jobs SET heartbeat_at = :now "
            "WHERE id = :id AND status = 'running' AND worker_id = :w"
        ),
        {"now": _now(), "id": job_id, "w": worker_id},
    )
    db.commit()
    return result.rowcount == 1


def complete_job(db: Session, job_id: str) -> None:
    db.execute(
        text(
            "UPDATE scan_jobs SET status = 'completed', completed_at = :now, error_message = NULL "
            "WHERE id = :id AND status = 'running'"
        ),
        {"now": _now(), "id": job_id},
    )
    db.commit()


def fail_job(db: Session, job: ClaimedJob, error: str, *, retryable: bool = True) -> str:
    """Record a failed attempt. Returns the job's new status ('pending' or 'failed')."""
    next_attempt = job.attempt + 1
    error = (error or "Scan failed")[:2000]
    if retryable and next_attempt < job.max_attempts:
        db.execute(
            text(
                "UPDATE scan_jobs SET status = 'pending', attempt = :a, worker_id = NULL, "
                "started_at = NULL, heartbeat_at = NULL, available_at = :avail, error_message = :err "
                "WHERE id = :id AND status = 'running'"
            ),
            {"a": next_attempt, "avail": _now() + retry_backoff(next_attempt), "err": error, "id": job.id},
        )
        db.execute(
            text("UPDATE scans SET status = 'pending', error_message = :err WHERE id = :sid"),
            {"err": f"Retrying after error: {error}"[:2000], "sid": job.scan_id},
        )
        db.commit()
        return "pending"

    db.execute(
        text(
            "UPDATE scan_jobs SET status = 'failed', attempt = :a, completed_at = :now, error_message = :err "
            "WHERE id = :id AND status = 'running'"
        ),
        {"a": next_attempt, "now": _now(), "err": error, "id": job.id},
    )
    db.execute(
        text(
            "UPDATE scans SET status = 'failed', error_message = :err, completed_at = :now "
            "WHERE id = :sid AND status <> 'completed'"
        ),
        {"err": error, "now": _now(), "sid": job.scan_id},
    )
    db.commit()
    return "failed"


def release_job(db: Session, job_id: str, scan_id: str) -> None:
    """Put a job back in the queue without using an attempt (graceful shutdown)."""
    db.execute(
        text(
            "UPDATE scan_jobs SET status = 'pending', worker_id = NULL, started_at = NULL, "
            "heartbeat_at = NULL, available_at = :now WHERE id = :id AND status = 'running'"
        ),
        {"now": _now(), "id": job_id},
    )
    db.execute(
        text("UPDATE scans SET status = 'pending' WHERE id = :sid AND status = 'running'"),
        {"sid": scan_id},
    )
    db.commit()


def reap_stale_jobs(db: Session, stale_after: Optional[timedelta] = None) -> int:
    """Recover jobs whose worker stopped sending heartbeats (crash, OOM, deploy)."""
    stale_after = stale_after or timedelta(
        seconds=int(getattr(settings, "SCAN_JOB_STALE_SECONDS", 300))
    )
    cutoff = _now() - stale_after
    stale = (
        db.query(ScanJob)
        .filter(ScanJob.status == "running")
        .filter((ScanJob.heartbeat_at.is_(None)) | (ScanJob.heartbeat_at < cutoff))
        .filter((ScanJob.started_at.is_(None)) | (ScanJob.started_at < cutoff))
        .all()
    )
    for job in stale:
        claimed = ClaimedJob(
            id=job.id, scan_id=job.scan_id, domain=job.domain, scan_type=job.scan_type,
            engine=job.engine or "v1", org_id=job.org_id or "", attempt=job.attempt or 0,
            max_attempts=job.max_attempts or 1, scan_options={},
        )
        new_status = fail_job(
            db, claimed, f"Worker {job.worker_id or '?'} stopped responding", retryable=True
        )
        logger.warning("Reaped stale job %s (scan %s) -> %s", job.id, job.scan_id, new_status)
    return len(stale)


def queue_stats(db: Session) -> dict:
    """Counts by status plus the age of the oldest pending job, for health checks."""
    rows = db.execute(text("SELECT status, COUNT(*) FROM scan_jobs GROUP BY status")).all()
    counts = {status: int(n) for status, n in rows}
    oldest = db.execute(
        text("SELECT MIN(created_at) FROM scan_jobs WHERE status = 'pending'")
    ).scalar()
    oldest_age = None
    if oldest is not None:
        if isinstance(oldest, str):
            try:
                oldest = datetime.fromisoformat(oldest)
            except ValueError:
                oldest = None
        if oldest is not None:
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
            oldest_age = int((_now() - oldest).total_seconds())
    return {"counts": counts, "oldest_pending_seconds": oldest_age}
