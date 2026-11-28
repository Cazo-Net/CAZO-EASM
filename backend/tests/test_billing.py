"""Billing: plan catalog, limit enforcement, Stripe webhooks and fulfilment.

No network: every Stripe call is monkeypatched. Webhooks are signed locally
with a throwaway secret.
"""
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta

import pytest

from app.billing import plans as plans_mod
from app.billing import stripe_service as svc
from app.billing.entitlements import (
    PlanLimitExceeded,
    check_scan_allowed,
    check_schedule_allowed,
    check_seat_available,
    get_entitlement,
    root_domain,
)
from app.config import settings
from app.models.billing import BillingEvent, BillingInvoice, BillingSubscription
from app.models.organization import Organization
from app.models.scan import Scan
from app.models.user import User

WEBHOOK_SECRET = "whsec_test_dummy"


@pytest.fixture
def org(db_session):
    org = Organization(name="Acme", slug=f"acme-{time.time_ns()}")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ENFORCE_LIMITS", True)


@pytest.fixture
def stripe_test(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "BILLING_ALLOW_LIVE_KEYS", False)


def _scan(db, org, domain, when=None):
    s = Scan(domain=domain, organization_id=org.id, status="completed")
    if when:
        s.created_at = when
    db.add(s)
    db.commit()
    return s


def _subscribe(db, org, plan, quantity=1, extra=0, end_days=365, status="active"):
    sub = BillingSubscription(
        organization_id=org.id, plan=plan, status=status, quantity=quantity, extra_domains=extra,
        payment_mode="manual",
        current_period_end=datetime.now(UTC) + timedelta(days=end_days),
    )
    db.add(sub)
    db.commit()
    return sub


def _signed(payload: dict):
    body = json.dumps(payload)
    ts = int(time.time())
    sig = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
    return body, f"t={ts},v1={sig}"


# ── Catalog ──────────────────────────────────────────────────────────────


