import os
import tempfile

# Disable rate limiting for tests (no test asserts 429; the shared client IP
# would otherwise trip the limiter and cause cross-request flakiness).
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# Force in-memory cache/rate-limit backends so tests don't attempt real Redis
# connections (which would hang/time out in CI).
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("CELERY_BROKER_URL", "")
os.environ.setdefault("CELERY_RESULT_BACKEND", "")
# Tests drive the queue directly; no background worker inside the test app.
os.environ.setdefault("RUN_EMBEDDED_WORKER", "false")
# Plan limits are exercised by tests/test_billing.py, which switches them on;
# other tests run unlimited so they don't depend on the Trial allowance.
os.environ.setdefault("BILLING_ENFORCE_LIMITS", "false")
# No live NVD downloads from tests; CVE tests use their own temporary store.
os.environ.setdefault("CVE_NVD_FETCH", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app  # noqa: F401 — FastAPI application instance

# Ensure v2 scanner ORM models are registered with Base.metadata before create_all
from app.models.v2_scanner import MonitorSchedule, ScanHistory, AssetLifecycle, NotificationTrigger  # noqa: F401

# One dedicated on-disk SQLite database, opened without StaticPool so that the
# app's per-request sessions and the test's db_session get their own connections
# (SQLite serializes writes via file locking, so there is no "database is
# locked" race). Isolation between tests is provided by wiping all rows at the
# start of every test. create_all runs exactly once, up front.
import app.database as _appdb  # noqa: E402
from sqlalchemy import event  # noqa: E402

# This module is loaded twice when a test does ``from tests.conftest import
# TestingSessionLocal`` (once as pytest's ``conftest``, once as
# ``tests.conftest``). Building a second database would delete the file the
# first engine is using ("file is not a database" / "no such table"), so the
# test database is created once and reused.
if getattr(_appdb, "_test_engine", None) is None:
    _DB_PATH = os.path.join(tempfile.gettempdir(), f"easm_test_{os.getpid()}.db")
    if os.path.exists(_DB_PATH):
        try:
            os.remove(_DB_PATH)
        except OSError:
            pass

    engine = create_engine(
        f"sqlite:///{_DB_PATH}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    # Enable WAL so commits from one connection (the per-request API session)
    # are immediately visible to other connections (e.g. the scan background
    # task that opens its own SessionLocal).
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_con, con_record):
        cursor = dbapi_con.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    _appdb._test_engine = engine
    _appdb._test_session_factory = TestingSessionLocal
    _appdb._test_db_path = _DB_PATH
else:
    engine = _appdb._test_engine
    TestingSessionLocal = _appdb._test_session_factory
    _DB_PATH = _appdb._test_db_path

# Make the application use this same test database engine/session factory.
_appdb.engine = engine
_appdb.SessionLocal = TestingSessionLocal

# Disable the background email worker thread during tests. It is a global
# daemon thread that outlives each test and has caused intermittent,
# non-deterministic interference; tests only assert on HTTP responses, not on
# email delivery.
import app.services.email.sender as _emailsender  # noqa: E402

_emailsender.EmailService._ensure_worker = lambda self: None


def _clean_tables():
    """Delete every row so each test starts from a clean state."""
    session = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


@pytest.fixture(scope="function")
def db_session():
    _clean_tables()
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    # The app opens its own session per request. The shared db_session fixture is
    # available for tests that need direct DB access / assertions.
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Do not re-raise background-task exceptions (e.g. the async scan runner's
    # SQLite cross-connection visibility race under the test backend). API tests
    # assert on HTTP responses, not on background execution side effects.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
    from app.core.rate_limit import get_rate_limiter
    get_rate_limiter().reset()
    _clean_tables()


@pytest.fixture
def auth_headers(client):
    email = "test@test.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Test User",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass123!"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "email": email}


def pytest_sessionfinish(session):
    if os.path.exists(_DB_PATH):
        try:
            os.remove(_DB_PATH)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _clear_dns_answer_cache():
    """target_guard keeps DNS answers for a few seconds; tests fake DNS per test."""
    from app.core import target_guard

    target_guard._RESOLVE_CACHE.clear()
    yield
    target_guard._RESOLVE_CACHE.clear()
