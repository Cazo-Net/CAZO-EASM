"""Durable scan queue, scan worker and periodic jobs."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models.organization import Organization
from app.models.scan import Scan, ScanJob
from app.models.scope import AuthorizedScope
from app.models.user import User
from app.services import job_queue
from tests.conftest import TestingSessionLocal


@pytest.fixture
def org_and_user(db_session):
    org = Organization(id=str(uuid.uuid4()), name="Acme", slug=f"acme-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()
    user = User(
        id=str(uuid.uuid4()), email=f"{uuid.uuid4().hex[:8]}@acme.test",
        hashed_password="x", full_name="A", organization_id=org.id, role="admin",
    )
    db_session.add(user)
    db_session.commit()
    return org, user


def _scan(db, org, user, domain="example.com", scan_type="quick"):
    scan = Scan(domain=domain, scan_type=scan_type, organization_id=org.id,
                created_by=user.id, status="pending", engine="v1")
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


@pytest.fixture
def open_scope(monkeypatch):
    monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "open")
    monkeypatch.setattr("app.core.target_guard.resolve_host", lambda host, timeout=4.0: ["93.184.215.14"])


# ── Queue primitives ──────────────────────────────────────────────────


def test_enqueue_is_idempotent_and_claim_marks_running(db_session, org_and_user):
    org, user = org_and_user
    scan = _scan(db_session, org, user)
    j1 = job_queue.enqueue_scan(db_session, scan, engine="v2")
    j2 = job_queue.enqueue_scan(db_session, scan, engine="v2")
    assert j1.id == j2.id
    assert db_session.query(ScanJob).count() == 1

    claimed = job_queue.claim_next_job(db_session, "w1")
    assert claimed and claimed.scan_id == scan.id and claimed.engine == "v2"
    assert job_queue.claim_next_job(db_session, "w2") is None  # nothing left

    db_session.expire_all()
    job = db_session.get(ScanJob, j1.id)
    assert job.status == "running" and job.worker_id == "w1" and job.heartbeat_at is not None

    job_queue.complete_job(db_session, j1.id)
    db_session.expire_all()
    assert db_session.get(ScanJob, j1.id).status == "completed"


def test_failure_retries_with_backoff_then_fails(db_session, org_and_user, monkeypatch):
    monkeypatch.setattr(settings, "SCAN_RETRY_BASE_SECONDS", 0)
    org, user = org_and_user
    scan = _scan(db_session, org, user)
    job_queue.enqueue_scan(db_session, scan, max_attempts=2)

    c = job_queue.claim_next_job(db_session, "w")
    assert job_queue.fail_job(db_session, c, "boom") == "pending"
    db_session.expire_all()
    assert db_session.get(Scan, scan.id).status == "pending"

    c = job_queue.claim_next_job(db_session, "w")
    assert c is not None and c.attempt == 1
    assert job_queue.fail_job(db_session, c, "boom again") == "failed"
    db_session.expire_all()
    s = db_session.get(Scan, scan.id)
    assert s.status == "failed" and "boom again" in s.error_message


def test_backoff_delays_next_claim(db_session, org_and_user, monkeypatch):
    monkeypatch.setattr(settings, "SCAN_RETRY_BASE_SECONDS", 3600)
    org, user = org_and_user
    job_queue.enqueue_scan(db_session, _scan(db_session, org, user), max_attempts=3)
    c = job_queue.claim_next_job(db_session, "w")
    job_queue.fail_job(db_session, c, "transient")
    assert job_queue.claim_next_job(db_session, "w") is None  # not available for an hour


def test_per_org_fair_share(db_session, org_and_user, monkeypatch):
    monkeypatch.setattr(settings, "SCAN_MAX_RUNNING_PER_ORG", 1)
    org, user = org_and_user
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"other-{uuid.uuid4().hex[:6]}")
    db_session.add(other)
    db_session.commit()
    for d in ("a.example.com", "b.example.com"):
        job_queue.enqueue_scan(db_session, _scan(db_session, org, user, d))
    other_scan = Scan(domain="c.example.org", organization_id=other.id, created_by=user.id, status="pending")
    db_session.add(other_scan)
    db_session.commit()
    job_queue.enqueue_scan(db_session, other_scan)

    first = job_queue.claim_next_job(db_session, "w")
    second = job_queue.claim_next_job(db_session, "w")
    third = job_queue.claim_next_job(db_session, "w")
    # Each tenant gets one slot; acme's second job waits for its first.
    assert {first.org_id, second.org_id} == {org.id, other.id}
    assert third is None


def test_reaper_recovers_jobs_from_dead_workers(db_session, org_and_user):
    org, user = org_and_user
    job = job_queue.enqueue_scan(db_session, _scan(db_session, org, user), max_attempts=2)
    job_queue.claim_next_job(db_session, "dead-worker")
    old = datetime.now(timezone.utc) - timedelta(hours=1)
    row = db_session.get(ScanJob, job.id)
    row.heartbeat_at = old
    row.started_at = old
    db_session.commit()

    assert job_queue.reap_stale_jobs(db_session, timedelta(minutes=5)) == 1
    db_session.expire_all()
    row = db_session.get(ScanJob, job.id)
    assert row.status == "pending" and row.attempt == 1


def test_cancel_pending_job_and_heartbeat_detects_cancel(db_session, org_and_user):
    org, user = org_and_user
    scan = _scan(db_session, org, user)
    job = job_queue.enqueue_scan(db_session, scan)
    job_queue.claim_next_job(db_session, "w")
    assert job_queue.heartbeat(db_session, job.id, "w") is True
    assert job_queue.cancel_scan_jobs(db_session, scan.id) == 1
    assert job_queue.heartbeat(db_session, job.id, "w") is False


def test_queue_stats(db_session, org_and_user):
    org, user = org_and_user
    job_queue.enqueue_scan(db_session, _scan(db_session, org, user))
    stats = job_queue.queue_stats(db_session)
    assert stats["counts"].get("pending") == 1
    assert stats["oldest_pending_seconds"] is not None


# ── Worker ────────────────────────────────────────────────────────────


def _run_worker_until_idle(worker):
    async def go():
        await worker.tick()
        await worker.drain()
    asyncio.run(go())


def test_worker_runs_job_to_completion(db_session, org_and_user, open_scope):
    from app.workers.scan_worker import ScanWorker

    org, user = org_and_user
    scan = _scan(db_session, org, user)
    job = job_queue.enqueue_scan(db_session, scan)
    ran = []

    async def executor(j):
        ran.append(j.scan_id)

    _run_worker_until_idle(ScanWorker(concurrency=2, worker_id="t", executor=executor, run_periodic=False))
    assert ran == [scan.id]
    db_session.expire_all()
    assert db_session.get(ScanJob, job.id).status == "completed"


def test_worker_retries_failed_scan(db_session, org_and_user, open_scope, monkeypatch):
    from app.workers.scan_worker import ScanWorker

    monkeypatch.setattr(settings, "SCAN_RETRY_BASE_SECONDS", 0)
    org, user = org_and_user
    scan = _scan(db_session, org, user)
    job = job_queue.enqueue_scan(db_session, scan, max_attempts=2)

    async def executor(j):
        raise RuntimeError("scanner crashed")

    w = ScanWorker(worker_id="t", executor=executor, run_periodic=False)
    _run_worker_until_idle(w)
    db_session.expire_all()
    assert db_session.get(ScanJob, job.id).status == "pending"
    _run_worker_until_idle(w)
    db_session.expire_all()
    assert db_session.get(ScanJob, job.id).status == "failed"
    assert db_session.get(Scan, scan.id).status == "failed"


def test_worker_enforces_time_limit(db_session, org_and_user, open_scope, monkeypatch):
    from app.workers import scan_worker
    from app.workers.scan_worker import ScanWorker

    monkeypatch.setattr(scan_worker, "scan_timeout_seconds", lambda scan_type: 0.2)
    org, user = org_and_user
    scan = _scan(db_session, org, user)
    job = job_queue.enqueue_scan(db_session, scan, max_attempts=1)

    async def executor(j):
        await asyncio.sleep(10)

    _run_worker_until_idle(ScanWorker(worker_id="t", executor=executor, run_periodic=False))
    db_session.expire_all()
    assert db_session.get(ScanJob, job.id).status == "failed"
    assert "timed out" in db_session.get(Scan, scan.id).error_message


def test_worker_refuses_target_that_left_scope(db_session, org_and_user, monkeypatch):
    """Scope is re-checked right before running: a revoked scope stops the scan."""
    from app.workers.scan_worker import ScanWorker

    monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "verified")
    monkeypatch.setattr("app.core.target_guard.resolve_host", lambda host, timeout=4.0: [])
    org, user = org_and_user
    scan = _scan(db_session, org, user)
    job = job_queue.enqueue_scan(db_session, scan)
    ran = []

    async def executor(j):
        ran.append(j)

    _run_worker_until_idle(ScanWorker(worker_id="t", executor=executor, run_periodic=False))
    assert ran == []
    db_session.expire_all()
    assert db_session.get(ScanJob, job.id).status == "failed"
    assert "Not authorized" in db_session.get(Scan, scan.id).error_message


def test_worker_stops_scan_when_cancelled(db_session, org_and_user, open_scope, monkeypatch):
    from app.workers.scan_worker import ScanWorker

    monkeypatch.setattr(settings, "SCAN_HEARTBEAT_SECONDS", 1)
    org, user = org_and_user
    scan = _scan(db_session, org, user)
    job_queue.enqueue_scan(db_session, scan)

    async def executor(j):
        db = TestingSessionLocal()
        try:
            job_queue.cancel_scan_jobs(db, j.scan_id)
        finally:
            db.close()
        await asyncio.sleep(10)

    _run_worker_until_idle(ScanWorker(worker_id="t", executor=executor, run_periodic=False))
    db_session.expire_all()
    assert db_session.get(Scan, scan.id).status == "cancelled"


def test_worker_shutdown_returns_job_to_queue(db_session, org_and_user, open_scope, monkeypatch):
    from app.workers.scan_worker import ScanWorker

    monkeypatch.setenv("SCAN_WORKER_SHUTDOWN_GRACE_SECONDS", "0")
    org, user = org_and_user
    scan = _scan(db_session, org, user)
    job = job_queue.enqueue_scan(db_session, scan)

    async def executor(j):
        await asyncio.sleep(10)

    async def go():
        w = ScanWorker(worker_id="t", executor=executor, run_periodic=False, poll_interval=0.05)
        task = asyncio.create_task(w.run())
        await asyncio.sleep(0.3)
        w.stop()
        await task

    asyncio.run(go())
    db_session.expire_all()
    row = db_session.get(ScanJob, job.id)
    assert row.status == "pending" and row.attempt == 0


# ── Periodic jobs and scheduled scans ────────────────────────────────


def test_periodic_job_runs_once_per_interval(db_session):
    from app.services.periodic import mark_done, try_acquire

    assert try_acquire(db_session, "job", timedelta(hours=1), "w1") is True
    assert try_acquire(db_session, "job", timedelta(hours=1), "w2") is False  # leased
    mark_done(db_session, "job")
    assert try_acquire(db_session, "job", timedelta(hours=1), "w2") is False  # ran recently


def test_run_periodic_tasks_skips_failing_job_until_retry(db_session):
    from app.services.periodic import PeriodicJob, run_periodic_tasks

    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("broken task")

    jobs = [PeriodicJob("broken", timedelta(seconds=0), boom)]
    run_periodic_tasks(db_session, "w", jobs=jobs)
    run_periodic_tasks(db_session, "w", jobs=jobs)
    assert len(calls) == 1  # backed off instead of retrying every loop


def test_due_schedule_creates_saved_scan_and_job(db_session, org_and_user, open_scope):
    from app.models.v2_scanner import MonitorSchedule
    from app.services.periodic import run_due_schedules

    org, user = org_and_user
    sched = MonitorSchedule(
        id=str(uuid.uuid4()), domain="example.com", interval_hours=6, scan_type="quick",
        enabled=True, created_by=user.id, organization_id=org.id,
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(sched)
    db_session.commit()

    assert run_due_schedules(db_session) == 1
    assert run_due_schedules(db_session) == 0  # next_run_at moved forward
    scan = db_session.query(Scan).filter(Scan.organization_id == org.id).one()
    job = db_session.query(ScanJob).filter(ScanJob.scan_id == scan.id).one()
    assert job.triggered_by == "schedule" and scan.domain == "example.com"


def test_due_schedule_skipped_when_scope_not_verified(db_session, org_and_user, monkeypatch):
    from app.models.v2_scanner import MonitorSchedule
    from app.services.periodic import run_due_schedules

    monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "verified")
    monkeypatch.setattr("app.core.target_guard.resolve_host", lambda host, timeout=4.0: [])
    org, user = org_and_user
    db_session.add(MonitorSchedule(
        id=str(uuid.uuid4()), domain="example.com", interval_hours=6, scan_type="quick",
        enabled=True, created_by=user.id, organization_id=org.id, next_run_at=None,
    ))
    db_session.commit()
    assert run_due_schedules(db_session) == 0
    assert db_session.query(Scan).count() == 0
    # A schedule never auto-registers scopes.
    assert db_session.query(AuthorizedScope).count() == 0


# ── Config / wiring ───────────────────────────────────────────────────


def test_execution_mode_defaults(monkeypatch):
    from app.services import scan_dispatch

    monkeypatch.setattr(settings, "SCAN_EXECUTION_MODE", "")
    monkeypatch.setattr(settings, "USE_CELERY", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert scan_dispatch.execution_mode() == "queue"
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert scan_dispatch.execution_mode() == "inline"
    monkeypatch.setattr(settings, "SCAN_EXECUTION_MODE", "queue")
    assert scan_dispatch.execution_mode() == "queue"


def test_celery_beat_schedules_are_valid():
    from celery.schedules import BaseSchedule

    from app.celery_app import celery_app

    for entry in celery_app.conf.beat_schedule.values():
        assert isinstance(entry["schedule"], BaseSchedule)


def test_single_alembic_head():
    import os

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "alembic"))
    assert len(ScriptDirectory.from_config(cfg).get_heads()) == 1


def test_postgres_urls_pinned_to_psycopg2():
    from app.config import normalize_postgres_url

    assert normalize_postgres_url("postgres://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert normalize_postgres_url("postgresql://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert normalize_postgres_url("postgresql+psycopg2://u@h/db") == "postgresql+psycopg2://u@h/db"
    assert normalize_postgres_url("sqlite:///x.db") == "sqlite:///x.db"
