"""Organization audit log: coverage, tenant isolation, permissions, export
and tamper evidence."""
import csv
import io
import json

from sqlalchemy import text

from app.models.audit import AuditEvent
from app.models.user import User
from app.services.audit import log_event, verify_chain

PW = "TestPass123!"


def _register_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": PW, "full_name": email})
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _owner_with_org(client, email, name):
    h = _register_login(client, email)
    assert client.post("/api/v1/organizations", headers=h, json={"name": name}).status_code in (200, 201)
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _actions(client, h, **params):
    r = client.get("/api/v1/audit-logs", headers=h, params={"limit": 200, **params})
    assert r.status_code == 200, r.text
    return [i["action"] for i in r.json()["items"]]


def test_actions_are_recorded_with_actor_ip_and_agent(client):
    h = _owner_with_org(client, "owner@acme.io", "Acme")
    hdr = {**h, "User-Agent": "pytest-agent/1.0", "X-Forwarded-For": "203.0.113.9"}
    r = client.post("/api/v1/webhooks", headers=hdr, json={"url": "https://8.8.8.8/hook?secret=not-a-hex-secret"})
    assert r.status_code == 201, r.text
    wid = r.json()["id"]
    assert client.delete(f"/api/v1/webhooks/{wid}", headers=hdr).status_code == 204

    r = client.get("/api/v1/audit-logs", headers=h, params={"action": "webhook.*"})
    items = r.json()["items"]
    assert [i["action"] for i in items] == ["webhook.delete", "webhook.create"]
    created = items[1]
    assert created["actor_email"] == "owner@acme.io"
    assert created["ip_address"] == "203.0.113.9"
    assert created["user_agent"] == "pytest-agent/1.0"
    assert created["target_id"] == wid
    # Only the host is kept: the URL's secret must not reach the log.
    assert created["detail"]["host"] == "8.8.8.8"
    assert "not-a-hex-secret" not in json.dumps(created)
    assert created["hash"] and created["seq"]


def test_sign_in_events_reach_the_org_log(client):
    h = _owner_with_org(client, "owner@signin.io", "Signin")
    client.post("/api/v1/auth/login", json={"email": "owner@signin.io", "password": "WrongPass1!"})
    actions = _actions(client, h, action="auth.*")
    assert "auth.login_success" in actions
    assert "auth.login_failed" in actions
    failed = client.get("/api/v1/audit-logs", headers=h, params={"action": "auth.login_failed"}).json()["items"][0]
    assert failed["status"] == "failure"


def test_api_key_lifecycle_is_logged_without_the_key(client):
    h = _owner_with_org(client, "owner@keys.io", "Keys")
    r = client.post("/api/v1/api-keys/v2", headers=h, json={"name": "ci"})
    assert r.status_code == 201, r.text
    raw, key_id = r.json()["key"], r.json()["id"]
    assert client.delete(f"/api/v1/api-keys/v2/{key_id}", headers=h).status_code == 200
    r = client.get("/api/v1/audit-logs", headers=h, params={"action": "api_key.*"})
    assert [i["action"] for i in r.json()["items"]] == ["api_key.revoke", "api_key.create"]
    assert raw not in r.text


def test_secrets_in_detail_are_redacted(client, db_session):
    h = _owner_with_org(client, "owner@redact.io", "Redact")
    org_id = db_session.query(User).filter(User.email == "owner@redact.io").first().organization_id
    log_event(db_session, action="test.secret", organization_id=org_id,
              detail={"api_token": "s3cr3t", "nested": {"Password": "hunter2", "ok": 1}})
    item = client.get("/api/v1/audit-logs", headers=h, params={"action": "test.secret"}).json()["items"][0]
    assert item["detail"] == {"api_token": "[redacted]", "nested": {"Password": "[redacted]", "ok": 1}}


def test_one_org_cannot_see_anothers_log(client):
    ha = _owner_with_org(client, "a@a.io", "Org A")
    hb = _owner_with_org(client, "b@b.io", "Org B")
    client.post("/api/v1/webhooks", headers=ha, json={"url": "https://8.8.8.8/a"})

    assert "webhook.create" in _actions(client, ha)
    b_items = client.get("/api/v1/audit-logs", headers=hb, params={"limit": 200}).json()["items"]
    assert b_items and all(i["actor_email"] == "b@b.io" for i in b_items)
    assert "webhook.create" not in [i["action"] for i in b_items]
    # Filters cannot widen the search to another organization.
    assert client.get("/api/v1/audit-logs", headers=hb, params={"actor": "a@a.io"}).json()["total"] == 0
    assert "a@a.io" not in client.get("/api/v1/audit-logs/export", headers=hb).text
    assert "webhook.create" not in client.get("/api/v1/audit-logs/actions", headers=hb).json()["actions"]
    # Each organization has its own chain starting at 1.
    assert client.get("/api/v1/audit-logs/verify", headers=hb).json()["valid"] is True


