"""Stripe integration: checkout, customer portal, payment methods, webhooks.

Payment flows:

* ``subscription``: Stripe Checkout in subscription mode. Renews every term
  and charges the saved payment method automatically. Cards work everywhere;
  other recurring-capable methods appear if they are enabled in the Stripe
  Dashboard.
* ``prepaid``: Stripe Checkout in payment mode for one full term (a year or a
  quarter). Does not renew by itself. This is the path for one-off local
  methods such as FPX and GrabPay, which Stripe does not support for
  recurring charges. FPX also needs a Malaysian Stripe account and MYR prices.

Payment methods are chosen by Stripe from what is enabled in the Dashboard
(dynamic payment methods), so turning a method on needs no code change.

Prices are sent inline (``price_data``) against one Stripe product per plan,
created on first use with a fixed id, so no Price ids need to be configured.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import stripe
from sqlalchemy.orm import Session

from app.billing.entitlements import get_subscription, subscription_is_current
from app.billing.plans import (
    EXTRA_DOMAIN_ADDON_ID,
    FREE_PLAN_ID,
    INTERVALS,
    catalog,
    get_plan,
)
from app.config import frontend_url, settings
from app.models.billing import BillingEvent, BillingInvoice, BillingSubscription
from app.models.organization import Organization

logger = logging.getLogger(__name__)


class BillingNotConfigured(RuntimeError):
    pass


class BillingError(ValueError):
    """A request that cannot be fulfilled (bad plan, wrong state, ...)."""


# ── Setup ────────────────────────────────────────────────────────────────


def stripe_mode() -> str:
    """'test', 'live' or 'off' depending on the configured secret key."""
    key = settings.STRIPE_SECRET_KEY or ""
    if not key:
        return "off"
    return "live" if "_live_" in key else "test"


def is_configured() -> bool:
    mode = stripe_mode()
    if mode == "off":
        return False
    return mode == "test" or settings.BILLING_ALLOW_LIVE_KEYS


def _key() -> str:
    mode = stripe_mode()
    if mode == "off":
        raise BillingNotConfigured("Payments are not set up yet (STRIPE_SECRET_KEY is empty).")
    if mode == "live" and not settings.BILLING_ALLOW_LIVE_KEYS:
        raise BillingNotConfigured(
            "A live Stripe key is configured but BILLING_ALLOW_LIVE_KEYS is not set. "
            "Refusing to take real payments."
        )
    return settings.STRIPE_SECRET_KEY


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("to_dict_recursive", "to_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except TypeError:
                continue
    return json.loads(str(obj))


def _ts(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if value else None


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _product_id(plan_id: str) -> str:
    return f"cazo_easm_{plan_id}"


def ensure_product(plan_id: str) -> str:
    """Return the Stripe product id for ``plan_id``, creating it on first use."""
    key = _key()
    pid = _product_id(plan_id)
    try:
        stripe.Product.retrieve(pid, api_key=key)
    except stripe.InvalidRequestError:
        plan = get_plan(plan_id) if plan_id in catalog() else None
        stripe.Product.create(
            id=pid,
            name=f"CAZO EASM {plan.name if plan else plan_id}",
            metadata={"plan": plan_id},
            api_key=key,
        )
    return pid


def get_or_create_subscription_row(db: Session, org: Organization) -> BillingSubscription:
    sub = get_subscription(db, org.id)
    if sub is None:
        sub = BillingSubscription(
            organization_id=org.id,
            plan=FREE_PLAN_ID,
            status="none",
            currency=settings.BILLING_CURRENCY,
        )
        db.add(sub)
        db.flush()
    return sub


def ensure_customer(db: Session, org: Organization, email: str | None) -> str:
    sub = get_or_create_subscription_row(db, org)
    if sub.stripe_customer_id:
        return sub.stripe_customer_id
    customer = stripe.Customer.create(
        name=org.name,
        email=email,
        metadata={"organization_id": org.id},
        api_key=_key(),
    )
    sub.stripe_customer_id = customer.id
    db.commit()
    return customer.id


# ── Checkout ─────────────────────────────────────────────────────────────


def _validate_order(plan_id: str, interval: str, quantity: int, extra_domains: int, currency: str):
    plan = catalog().get(plan_id)
    if plan is None or not plan.purchasable:
        raise BillingError(f"Unknown plan '{plan_id}'.")
    if interval not in INTERVALS:
        raise BillingError("Billing interval must be 'year' or 'quarter'.")
    if plan.per_client:
        if quantity < plan.min_quantity:
            raise BillingError(f"The {plan.name} plan starts at {plan.min_quantity} clients.")
    else:
        quantity = 1
    if extra_domains < 0 or extra_domains > 500:
        raise BillingError("Extra root domains must be between 0 and 500.")
    if plan.term_price(currency, interval) is None:
        raise BillingError(f"No {currency.upper()} price is set for the {plan.name} plan.")
    if extra_domains and catalog()[EXTRA_DOMAIN_ADDON_ID].term_price(currency, interval) is None:
        raise BillingError(f"No {currency.upper()} price is set for extra root domains.")
    return plan, quantity


def _line_items(plan, interval: str, quantity: int, extra_domains: int, currency: str, recurring: bool):
    spec = INTERVALS[interval]

    def item(plan_id: str, unit_amount: int, qty: int) -> dict:
        price_data: dict[str, Any] = {
            "currency": currency,
            "product": ensure_product(plan_id),
            "unit_amount": unit_amount,
        }
        if recurring:
            price_data["recurring"] = {
                "interval": spec["stripe_interval"],
                "interval_count": spec["stripe_interval_count"],
            }
        return {"price_data": price_data, "quantity": qty}

    items = [item(plan.id, plan.term_price(currency, interval), quantity)]
    if extra_domains:
        addon = catalog()[EXTRA_DOMAIN_ADDON_ID]
        items.append(item(addon.id, addon.term_price(currency, interval), extra_domains))
    return items


def create_checkout_session(
    db: Session,
    org: Organization,
    user_email: str | None,
    *,
    plan_id: str,
    interval: str,
    quantity: int = 1,
    extra_domains: int = 0,
    payment: str = "subscription",
) -> dict[str, Any]:
    """Start a Stripe Checkout session, or change an existing subscription in place.

    Returns ``{"url": ...}`` to redirect to, or ``{"updated": True}`` when an
    active Stripe subscription was changed without a new checkout.
    """
    currency = settings.BILLING_CURRENCY
    plan, quantity = _validate_order(plan_id, interval, quantity, extra_domains, currency)
    if payment not in ("subscription", "prepaid"):
        raise BillingError("Payment must be 'subscription' or 'prepaid'.")
    key = _key()

    sub = get_or_create_subscription_row(db, org)
    has_auto_renew = bool(
        sub.stripe_subscription_id
        and sub.payment_mode == "subscription"
        and sub.status in ("active", "trialing", "past_due")
    )
    if has_auto_renew and payment == "prepaid":
        raise BillingError(
            "You have an auto-renewing plan. Change it here, or cancel its renewal "
            "before paying for a single term."
        )
    if has_auto_renew:
        change_subscription(db, sub, plan.id, interval, quantity, extra_domains)
        return {"updated": True, "url": None}

    customer_id = ensure_customer(db, org, user_email)
    metadata = {
        "organization_id": org.id,
        "plan": plan.id,
        "interval": interval,
        "quantity": str(quantity),
        "extra_domains": str(extra_domains),
        "payment": payment,
    }
    params: dict[str, Any] = {
        "customer": customer_id,
        "client_reference_id": org.id,
        "line_items": _line_items(plan, interval, quantity, extra_domains, currency, payment == "subscription"),
        "allow_promotion_codes": True,
        "billing_address_collection": "required",
        "tax_id_collection": {"enabled": True},
        "automatic_tax": {"enabled": bool(settings.BILLING_AUTOMATIC_TAX)},
        "customer_update": {"name": "auto", "address": "auto"},
        "metadata": metadata,
        "success_url": frontend_url("/billing/success?session_id={CHECKOUT_SESSION_ID}"),
        "cancel_url": frontend_url(f"/billing/checkout?plan={plan.id}&canceled=1"),
    }
    if payment == "subscription":
        params["mode"] = "subscription"
        params["subscription_data"] = {"metadata": metadata}
    else:
        params["mode"] = "payment"
        params["invoice_creation"] = {
            "enabled": True,
            "invoice_data": {
                "description": f"CAZO EASM {plan.name}, {INTERVALS[interval]['label'].lower()} term (prepaid)",
                "metadata": metadata,
            },
        }
        params["payment_intent_data"] = {"metadata": metadata}

    session = stripe.checkout.Session.create(api_key=key, **params)
    return {"url": session.url, "id": session.id, "updated": False}


def change_subscription(db: Session, sub: BillingSubscription, plan_id: str, interval: str,
                        quantity: int, extra_domains: int) -> None:
    """Switch an auto-renewing subscription to another plan, prorating the difference."""
    key = _key()
    currency = sub.currency or settings.BILLING_CURRENCY
    plan, quantity = _validate_order(plan_id, interval, quantity, extra_domains, currency)
    remote = _as_dict(stripe.Subscription.retrieve(sub.stripe_subscription_id, api_key=key))
    existing = [i["id"] for i in remote.get("items", {}).get("data", [])]
    new_items = _line_items(plan, interval, quantity, extra_domains, currency, recurring=True)
    items: list[dict[str, Any]] = [{"id": item_id, "deleted": True} for item_id in existing]
    items.extend(new_items)
    metadata = {
        "organization_id": sub.organization_id,
        "plan": plan.id,
        "interval": interval,
        "quantity": str(quantity),
        "extra_domains": str(extra_domains),
        "payment": "subscription",
    }
    updated = stripe.Subscription.modify(
        sub.stripe_subscription_id,
        items=items,
        metadata=metadata,
        cancel_at_period_end=False,
        proration_behavior="always_invoice",
        payment_behavior="error_if_incomplete",
        api_key=key,
    )
    apply_stripe_subscription(db, _as_dict(updated))


# ── Fulfilment (shared by webhooks and the success page) ─────────────────


def _sync_org_plan(db: Session, org_id: str, plan_id: str) -> None:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is not None and org.plan != plan_id:
        org.plan = plan_id


def _find_sub(db: Session, *, org_id: str | None = None, customer: str | None = None,
              subscription: str | None = None) -> BillingSubscription | None:
    q = db.query(BillingSubscription)
    if subscription:
        row = q.filter(BillingSubscription.stripe_subscription_id == subscription).first()
        if row:
            return row
    if org_id:
        row = q.filter(BillingSubscription.organization_id == org_id).first()
        if row:
            return row
    if customer:
        return q.filter(BillingSubscription.stripe_customer_id == customer).first()
    return None


def _period(obj: dict[str, Any]):
    start = obj.get("current_period_start")
    end = obj.get("current_period_end")
    if start is None or end is None:
        # API versions from 2025-03-31 moved the period onto subscription items.
        items = obj.get("items", {}).get("data", [])
        if items:
            start = start or items[0].get("current_period_start")
            end = end or items[0].get("current_period_end")
    return _ts(start), _ts(end)


def apply_stripe_subscription(db: Session, obj: dict[str, Any]) -> BillingSubscription | None:
    """Mirror a Stripe Subscription object onto the org's billing row."""
    meta = obj.get("metadata") or {}
    sub = _find_sub(db, org_id=meta.get("organization_id"), customer=obj.get("customer"),
                    subscription=obj.get("id"))
    if sub is None and meta.get("organization_id"):
        org = db.query(Organization).filter(Organization.id == meta["organization_id"]).first()
        if org is not None:
            sub = get_or_create_subscription_row(db, org)
    if sub is None:
        logger.warning("Stripe subscription %s has no matching organization", obj.get("id"))
        return None

    status = obj.get("status") or "active"
    status_map = {"unpaid": "past_due", "incomplete_expired": "expired", "paused": "past_due"}
    sub.status = status_map.get(status, status)
    sub.stripe_subscription_id = obj.get("id")
    sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
    sub.payment_mode = "subscription"
    if meta.get("plan") in catalog():
        sub.plan = meta["plan"]
    if meta.get("interval") in INTERVALS:
        sub.billing_interval = meta["interval"]
    try:
        sub.quantity = max(int(meta.get("quantity") or 1), 1)
        sub.extra_domains = max(int(meta.get("extra_domains") or 0), 0)
    except ValueError:
        pass
    sub.currency = (obj.get("currency") or sub.currency or "usd").lower()
    sub.current_period_start, sub.current_period_end = _period(obj)
    sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    sub.canceled_at = _ts(obj.get("canceled_at"))
    if sub.status == "canceled":
        sub.current_period_end = _ts(obj.get("ended_at")) or sub.current_period_end
    _sync_org_plan(db, sub.organization_id, sub.plan if subscription_is_current(sub) else FREE_PLAN_ID)
    db.commit()
    return sub


