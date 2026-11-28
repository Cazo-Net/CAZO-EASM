"""Client diagnostics view: admin-only, read-only, and limited to technical metadata."""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

# Same throwaway-SQLite setup as the rest of the admin panel tests. setdefault
# keeps whatever a shared conftest already configured.
_DB_DIR = tempfile.mkdtemp(prefix="cazo-admin-diag-")
os.environ.setdefault("USE_SQLITE", "true")
os.environ.setdefault("EASM_SQLITE_PATH", os.path.join(_DB_DIR, "easm.db"))
os.environ.setdefault("ADMIN_JWT_SECRET", "test-admin-secret-0123456789abcdef")
os.environ.setdefault("ADMIN_PASSWORD", "")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import main  # noqa: E402
from app.database import engine  # noqa: E402
from app.user_agent import parse_user_agent  # noqa: E402

ADMIN = "ops@cazoeasm.io"
CHROME_WIN = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SAFARI_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")

# Mirrors the columns of backend/app/models that the diagnostics view reads.
_TABLES = ["platform_logs", "audit_events", "auth_audit_logs", "user_sessions",
           "billing_subscriptions", "users", "organizations"]
_SCHEMA = [
    """CREATE TABLE organizations (id VARCHAR(36) PRIMARY KEY, name VARCHAR(255), plan VARCHAR(50),
        is_active BOOLEAN)""",
    """CREATE TABLE users (
        id VARCHAR(36) PRIMARY KEY, email VARCHAR(255) NOT NULL, full_name VARCHAR(255),
        hashed_password VARCHAR(255), role VARCHAR(20), is_active BOOLEAN, organization_id VARCHAR(36),
        email_verified BOOLEAN, totp_enabled BOOLEAN, mfa_enforced BOOLEAN, google_id VARCHAR(255),
        failed_login_attempts INTEGER, locked_until DATETIME, last_login DATETIME,
        password_changed_at DATETIME, created_at DATETIME)""",
    """CREATE TABLE billing_subscriptions (id VARCHAR(36) PRIMARY KEY, organization_id VARCHAR(36),
        plan VARCHAR(50), status VARCHAR(30), billing_interval VARCHAR(20), current_period_end DATETIME,
        cancel_at_period_end BOOLEAN, last_payment_error TEXT)""",
    """CREATE TABLE user_sessions (
        id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36), refresh_token_hash VARCHAR(255),
        device_fingerprint VARCHAR(255), user_agent TEXT, browser VARCHAR(100), os VARCHAR(100),
        ip_address VARCHAR(45), location_city VARCHAR(100), location_country VARCHAR(100),
        is_trusted BOOLEAN, is_active BOOLEAN, last_activity DATETIME, created_at DATETIME,
        expires_at DATETIME)""",
    """CREATE TABLE auth_audit_logs (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36),
        event_type VARCHAR(50), event_detail JSON, ip_address VARCHAR(45), user_agent TEXT,
        success BOOLEAN, created_at DATETIME)""",
    """CREATE TABLE audit_events (id VARCHAR(36) PRIMARY KEY, action VARCHAR(64),
        organization_id VARCHAR(36), actor_id VARCHAR(36), actor_type VARCHAR(20),
        target_type VARCHAR(40), target_id VARCHAR(36), status VARCHAR(20), detail JSON,
        ip_address VARCHAR(64), user_agent VARCHAR(400), created_at DATETIME)""",
    """CREATE TABLE platform_logs (id VARCHAR(36) PRIMARY KEY, category VARCHAR(32),
        severity VARCHAR(16), message TEXT, detail JSON, organization_id VARCHAR(36),
        user_id VARCHAR(36), request_id VARCHAR(32), client_ip VARCHAR(45), path VARCHAR(512),
        method VARCHAR(10), status_code INTEGER, duration_ms FLOAT,
        related_entity_type VARCHAR(40), related_entity_id VARCHAR(36), created_at DATETIME)""",
]