def test_plain_members_and_anonymous_users_are_refused(client, db_session):
    _owner_with_org(client, "owner@perm.io", "Perm")
    hm = _register_login(client, "member@perm.io")
    owner = db_session.query(User).filter(User.email == "owner@perm.io").first()
    member = db_session.query(User).filter(User.email == "member@perm.io").first()
    member.organization_id = owner.organization_id
    member.role = "member"
    db_session.commit()

    for path in ("", "/actions", "/verify", "/export"):
        assert client.get(f"/api/v1/audit-logs{path}", headers=hm).status_code == 403, path
        assert client.get(f"/api/v1/audit-logs{path}").status_code in (401, 403), path

    member.role = "security_manager"
    db_session.commit()
    assert client.get("/api/v1/audit-logs", headers=hm).status_code == 200


def test_export_csv_and_jsonl_and_export_is_itself_logged(client, db_session):
    h = _owner_with_org(client, "owner@export.io", "Export")
    org_id = db_session.query(User).filter(User.email == "owner@export.io").first().organization_id
    log_event(db_session, action="test.formula", organization_id=org_id, actor_email="=cmd|' /C calc'!A0")

    r = client.get("/api/v1/audit-logs/export", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert rows and rows[0]["seq"] == "1"
    formula = [x for x in rows if x["action"] == "test.formula"][0]
    assert formula["actor_email"].startswith("'=")  # not runnable in a spreadsheet

    r = client.get("/api/v1/audit-logs/export", headers=h, params={"format": "jsonl"})
    lines = [json.loads(line) for line in r.text.splitlines()]
    assert [x["seq"] for x in lines] == sorted(x["seq"] for x in lines)
    assert "audit.export" in [x["action"] for x in lines]
    assert client.get("/api/v1/audit-logs/export", headers=h, params={"format": "xml"}).status_code == 422


def test_chain_detects_edits_deletions_and_forged_rows(client, db_session):
    h = _owner_with_org(client, "owner@chain.io", "Chain")
    org_id = db_session.query(User).filter(User.email == "owner@chain.io").first().organization_id
    for i in range(5):
        log_event(db_session, action="test.step", organization_id=org_id, detail={"i": i})

    ok = client.get("/api/v1/audit-logs/verify", headers=h).json()
    assert ok["valid"] is True and ok["checked"] >= 5 and ok["problem"] is None

    rows = (db_session.query(AuditEvent).filter(AuditEvent.organization_id == org_id)
            .order_by(AuditEvent.seq).all())
    victim = rows[-3]
    victim_id, victim_seq = victim.id, victim.seq

    # 1. Edit an entry in place.
    db_session.execute(text("UPDATE audit_events SET action = 'test.innocent' WHERE id = :i"), {"i": victim_id})
    db_session.commit()
    bad = client.get("/api/v1/audit-logs/verify", headers=h).json()
    assert bad["valid"] is False and bad["problem"]["seq"] == victim_seq and bad["problem"]["reason"] == "modified"
    db_session.execute(text("UPDATE audit_events SET action = 'test.step' WHERE id = :i"), {"i": victim_id})
    db_session.commit()
    assert client.get("/api/v1/audit-logs/verify", headers=h).json()["valid"] is True

    # 2. Delete an entry from the middle.
    db_session.execute(text("DELETE FROM audit_events WHERE id = :i"), {"i": victim_id})
    db_session.commit()
    db_session.expire_all()
    gone = verify_chain(db_session, org_id)
    assert gone["valid"] is False and gone["problem"] == {
        "seq": victim_seq, "reason": "missing", "message": f"Entry {victim_seq} is missing.",
    }


def test_forged_entry_without_the_key_fails(client, db_session):
    h = _owner_with_org(client, "owner@forge.io", "Forge")
    org_id = db_session.query(User).filter(User.email == "owner@forge.io").first().organization_id
    last = (db_session.query(AuditEvent).filter(AuditEvent.organization_id == org_id)
            .order_by(AuditEvent.seq.desc()).first())
    import hashlib
    db_session.add(AuditEvent(
        action="org.member.role_changed", organization_id=org_id, seq=last.seq + 1,
        prev_hash=last.hash, hash=hashlib.sha256(b"guess").hexdigest(),
    ))
    db_session.commit()
    res = client.get("/api/v1/audit-logs/verify", headers=h).json()
    assert res["valid"] is False and res["problem"]["seq"] == last.seq + 1


def test_legacy_rows_are_listed_but_not_counted_as_verified(client, db_session):
    h = _owner_with_org(client, "owner@legacy.io", "Legacy")
    org_id = db_session.query(User).filter(User.email == "owner@legacy.io").first().organization_id
    db_session.add(AuditEvent(action="scan.create", organization_id=org_id))
    db_session.commit()
    res = client.get("/api/v1/audit-logs/verify", headers=h).json()
    assert res["valid"] is True and res["legacy_unverified"] == 1
    assert "scan.create" in _actions(client, h)


def test_audit_failure_never_breaks_the_request(client, monkeypatch):
    h = _owner_with_org(client, "owner@besteffort.io", "BestEffort")
    import app.services.audit as audit

    def boom(*a, **k):
        raise RuntimeError("hash failure")

    monkeypatch.setattr(audit, "compute_hash", boom)
    r = client.post("/api/v1/webhooks", headers=h, json={"url": "https://8.8.8.8/hook"})
    assert r.status_code == 201, r.text
