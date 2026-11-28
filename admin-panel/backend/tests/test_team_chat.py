"""Admin team chat: admins only, plain text, unread tracking, own-message delete."""
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import text

from app import main
from app.database import engine

from .conftest import auth

API = "/team-chat"
ALICE = "alice@cazoeasm.io"
BOB = "bob@cazoeasm.io"


def _send(client, who, message):
    return client.post(f"{API}/messages", headers=auth(who), json={"message": message})


def test_requires_admin_token(client):
    assert client.get(f"{API}/messages").status_code in (401, 403)
    assert client.post(f"{API}/messages", json={"message": "hi"}).status_code in (401, 403)

    # A token signed with another secret (e.g. the customer API's) is refused.
    forged = jwt.encode(
        {"sub": ALICE, "type": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "some-other-secret", algorithm="HS256",
    )
    r = client.get(f"{API}/messages", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401

    # A correctly signed token that is not an admin token is refused.
    access = jwt.encode(
        {"sub": ALICE, "type": "access", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        main.settings.ADMIN_JWT_SECRET, algorithm="HS256",
    )
    assert client.get(f"{API}/messages", headers={"Authorization": f"Bearer {access}"}).status_code == 401

    # Customers (non-superusers) cannot use it even with an admin-panel token.
    assert client.get(f"{API}/messages", headers=auth("customer@example.com")).status_code == 401


def test_disabled_admin_loses_access(client):
    assert client.get(f"{API}/messages", headers=auth(BOB)).status_code == 200
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = 0 WHERE email = :e"), {"e": BOB})
    assert client.get(f"{API}/messages", headers=auth(BOB)).status_code == 401


def test_send_and_read_history(client):
    r = _send(client, ALICE, "  Deploy is at 6pm, please hold merges  ")
    assert r.status_code == 200
    sent = r.json()
    assert sent["message"] == "Deploy is at 6pm, please hold merges"
    assert sent["author_name"] == "Alice Tan" and sent["mine"] is True
    _send(client, BOB, "Ack")

    as_bob = client.get(f"{API}/messages", headers=auth(BOB)).json()
    assert [m["message"] for m in as_bob["messages"]] == ["Deploy is at 6pm, please hold merges", "Ack"]
    assert [m["mine"] for m in as_bob["messages"]] == [False, True]
    assert [m["author_name"] for m in as_bob["messages"]] == ["Alice Tan", "Bob Lim"]
    assert as_bob["messages"][0]["created_at"].endswith("+00:00")
    assert as_bob["me"] == BOB and as_bob["has_more"] is False


def test_plain_text_rules(client):
    assert _send(client, ALICE, "   ").status_code == 400
    assert _send(client, ALICE, "x" * 4001).status_code == 400
    assert _send(client, ALICE, "x" * 4000).status_code == 200
    r = _send(client, ALICE, "line1\r\nline2‮​\x07 <script>alert(1)</script>")
    assert r.status_code == 200
    # Control/invisible characters go; markup is kept as literal text (the UI never renders HTML).
    assert r.json()["message"] == "line1\nline2 <script>alert(1)</script>"


def test_unread_counts_per_admin(client):
    _send(client, ALICE, "one")
    _send(client, ALICE, "two")
    assert client.get(f"{API}/unread", headers=auth(ALICE)).json()["count"] == 0
    assert client.get(f"{API}/unread", headers=auth(BOB)).json()["count"] == 2

    client.post(f"{API}/read", headers=auth(BOB))
    assert client.get(f"{API}/unread", headers=auth(BOB)).json()["count"] == 0

    # Replying also marks the room read for the sender.
    _send(client, ALICE, "three")
    _send(client, BOB, "reply")
    assert client.get(f"{API}/unread", headers=auth(BOB)).json()["count"] == 0
    assert client.get(f"{API}/unread", headers=auth(ALICE)).json()["count"] == 1


def test_delete_own_messages_only(client):
    mine = _send(client, ALICE, "typo").json()
    r = client.delete(f"{API}/messages/{mine['id']}", headers=auth(BOB))
    assert r.status_code == 403
    assert client.delete(f"{API}/messages/{mine['id']}", headers=auth(ALICE)).status_code == 200
    assert client.get(f"{API}/messages", headers=auth(ALICE)).json()["messages"] == []
    assert client.delete(f"{API}/messages/{mine['id']}", headers=auth(ALICE)).status_code == 404


def test_rate_limit(client):
    for i in range(main.TEAM_CHAT_RATE_LIMIT):
        assert _send(client, ALICE, f"m{i}").status_code == 200
    assert _send(client, ALICE, "one too many").status_code == 429
    # The limit is per admin.
    assert _send(client, BOB, "still fine").status_code == 200


def test_older_history_pages(client):
    base = datetime(2026, 11, 1)
    msg_t = main._get_table("admin_chat_messages")
    with engine.begin() as conn:
        for i in range(7):
            conn.execute(msg_t.insert().values(
                id=f"m{i}", author_email=ALICE, author_name="Alice Tan",
                message=f"msg {i}", created_at=base + timedelta(minutes=i),
            ))
    first = client.get(f"{API}/messages", params={"limit": 3}, headers=auth(BOB)).json()
    assert [m["message"] for m in first["messages"]] == ["msg 4", "msg 5", "msg 6"]
    assert first["has_more"] is True
    older = client.get(
        f"{API}/messages", params={"limit": 3, "before": first["messages"][0]["id"]}, headers=auth(BOB)
    ).json()
    assert [m["message"] for m in older["messages"]] == ["msg 1", "msg 2", "msg 3"]
    last = client.get(
        f"{API}/messages", params={"limit": 3, "before": older["messages"][0]["id"]}, headers=auth(BOB)
    ).json()
    assert [m["message"] for m in last["messages"]] == ["msg 0"] and last["has_more"] is False


def test_members_are_active_superusers(client):
    body = client.get(f"{API}/members", headers=auth(ALICE)).json()
    assert [m["email"] for m in body["members"]] == [ALICE, BOB]
    assert body["members"][0]["name"] == "Alice Tan"


def test_missing_tables(client):
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE admin_chat_reads"))
        conn.execute(text("DROP TABLE admin_chat_messages"))
    assert client.get(f"{API}/messages", headers=auth(ALICE)).json()["messages"] == []
    assert client.get(f"{API}/unread", headers=auth(ALICE)).json()["count"] == 0
    assert _send(client, ALICE, "hi").status_code == 503