def _ts(minutes_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S.%f")


@pytest.fixture
def db():
    with engine.begin() as conn:
        for t in _TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
        for ddl in _SCHEMA:
            conn.execute(text(ddl))
        conn.execute(text("INSERT INTO organizations VALUES ('org-1', 'Acme Sdn Bhd', 'pro', 1)"))
        conn.execute(text(
            "INSERT INTO users (id, email, full_name, hashed_password, role, is_active, organization_id,"
            " email_verified, totp_enabled, failed_login_attempts, last_login, created_at)"
            " VALUES ('admin-0', :a, 'Ops', 'x', 'superuser', 1, NULL, 1, 1, 0, NULL, :c)"),
            {"a": ADMIN, "c": _ts(10000)})
        conn.execute(text(
            "INSERT INTO users (id, email, full_name, hashed_password, role, is_active, organization_id,"
            " email_verified, totp_enabled, failed_login_attempts, last_login, created_at)"
            " VALUES ('cust-1', 'aisha@acme.my', 'Aisha', 'secret-hash', 'admin', 1, 'org-1', 1, 0, 2, :l, :c)"),
            {"l": _ts(120), "c": _ts(5000)})
        conn.execute(text(
            "INSERT INTO billing_subscriptions VALUES ('sub-1', 'org-1', 'pro', 'past_due', 'year', NULL, 0,"
            " 'Card declined')"))
        conn.execute(text(
            "INSERT INTO user_sessions (id, user_id, refresh_token_hash, user_agent, browser, os, ip_address,"
            " location_city, location_country, is_trusted, is_active, last_activity, created_at)"
            " VALUES ('sess-old', 'cust-1', 'hash-old', :ua, 'Mozilla/5.0 (iPhone; CPU', 'garbage', '10.0.0.9',"
            " NULL, NULL, 0, 0, :la, :ca)"),
            {"ua": SAFARI_IPHONE, "la": _ts(3000), "ca": _ts(3100)})
        conn.execute(text(
            "INSERT INTO user_sessions (id, user_id, refresh_token_hash, user_agent, browser, os, ip_address,"
            " location_city, location_country, is_trusted, is_active, last_activity, created_at)"
            " VALUES ('sess-new', 'cust-1', 'hash-new', :ua, 'Chrome 131', 'Windows 10/11', '203.0.113.7',"
            " 'Kuala Lumpur', 'MY', 0, 1, :la, :ca)"),
            {"ua": CHROME_WIN, "la": _ts(5), "ca": _ts(120)})
        conn.execute(text(
            "INSERT INTO auth_audit_logs VALUES ('ev-1', 'cust-1', 'login_success',"
            " :d, '203.0.113.7', :ua, 1, :c)"),
            {"d": json.dumps({"method": "password", "session_id": "sess-new", "token": "should-not-show"}),
             "ua": CHROME_WIN, "c": _ts(120)})
        conn.execute(text(
            "INSERT INTO auth_audit_logs VALUES ('ev-2', 'cust-1', 'login_failed', '{}', '203.0.113.7',"
            " NULL, 0, :c)"), {"c": _ts(125)})
        conn.execute(text(
            "INSERT INTO audit_events (id, action, organization_id, actor_id, actor_type, target_type,"
            " target_id, status, ip_address, created_at)"
            " VALUES ('ae-1', 'scan.create', 'org-1', 'cust-1', 'user', 'scan', 'scan-9', 'success',"
            " '203.0.113.7', :c)"), {"c": _ts(30)})
        conn.execute(text(
            "INSERT INTO platform_logs (id, category, severity, message, detail, organization_id, user_id,"
            " request_id, client_ip, path, method, status_code, created_at)"
            " VALUES ('pl-1', 'api_request', 'error', 'POST /api/v1/scans → 500', '{}', 'org-1', 'cust-1',"
            " 'req123', '203.0.113.7', '/api/v1/scans', 'POST', 500, :c)"), {"c": _ts(20)})
        conn.execute(text(
            "INSERT INTO platform_logs (id, category, severity, message, detail, user_id, created_at)"
            " VALUES ('pl-2', 'unexpected', 'error', 'TypeError: x is undefined', :d, 'cust-1', :c)"),
            {"d": json.dumps({"url": "/scans/abc", "browser": "Chrome 131"}), "c": _ts(15)})
        conn.execute(text(
            "INSERT INTO platform_logs (id, category, severity, message, detail, user_id, created_at)"
            " VALUES ('pl-3', 'api_request', 'info', 'fine', '{}', 'cust-1', :c)"), {"c": _ts(10)})
    yield


@pytest.fixture
def client(db):
    return TestClient(main.app)


def auth(email: str = ADMIN) -> dict:
    return {"Authorization": f"Bearer {main.create_admin_token(email)}"}


# ── Access control ─────────────────────────────────────────────────────
def test_requires_admin_token(client):
    assert client.get("/diagnostics/users/cust-1").status_code in (401, 403)
    assert client.get("/diagnostics/sessions/sess-new").status_code in (401, 403)


def test_rejects_forged_or_customer_tokens(client):
    from jose import jwt
    forged = jwt.encode({"sub": ADMIN, "type": "admin"}, "wrong-secret", algorithm="HS256")
    r = client.get("/diagnostics/users/cust-1", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
    # A valid admin-panel token for someone who is not a superuser is refused.
    r = client.get("/diagnostics/users/cust-1", headers=auth("aisha@acme.my"))
    assert r.status_code == 401


# ── User view ──────────────────────────────────────────────────────────
def test_user_diagnostics_shows_technical_details(client):
    r = client.get("/diagnostics/users/cust-1", headers=auth())
    assert r.status_code == 200, r.text
    d = r.json()

    assert d["user"]["email"] == "aisha@acme.my"
    assert d["user"]["sign_in_method"] == "password"
    assert d["organization"]["name"] == "Acme Sdn Bhd"
    assert d["organization"]["subscription"]["status"] == "past_due"
    assert d["organization"]["subscription"]["last_payment_error"] == "Card declined"

    s = d["summary"]
    assert s["browser"] == "Chrome 131"
    assert s["os"] == "Windows 10/11"
    assert s["device_type"] == "desktop"
    assert s["ip_address"] == "203.0.113.7"
    assert s["location"] == "Kuala Lumpur, MY"
    assert s["active_sessions"] == 1
    assert s["errors_7d"] == 2
    assert s["failed_logins_7d"] == 1
    assert s["last_seen"] is not None

    # Sessions are newest first and parsed from the stored user agent, which
    # also fixes old rows whose browser/os columns held raw UA fragments.
    assert [x["id"] for x in d["sessions"]] == ["sess-new", "sess-old"]
    old = d["sessions"][1]
    assert (old["browser"], old["os"], old["device_type"]) == ("Safari 17", "iOS 17", "mobile")

    assert [e["event_type"] for e in d["auth_events"]] == ["login_success", "login_failed"]
    assert [a["action"] for a in d["activity"]] == ["scan.create"]
    msgs = [e["message"] for e in d["errors"]]
    assert "TypeError: x is undefined" in msgs and "POST /api/v1/scans → 500" in msgs
    assert "fine" not in msgs  # info-level logs are not errors
    assert next(e for e in d["errors"] if e["id"] == "pl-2")["path"] == "/scans/abc"


def test_user_diagnostics_leaves_out_secrets(client):
    body = client.get("/diagnostics/users/cust-1", headers=auth()).text
    for secret in ("secret-hash", "hash-new", "hash-old", "should-not-show", "refresh_token_hash",
                   "hashed_password", "totp_secret"):
        assert secret not in body
    ev = client.get("/diagnostics/users/cust-1", headers=auth()).json()["auth_events"][0]
    assert ev["detail"] == {"method": "password", "session_id": "sess-new"}


def test_user_diagnostics_unknown_user(client):
    assert client.get("/diagnostics/users/nope", headers=auth()).status_code == 404


def test_views_are_recorded_internally(client):
    client.get("/diagnostics/users/cust-1", headers=auth())
    client.get("/diagnostics/sessions/sess-new", headers=auth())
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT related_entity_type, related_entity_id, detail FROM platform_logs"
            " WHERE category = 'security_event' ORDER BY created_at")).all()
    assert [(r[0], r[1]) for r in rows] == [("user", "cust-1"), ("session", "sess-new")]
    assert json.loads(rows[0][2])["admin"] == ADMIN
    # The access records never show up as the customer's own errors, and
    # nothing is written to the customer-visible organization audit log.
    d = client.get("/diagnostics/users/cust-1", headers=auth()).json()
    assert all(e["category"] != "security_event" for e in d["errors"])
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM audit_events")).scalar() == 1