def apply_prepaid_session(db: Session, session: dict[str, Any]) -> BillingSubscription | None:
    """Grant a prepaid term once its checkout session is paid. Idempotent."""
    if session.get("payment_status") != "paid":
        return None
    meta = session.get("metadata") or {}
    org_id = meta.get("organization_id") or session.get("client_reference_id")
    if not org_id:
        return None
    # Already applied?
    if db.query(BillingInvoice).filter(BillingInvoice.stripe_id == session["id"]).first():
        return get_subscription(db, org_id)

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        return None
    sub = get_or_create_subscription_row(db, org)
    interval = meta.get("interval") if meta.get("interval") in INTERVALS else "year"
    months = INTERVALS[interval]["months"]
    now = datetime.now(UTC)
    current_end = _aware(sub.current_period_end)
    same_plan = sub.plan == meta.get("plan") and subscription_is_current(sub) and current_end
    start = current_end if same_plan and current_end > now else now
    end = start + timedelta(days=round(months * 365 / 12))

    sub.plan = meta.get("plan") if meta.get("plan") in catalog() else sub.plan
    sub.status = "active"
    sub.payment_mode = "prepaid"
    sub.billing_interval = interval
    sub.currency = (session.get("currency") or sub.currency or "usd").lower()
    sub.quantity = max(int(meta.get("quantity") or 1), 1)
    sub.extra_domains = max(int(meta.get("extra_domains") or 0), 0)
    sub.stripe_customer_id = session.get("customer") or sub.stripe_customer_id
    sub.current_period_start = start if not same_plan else (_aware(sub.current_period_start) or start)
    sub.current_period_end = end
    sub.cancel_at_period_end = True  # prepaid terms do not renew by themselves
    sub.last_payment_error = None

    invoice_id = session.get("invoice")
    db.add(BillingInvoice(
        organization_id=org_id,
        stripe_id=session["id"],
        number=None,
        description=f"{get_plan(sub.plan).name}, {INTERVALS[interval]['label'].lower()} term (prepaid)",
        amount_cents=session.get("amount_total") or 0,
        currency=sub.currency,
        status="paid",
        hosted_url=None,
        period_start=start,
        period_end=end,
        paid_at=now,
    ))
    _sync_org_plan(db, org_id, sub.plan)
    db.commit()
    if invoice_id:
        try:
            inv = _as_dict(stripe.Invoice.retrieve(invoice_id, api_key=_key()))
            row = db.query(BillingInvoice).filter(BillingInvoice.stripe_id == session["id"]).first()
            row.number = inv.get("number")
            row.hosted_url = inv.get("hosted_invoice_url")
            row.pdf_url = inv.get("invoice_pdf")
            db.commit()
        except Exception:  # noqa: BLE001 - the receipt link is optional
            logger.info("Could not fetch invoice %s for prepaid session", invoice_id)
    return sub