class TestCatalog:
    def test_business_plan_prices(self):
        plan = plans_mod.get_plan("business")
        assert plan.term_price("usd", "year") == 1_200_000
        assert plan.term_price("usd", "quarter") == 300_000

    def test_mssp_limits_scale_per_client(self):
        mssp = plans_mod.get_plan("mssp")
        limits = plans_mod.plan_limits(mssp, quantity=12, extra_domains=2)
        assert limits["root_domains"] == 3 * 12 + 2
        assert limits["hosts"] == 250 * 12
        assert limits["users"] is None

    def test_order_total_with_addon(self):
        mssp = plans_mod.get_plan("mssp")
        total = plans_mod.order_total(mssp, "year", 10, 1, "usd")
        assert total == 20_000 * 12 * 10 + 10_000 * 12

    def test_json_override(self, monkeypatch):
        monkeypatch.setattr(settings, "BILLING_PLANS_JSON",
                            json.dumps({"business": {"prices": {"myr": 450_000}, "limits": {"users": 20}}}))
        plans_mod.reload_catalog()
        try:
            plan = plans_mod.get_plan("business")
            assert plan.monthly_price("myr") == 450_000
            assert plan.monthly_price("usd") == 100_000
            assert plan.limits["users"] == 20
            assert plan.limits["root_domains"] == 10
        finally:
            monkeypatch.setattr(settings, "BILLING_PLANS_JSON", "")
            plans_mod.reload_catalog()

    def test_plans_endpoint_is_public(self, client):
        resp = client.get("/api/v1/billing/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert [p["id"] for p in data["plans"]] == ["essentials", "business", "plus", "mssp"]
        assert data["checkout_enabled"] is False  # no key in tests

    def test_quote(self, client):
        resp = client.post("/api/v1/billing/quote", json={"plan": "mssp", "interval": "year", "clients": 3})
        assert resp.status_code == 200
        assert resp.json()["clients"] == 10  # raised to the minimum


class TestRootDomain:
    @pytest.mark.parametrize("target,expected", [
        ("example.com", "example.com"),
        ("a.b.example.com", "example.com"),
        ("https://shop.example.com.my/path", "example.com.my"),
        ("www.example.co.uk", "example.co.uk"),
        ("*.example.com", "example.com"),
        ("8.8.8.8", "8.8.8.8"),
        ("Example.COM:8443", "example.com"),
    ])
    def test_root_domain(self, target, expected):
        assert root_domain(target) == expected


# ── Enforcement ──────────────────────────────────────────────────────────


class TestLimits:
    def test_no_subscription_is_trial(self, db_session, org):
        ent = get_entitlement(db_session, org.id)
        assert ent.plan.id == "free"
        assert ent.limits["root_domains"] == 1

    def test_trial_blocks_second_root_domain(self, db_session, org, enforce):
        _scan(db_session, org, "example.com")
        check_scan_allowed(db_session, org.id, "api.example.com")  # same root: fine
        with pytest.raises(PlanLimitExceeded) as exc:
            check_scan_allowed(db_session, org.id, "other.org")
        assert exc.value.metric == "root_domains"

    def test_paid_plan_allows_more_domains(self, db_session, org, enforce):
        _subscribe(db_session, org, "essentials")
        for d in ("a.com", "b.com"):
            _scan(db_session, org, d)
        check_scan_allowed(db_session, org.id, "c.com")
        _scan(db_session, org, "c.com")
        with pytest.raises(PlanLimitExceeded):
            check_scan_allowed(db_session, org.id, "d.com")

    def test_extra_domains_add_allowance(self, db_session, org, enforce):
        _subscribe(db_session, org, "essentials", extra=1)
        for d in ("a.com", "b.com", "c.com"):
            _scan(db_session, org, d)
        check_scan_allowed(db_session, org.id, "d.com")

    def test_expired_plan_falls_back_to_trial(self, db_session, org, enforce, monkeypatch):
        monkeypatch.setattr(settings, "BILLING_GRACE_DAYS", 7)
        _subscribe(db_session, org, "business", end_days=-8)
        ent = get_entitlement(db_session, org.id)
        assert ent.plan.id == "free"
        assert ent.status == "expired"

    def test_grace_period_keeps_plan(self, db_session, org, monkeypatch):
        monkeypatch.setattr(settings, "BILLING_GRACE_DAYS", 7)
        _subscribe(db_session, org, "business", end_days=-2, status="past_due")
        assert get_entitlement(db_session, org.id).plan.id == "business"

    def test_monthly_scan_quota(self, db_session, org, enforce):
        for _ in range(10):
            _scan(db_session, org, "example.com")
        # Last month's scans do not count
        _scan(db_session, org, "example.com", when=datetime.now(UTC) - timedelta(days=40))
        with pytest.raises(PlanLimitExceeded) as exc:
            check_scan_allowed(db_session, org.id, "example.com")
        assert exc.value.metric == "scans_per_month"
        # Ad-hoc v2 scans that do not create a Scan row skip the quota
        check_scan_allowed(db_session, org.id, "example.com", counts_toward_quota=False)

    def test_schedule_frequency(self, db_session, org, enforce):
        _subscribe(db_session, org, "essentials")  # weekly
        with pytest.raises(PlanLimitExceeded) as exc:
            check_schedule_allowed(db_session, org.id, "example.com", 24)
        assert exc.value.metric == "scan_frequency"
        check_schedule_allowed(db_session, org.id, "example.com", 168)

    def test_seats(self, db_session, org, enforce):
        for i in range(2):
            db_session.add(User(email=f"u{i}@acme.test", organization_id=org.id, is_active=True))
        db_session.commit()
        with pytest.raises(PlanLimitExceeded) as exc:
            check_seat_available(db_session, org.id)
        assert exc.value.metric == "users"

    def test_enforcement_switch(self, db_session, org, monkeypatch):
        monkeypatch.setattr(settings, "BILLING_ENFORCE_LIMITS", False)
        _scan(db_session, org, "example.com")
        check_scan_allowed(db_session, org.id, "other.org")

    def test_scan_api_returns_402(self, client, auth_headers, enforce, monkeypatch):
        import app.services.scan_dispatch as dispatch

        monkeypatch.setattr(dispatch, "dispatch_scan_v2", lambda *a, **k: None)
        headers = {"Authorization": auth_headers["Authorization"]}
        assert client.post("/api/v1/organizations", json={"name": "Acme"}, headers=headers).status_code in (200, 201)
        first = client.post("/api/v1/scans", json={"domain": "example.com"}, headers=headers)
        assert first.status_code == 200, first.text
        second = client.post("/api/v1/scans", json={"domain": "other.org"}, headers=headers)
        assert second.status_code == 402
        detail = second.json()["detail"]
        assert detail["code"] == "plan_limit_reached"
        assert detail["metric"] == "root_domains"

        overview = client.get("/api/v1/billing/subscription", headers=headers)
        assert overview.status_code == 200
        body = overview.json()
        assert body["plan"]["id"] == "free"
        assert body["usage"]["root_domains"] == {"used": 1, "limit": 1, "unlimited": False}


    def test_schedule_api_frequency_402(self, client, auth_headers, enforce):
        headers = {"Authorization": auth_headers["Authorization"]}
        client.post("/api/v1/organizations", json={"name": "Acme"}, headers=headers)
        resp = client.post("/api/v1/scanner-v2/schedule",
                           json={"domain": "example.com", "interval_hours": 24}, headers=headers)
        assert resp.status_code == 402
        assert resp.json()["detail"]["metric"] == "scan_frequency"


# ── Stripe ───────────────────────────────────────────────────────────────


class TestStripeSafety:
    def test_live_key_refused(self, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_live_dummy")
        monkeypatch.setattr(settings, "BILLING_ALLOW_LIVE_KEYS", False)
        assert svc.is_configured() is False
        with pytest.raises(svc.BillingNotConfigured):
            svc._key()

    def test_checkout_without_key_is_503(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
        headers = {"Authorization": auth_headers["Authorization"]}
        client.post("/api/v1/organizations", json={"name": "Acme"}, headers=headers)
        resp = client.post("/api/v1/billing/checkout", json={"plan": "business"}, headers=headers)
        assert resp.status_code == 503

    def test_checkout_rejects_bad_orders(self, client, auth_headers, stripe_test):
        headers = {"Authorization": auth_headers["Authorization"]}
        client.post("/api/v1/organizations", json={"name": "Acme"}, headers=headers)
        resp = client.post("/api/v1/billing/checkout", json={"plan": "internal"}, headers=headers)
        assert resp.status_code == 400
        resp = client.post("/api/v1/billing/checkout", json={"plan": "mssp", "clients": 2}, headers=headers)
        assert resp.status_code == 400


class TestCheckoutSession:
    def test_subscription_checkout_params(self, db_session, org, stripe_test, monkeypatch):
        calls = {}

        class Obj:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        monkeypatch.setattr(svc.stripe.Product, "retrieve", lambda *a, **k: Obj(id=a[0]))
        monkeypatch.setattr(svc.stripe.Customer, "create", lambda **k: Obj(id="cus_123"))

        def fake_session(**kw):
            calls.update(kw)
            return Obj(id="cs_test_1", url="https://checkout.stripe.test/cs_test_1")

        monkeypatch.setattr(svc.stripe.checkout.Session, "create", fake_session)
        out = svc.create_checkout_session(
            db_session, org, "owner@acme.test", plan_id="mssp", interval="quarter",
            quantity=10, extra_domains=2, payment="subscription",
        )
        assert out["url"].startswith("https://checkout.stripe.test/")
        assert calls["mode"] == "subscription"
        assert calls["customer"] == "cus_123"
        main, addon = calls["line_items"]
        assert main["quantity"] == 10
        assert main["price_data"]["unit_amount"] == 20_000 * 3
        assert main["price_data"]["recurring"] == {"interval": "month", "interval_count": 3}
        assert addon["quantity"] == 2
        assert calls["subscription_data"]["metadata"]["plan"] == "mssp"

    def test_prepaid_checkout_is_one_off(self, db_session, org, stripe_test, monkeypatch):
        calls = {}

        class Obj:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        monkeypatch.setattr(svc.stripe.Product, "retrieve", lambda *a, **k: Obj(id=a[0]))
        monkeypatch.setattr(svc.stripe.Customer, "create", lambda **k: Obj(id="cus_123"))
        monkeypatch.setattr(svc.stripe.checkout.Session, "create",
                            lambda **kw: calls.update(kw) or Obj(id="cs_2", url="https://x"))
        svc.create_checkout_session(db_session, org, None, plan_id="business", interval="year", payment="prepaid")
        assert calls["mode"] == "payment"
        assert "recurring" not in calls["line_items"][0]["price_data"]
        assert calls["line_items"][0]["price_data"]["unit_amount"] == 1_200_000


class TestWebhooks:
    def test_bad_signature_rejected(self, client, stripe_test):
        resp = client.post("/api/v1/billing/webhook", content=b"{}",
                           headers={"stripe-signature": "t=1,v1=bad"})
        assert resp.status_code == 400

    def test_subscription_event_sets_plan(self, client, db_session, org, stripe_test):
        now = int(time.time())
        event = {
            "id": "evt_1",
            "type": "customer.subscription.updated",
            "data": {"object": {
                "id": "sub_1",
                "object": "subscription",
                "customer": "cus_1",
                "status": "active",
                "currency": "usd",
                "cancel_at_period_end": False,
                "metadata": {"organization_id": org.id, "plan": "business", "interval": "year",
                             "quantity": "1", "extra_domains": "3"},
                "items": {"data": [{"id": "si_1", "current_period_start": now,
                                    "current_period_end": now + 365 * 86400}]},
            }},
        }
        body, sig = _signed(event)
        resp = client.post("/api/v1/billing/webhook", content=body, headers={"stripe-signature": sig})
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        ent = get_entitlement(db_session, org.id)
        assert ent.plan.id == "business"
        assert ent.limits["root_domains"] == 13
        assert db_session.get(Organization, org.id).plan == "business"

        # Replaying the same event is a no-op
        resp = client.post("/api/v1/billing/webhook", content=body, headers={"stripe-signature": sig})
        assert resp.status_code == 200
        assert db_session.query(BillingEvent).count() == 1

        # Cancellation drops back to the trial once the period is over
        event["id"] = "evt_2"
        event["type"] = "customer.subscription.deleted"
        event["data"]["object"].update(status="canceled", ended_at=now - 30 * 86400)
        body, sig = _signed(event)
        client.post("/api/v1/billing/webhook", content=body, headers={"stripe-signature": sig})
        db_session.expire_all()
        assert get_entitlement(db_session, org.id).plan.id == "free"

    def test_prepaid_session_grants_term_once(self, client, db_session, org, stripe_test):
        event = {
            "id": "evt_p1",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_paid_1",
                "object": "checkout.session",
                "mode": "payment",
                "payment_status": "paid",
                "status": "complete",
                "customer": "cus_9",
                "client_reference_id": org.id,
                "amount_total": 600_000,
                "currency": "usd",
                "invoice": None,
                "metadata": {"organization_id": org.id, "plan": "essentials", "interval": "year",
                             "quantity": "1", "extra_domains": "0", "payment": "prepaid"},
            }},
        }
        body, sig = _signed(event)
        assert client.post("/api/v1/billing/webhook", content=body,
                           headers={"stripe-signature": sig}).status_code == 200
        db_session.expire_all()
        sub = db_session.query(BillingSubscription).filter_by(organization_id=org.id).one()
        assert sub.plan == "essentials" and sub.payment_mode == "prepaid"
        end = sub.current_period_end
        end = end if end.tzinfo else end.replace(tzinfo=UTC)
        assert timedelta(days=360) < end - datetime.now(UTC) < timedelta(days=370)
        assert db_session.query(BillingInvoice).filter_by(organization_id=org.id).count() == 1

        # Applying the same session again (success page after the webhook) does nothing
        svc.apply_prepaid_session(db_session, event["data"]["object"])
        assert db_session.query(BillingInvoice).filter_by(organization_id=org.id).count() == 1

    def test_unpaid_async_session_does_not_grant(self, db_session, org, stripe_test):
        session = {"id": "cs_pending", "mode": "payment", "payment_status": "unpaid",
                   "client_reference_id": org.id, "metadata": {"organization_id": org.id, "plan": "plus"}}
        assert svc.apply_prepaid_session(db_session, session) is None
        assert get_entitlement(db_session, org.id).plan.id == "free"


class TestManualPlan:
    def test_superuser_only(self, client, auth_headers, db_session):
        headers = {"Authorization": auth_headers["Authorization"]}
        client.post("/api/v1/organizations", json={"name": "Acme"}, headers=headers)
        user = db_session.query(User).filter_by(email=auth_headers["email"]).one()
        url = f"/api/v1/billing/admin/organizations/{user.organization_id}/plan"
        assert client.post(url, json={"plan": "plus"}, headers=headers).status_code == 403

        user.role = "superuser"
        db_session.commit()
        resp = client.post(url, json={"plan": "plus", "extra_domains": 5}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["limits"]["root_domains"] == 30
