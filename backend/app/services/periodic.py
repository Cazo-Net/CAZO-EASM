"""Periodic jobs run by scan workers: scheduled scans and maintenance tasks.

Every worker calls :func:`run_periodic_tasks` on each loop. A job only runs
when its interval has passed *and* the worker wins the row lock in
``periodic_task_state``, so adding workers never duplicates a job.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Lease-based "run at most once per interval" lock ───────────────────


def try_acquire(db: Session, name: str, interval: timedelta, worker_id: str,
                lease: timedelta = timedelta(minutes=30)) -> bool:
    """Claim periodic job ``name`` if it is due and nobody else holds it."""
    from app.models.periodic_task import PeriodicTaskState

    now = _now()
    if db.get(PeriodicTaskState, name) is None:
        try:
            db.add(PeriodicTaskState(name=name))
            db.commit()
        except IntegrityError:
            db.rollback()

    row = db.get(PeriodicTaskState, name)
    db.refresh(row)
    last_run = _as_aware(row.last_run_at)
    locked_until = _as_aware(row.locked_until)
    if last_run is not None and last_run > now - interval:
        db.rollback()
        return False
    if locked_until is not None and locked_until > now:
        db.rollback()
        return False

    # Compare-and-set on the values we just read, so two workers racing on
    # the same row cannot both win.
    result = db.execute(
        text(
            "UPDATE periodic_task_state SET locked_until = :until, locked_by = :w "
            "WHERE name = :n "
            "AND ((:lr IS NULL AND last_run_at IS NULL) OR last_run_at = :lr) "
            "AND ((:lu IS NULL AND locked_until IS NULL) OR locked_until = :lu)"
        ),
        {"until": now + lease, "w": worker_id, "n": name,
         "lr": row.last_run_at, "lu": row.locked_until},
    )
    db.commit()
    return result.rowcount == 1


def mark_done(db: Session, name: str) -> None:
    db.execute(
        text("UPDATE periodic_task_state SET last_run_at = :now, locked_until = NULL WHERE name = :n"),
        {"now": _now(), "n": name},
    )
    db.commit()


def release(db: Session, name: str, retry_in: timedelta = timedelta(minutes=15)) -> None:
    """After a failure, keep the lease until ``retry_in`` so a broken job is
    retried later instead of on every worker loop."""
    db.execute(
        text("UPDATE periodic_task_state SET locked_until = :until WHERE name = :n"),
        {"until": _now() + retry_in, "n": name},
    )
    db.commit()


# ── Scheduled (continuous monitoring) scans ────────────────────────────


def default_engine() -> str:
    import os

    return os.environ.get("SCAN_ENGINE", "v2").lower()


def run_due_schedules(db: Session, limit: int = 50) -> int:
    """Turn every due ``monitor_schedules`` row into a real, queued scan.

    Previously the in-process scheduler ran the scan inline in the web
    process and only logged the risk score; nothing was saved. Now each due
    schedule creates a normal ``Scan`` row (so results show up in the UI,
    history and change tracking) and a durable job.
    """
    from app.core.scope import authorize_scan_target
    from app.models.scan import Scan
    from app.models.v2_scanner import MonitorSchedule
    from app.services.audit import log_event
    from app.services.job_queue import enqueue_scan

    now = _now()
    q = (
        db.query(MonitorSchedule)
        .filter(MonitorSchedule.enabled.is_(True))
        .filter((MonitorSchedule.next_run_at.is_(None)) | (MonitorSchedule.next_run_at <= now))
        .order_by(MonitorSchedule.next_run_at)
        .limit(limit)
    )
    if db.get_bind().dialect.name == "postgresql":
        q = q.with_for_update(skip_locked=True)
    due = q.all()

    # Claim first: move next_run_at forward and commit, so no other worker
    # picks these rows even if creating the scan below fails.
    claimed = []
    for sched in due:
        hours = max(1, int(sched.interval_hours or 24))
        sched.last_run_at = now
        sched.next_run_at = now + timedelta(hours=hours)
        sched.updated_at = now
        claimed.append((sched.id, sched.domain, sched.scan_type, sched.organization_id,
                        sched.created_by, sched.project_id))
    db.commit()

    created = 0
    for sched_id, domain, scan_type, org_id, user_id, project_id in claimed:
        try:
            auth = authorize_scan_target(db, org_id, domain, actor_id=user_id, auto_register=False)
            if not auth.authorized:
                logger.warning("Skipping scheduled scan %s for %s: %s", sched_id, domain, auth.reason)
                if org_id:
                    log_event(
                        db, action="scan.schedule.denied", organization_id=org_id, actor_id=user_id,
                        target_type="domain", target_id=domain, status="denied",
                        detail={"schedule_id": sched_id, "reason": auth.reason},
                    )
                continue
            engine = default_engine()
            scan = Scan(
                domain=auth.target,
                scan_type=scan_type or "quick",
                created_by=user_id,
                organization_id=org_id,
                project_id=project_id,
                engine=engine,
                status="pending",
            )
            db.add(scan)
            db.commit()
            db.refresh(scan)
            enqueue_scan(db, scan, engine=engine, triggered_by="schedule")
            created += 1
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("Failed to start scheduled scan %s for %s", sched_id, domain)
    if created:
        logger.info("Queued %d scheduled scan(s)", created)
    return created


# ── Maintenance jobs (formerly Celery beat) ────────────────────────────


@dataclass
class PeriodicJob:
    name: str
    interval: timedelta
    func: Callable[[], object]


def _ssl_expiry():
    from app.tasks import check_ssl_expiry
    check_ssl_expiry()


def _weekly_digest():
    from app.tasks import send_weekly_digest
    send_weekly_digest()


def _cve_sync():
    from app.tasks import sync_cve_database
    sync_cve_database()


MAINTENANCE_JOBS: List[PeriodicJob] = [
    PeriodicJob("check_ssl_expiry", timedelta(days=1), _ssl_expiry),
    PeriodicJob("send_weekly_digest", timedelta(days=7), _weekly_digest),
    PeriodicJob("sync_cve_database", timedelta(days=7), _cve_sync),
]

SCHEDULE_TICK = timedelta(seconds=60)


def run_periodic_tasks(db: Session, worker_id: str, jobs: Optional[List[PeriodicJob]] = None) -> List[str]:
    """Run whichever periodic jobs are due. Returns the names that ran."""
    if not getattr(settings, "RUN_PERIODIC_TASKS", True):
        return []
    ran: List[str] = []

    if try_acquire(db, "scheduled_scans", SCHEDULE_TICK, worker_id, lease=timedelta(minutes=5)):
        try:
            run_due_schedules(db)
            mark_done(db, "scheduled_scans")
            ran.append("scheduled_scans")
        except Exception:  # noqa: BLE001
            db.rollback()
            release(db, "scheduled_scans", retry_in=timedelta(minutes=1))
            logger.exception("Scheduled-scan tick failed")

    for job in (MAINTENANCE_JOBS if jobs is None else jobs):
        if not try_acquire(db, job.name, job.interval, worker_id):
            continue
        try:
            job.func()
            mark_done(db, job.name)
            ran.append(job.name)
        except Exception:  # noqa: BLE001
            db.rollback()
            release(db, job.name)
            logger.exception("Periodic job %s failed", job.name)
    return ran
