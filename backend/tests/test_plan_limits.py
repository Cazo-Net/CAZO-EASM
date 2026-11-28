"""Plan limits on every path that adds a root domain, a scan, a schedule or a seat.

Complements tests/test_billing.py (catalog, Stripe, basic checks). These cover
the bypasses found in the November 2026 billing review: scopes, ad-hoc and
streamed Scanner v2 scans, monitors, stacked schedules, downgrades, staff
plans, client-set org plans and re-enabled users.
"""
import time
from datetime import UTC, datetime, timedelta

import pytest

from app.billing import entitlements as ent_mod
from app.billing import stripe_service as svc
from app.billing.entitlements import (
    PlanLimitExceeded,
    check_root_domain_allowed,
    check_scan_allowed,
    check_schedule_allowed,
    count_scans_this_month,
    monitored_root_domains,
    plan_change_conflicts,
    record_adhoc_scan,
    root_domain_status,
)
from app.billing.plans import get_plan, plan_limits
from app.config import settings
from app.models.billing import BillingSubscription
from app.models.organization import Organization
from app.models.scan import Scan
from app.models.scope import AuthorizedScope
from app.models.user import User
from app.models.v2_scanner import MonitorSchedule


@pytest.fixture
def org(db_session):
    org = Organization(name="Acme", slug=f"acme-{time.time_ns()}")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture(autouse=True)