def apply_invoice(db: Session, inv: dict[str, Any], failed: bool = False) -> None:
    """Record a Stripe invoice from a subscription and flag failed payments."""
    sub = _find_sub(db, customer=inv.get("customer"))
    if sub is None:
        return
    # Invoices created for prepaid checkouts are recorded against the session.
    meta = inv.get("metadata") or {}
    if meta.get("payment") == "prepaid":
        return
    row = db.query(BillingInvoice).filter(BillingInvoice.stripe_id == inv["id"]).first()
    if row is None:
        row = BillingInvoice(organization_id=sub.organization_id, stripe_id=inv["id"])
        db.add(row)
    lines = inv.get("lines", {}).get("data", [])
    period = (lines[0].get("period") if lines else None) or {}
    row.number = inv.get("number")
    row.description = inv.get("description") or f"{get_plan(sub.plan).name} subscription"
    row.amount_cents = inv.get("amount_paid") if inv.get("status") == "paid" else inv.get("amount_due") or 0
    row.currency = (inv.get("currency") or "usd").lower()
    row.status = "failed" if failed else (inv.get("status") or "open")
    row.hosted_url = inv.get("hosted_invoice_url")
    row.pdf_url = inv.get("invoice_pdf")
    row.period_start = _ts(period.get("start"))
    row.period_end = _ts(period.get("end"))
    row.paid_at = _ts((inv.get("status_transitions") or {}).get("paid_at"))
    if failed:
        err = (inv.get("last_finalization_error") or {}).get("message")
        sub.last_payment_error = err or "The last payment attempt failed. Update your payment method."
    elif inv.get("status") == "paid":
        sub.last_payment_error = None
    db.commit()


