"""Support chat: real messages only, isolation between customers, visitors."""
from datetime import datetime, timedelta, timezone

from app.models.support import SupportConversation, SupportMessage

PW = "TestPass123!"
API = "/api/v1/support"


def _login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": PW, "full_name": email})
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _team_reply(db, conversation_id, text="Hello from the team", minutes_ago=0):
    """What the admin panel does when someone on the team answers."""
    msg = SupportMessage(
        conversation_id=conversation_id, sender_type="admin", sender_id="admin",
        sender_name="owner@cazoeasm.io", message=text, is_read=False,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.add(msg)
    db.commit()
    return msg


def test_no_automatic_replies(client, db_session):
    h = _login(client, "a@test.io")
    conv = client.post(f"{API}/conversations", headers=h, json={"message": "Scan is stuck"}).json()
    client.post(f"{API}/conversations/{conv['id']}/messages", headers=h, json={"message": "Still stuck"})
    msgs = client.get(f"{API}/conversations/{conv['id']}/messages", headers=h).json()["messages"]
    assert [m["sender_type"] for m in msgs] == ["user", "user"]
    assert client.get(f"{API}/unread", headers=h).json()["count"] == 0
    assert db_session.query(SupportMessage).filter(SupportMessage.sender_type == "admin").count() == 0


def test_reply_is_unread_until_opened_and_hides_admin_identity(client, db_session):
    h = _login(client, "a@test.io")
    conv = client.post(f"{API}/conversations", headers=h, json={"message": "Hi"}).json()
    _team_reply(db_session, conv["id"])
    assert client.get(f"{API}/unread", headers=h).json()["count"] == 1
    listed = client.get(f"{API}/conversations", headers=h).json()["conversations"]
    assert listed[0]["id"] == conv["id"] and listed[0]["unread_count"] == 1

    body = client.get(f"{API}/conversations/{conv['id']}/messages", headers=h)
    assert "owner@cazoeasm.io" not in body.text
    assert body.json()["messages"][-1]["sender_name"] == "CAZO Support"
    assert body.json()["messages"][-1]["created_at"].endswith("+00:00")
    assert client.get(f"{API}/unread", headers=h).json()["count"] == 0


def test_reply_with_null_read_flag_still_counts_as_unread(client, db_session):
    """Older admin replies were inserted without is_read."""
    h = _login(client, "a@test.io")
    conv = client.post(f"{API}/conversations", headers=h, json={"message": "Hi"}).json()
    msg = _team_reply(db_session, conv["id"])
    db_session.query(SupportMessage).filter(SupportMessage.id == msg.id).update({"is_read": None})
    db_session.commit()
    assert client.get(f"{API}/unread", headers=h).json()["count"] == 1


def test_users_cannot_reach_each_others_conversations(client):
    a = _login(client, "a@test.io")
    conv = client.post(f"{API}/conversations", headers=a, json={"message": "private"}).json()
    b = _login(client, "b@test.io")
    assert client.get(f"{API}/conversations", headers=b).json()["conversations"] == []
    assert client.get(f"{API}/conversations/{conv['id']}/messages", headers=b).status_code == 404
    assert client.post(f"{API}/conversations/{conv['id']}/messages", headers=b, json={"message": "x"}).status_code == 404
    assert client.get(f"{API}/conversations").status_code in (401, 403)


def test_message_validation(client):
    h = _login(client, "a@test.io")
    assert client.post(f"{API}/conversations", headers=h, json={"message": "   "}).status_code == 422
    assert client.post(f"{API}/conversations", headers=h, json={"message": "x" * 4001}).status_code == 422
    conv = client.post(f"{API}/conversations", headers=h, json={"message": "  ok  "}).json()
    msgs = client.get(f"{API}/conversations/{conv['id']}/messages", headers=h).json()["messages"]
    assert msgs[0]["message"] == "ok"


def test_writing_to_a_closed_conversation_reopens_it(client, db_session):
    h = _login(client, "a@test.io")
    conv = client.post(f"{API}/conversations", headers=h, json={"message": "Hi"}).json()
    db_session.query(SupportConversation).update({"status": "closed"})
    db_session.commit()
    assert client.post(f"{API}/conversations/{conv['id']}/messages", headers=h, json={"message": "again"}).status_code == 200
    db_session.expire_all()
    assert db_session.query(SupportConversation).one().status == "open"


def test_conversation_records_the_organization(client, db_session):
    h = _login(client, "a@test.io")
    assert client.post("/api/v1/organizations", headers=h, json={"name": "Acme"}).status_code in (200, 201)
    h = {"Authorization": "Bearer " + client.post(
        "/api/v1/auth/login", json={"email": "a@test.io", "password": PW}).json()["access_token"]}
    client.post(f"{API}/conversations", headers=h, json={"message": "Hi"})
    assert db_session.query(SupportConversation).one().organization_id


# ── Website visitors ───────────────────────────────────────────────────


def _guest(client, **extra):
    body = {"name": "Vera Visitor", "email": "Vera@Example.com", "message": "Do you scan IPv6?", **extra}
    return client.post(f"{API}/guest/conversations", json=body)


def test_guest_conversation_needs_its_token(client, db_session):
    r = _guest(client)
    assert r.status_code == 200, r.text
    cid, token = r.json()["id"], r.json()["token"]
    conv = db_session.query(SupportConversation).one()
    assert conv.user_id is None and conv.guest_email == "vera@example.com"
    assert token not in (conv.guest_token_hash or "") and len(conv.guest_token_hash) == 64

    url = f"{API}/guest/conversations/{cid}/messages"
    assert client.get(url).status_code == 404
    assert client.get(url, headers={"X-Support-Token": "wrong"}).status_code == 404
    assert client.post(url, json={"message": "x"}, headers={"X-Support-Token": "wrong"}).status_code == 404

    ok = {"X-Support-Token": token}
    _team_reply(db_session, cid, "Yes, we do.")
    unread_url = f"{API}/guest/conversations/{cid}/unread"
    assert client.get(unread_url, headers={"X-Support-Token": "wrong"}).status_code == 404
    assert client.get(unread_url, headers=ok).json()["count"] == 1
    first = client.get(url, headers=ok).json()
    assert [m["sender_type"] for m in first["messages"]] == ["user", "admin"]
    assert first["unread_count"] == 1
    assert client.get(url, headers=ok).json()["unread_count"] == 0
    assert client.post(url, json={"message": "Thanks"}, headers=ok).status_code == 200


def test_guest_token_does_not_open_other_conversations(client):
    one, two = _guest(client).json(), _guest(client, email="other@example.com").json()
    url = f"{API}/guest/conversations/{two['id']}/messages"
    assert client.get(url, headers={"X-Support-Token": one["token"]}).status_code == 404


def test_signed_in_user_cannot_read_guest_conversation(client):
    g = _guest(client).json()
    h = _login(client, "a@test.io")
    assert client.get(f"{API}/conversations/{g['id']}/messages", headers=h).status_code == 404
    assert client.get(f"{API}/conversations", headers=h).json()["conversations"] == []


def test_guest_user_token_cannot_be_used_on_account_conversation(client):
    h = _login(client, "a@test.io")
    conv = client.post(f"{API}/conversations", headers=h, json={"message": "Hi"}).json()
    url = f"{API}/guest/conversations/{conv['id']}/messages"
    assert client.get(url, headers={"X-Support-Token": ""}).status_code == 404
    assert client.get(url, headers={"X-Support-Token": "anything"}).status_code == 404


def test_guest_validation_and_honeypot(client, db_session):
    assert _guest(client, email="not-an-email").status_code == 422
    assert _guest(client, message="").status_code == 422
    bot = _guest(client, website="http://spam.example")
    assert bot.status_code == 200
    assert db_session.query(SupportConversation).count() == 0


def test_guest_rate_limit(client, monkeypatch):
    from app.config import settings
    from app.core.rate_limit import get_failure_limiter
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    get_failure_limiter().reset()
    try:
        codes = [_guest(client).status_code for _ in range(4)]
    finally:
        get_failure_limiter().reset()
    assert codes == [200, 200, 200, 429]


# ── Email ──────────────────────────────────────────────────────────────


class _Outbox:
    def __init__(self):
        self.sent = []

    def send_async(self, to, subject, html_body, **kw):
        # Sign-up and sign-in also send mail; keep only support chat emails.
        if "upport" in subject:
            self.sent.append((to, subject, html_body))


def test_team_is_emailed_once_per_burst(client, db_session, monkeypatch):
    import app.services.email.sender as sender
    from app.config import settings
    box = _Outbox()
    monkeypatch.setattr(sender, "get_email_service", lambda: box)
    monkeypatch.setattr(settings, "SUPPORT_NOTIFY_EMAIL", "team@cazoeasm.io, second@cazoeasm.io")

    h = _login(client, "a@test.io")
    conv = client.post(f"{API}/conversations", headers=h, json={"message": "<b>help</b>"}).json()
    assert [to for to, _, _ in box.sent] == ["team@cazoeasm.io", "second@cazoeasm.io"]
    assert "&lt;b&gt;help&lt;/b&gt;" in box.sent[0][2] and "<b>help</b>" not in box.sent[0][2]

    client.post(f"{API}/conversations/{conv['id']}/messages", headers=h, json={"message": "more"})
    assert len(box.sent) == 2  # same burst, no second email
    _team_reply(db_session, conv["id"])
    client.post(f"{API}/conversations/{conv['id']}/messages", headers=h, json={"message": "thanks"})
    assert len(box.sent) == 4


def test_no_team_email_when_not_configured(client, monkeypatch):
    import app.services.email.sender as sender
    box = _Outbox()
    monkeypatch.setattr(sender, "get_email_service", lambda: box)
    h = _login(client, "a@test.io")
    client.post(f"{API}/conversations", headers=h, json={"message": "hi"})
    assert box.sent == []


def test_unread_replies_are_emailed_once(client, db_session, monkeypatch):
    import app.services.email.sender as sender
    from app.api.v1.support import send_reply_notifications
    box = _Outbox()
    monkeypatch.setattr(sender, "get_email_service", lambda: box)

    h = _login(client, "a@test.io")
    seen = client.post(f"{API}/conversations", headers=h, json={"message": "one"}).json()
    unseen = client.post(f"{API}/conversations", headers=h, json={"message": "two"}).json()
    guest = _guest(client).json()
    _team_reply(db_session, seen["id"], "read already", minutes_ago=10)
    client.get(f"{API}/conversations/{seen['id']}/messages", headers=h)
    _team_reply(db_session, unseen["id"], "first answer", minutes_ago=10)
    _team_reply(db_session, unseen["id"], "second answer", minutes_ago=9)
    _team_reply(db_session, guest["id"], "for the visitor", minutes_ago=10)
    _team_reply(db_session, unseen["id"], "too fresh", minutes_ago=0)

    assert send_reply_notifications(db_session) == 2
    by_to = {to: body for to, _, body in box.sent}
    assert set(by_to) == {"a@test.io", "vera@example.com"}
    assert "first answer" in by_to["a@test.io"] and "second answer" in by_to["a@test.io"]
    assert "too fresh" not in by_to["a@test.io"] and "read already" not in by_to["a@test.io"]
    assert send_reply_notifications(db_session) == 0


# ── Hostile input ──────────────────────────────────────────────────────

XSS = '<img src=x onerror="alert(1)"><script>fetch("/steal")</script>'


def test_markup_is_stored_and_returned_as_plain_text(client, db_session):
    """The API never rewrites text into HTML; screens render it as text."""
    r = _guest(client, name="<b>Eve</b>\r\nBcc: x@evil.test", message=XSS)
    assert r.status_code == 200, r.text
    conv = db_session.query(SupportConversation).one()
    assert conv.guest_name == "<b>Eve</b> Bcc: x@evil.test"  # one line, no header break
    out = client.get(f"{API}/guest/conversations/{r.json()['id']}/messages",
                     headers={"X-Support-Token": r.json()["token"]})
    assert out.headers["content-type"].startswith("application/json")
    assert out.json()["messages"][0]["message"] == XSS


def test_invisible_and_control_characters_are_removed(client, db_session):
    h = _login(client, "a@test.io")
    hidden = "pay\u202egnp.exe\u200b\x00\x1b[31m to\r\nline two"
    client.post(f"{API}/conversations", headers=h, json={"message": hidden})
    assert db_session.query(SupportMessage).one().message == "paygnp.exe[31m to\nline two"
    assert client.post(f"{API}/conversations", headers=h, json={"message": "\u200b\u202e"}).status_code == 422


def test_team_email_escapes_hostile_names_and_text(client, monkeypatch):
    import app.services.email.sender as sender
    from app.config import settings
    box = _Outbox()
    monkeypatch.setattr(sender, "get_email_service", lambda: box)
    monkeypatch.setattr(settings, "SUPPORT_NOTIFY_EMAIL", "team@cazoeasm.io")
    _guest(client, name="<script>alert(1)</script>\nBcc: x@evil.test", message=XSS)
    to, subject, body = box.sent[0]
    assert "\n" not in subject and "\r" not in subject
    assert "<script>" not in body and "<img" not in body
    assert "&lt;script&gt;" in body


def test_one_conversation_cannot_flood_the_inbox(client, db_session, monkeypatch):
    import app.api.v1.support as support
    monkeypatch.setattr(support, "MAX_UNANSWERED_MESSAGES", 3)
    g = _guest(client).json()
    url = f"{API}/guest/conversations/{g['id']}/messages"
    ok = {"X-Support-Token": g["token"]}
    codes = [client.post(url, json={"message": f"m{i}"}, headers=ok).status_code for i in range(3)]
    assert codes == [200, 200, 429]
    _team_reply(db_session, g["id"])
    assert client.post(url, json={"message": "after reply"}, headers=ok).status_code == 200


def test_customer_api_has_no_staff_routes(client):
    """Nothing on the customer API lists other people's conversations or replies as staff."""
    h = _login(client, "a@test.io")
    g = _guest(client).json()
    for method, path in [("get", f"/guest/conversations"), ("delete", f"/conversations/{g['id']}"),
                         ("put", f"/conversations/{g['id']}/status")]:
        assert getattr(client, method)(f"{API}{path}", headers=h).status_code in (404, 405)
    body = client.post(f"{API}/conversations", headers=h,
                       json={"message": "hi", "sender_type": "admin", "user_id": "someone-else"})
    assert body.status_code == 200
