"""Per-organization integrations: validation, secrecy, tenant isolation,
delivery, de-duplication and failure handling."""
import json

import httpx
import pytest

from app.models.integration import IntegrationDelivery, OrgIntegration
from app.models.user import User
from app.services import integration_delivery as delivery
from app.services.notification_service import dispatch_notification

PW = "TestPass123!"
# Deliveries queued by the code under test; run after the caller has committed,
# as the background pool would.
PENDING = []
SLACK_URL = "https://hooks.slack.com/services/T000/B000/sEcReTsEcReT1234"


def _register_login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": PW, "full_name": email})
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _owner_with_org(client, email, name):
    h = _register_login(client, email)
    assert client.post("/api/v1/organizations", headers=h, json={"name": name}).status_code in (200, 201)
    data = client.post("/api/v1/auth/login", json={"email": email, "password": PW}).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _user(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).first()


@pytest.fixture
def outbox(monkeypatch):
    """Capture outbound requests; deliveries run inline instead of in the pool."""
    box = {"requests": [], "status": 200, "json": {"key": "SEC-7"}}

    def handler(request: httpx.Request) -> httpx.Response:
        box["requests"].append(request)
        status = box["status"](request) if callable(box["status"]) else box["status"]
        return httpx.Response(status, json=box["json"])

    monkeypatch.setattr(delivery, "_make_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    PENDING.clear()
    monkeypatch.setattr(delivery, "_submit", lambda i, o, m: PENDING.append((i, o, m)))
    monkeypatch.setattr(delivery, "_ATTEMPTS", 1)
    delivery._recent.clear()
    return box


def _create(client, h, kind, settings, **extra):
    return client.post("/api/v1/integrations", headers=h, json={"kind": kind, "settings": settings, **extra})


JIRA = {"base_url": "https://8.8.8.8", "email": "bot@acme.io", "api_token": "jira-tok-123456", "project_key": "sec"}
SPLUNK = {"hec_url": "https://8.8.8.8:8088/services/collector/event", "token": "hec-tok-123456"}


def _alert(db, org_id, user_id, **kw):
    args = dict(
        db=db, organization_id=org_id, user_id=user_id, notification_type="inventory_new_finding",
        title="2 new findings on acme.io", message="New findings were detected.",
        related_entity_type="scan", related_entity_id="scan-1",
        data={"domain": "acme.io", "alert_type": "new_critical_finding", "url": "/inventory?tab=changes",
              "items": ["api.acme.io: exposed .env file", "<!channel> & <b>x</b>"], "more": 0},
    )
    args.update(kw)
    note = dispatch_notification(**args)
    while PENDING:
        delivery.deliver(*PENDING.pop(0))
    return note


# ── Validation ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind,settings", [
    ("slack", {"webhook_url": "https://evil.example.com/services/x"}),
    ("slack", {"webhook_url": "http://hooks.slack.com/services/x"}),
    ("slack", {"webhook_url": "https://hooks.slack.com.evil.io/services/x"}),
    ("slack", {"webhook_url": "https://user:pw@hooks.slack.com/services/x"}),
    ("slack", {}),
    ("teams", {"webhook_url": "https://127.0.0.1/hook"}),
    ("teams", {"webhook_url": "https://169.254.169.254/latest/meta-data"}),
    ("jira", {**JIRA, "base_url": "https://10.0.0.5"}),
    ("jira", {**JIRA, "base_url": "http://8.8.8.8"}),
    ("jira", {**JIRA, "base_url": "https://localhost"}),
    ("jira", {**JIRA, "project_key": "../../x"}),
    ("jira", {**JIRA, "email": "not-an-email"}),
    ("jira", {**JIRA, "api_token": ""}),
    ("jira", {**JIRA, "surprise": "1"}),
    ("splunk", {**SPLUNK, "hec_url": "https://[::1]:8088"}),
    ("splunk", {**SPLUNK, "index": "main\r\nX-Evil: 1"}),
    ("pagerduty", {"x": "y"}),
])
def test_bad_settings_are_refused(client, kind, settings):
    h = _owner_with_org(client, "owner@val.io", "Val")
    r = _create(client, h, kind, settings)
    assert r.status_code == 400, (kind, settings, r.text)
    assert client.get("/api/v1/integrations", headers=h).json() == []