def enforce(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ENFORCE_LIMITS", True)


def _scan(db, org, domain, when=None):
    s = Scan(domain=domain, organization_id=org.id, status="completed")
    if when:
        s.created_at = when
    db.add(s)
    db.commit()
    return s


def _scope(db, org, value, scope_type="domain", when=None):
    s = AuthorizedScope(organization_id=org.id, scope_type=scope_type, value=value, verified=True)
    if when:
        s.created_at = when
    db.add(s)
    db.commit()
    return s


def _subscribe(db, org, plan, quantity=1, extra=0, end_days=365, mode="manual"):
    sub = db.query(BillingSubscription).filter_by(organization_id=org.id).first()
    if sub is None:
        sub = BillingSubscription(organization_id=org.id)
        db.add(sub)
    sub.plan, sub.status, sub.quantity, sub.extra_domains = plan, "active", quantity, extra
    sub.payment_mode = mode
    sub.current_period_end = datetime.now(UTC) + timedelta(days=end_days)
    db.commit()
    return sub


def _owner_headers(client, auth_headers):
    headers = {"Authorization": auth_headers["Authorization"]}
    resp = client.post("/api/v1/organizations", json={"name": "Acme"}, headers=headers)
    assert resp.status_code in (200, 201), resp.text
    return headers, resp.json()["id"]


# ── Root domains: what counts ────────────────────────────────────────────


class TestRootDomainCounting:
    def test_scopes_count_as_root_domains(self, db_session, org):
        _scope(db_session, org, "example.com")
        _scope(db_session, org, "*.example.com", "wildcard")  # same root
        _scope(db_session, org, "10.0.0.0/24", "cidr")  # not a domain
        assert monitored_root_domains(db_session, org.id) == {"example.com"}

    def test_scope_and_scan_union(self, db_session, org):
        _scope(db_session, org, "a.com")
        _scan(db_session, org, "www.b.com")
        assert monitored_root_domains(db_session, org.id) == {"a.com", "b.com"}

    def test_recent_adhoc_scans_count(self, db_session, org):
        record_adhoc_scan(db_session, org.id, None, "c.org", "quick")
        assert "c.org" in monitored_root_domains(db_session, org.id)
        assert count_scans_this_month(db_session, org.id) == 1

    def test_old_adhoc_scans_free_the_slot(self, db_session, org):
        from app.models.v2_scanner import ScanHistory

        record_adhoc_scan(db_session, org.id, None, "c.org", "quick")
        row = db_session.query(ScanHistory).one()
        row.created_at = datetime.now(UTC) - timedelta(days=31)
        db_session.commit()
        assert monitored_root_domains(db_session, org.id) == set()

    def test_status_marks_oldest_active(self, db_session, org):
        now = datetime.now(UTC)
        _scan(db_session, org, "old.com", when=now - timedelta(days=30))
        _scope(db_session, org, "mid.com", when=now - timedelta(days=20))
        _scan(db_session, org, "new.com", when=now - timedelta(days=1))
        status = root_domain_status(db_session, org.id, 2)
        assert [(d["domain"], d["active"]) for d in status] == [
            ("old.com", True), ("mid.com", True), ("new.com", False),
        ]


# ── Root domains: enforcement ────────────────────────────────────────────


class TestRootDomainEnforcement:
    def test_trial_blocks_second_domain_via_scope(self, db_session, org):
        _scope(db_session, org, "example.com")
        check_root_domain_allowed(db_session, org.id, "api.example.com")
        with pytest.raises(PlanLimitExceeded) as exc:
            check_root_domain_allowed(db_session, org.id, "other.org")
        assert exc.value.metric == "root_domains"
        assert exc.value.limit == 1 and exc.value.used == 1

    def test_downgrade_pauses_newest_domains(self, db_session, org):
        _subscribe(db_session, org, "business")
        now = datetime.now(UTC)
        for i, d in enumerate(["a.com", "b.com", "c.com", "d.com", "e.com"]):
            _scan(db_session, org, d, when=now - timedelta(days=10 - i))
        _subscribe(db_session, org, "essentials")  # 3 root domains
        for d in ("a.com", "b.com", "c.com"):
            check_scan_allowed(db_session, org.id, d)
        with pytest.raises(PlanLimitExceeded) as exc:
            check_scan_allowed(db_session, org.id, "d.com")
        assert "paused" in exc.value.message
        with pytest.raises(PlanLimitExceeded):
            check_scan_allowed(db_session, org.id, "new.com")

    def test_expired_plan_pauses_all_but_oldest(self, db_session, org, monkeypatch):
        monkeypatch.setattr(settings, "BILLING_GRACE_DAYS", 7)
        _subscribe(db_session, org, "business", end_days=-30)
        now = datetime.now(UTC)
        _scan(db_session, org, "first.com", when=now - timedelta(days=5))
        _scan(db_session, org, "second.com", when=now - timedelta(days=1))
        check_scan_allowed(db_session, org.id, "first.com")
        with pytest.raises(PlanLimitExceeded):
            check_scan_allowed(db_session, org.id, "second.com")

    def test_removing_a_scope_frees_the_slot(self, db_session, org):
        scope = _scope(db_session, org, "example.com")
        db_session.delete(scope)
        db_session.commit()
        check_root_domain_allowed(db_session, org.id, "other.org")

    def test_internal_plan_unlimited(self, db_session, org):
        _subscribe(db_session, org, "internal")
        for i in range(30):
            _scope(db_session, org, f"d{i}.com")
        check_root_domain_allowed(db_session, org.id, "one-more.com")


class TestScopeApi:
    def test_scope_over_limit_is_402(self, client, auth_headers):
        headers, _ = _owner_headers(client, auth_headers)
        ok = client.post("/api/v1/scopes", json={"scope_type": "domain", "value": "example.com"}, headers=headers)
        assert ok.status_code == 201, ok.text
        same_root = client.post("/api/v1/scopes", json={"scope_type": "wildcard", "value": "*.example.com"},
                                headers=headers)
        assert same_root.status_code == 201
        over = client.post("/api/v1/scopes", json={"scope_type": "domain", "value": "other.org"}, headers=headers)
        assert over.status_code == 402
        detail = over.json()["detail"]
        assert detail["code"] == "plan_limit_reached" and detail["metric"] == "root_domains"
        assert "other.org" in detail["message"]
        # IP scopes are not root domains.
        ip = client.post("/api/v1/scopes", json={"scope_type": "ip", "value": "8.8.8.8"}, headers=headers)
        assert ip.status_code == 201

    def test_refused_scan_leaves_no_scope(self, client, auth_headers, db_session, monkeypatch):
        monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "verified")
        headers, org_id = _owner_headers(client, auth_headers)
        client.post("/api/v1/scopes", json={"scope_type": "domain", "value": "example.com"}, headers=headers)
        resp = client.post("/api/v1/scans", json={"domain": "other.org"}, headers=headers)
        assert resp.status_code == 402
        values = {s.value for s in db_session.query(AuthorizedScope).filter_by(organization_id=org_id)}
        assert values == {"example.com"}


# ── Scanner v2 ───────────────────────────────────────────────────────────


@pytest.fixture
def fake_runner(monkeypatch):
    from app.scanners.v2 import runner as runner_mod

    async def fake(self, domain, config=None, **kw):
        return {"assets": {"subdomains": [domain]}, "pipeline": {}, "risk_score": {}}

    monkeypatch.setattr(runner_mod.EnhancedScanRunner, "run_scan", fake)
    monkeypatch.setattr(runner_mod.EnhancedScanRunner, "run_quick_scan", fake)


