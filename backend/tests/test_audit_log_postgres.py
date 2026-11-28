"""Audit chain under concurrent writers, on real Postgres.

Skipped unless ``TEST_POSTGRES_URL`` points at a throwaway database, e.g.::

    TEST_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/easm_test pytest tests/test_audit_log_postgres.py
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

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


def test_concurrent_writers_keep_each_org_chain_intact(pg_sessionmaker):
    from app.models.audit import AuditEvent
    from app.services.audit import log_event, verify_chain

    orgs = [str(uuid.uuid4()) for _ in range(3)]
    per_org = 40

    def write(i):
        db = pg_sessionmaker()
        try:
            return log_event(db, action="test.concurrent", organization_id=orgs[i % 3],
                             detail={"i": i, "note": "naïve ✓"}, target_id="x" * 50) is not None
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=16) as pool:
        assert all(pool.map(write, range(per_org * 3)))

    db = pg_sessionmaker()
    try:
        for org in orgs:
            seqs = [s for (s,) in db.query(AuditEvent.seq).filter(AuditEvent.organization_id == org)
                    .order_by(AuditEvent.seq)]
            assert seqs == list(range(1, per_org + 1))
            result = verify_chain(db, org, batch=7)
            assert result["valid"] is True and result["checked"] == per_org, result
    finally:
        db.close()