def fulfil_checkout_session(db: Session, session: dict[str, Any]) -> None:
    mode = session.get("mode")
    if mode == "subscription" and session.get("subscription"):
        remote = stripe.Subscription.retrieve(session["subscription"], api_key=_key())
        data = _as_dict(remote)
        if not (data.get("metadata") or {}).get("organization_id"):
            data["metadata"] = session.get("metadata") or {}
        apply_stripe_subscription(db, data)
    elif mode == "payment":
        apply_prepaid_session(db, session)
    elif mode == "setup" and session.get("setup_intent"):
        si = _as_dict(stripe.SetupIntent.retrieve(session["setup_intent"], api_key=_key()))
        pm = si.get("payment_method")
        if pm and session.get("customer"):
            stripe.Customer.modify(
                session["customer"],
                invoice_settings={"default_payment_method": pm},
                api_key=_key(),
            )


def handle_webhook(db: Session, payload: bytes, signature: str | None) -> str:
    """Verify and apply a Stripe webhook. Returns the event type."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BillingNotConfigured("STRIPE_WEBHOOK_SECRET is not set.")
    _key()  # refuses live keys unless allowed
    stripe.Webhook.construct_event(payload, signature or "", settings.STRIPE_WEBHOOK_SECRET)
    event = json.loads(payload)
    event_id, event_type = event.get("id"), event.get("type", "")
    if db.query(BillingEvent).filter(BillingEvent.stripe_event_id == event_id).first():
        return event_type

    obj = (event.get("data") or {}).get("object") or {}
    record = BillingEvent(stripe_event_id=event_id, event_type=event_type)
    try:
        if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            fulfil_checkout_session(db, obj)
            record.organization_id = (obj.get("metadata") or {}).get("organization_id")
        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ):
            sub = apply_stripe_subscription(db, obj)
            record.organization_id = sub.organization_id if sub else None
        elif event_type in ("invoice.paid", "invoice.finalized", "invoice.voided",
                            "invoice.marked_uncollectible"):
            apply_invoice(db, obj)
        elif event_type == "invoice.payment_failed":
            apply_invoice(db, obj, failed=True)
    except Exception as exc:
        db.rollback()
        record.error = str(exc)[:2000]
        db.add(record)
        db.commit()
        raise
    db.add(record)
    db.commit()
    return event_type


def retrieve_checkout_session(db: Session, org: Organization, session_id: str) -> dict[str, Any]:
    """Look up a session for the success page and apply it if the webhook has not yet."""
    session = _as_dict(stripe.checkout.Session.retrieve(session_id, api_key=_key()))
    if session.get("client_reference_id") != org.id:
        raise BillingError("This checkout session belongs to another organization.")
    if session.get("status") == "complete":
        fulfil_checkout_session(db, session)
    return {
        "status": session.get("status"),
        "payment_status": session.get("payment_status"),
        "mode": session.get("mode"),
        "amount_total": session.get("amount_total"),
        "currency": session.get("currency"),
        "plan": (session.get("metadata") or {}).get("plan"),
    }


# ── Self-service management ──────────────────────────────────────────────


def portal_url(db: Session, org: Organization, email: str | None) -> str:
    customer = ensure_customer(db, org, email)
    session = stripe.billing_portal.Session.create(
        customer=customer, return_url=frontend_url("/billing"), api_key=_key()
    )
    return session.url


def setup_session_url(db: Session, org: Organization, email: str | None) -> str:
    """Checkout in setup mode: add a card for future renewals."""
    customer = ensure_customer(db, org, email)
    session = stripe.checkout.Session.create(
        mode="setup",
        customer=customer,
        client_reference_id=org.id,
        currency=settings.BILLING_CURRENCY,
        payment_method_types=["card"],
        metadata={"organization_id": org.id},
        success_url=frontend_url("/billing?payment_method=added"),
        cancel_url=frontend_url("/billing"),
        api_key=_key(),
    )
    return session.url


def list_payment_methods(sub: BillingSubscription | None) -> list[dict[str, Any]]:
    if sub is None or not sub.stripe_customer_id:
        return []
    key = _key()
    customer = _as_dict(stripe.Customer.retrieve(sub.stripe_customer_id, api_key=key))
    default_pm = (customer.get("invoice_settings") or {}).get("default_payment_method")
    methods = _as_dict(stripe.Customer.list_payment_methods(sub.stripe_customer_id, limit=20, api_key=key))
    out = []
    for pm in methods.get("data", []):
        card = pm.get("card") or {}
        out.append({
            "id": pm["id"],
            "type": pm.get("type"),
            "brand": card.get("brand") or pm.get("type"),
            "last4": card.get("last4"),
            "exp_month": card.get("exp_month"),
            "exp_year": card.get("exp_year"),
            "is_default": pm["id"] == default_pm,
        })
    return out


def _owned_pm(sub: BillingSubscription | None, pm_id: str) -> dict[str, Any]:
    if sub is None or not sub.stripe_customer_id:
        raise BillingError("No payment methods on file.")
    pm = _as_dict(stripe.PaymentMethod.retrieve(pm_id, api_key=_key()))
    if pm.get("customer") != sub.stripe_customer_id:
        raise BillingError("Payment method not found.")
    return pm


def set_default_payment_method(sub: BillingSubscription | None, pm_id: str) -> None:
    _owned_pm(sub, pm_id)
    key = _key()
    stripe.Customer.modify(sub.stripe_customer_id,
                           invoice_settings={"default_payment_method": pm_id}, api_key=key)
    if sub.stripe_subscription_id:
        stripe.Subscription.modify(sub.stripe_subscription_id,
                                   default_payment_method=pm_id, api_key=key)


def detach_payment_method(sub: BillingSubscription | None, pm_id: str) -> None:
    _owned_pm(sub, pm_id)
    stripe.PaymentMethod.detach(pm_id, api_key=_key())


def set_cancel_at_period_end(db: Session, sub: BillingSubscription | None, cancel: bool) -> BillingSubscription:
    if sub is None or not subscription_is_current(sub):
        raise BillingError("There is no active plan to change.")
    if sub.payment_mode == "subscription" and sub.stripe_subscription_id:
        updated = stripe.Subscription.modify(
            sub.stripe_subscription_id, cancel_at_period_end=cancel, api_key=_key()
        )
        apply_stripe_subscription(db, _as_dict(updated))
    elif sub.payment_mode == "prepaid":
        if not cancel:
            raise BillingError("Prepaid terms do not renew automatically. Buy a new term before it ends.")
    else:
        raise BillingError("This plan is managed by CAZO staff. Contact support to change it.")
    db.refresh(sub)
    return sub