class TestScannerV2:
    def test_adhoc_scans_use_monthly_quota(self, client, auth_headers, db_session, fake_runner):
        headers, org_id = _owner_headers(client, auth_headers)
        for _ in range(10):
            _scan(db_session, db_session.get(Organization, org_id), "example.com")
        resp = client.post("/api/v1/scanner-v2/scan", json={"domain": "example.com"}, headers=headers)
        assert resp.status_code == 402
        assert resp.json()["detail"]["metric"] == "scans_per_month"

    def test_adhoc_scan_counts_and_blocks_new_root(self, client, auth_headers, db_session, fake_runner):
        headers, org_id = _owner_headers(client, auth_headers)
        first = client.post("/api/v1/scanner-v2/scan", json={"domain": "example.com"}, headers=headers)
        assert first.status_code == 200, first.text
        assert count_scans_this_month(db_session, org_id) == 1
        second = client.post("/api/v1/scanner-v2/scan", json={"domain": "other.org"}, headers=headers)
        assert second.status_code == 402
        assert second.json()["detail"]["metric"] == "root_domains"

    def test_monitor_respects_frequency(self, client, auth_headers):
        headers, _ = _owner_headers(client, auth_headers)
        resp = client.post("/api/v1/scanner-v2/monitor",
                           json={"domain": "example.com", "interval_hours": 1}, headers=headers)
        assert resp.status_code == 402
        assert resp.json()["detail"]["metric"] == "scan_frequency"

    def test_monitor_respects_root_domains(self, client, auth_headers, db_session):
        headers, org_id = _owner_headers(client, auth_headers)
        _scan(db_session, db_session.get(Organization, org_id), "example.com")
        resp = client.post("/api/v1/scanner-v2/monitor",
                           json={"domain": "other.org", "interval_hours": 168}, headers=headers)
        assert resp.status_code == 402
        assert resp.json()["detail"]["metric"] == "root_domains"


# ── Schedules ────────────────────────────────────────────────────────────


def _schedule(db, org, domain, hours, enabled=True):
    import uuid

    row = MonitorSchedule(id=str(uuid.uuid4()), domain=domain, interval_hours=hours, enabled=enabled,
                          created_by="u", organization_id=org.id, next_run_at=datetime.now(UTC))
    db.add(row)
    db.commit()
    return row


class TestSchedules:
    def test_weekly_schedules_cannot_stack(self, db_session, org):
        _schedule(db_session, org, "example.com", 168)
        with pytest.raises(PlanLimitExceeded) as exc:
            check_schedule_allowed(db_session, org.id, "www.example.com", 168)
        assert exc.value.metric == "scan_frequency"

    def test_disabled_and_excluded_schedules_do_not_count(self, db_session, org):
        _schedule(db_session, org, "example.com", 168, enabled=False)
        check_schedule_allowed(db_session, org.id, "example.com", 168)
        row = _schedule(db_session, org, "example.com", 168)
        check_schedule_allowed(db_session, org.id, "example.com", 168, exclude_schedule_id=row.id)

    def test_daily_plan_allows_two_every_other_day(self, db_session, org):
        _subscribe(db_session, org, "business")
        _schedule(db_session, org, "example.com", 48)
        check_schedule_allowed(db_session, org.id, "example.com", 48)
        _schedule(db_session, org, "example.com", 48)
        with pytest.raises(PlanLimitExceeded):
            check_schedule_allowed(db_session, org.id, "example.com", 48)

    def test_scheduler_clamps_interval_and_skips_paused(self, db_session, org, monkeypatch):
        from app.services import periodic

        monkeypatch.setattr("app.services.job_queue.enqueue_scan", lambda *a, **k: None)
        monkeypatch.setattr(settings, "SCOPE_ENFORCEMENT", "open")
        now = datetime.now(UTC)
        _scan(db_session, org, "keep.com", when=now - timedelta(days=5))
        _scan(db_session, org, "paused.com", when=now - timedelta(days=1))
        keep = _schedule(db_session, org, "keep.com", 24)  # Trial is weekly
        paused = _schedule(db_session, org, "paused.com", 168)
        keep_id, paused_id = keep.id, paused.id

        assert periodic.run_due_schedules(db_session) == 1
        db_session.expire_all()
        keep = db_session.get(MonitorSchedule, keep_id)
        gap = ent_mod._aware(keep.next_run_at) - ent_mod._aware(keep.last_run_at)
        assert gap >= timedelta(hours=168)
        domains = [s.domain for s in db_session.query(Scan).filter_by(organization_id=org.id)
                   .filter(Scan.created_at >= now - timedelta(minutes=1))]
        assert "paused.com" not in domains
        assert db_session.get(MonitorSchedule, paused_id) is not None