# ── Session view ───────────────────────────────────────────────────────
def test_session_diagnostics(client):
    r = client.get("/diagnostics/sessions/sess-new", headers=auth())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["session"]["user_agent"] == CHROME_WIN
    assert d["session"]["browser"] == "Chrome 131"
    assert d["user"]["email"] == "aisha@acme.my"
    assert d["organization"]["plan"] == "pro"
    # Events while this session was in use; not the failed login from before it.
    assert [e["event_type"] for e in d["auth_events"]] == ["login_success"]
    assert {e["id"] for e in d["errors"]} == {"pl-1", "pl-2"}


def test_old_session_window_excludes_later_events(client):
    d = client.get("/diagnostics/sessions/sess-old", headers=auth()).json()
    assert d["session"]["is_active"] is False
    assert d["auth_events"] == [] and d["errors"] == []


def test_unknown_session(client):
    assert client.get("/diagnostics/sessions/nope", headers=auth()).status_code == 404


def test_sessions_list_includes_email(client):
    rows = client.get("/sessions", headers=auth()).json()
    assert rows[0]["user_email"] == "aisha@acme.my"


# ── User agent parsing ─────────────────────────────────────────────────
@pytest.mark.parametrize("ua,expected", [
    (CHROME_WIN, ("Chrome", "131", "Windows", "10/11", "desktop")),
    (SAFARI_IPHONE, ("Safari", "17", "iOS", "17", "mobile")),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.2903.70", ("Edge", "131", "macOS", "10.15", "desktop")),
    ("Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
     ("Firefox", "133", "Linux", None, "desktop")),
    ("Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/131.0.0.0 Safari/537.36", ("Chrome", "131", "Android", "14", "tablet")),
    ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
     "SamsungBrowser/25.0 Chrome/121.0.0.0 Mobile Safari/537.36",
     ("Samsung Internet", "25", "Android", "14", "mobile")),
    ("curl/8.5.0", ("curl", None, None, None, "bot")),
    ("", (None, None, None, None, None)),
])
def test_parse_user_agent(ua, expected):
    p = parse_user_agent(ua)
    assert (p["browser"], p["browser_version"], p["os"], p["os_version"], p["device_type"]) == expected
