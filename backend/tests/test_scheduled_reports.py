"""Scheduled email reports: schedule arithmetic, validation, permissions,
tenant isolation, sending and the due-report runner."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.audit import AuditEvent
from app.models.report_schedule import ReportSchedule
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.services import scheduled_reports as reports
from app.services.email.sender import EmailMessage, EmailService

PW = "TestPass123!"
BASE = "/api/v1/report-schedules"


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


class _Recorder:
    def __init__(self):
        self.messages = []
        self.fail_for = set()

    def send(self, message: EmailMessage) -> bool:
        self.messages.append(message)
        return message.to not in self.fail_for


@pytest.fixture
def mailbox(monkeypatch):
    """Email looks configured and every message lands in a list instead of leaving."""
    recorder = _Recorder()
    monkeypatch.setattr(reports, "email_configured", lambda: True)
    monkeypatch.setattr("app.services.email.get_email_service", lambda: EmailService(provider=recorder))
    reports._manual_sends.clear()
    return recorder


def _create(client, h, **body):
    payload = {"frequency": "weekly", "weekday": 0, "hour": 8, "timezone": "Asia/Kuala_Lumpur",
               "recipients": ["ciso@acme.io"], **body}
    return client.post(BASE, headers=h, json=payload)


def _finding(db, org_id, name, severity="high", when=None, status="open"):
    scan = Scan(domain=f"{name}.example", organization_id=org_id, status="completed")
    db.add(scan)
    db.flush()
    when = when or datetime.now(timezone.utc) - timedelta(days=1)
    db.add(Vulnerability(scan_id=scan.id, template_id="t", name=name, severity=severity, host=f"{name}.example",
                         status=status, first_seen=when, organization_id=org_id))
    db.commit()


# ── Schedule arithmetic ──────────────────────────────────────────────────


def test_weekly_next_run_respects_time_zone():
    # Wednesday 2026-11-25 00:30 UTC is 08:30 in Kuala Lumpur, so Monday 08:00 local is next week.
    after = datetime(2026, 11, 25, 0, 30, tzinfo=timezone.utc)
    nxt = reports.compute_next_run("weekly", 0, 1, 8, "Asia/Kuala_Lumpur", after=after)
    assert nxt == datetime(2026, 11, 30, 0, 0, tzinfo=timezone.utc)


def test_weekly_same_day_later_hour_runs_today():
    after = datetime(2026, 11, 30, 5, 0, tzinfo=timezone.utc)  # Monday
    assert reports.compute_next_run("weekly", 0, 1, 9, "UTC", after=after) == datetime(2026, 11, 30, 9, tzinfo=timezone.utc)
    # Exactly at the scheduled moment the next run is a week later, never "now" again.
    at = datetime(2026, 11, 30, 9, 0, tzinfo=timezone.utc)
    assert reports.compute_next_run("weekly", 0, 1, 9, "UTC", after=at) == datetime(2026, 12, 7, 9, tzinfo=timezone.utc)


def test_monthly_next_run_rolls_over_the_year():
    after = datetime(2026, 12, 20, 12, 0, tzinfo=timezone.utc)
    assert reports.compute_next_run("monthly", 0, 15, 6, "UTC", after=after) == datetime(2027, 1, 15, 6, tzinfo=timezone.utc)


def test_local_hour_survives_daylight_saving():
    # New York leaves DST on 2026-11-01; 09:00 local is 13:00 UTC before and 14:00 UTC after.
    before = reports.compute_next_run("weekly", 0, 1, 9, "America/New_York", after=datetime(2026, 10, 20, tzinfo=timezone.utc))
    after = reports.compute_next_run("weekly", 0, 1, 9, "America/New_York", after=datetime(2026, 11, 1, 12, tzinfo=timezone.utc))
    assert (before.hour, after.hour) == (13, 14)


# ── API: validation and permissions ──────────────────────────────────────


def test_create_list_update_delete_with_audit(client, db_session):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    r = _create(client, h, name="  Board   report ", recipients=["CISO@acme.io", "ciso@acme.io", "it@acme.io"])
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["name"] == "Board report"
    assert row["recipients"] == ["ciso@acme.io", "it@acme.io"]
    assert row["description"] == "every Monday at 08:00 (Asia/Kuala_Lumpur)"
    assert row["next_run_at"]

    listing = client.get(BASE, headers=h).json()
    assert [s["id"] for s in listing["schedules"]] == [row["id"]]
    assert listing["email_configured"] is False

    r = client.put(f"{BASE}/{row['id']}", headers=h, json={"frequency": "monthly", "day_of_month": 5, "enabled": False})
    assert r.status_code == 200
    assert r.json()["description"].startswith("day 5 of each month")
    assert r.json()["next_run_at"] is None  # paused

    assert client.delete(f"{BASE}/{row['id']}", headers=h).status_code == 200
    assert client.get(BASE, headers=h).json()["schedules"] == []
    org_id = _user(db_session, "own@acme.io").organization_id
    actions = [a for (a,) in db_session.query(AuditEvent.action).filter(AuditEvent.organization_id == org_id).all()]
    for expected in ("report_schedule.create", "report_schedule.update", "report_schedule.delete"):
        assert expected in actions


@pytest.mark.parametrize("body", [
    {"frequency": "daily"},
    {"weekday": 7},
    {"frequency": "monthly", "day_of_month": 31},
    {"hour": 24},
    {"timezone": "Mars/Olympus"},
    {"recipients": []},
    {"recipients": ["not-an-email"]},
    {"recipients": ["a@b.io\nBcc: x@y.io"]},
    {"recipients": [f"u{i}@acme.io" for i in range(21)]},
])
def test_invalid_schedules_are_rejected(client, body):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    assert _create(client, h, **body).status_code == 422


def test_schedule_limit_per_organization(client):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    for _ in range(reports.MAX_SCHEDULES_PER_ORG):
        assert _create(client, h).status_code == 201
    assert _create(client, h).status_code == 409


def test_requires_login_and_permission(client, db_session):
    assert client.get(BASE).status_code in (401, 403)
    h = _owner_with_org(client, "own@acme.io", "Acme")
    sid = _create(client, h).json()["id"]
    viewer = _register_login(client, "view@acme.io")
    u = _user(db_session, "view@acme.io")
    u.organization_id = _user(db_session, "own@acme.io").organization_id
    u.role = "viewer"
    db_session.commit()
    viewer = {"Authorization": "Bearer " + client.post(
        "/api/v1/auth/login", json={"email": "view@acme.io", "password": PW}).json()["access_token"]}
    assert client.get(BASE, headers=viewer).status_code == 403
    assert _create(client, viewer).status_code == 403
    assert client.post(f"{BASE}/{sid}/send-now", headers=viewer).status_code == 403


def test_other_organization_cannot_touch_a_schedule(client, mailbox):
    a = _owner_with_org(client, "a@acme.io", "Acme")
    b = _owner_with_org(client, "b@globex.io", "Globex")
    sid = _create(client, a).json()["id"]
    assert client.get(BASE, headers=b).json()["schedules"] == []
    assert client.put(f"{BASE}/{sid}", headers=b, json={"recipients": ["evil@globex.io"]}).status_code == 404
    assert client.delete(f"{BASE}/{sid}", headers=b).status_code == 404
    assert client.post(f"{BASE}/{sid}/send-now", headers=b).status_code == 404
    assert client.get(f"{BASE}/{sid}/preview.pdf", headers=b).status_code == 404
    assert mailbox.messages == []


# ── Content ──────────────────────────────────────────────────────────────


def test_summary_contains_only_the_organizations_own_data(client, db_session):
    _owner_with_org(client, "a@acme.io", "Acme")
    _owner_with_org(client, "b@globex.io", "Globex")
    acme = _user(db_session, "a@acme.io").organization_id
    globex = _user(db_session, "b@globex.io").organization_id
    _finding(db_session, acme, "acme-sqli", "critical")
    _finding(db_session, acme, "acme-old", "high", when=datetime.now(timezone.utc) - timedelta(days=40))
    _finding(db_session, acme, "acme-fixed", "high", status="resolved")
    _finding(db_session, globex, "globex-rce", "critical")

    end = datetime.now(timezone.utc)
    summary = reports.build_summary(db_session, acme, end - timedelta(days=7), end)
    assert summary["organization"] == "Acme"
    assert summary["new_findings"]["critical"] == 1 and summary["new_findings"]["high"] == 1
    assert summary["open_total"] == 2  # the resolved one is not open
    names = [f["name"] for f in summary["top_new_findings"]]
    assert names[0] == "acme-sqli" and "acme-old" not in names
    subject, html_body, text_body = reports.render_email(summary, "Weekly", "UTC", "weekly")
    pdf = reports.render_pdf(summary, "UTC", "weekly")
    assert pdf.startswith(b"%PDF")
    for blob in (subject, html_body, text_body):
        assert "globex" not in blob.lower()
    assert "1 critical and 1 high new findings need attention" in subject


def test_report_escapes_html_in_finding_names(client, db_session):
    _owner_with_org(client, "a@acme.io", "Acme")
    acme = _user(db_session, "a@acme.io").organization_id
    _finding(db_session, acme, "<script>alert(1)</script>", "high")
    end = datetime.now(timezone.utc)
    summary = reports.build_summary(db_session, acme, end - timedelta(days=7), end)
    _, html_body, _ = reports.render_email(summary, "<b>x</b>", "UTC", "weekly")
    assert "<script>alert(1)</script>" not in html_body and "<b>x</b>" not in html_body
    assert reports.render_pdf(summary, "UTC", "weekly").startswith(b"%PDF")


# ── Sending ──────────────────────────────────────────────────────────────


def test_send_now_goes_only_to_the_caller_with_pdf(client, mailbox):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    sid = _create(client, h, recipients=["ciso@acme.io", "board@acme.io"]).json()["id"]
    r = client.post(f"{BASE}/{sid}/send-now", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "sent"
    assert [m.to for m in mailbox.messages] == ["own@acme.io"]
    name, data, mime = mailbox.messages[0].attachments[0]
    assert name.endswith(".pdf") and data.startswith(b"%PDF") and mime == "application/pdf"


def test_send_now_is_rate_limited(client, mailbox):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    sid = _create(client, h).json()["id"]
    codes = [client.post(f"{BASE}/{sid}/send-now", headers=h).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


def test_send_now_reports_when_email_is_not_set_up(client):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    sid = _create(client, h).json()["id"]
    reports._manual_sends.clear()
    r = client.post(f"{BASE}/{sid}/send-now", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "not_configured"


def test_preview_pdf_download(client):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    sid = _create(client, h).json()["id"]
    r = client.get(f"{BASE}/{sid}/preview.pdf", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"


def _make_due(db, sid):
    db.expire_all()
    row = db.query(ReportSchedule).filter(ReportSchedule.id == sid).first()
    row.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()


def test_due_report_is_sent_once_and_rescheduled(client, db_session, mailbox):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    sid = _create(client, h, recipients=["ciso@acme.io", "board@acme.io"], include_pdf=False).json()["id"]
    assert reports.run_due_reports(db_session) == 0  # not due yet
    _make_due(db_session, sid)
    assert reports.run_due_reports(db_session) == 1
    assert sorted(m.to for m in mailbox.messages) == ["board@acme.io", "ciso@acme.io"]
    assert mailbox.messages[0].attachments == []
    assert reports.run_due_reports(db_session) == 0  # second pass sends nothing
    assert len(mailbox.messages) == 2
    db_session.expire_all()
    row = db_session.query(ReportSchedule).filter(ReportSchedule.id == sid).first()
    assert row.last_status == "sent" and row.last_error is None
    assert row.next_run_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
    assert db_session.query(AuditEvent).filter(AuditEvent.action == "report_schedule.sent").count() == 1


def test_partial_failure_and_disabled_schedules(client, db_session, mailbox):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    sid = _create(client, h, recipients=["ciso@acme.io", "bounce@acme.io"]).json()["id"]
    off = _create(client, h, enabled=False).json()["id"]
    mailbox.fail_for.add("bounce@acme.io")
    _make_due(db_session, sid)
    _make_due(db_session, off)
    assert reports.run_due_reports(db_session) == 1
    db_session.expire_all()
    row = db_session.query(ReportSchedule).filter(ReportSchedule.id == sid).first()
    assert row.last_status == "partial" and "1 of 2" in row.last_error
    assert db_session.query(ReportSchedule).filter(ReportSchedule.id == off).first().last_run_at is None


def test_due_report_without_email_setup_is_marked_not_configured(client, db_session):
    h = _owner_with_org(client, "own@acme.io", "Acme")
    sid = _create(client, h).json()["id"]
    _make_due(db_session, sid)
    assert reports.run_due_reports(db_session) == 1
    db_session.expire_all()
    assert db_session.query(ReportSchedule).filter(ReportSchedule.id == sid).first().last_status == "not_configured"


# ── Email attachments ────────────────────────────────────────────────────


def test_resend_payload_carries_attachment(monkeypatch):
    import base64

    from app.services.email import sender

    captured = {}

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"id": "x"}

        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        captured.update(kwargs.get("json") or {})
        return _Resp()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = sender.ResendProvider(api_key="re_test")
    ok = provider.send(EmailMessage(to="a@b.io", subject="s", html_body="<p>h</p>", text_body="t",
                                    from_email="r@cazoeasm.io", from_name="CAZO",
                                    attachments=[("r.pdf", b"%PDF-1.4", "application/pdf")]))
    assert ok is True
    assert captured["attachments"] == [{"filename": "r.pdf", "content": base64.b64encode(b"%PDF-1.4").decode()}]
