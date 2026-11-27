"""Concurrency checks that only mean something on real Postgres.

Skipped unless ``TEST_POSTGRES_URL`` points at a throwaway database, e.g.::

    TEST_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/easm_test pytest tests/test_queue_postgres.py

The database is wiped and rebuilt from the models.
"""
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

PG_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL not set")


@pytest.fixture(scope="module")
def pg_sessionmaker():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import models  # noqa: F401
    from app.config import normalize_postgres_url
    from app.database import Base

    engine = create_engine(normalize_postgres_url(PG_URL), pool_size=20, max_overflow=10)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed(Session, n_orgs=4, per_org=5):
    from app.models.organization import Organization
    from app.models.scan import Scan
    from app.models.user import User
    from app.services.job_queue import enqueue_scan

    db = Session()
    try:
        org_ids = []
        for i in range(n_orgs):
            org = Organization(name=f"o{i}", slug=f"o{i}-{uuid.uuid4().hex[:6]}")
            db.add(org)
            db.flush()
            user = User(email=f"{uuid.uuid4().hex[:8]}@t.test", organization_id=org.id)
            db.add(user)
            db.flush()
            for j in range(per_org):
                scan = Scan(domain=f"h{j}.example.com", organization_id=org.id, created_by=user.id)
                db.add(scan)
                db.commit()
                enqueue_scan(db, scan)
            org_ids.append(org.id)
        return org_ids
    finally:
        db.close()


def test_concurrent_claims_never_duplicate(pg_sessionmaker, monkeypatch):
    from app.config import settings
    from app.services.job_queue import claim_next_job

    monkeypatch.setattr(settings, "SCAN_MAX_RUNNING_PER_ORG", 100)
    _seed(pg_sessionmaker)
    claimed, lock = [], threading.Lock()

    def worker(name):
        db = pg_sessionmaker()
        try:
            while True:
                job = claim_next_job(db, name)
                if job is None:
                    return
                with lock:
                    claimed.append(job.id)
        finally:
            db.close()

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claimed) == 20
    assert len(set(claimed)) == 20


def test_periodic_lock_has_one_winner(pg_sessionmaker):
    from app.services.periodic import try_acquire

    wins, lock = [], threading.Lock()
    name = f"job-{uuid.uuid4().hex[:6]}"

    def attempt(i):
        db = pg_sessionmaker()
        try:
            if try_acquire(db, name, timedelta(hours=1), f"w{i}"):
                with lock:
                    wins.append(i)
        finally:
            db.close()

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(wins) == 1


def test_due_schedules_claimed_once(pg_sessionmaker, monkeypatch):
    from app.config import settings
    from app.models.organization import Organization
    from app.models.scan import ScanJob
    from app.models.user import User
    from app.models.v2_scanner import MonitorSchedule
    from app.services.periodic import run_due_schedules

    monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "open")
    monkeypatch.setattr("app.core.target_guard.resolve_host", lambda host, timeout=4.0: [])
    db = pg_sessionmaker()
    org = Organization(name="s", slug=f"s-{uuid.uuid4().hex[:6]}")
    db.add(org)
    db.flush()
    user = User(email=f"{uuid.uuid4().hex[:8]}@t.test", organization_id=org.id)
    db.add(user)
    db.flush()
    for i in range(10):
        db.add(MonitorSchedule(
            id=str(uuid.uuid4()), domain=f"s{i}.example.com", interval_hours=1, scan_type="quick",
            enabled=True, created_by=user.id, organization_id=org.id,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ))
    db.commit()
    db.close()

    counts, lock = [], threading.Lock()

    def tick():
        s = pg_sessionmaker()
        try:
            n = run_due_schedules(s)
            with lock:
                counts.append(n)
        finally:
            s.close()

    threads = [threading.Thread(target=tick) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(counts) == 10
    db = pg_sessionmaker()
    try:
        assert db.query(ScanJob).filter(ScanJob.triggered_by == "schedule").count() == 10
    finally:
        db.close()
