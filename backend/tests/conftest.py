import os
import tempfile

# Disable rate limiting for tests (no test asserts 429; the shared client IP
# would otherwise trip the limiter and cause cross-request flakiness).
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# One dedicated on-disk SQLite database, opened without StaticPool so that the
# app's per-request sessions and the test's db_session get their own connections
# (SQLite serializes writes via file locking, so there is no "database is
# locked" race). Isolation between tests is provided by wiping all rows at the
# start of every test. create_all runs exactly once, up front.
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
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Make the application use this same test database engine/session factory.
import app.database as _appdb

_appdb.engine = engine
_appdb.SessionLocal = TestingSessionLocal

# Disable the background email worker thread during tests. It is a global
# daemon thread that outlives each test and has caused intermittent,
# non-deterministic interference; tests only assert on HTTP responses, not on
# email delivery.
import app.services.email.sender as _emailsender

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
    with TestClient(app, raise_server_exceptions=True) as c:
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