def test_unknown_event_is_refused_and_defaults_apply(client):
    h = _owner_with_org(client, "owner@ev.io", "Ev")
    assert _create(client, h, "slack", {"webhook_url": SLACK_URL}, event_types=["nope.event"]).status_code == 400
    r = _create(client, h, "jira", JIRA)
    assert r.status_code == 201, r.text
    assert r.json()["event_types"] == ["finding.critical", "finding.high", "cve.new_match"]
    assert r.json()["settings"]["project_key"] == "SEC"
    assert r.json()["settings"]["issue_type"] == "Task"


# ── Secrecy ──────────────────────────────────────────────────────────────


def test_credentials_are_encrypted_and_never_returned(client, db_session):
    h = _owner_with_org(client, "owner@sec.io", "Sec")
    created = [
        _create(client, h, "slack", {"webhook_url": SLACK_URL}),
        _create(client, h, "jira", JIRA),
        _create(client, h, "splunk", SPLUNK),
    ]
    assert all(r.status_code == 201 for r in created), [r.text for r in created]
    listing = client.get("/api/v1/integrations", headers=h)
    audit = client.get("/api/v1/audit-logs", headers=h, params={"action": "integration.*"})
    assert audit.json()["total"] == 3
    for text in [r.text for r in created] + [listing.text, audit.text]:
        for secret in ("sEcReTsEcReT", "jira-tok-123456", "hec-tok-123456"):
            assert secret not in text
    slack = created[0].json()
    assert slack["has_secret"] is True and slack["destination"] == "hooks.slack.com/…1234"
    assert slack["settings"] == {}
    assert created[2].json()["settings"]["hec_url"] == "https://8.8.8.8:8088"

    for row in db_session.query(OrgIntegration).all():
        stored = json.dumps(row.config) + row.secret_encrypted
        for secret in ("sEcReTsEcReT", "jira-tok-123456", "hec-tok-123456"):
            assert secret not in stored


def test_blank_secret_on_update_keeps_the_stored_one(client, outbox):
    h = _owner_with_org(client, "owner@upd.io", "Upd")
    iid = _create(client, h, "jira", JIRA).json()["id"]
    r = client.put(f"/api/v1/integrations/{iid}", headers=h, json={
        "settings": {**JIRA, "api_token": "", "project_key": "OPS"}, "name": "  Ops   board "})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["project_key"] == "OPS" and r.json()["name"] == "Ops board"
    assert client.post(f"/api/v1/integrations/{iid}/test", headers=h).json() == {"success": True, "error": None}
    req = outbox["requests"][-1]
    # Testing Jira checks access to the project; it does not open an issue.
    assert req.method == "GET" and req.url.path == "/rest/api/2/project/OPS"
    assert req.headers["authorization"] == httpx.BasicAuth("bot@acme.io", "jira-tok-123456")._auth_header


def test_unreadable_credentials_are_reported_not_crashed(client, monkeypatch):
    h = _owner_with_org(client, "owner@key.io", "Key")
    iid = _create(client, h, "slack", {"webhook_url": SLACK_URL}).json()["id"]
    from app.config import settings
    monkeypatch.setattr(settings, "INTEGRATIONS_ENCRYPTION_KEY", "a-different-key")
    item = client.get("/api/v1/integrations", headers=h).json()[0]
    assert item["credentials_readable"] is False and item["destination"] == ""
    assert client.post(f"/api/v1/integrations/{iid}/test", headers=h).status_code == 400


# ── Access ───────────────────────────────────────────────────────────────


def test_other_organizations_and_plain_members_are_shut_out(client, db_session, outbox):
    ha = _owner_with_org(client, "a@a.io", "Org A")
    hb = _owner_with_org(client, "b@b.io", "Org B")
    iid = _create(client, ha, "slack", {"webhook_url": SLACK_URL}).json()["id"]

    assert client.get("/api/v1/integrations", headers=hb).json() == []
    assert client.put(f"/api/v1/integrations/{iid}", headers=hb, json={"enabled": False}).status_code == 404
    assert client.post(f"/api/v1/integrations/{iid}/test", headers=hb).status_code == 404
    assert client.delete(f"/api/v1/integrations/{iid}", headers=hb).status_code == 404
    assert outbox["requests"] == []

    # An alert in org B never reaches org A's Slack.
    b = _user(db_session, "b@b.io")
    _alert(db_session, b.organization_id, b.id)
    assert outbox["requests"] == []
    # Even a forged job naming org A's integration is refused by the worker.
    assert delivery.deliver(iid, b.organization_id, delivery.test_message()) is None
    assert outbox["requests"] == []

    hm = _register_login(client, "member@a.io")
    member, owner = _user(db_session, "member@a.io"), _user(db_session, "a@a.io")
    member.organization_id, member.role = owner.organization_id, "member"
    db_session.commit()
    for method, path in [("get", ""), ("get", "/catalog"), ("post", f"/{iid}/test"), ("delete", f"/{iid}")]:
        assert getattr(client, method)(f"/api/v1/integrations{path}", headers=hm).status_code == 403
        assert getattr(client, method)(f"/api/v1/integrations{path}").status_code in (401, 403)
    assert outbox["requests"] == []