# ── Plan changes ─────────────────────────────────────────────────────────


class TestPlanChanges:
    def test_conflicts_listed(self, db_session, org):
        for d in ("a.com", "b.com", "c.com", "d.com"):
            _scan(db_session, org, d)
        conflicts = plan_change_conflicts(db_session, org.id, plan_limits(get_plan("essentials")))
        assert conflicts == [{"metric": "root_domains", "used": 4, "limit": 3}]
        assert plan_change_conflicts(db_session, org.id, plan_limits(get_plan("essentials"), 1, 1)) == []

    def test_checkout_downgrade_needs_confirmation(self, client, auth_headers, db_session, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy")
        monkeypatch.setattr(settings, "BILLING_ALLOW_LIVE_KEYS", False)
        monkeypatch.setattr(svc, "create_checkout_session", lambda *a, **k: {"url": "https://x", "updated": False})
        headers, org_id = _owner_headers(client, auth_headers)
        org = db_session.get(Organization, org_id)
        for d in ("a.com", "b.com", "c.com", "d.com"):
            _scan(db_session, org, d)
        order = {"plan": "essentials", "interval": "year"}
        refused = client.post("/api/v1/billing/checkout", json=order, headers=headers)
        assert refused.status_code == 409
        detail = refused.json()["detail"]
        assert detail["code"] == "plan_change_over_limit"
        assert detail["conflicts"][0]["metric"] == "root_domains"
        ok = client.post("/api/v1/billing/checkout", json=order | {"accept_over_limit": True}, headers=headers)
        assert ok.status_code == 200, ok.text
        # Buying an extra domain removes the conflict without confirmation.
        ok2 = client.post("/api/v1/billing/checkout", json=order | {"extra_domains": 1}, headers=headers)
        assert ok2.status_code == 200

    def test_staff_managed_plan_cannot_checkout(self, client, auth_headers, db_session, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy")
        headers, org_id = _owner_headers(client, auth_headers)
        _subscribe(db_session, db_session.get(Organization, org_id), "business", mode="manual")
        resp = client.post("/api/v1/billing/checkout", json={"plan": "plus"}, headers=headers)
        assert resp.status_code == 409
        overview = client.get("/api/v1/billing/subscription", headers=headers).json()
        assert overview["managed_by_staff"] is True

    def test_overview_lists_root_domains(self, client, auth_headers, db_session):
        headers, org_id = _owner_headers(client, auth_headers)
        org = db_session.get(Organization, org_id)
        now = datetime.now(UTC)
        _scan(db_session, org, "a.com", when=now - timedelta(days=2))
        _scope(db_session, org, "b.com")
        body = client.get("/api/v1/billing/subscription", headers=headers).json()
        assert [(d["domain"], d["active"]) for d in body["root_domains"]] == [("a.com", True), ("b.com", False)]
        assert body["usage"]["root_domains"]["used"] == 2
        assert body["managed_by_staff"] is False


# ── Organization plan field and seats ────────────────────────────────────


class TestOrgPlanAndSeats:
    def test_client_cannot_set_org_plan(self, client, auth_headers, db_session):
        headers = {"Authorization": auth_headers["Authorization"]}
        resp = client.post("/api/v1/organizations", json={"name": "Acme", "plan": "internal"}, headers=headers)
        assert resp.status_code in (200, 201)
        org_id = resp.json()["id"]
        assert resp.json()["plan"] == "free"
        upd = client.put(f"/api/v1/organizations/{org_id}", json={"plan": "plus", "name": "Acme 2"}, headers=headers)
        assert upd.status_code == 200
        assert upd.json()["plan"] == "free" and upd.json()["name"] == "Acme 2"

    def test_reenabling_user_needs_a_seat(self, client, auth_headers, db_session):
        headers, org_id = _owner_headers(client, auth_headers)
        db_session.add(User(email="b@acme.test", organization_id=org_id, is_active=True))
        disabled = User(email="c@acme.test", organization_id=org_id, is_active=False)
        db_session.add(disabled)
        db_session.commit()
        resp = client.put(f"/api/v1/admin/users/{disabled.id}/enable", headers=headers)
        assert resp.status_code == 402, resp.text
        assert resp.json()["detail"]["metric"] == "users"
