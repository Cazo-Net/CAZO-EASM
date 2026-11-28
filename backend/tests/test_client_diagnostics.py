"""Support diagnostics captured by the platform for the admin panel's client view.

Only technical metadata: parsed browser/OS on the session, session
last-activity time, and the user on failed requests / front-end errors.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.api import deps
from app.config import settings
from app.core.client_info import MAX_UA_LENGTH, edge_geo, parse_user_agent
from app.core.security import decode_token
from app.models.auth_models import UserSession
from app.models.user import User

PW = "TestPass123!"
CHROME_WIN = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
FIREFOX_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0"


def _login(client, email="diag@example.com", headers=None):
    client.post("/api/v1/auth/register", json={"email": email, "password": PW, "full_name": "Diag"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PW}, headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()


class _Req:
    def __init__(self, headers):
        self.headers = headers


def test_login_stores_parsed_browser_and_os(client, db_session):
    tokens = _login(client, headers={"User-Agent": CHROME_WIN})
    s = db_session.query(UserSession).one()
    assert (s.browser, s.os) == ("Chrome 131", "Windows 10/11")
    assert s.user_agent == CHROME_WIN
    # The access token names its session so activity can be attributed to it.
    assert decode_token(tokens["access_token"])["sid"] == s.id


def test_oversized_user_agent_is_truncated(client, db_session):
    _login(client, headers={"User-Agent": "A" * 5000})
    s = db_session.query(UserSession).one()
    assert len(s.user_agent) == MAX_UA_LENGTH
    assert s.browser == "Unknown" and s.os == "Unknown"


def test_refresh_records_current_browser(client, db_session):
    tokens = _login(client, headers={"User-Agent": CHROME_WIN})
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]},
                    headers={"User-Agent": FIREFOX_MAC})
    assert r.status_code == 200, r.text
    active = db_session.query(UserSession).filter(UserSession.is_active.is_(True)).one()
    assert (active.browser, active.os) == ("Firefox 133", "macOS 10.15")
    assert decode_token(r.json()["access_token"])["sid"] == active.id


def test_authenticated_requests_update_last_activity(client, db_session):
    tokens = _login(client)
    sid = decode_token(tokens["access_token"])["sid"]
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    db_session.query(UserSession).filter(UserSession.id == sid).update({"last_activity": old})
    db_session.commit()
    deps._ACTIVITY_SEEN.clear()

    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/api/v1/users/me", headers=h).status_code == 200
    db_session.expire_all()
    first = db_session.query(UserSession).filter(UserSession.id == sid).one().last_activity
    assert first.replace(tzinfo=timezone.utc) > old + timedelta(hours=2)

    # Throttled: a second request straight after does not write again.
    db_session.query(UserSession).filter(UserSession.id == sid).update({"last_activity": old})
    db_session.commit()
    assert client.get("/api/v1/users/me", headers=h).status_code == 200
    db_session.expire_all()
    again = db_session.query(UserSession).filter(UserSession.id == sid).one().last_activity
    assert again.replace(tzinfo=timezone.utc) < old + timedelta(minutes=1)


def test_failed_requests_are_logged_with_the_user(client, db_session, monkeypatch):
    import app.main as app_main
    calls = []
    monkeypatch.setattr(app_main, "log_api_request", lambda *a, **k: calls.append(k))
    tokens = _login(client)
    user = db_session.query(User).one()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/api/v1/scans/does-not-exist", headers=h).status_code == 404
    mine = [c for c in calls if c.get("status_code") == 404]
    assert mine and mine[-1]["user_id"] == user.id


def test_client_error_is_linked_to_signed_in_user(client, db_session, monkeypatch):
    from app.api.v1 import logs
    calls = []
    monkeypatch.setattr(logs, "log_client_error", lambda **k: calls.append(k))
    tokens = _login(client)
    user = db_session.query(User).one()

    r = client.post(
        "/api/v1/logs/client-error",
        json={"message": "TypeError: x is undefined", "url": "/scans/abc?token=SECRET#frag"},
        headers={"Authorization": f"Bearer {tokens['access_token']}", "User-Agent": CHROME_WIN},
    )
    assert r.status_code == 200
    k = calls[-1]
    assert k["user_id"] == user.id
    assert k["detail"]["url"] == "/scans/abc"          # query string and fragment dropped
    assert "SECRET" not in str(k)
    assert k["detail"]["browser"] == "Chrome 131"

    # Still works signed out, and a bad token is not an error.
    for headers in ({}, {"Authorization": "Bearer not-a-token"}):
        assert client.post("/api/v1/logs/client-error", json={"message": "boom"}, headers=headers).status_code == 200
        assert calls[-1]["user_id"] is None


def test_edge_geo_only_when_trusted(monkeypatch):
    req = _Req({"cf-ipcountry": "MY", "cf-ipcity": "Kuala Lumpur"})
    monkeypatch.setattr(settings, "TRUST_EDGE_GEO_HEADERS", False)
    assert edge_geo(req) == (None, None)
    monkeypatch.setattr(settings, "TRUST_EDGE_GEO_HEADERS", True)
    assert edge_geo(req) == ("Kuala Lumpur", "MY")
    assert edge_geo(_Req({"cf-ipcountry": "XX"})) == (None, None)
    assert edge_geo(_Req({"cf-ipcountry": "<script>MY"})) == (None, "scriptMY")


@pytest.mark.parametrize("ua,browser,os_name,device", [
    (CHROME_WIN, "Chrome", "Windows", "desktop"),
    (FIREFOX_MAC, "Firefox", "macOS", "desktop"),
    ("Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
     "Version/17.5 Mobile/15E148 Safari/604.1", "Safari", "iPadOS", "tablet"),
    ("python-requests/2.32.0", "python-requests", None, "bot"),
    (None, None, None, None),
])
def test_parse_user_agent(ua, browser, os_name, device):
    p = parse_user_agent(ua)
    assert (p["browser"], p["os"], p["device_type"]) == (browser, os_name, device)