# ── Delivery ─────────────────────────────────────────────────────────────


def test_an_alert_reaches_slack_teams_jira_and_splunk(client, db_session, outbox):
    h = _owner_with_org(client, "owner@send.io", "Send")
    assert _create(client, h, "slack", {"webhook_url": SLACK_URL}).status_code == 201
    assert _create(client, h, "teams", {"webhook_url": "https://8.8.4.4/workflows/abc"}).status_code == 201
    assert _create(client, h, "jira", JIRA).status_code == 201
    assert _create(client, h, "splunk", {**SPLUNK, "index": "sec"}).status_code == 201
    u = _user(db_session, "owner@send.io")
    _alert(db_session, u.organization_id, u.id)

    by_host = {(r.url.host, r.url.path): r for r in outbox["requests"]}
    assert len(outbox["requests"]) == 4

    slack = json.loads(by_host[("hooks.slack.com", "/services/T000/B000/sEcReTsEcReT1234")].content)
    body = slack["blocks"][1]["text"]["text"]
    assert "exposed .env file" in body
    # Data from a scan cannot ping a channel or inject Slack markup.
    assert "<!channel>" not in body and "&lt;!channel&gt; &amp; &lt;b&gt;" in body
    assert "/inventory?tab=changes" in slack["blocks"][2]["elements"][0]["text"]

    teams = json.loads(by_host[("8.8.4.4", "/workflows/abc")].content)
    assert teams["attachments"][0]["content"]["body"][0]["text"] == "2 new findings on acme.io"

    jira_req = by_host[("8.8.8.8", "/rest/api/2/issue")]
    fields = json.loads(jira_req.content)["fields"]
    assert fields["project"] == {"key": "SEC"} and fields["summary"].startswith("[CRITICAL] 2 new findings")
    assert "cazo-easm" in fields["labels"]

    splunk_req = by_host[("8.8.8.8", "/services/collector/event")]
    assert splunk_req.headers["authorization"] == "Splunk hec-tok-123456"
    event = json.loads(splunk_req.content)
    assert event["index"] == "sec" and event["event"]["event_type"] == "finding.critical"
    assert event["event"]["domain"] == "acme.io" and "dedupe_key" not in event["event"]

    db_session.expire_all()
    rows = db_session.query(OrgIntegration).all()
    assert all(r.last_success_at and r.failure_count == 0 for r in rows)
    assert db_session.query(IntegrationDelivery).one().external_ref == "SEC-7"


def test_same_alert_is_sent_once_and_jira_never_gets_a_second_ticket(client, db_session, outbox):
    h = _owner_with_org(client, "owner@dup.io", "Dup")
    _create(client, h, "slack", {"webhook_url": SLACK_URL})
    _create(client, h, "jira", JIRA)
    u = _user(db_session, "owner@dup.io")
    _alert(db_session, u.organization_id, u.id, skip_dedup=True)
    _alert(db_session, u.organization_id, u.id, skip_dedup=True)  # second recipient, same alert
    assert len(outbox["requests"]) == 2

    delivery._recent.clear()  # e.g. another worker process, or a later re-run
    _alert(db_session, u.organization_id, u.id, skip_dedup=True)
    hosts = [r.url.host for r in outbox["requests"]]
    assert hosts.count("8.8.8.8") == 1 and hosts.count("hooks.slack.com") == 2

    delivery._recent.clear()
    _alert(db_session, u.organization_id, u.id, skip_dedup=True, related_entity_id="scan-2")
    assert [r.url.host for r in outbox["requests"]].count("8.8.8.8") == 2


def test_only_subscribed_events_are_sent_and_disabled_ones_are_skipped(client, db_session, outbox):
    h = _owner_with_org(client, "owner@filter.io", "Filter")
    jira_id = _create(client, h, "jira", JIRA).json()["id"]
    slack_id = _create(client, h, "slack", {"webhook_url": SLACK_URL}, event_types=["scan.completed"]).json()["id"]
    u = _user(db_session, "owner@filter.io")
    _alert(db_session, u.organization_id, u.id, notification_type="scan_completed", title="Scan finished",
           skip_dedup=True)
    assert [r.url.host for r in outbox["requests"]] == ["hooks.slack.com"]  # Jira takes findings only

    client.put(f"/api/v1/integrations/{slack_id}", headers=h, json={"enabled": False})
    client.put(f"/api/v1/integrations/{jira_id}", headers=h, json={"enabled": False})
    delivery._recent.clear()
    _alert(db_session, u.organization_id, u.id, skip_dedup=True)
    _alert(db_session, u.organization_id, u.id, notification_type="scan_completed", title="Scan finished",
           skip_dedup=True)
    assert len(outbox["requests"]) == 1


