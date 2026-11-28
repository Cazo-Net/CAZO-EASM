"""Admin panel tests run against a throwaway SQLite copy of the EASM schema."""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cazo-admin-test-")
os.environ["USE_SQLITE"] = "true"
os.environ["EASM_SQLITE_PATH"] = os.path.join(_DB_DIR, "easm.db")
os.environ["ADMIN_JWT_SECRET"] = "test-admin-secret-0123456789abcdef"
os.environ["ADMIN_PASSWORD"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import main  # noqa: E402
from app.database import engine  # noqa: E402

# Mirrors backend/app/models (users) and backend/app/models/admin_chat.py.
_SCHEMA = [
    """CREATE TABLE users (
        id VARCHAR(36) PRIMARY KEY, email VARCHAR(255) NOT NULL, full_name VARCHAR(255),
        hashed_password VARCHAR(255), role VARCHAR(20), is_active BOOLEAN)""",
    """CREATE TABLE admin_chat_messages (
        id VARCHAR(36) PRIMARY KEY, author_email VARCHAR(255) NOT NULL,
        author_name VARCHAR(255), message TEXT NOT NULL, created_at DATETIME)""",
    """CREATE TABLE admin_chat_reads (
        admin_email VARCHAR(255) PRIMARY KEY, last_read_at DATETIME)""",
]

ADMINS = {
    "alice@cazoeasm.io": "Alice Tan",
    "bob@cazoeasm.io": "Bob Lim",
}


@pytest.fixture(autouse=True)
def fresh_db():
    with engine.begin() as conn:
        for t in ("admin_chat_reads", "admin_chat_messages", "users"):
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
        for ddl in _SCHEMA:
            conn.execute(text(ddl))
        for i, (email, name) in enumerate(ADMINS.items()):
            conn.execute(
                text("INSERT INTO users VALUES (:id, :e, :n, 'x', 'superuser', 1)"),
                {"id": f"admin-{i}", "e": email, "n": name},
            )
        conn.execute(text(
            "INSERT INTO users VALUES ('cust-1', 'customer@example.com', 'Customer', 'x', 'admin', 1)"
        ))
    main._TEAM_CHAT_SENDS.clear()
    yield


@pytest.fixture
def client():
    return TestClient(main.app)


def auth(email: str) -> dict:
    return {"Authorization": f"Bearer {main.create_admin_token(email)}"}