def test_failures_are_recorded_without_secrets_and_switch_off_after_many(client, db_session, outbox):
    h = _owner_with_org(client, "owner@fail.io", "Fail")
    iid = _create(client, h, "slack", {"webhook_url": SLACK_URL}).json()["id"]
    jid = _create(client, h, "jira", JIRA).json()["id"]
    u = _user(db_session, "owner@fail.io")

    outbox["status"] = 404
    r = client.post(f"/api/v1/integrations/{iid}/test", headers=h).json()
    assert r == {"success": False, "error": "The webhook URL no longer exists."}

    def boom(request):
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)

    outbox["status"] = boom
    _alert(db_session, u.organization_id, u.id, skip_dedup=True)
    items = {i["id"]: i for i in client.get("/api/v1/integrations", headers=h).json()}
    assert items[iid]["last_error"] == "Could not connect to the destination."
    assert items[iid]["failure_count"] == 2 and "sEcReT" not in json.dumps(items)
    # A failed Jira delivery is not remembered, so the next alert can retry.
    assert db_session.query(IntegrationDelivery).count() == 0 and items[jid]["failure_count"] == 1

    for n in range(delivery.AUTO_DISABLE_AFTER):
        delivery._recent.clear()
        _alert(db_session, u.organization_id, u.id, skip_dedup=True, related_entity_id=f"s{n}")
    item = {i["id"]: i for i in client.get("/api/v1/integrations", headers=h).json()}[iid]
    assert item["enabled"] is False and item["last_error"].startswith("Turned off after")
    sent_before = len(outbox["requests"])
    delivery._recent.clear()
    _alert(db_session, u.organization_id, u.id, skip_dedup=True, related_entity_id="later")
    assert len(outbox["requests"]) == sent_before

    # Turning it back on gives it a fresh start.
    r = client.put(f"/api/v1/integrations/{iid}", headers=h, json={"enabled": True}).json()
    assert r["enabled"] is True and r["failure_count"] == 0


def test_a_broken_integration_never_breaks_the_alert(client, db_session, monkeypatch):
    h = _owner_with_org(client, "owner@safe.io", "Safe")
    _create(client, h, "slack", {"webhook_url": SLACK_URL})
    u = _user(db_session, "owner@safe.io")

    def explode(*a, **k):
        raise RuntimeError("pool is gone")

    monkeypatch.setattr(delivery, "_submit", explode)
    delivery._recent.clear()
    assert _alert(db_session, u.organization_id, u.id, skip_dedup=True) is not None


def test_requests_to_internal_addresses_are_blocked_at_send_time():
    """Even if a stored URL later resolves to an internal address."""
    import asyncio

    result = asyncio.run(delivery.send_once(
        "teams", {}, {"webhook_url": "https://127.0.0.1:9/hook"}, delivery.test_message()))
    assert result.ok is False and result.error == "The destination address is not a public internet address."


def test_delete_removes_the_integration_and_its_history(client, db_session, outbox):
    h = _owner_with_org(client, "owner@del.io", "Del")
    iid = _create(client, h, "jira", JIRA).json()["id"]
    u = _user(db_session, "owner@del.io")
    _alert(db_session, u.organization_id, u.id, skip_dedup=True)
    assert db_session.query(IntegrationDelivery).count() == 1
    assert client.delete(f"/api/v1/integrations/{iid}", headers=h).status_code == 204
    db_session.expire_all()
    assert db_session.query(OrgIntegration).count() == 0 and db_session.query(IntegrationDelivery).count() == 0


def test_catalog_lists_types_without_leaking_platform_settings(client):
    h = _owner_with_org(client, "owner@cat.io", "Cat")
    cat = client.get("/api/v1/integrations/catalog", headers=h).json()
    assert [k["kind"] for k in cat["kinds"]] == ["slack", "teams", "jira", "splunk"]
    # The old endpoint showed the platform's own environment settings to any user.
    assert client.get("/api/v1/integrations/status", headers=h).status_code in (404, 405)
