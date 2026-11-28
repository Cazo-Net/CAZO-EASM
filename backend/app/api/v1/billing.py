"""Billing API: plans, current subscription and usage, checkout, payment methods, invoices."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.billing import stripe_service as svc
from app.billing.entitlements import get_entitlement, get_subscription, usage
from app.billing.plans import (
    EXTRA_DOMAIN_ADDON_ID,
    INTERVALS,
    LIMIT_KEYS,
    billing_currency,
    catalog,
    get_plan,
    order_total,
    plan_limits,
    purchasable_plans,
)
from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.billing import BillingInvoice, BillingSubscription
from app.models.organization import Organization
from app.models.user import User
from app.services.audit import log_event, log_user_action

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    plan: str
    interval: str = "year"
    clients: int = Field(1, ge=1, le=10_000, description="MSSP: number of client organizations")
    extra_domains: int = Field(0, ge=0, le=500)
    payment: str = Field("subscription", description="subscription (auto-renew) or prepaid (one term)")


class QuoteRequest(BaseModel):
    plan: str
    interval: str = "year"
    clients: int = Field(1, ge=1, le=10_000)
    extra_domains: int = Field(0, ge=0, le=500)


class CancelRequest(BaseModel):
    at_period_end: bool = True


class ManualPlanRequest(BaseModel):
    plan: str
    clients: int = Field(1, ge=1, le=10_000)
    extra_domains: int = Field(0, ge=0, le=500)
    period_end: datetime | None = None
    note: str | None = Field(None, max_length=1000)


# ── Helpers ──────────────────────────────────────────────────────────────


def _org(db: Session, user: User) -> Organization:
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="Create or join an organization first.")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return org


def _stripe_call(fn, *args, **kwargs):
    """Run a Stripe-backed operation and map failures to clean HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except svc.BillingNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except svc.BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except stripe.StripeError as exc:
        logger.warning("Stripe error: %s", exc)
        msg = getattr(exc, "user_message", None) or "The payment provider rejected the request."
        raise HTTPException(status_code=502, detail=msg)


def _payment_options(currency: str) -> list:
    options = [
        {
            "id": "subscription",
            "label": "Card, renews automatically",
            "description": "Charged at the start of each term. Cancel any time before renewal.",
            "methods": ["card"],
        },
        {
            "id": "prepaid",
            "label": "Pay for one term",
            "description": "A single payment for the whole term. Renew manually.",
            "methods": ["card"] + (["fpx", "grabpay"] if currency == "myr" else []),
        },
    ]
    return options


def _plan_out(plan, currency: str) -> dict:
    return {
        "id": plan.id,
        "name": plan.name,
        "tagline": plan.tagline,
        "highlight": plan.highlight,
        "per_client": plan.per_client,
        "min_quantity": plan.min_quantity,
        "monthly_price": plan.monthly_price(currency),
        "prices": {i: plan.term_price(currency, i) for i in INTERVALS},
        "limits": plan.limits,
        "scan_frequency": plan.scan_frequency,
        "features": plan.features,
    }


# ── Public ───────────────────────────────────────────────────────────────


@router.get("/plans")
async def list_plans():
    """Plan catalog for the pricing page (no auth)."""
    currency = billing_currency()
    addon = catalog()[EXTRA_DOMAIN_ADDON_ID]
    return {
        "currency": currency,
        "intervals": [{"id": k, "label": v["label"], "months": v["months"]} for k, v in INTERVALS.items()],
        "plans": [_plan_out(p, currency) for p in purchasable_plans() if p.monthly_price(currency) is not None],
        "addons": {
            "extra_domain": {
                "monthly_price": addon.monthly_price(currency),
                "prices": {i: addon.term_price(currency, i) for i in INTERVALS},
            }
        },
        "payment_options": _payment_options(currency),
        "checkout_enabled": svc.is_configured(),
        "test_mode": svc.stripe_mode() == "test",
    }


@router.post("/quote")
async def quote(req: QuoteRequest):
    plan = catalog().get(req.plan)
    if plan is None or not plan.purchasable or req.interval not in INTERVALS:
        raise HTTPException(status_code=400, detail="Unknown plan or interval.")
    currency = billing_currency()
    qty = max(req.clients, plan.min_quantity) if plan.per_client else 1
    total = order_total(plan, req.interval, qty, req.extra_domains, currency)
    if total is None:
        raise HTTPException(status_code=400, detail=f"No {currency.upper()} price for this order.")
    return {
        "plan": plan.id,
        "interval": req.interval,
        "clients": qty,
        "extra_domains": req.extra_domains,
        "currency": currency,
        "total": total,
        "limits": plan_limits(plan, qty, req.extra_domains),
    }


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    try:
        event_type = svc.handle_webhook(db, payload, request.headers.get("stripe-signature"))
    except svc.BillingNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature or payload.")
    return {"received": True, "type": event_type}


# ── Organization billing ─────────────────────────────────────────────────


@router.get("/subscription")
async def get_billing_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current plan, allowances and usage for the caller's organization."""
    org = _org(db, current_user)
    ent = get_entitlement(db, org.id)
    used = usage(db, org.id)
    sub: BillingSubscription | None = ent.subscription
    return {
        "organization_id": org.id,
        "plan": _plan_out(ent.plan, billing_currency()) | {"limits": ent.limits},
        "status": ent.status,
        "payment_mode": sub.payment_mode if sub else None,
        "interval": sub.billing_interval if sub else None,
        "clients": ent.quantity,
        "extra_domains": ent.extra_domains,
        "currency": (sub.currency if sub else None) or billing_currency(),
        "current_period_start": sub.current_period_start if sub else None,
        "current_period_end": ent.period_end,
        "cancel_at_period_end": bool(sub.cancel_at_period_end) if sub else False,
        "last_payment_error": sub.last_payment_error if sub else None,
        "has_customer": bool(sub and sub.stripe_customer_id),
        "usage": {
            key: {
                "used": used[key],
                "limit": ent.limits[key],
                "unlimited": ent.limits[key] is None,
            }
            for key in LIMIT_KEYS
        },
        "checkout_enabled": svc.is_configured(),
        "test_mode": svc.stripe_mode() == "test",
    }


@router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    result = _stripe_call(
        svc.create_checkout_session, db, org, current_user.email,
        plan_id=req.plan, interval=req.interval, quantity=req.clients,
        extra_domains=req.extra_domains, payment=req.payment,
    )
    log_user_action(db, current_user, "billing.checkout_started", "subscription", detail={
        "plan": req.plan, "interval": req.interval, "clients": req.clients, "extra_domains": req.extra_domains,
    })
    return result


@router.get("/checkout/{session_id}")
async def checkout_status(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _org(db, current_user)
    return _stripe_call(svc.retrieve_checkout_session, db, org, session_id)


@router.post("/portal")
async def billing_portal(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    return {"url": _stripe_call(svc.portal_url, db, org, current_user.email)}


@router.get("/payment-methods")
async def payment_methods(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    sub = get_subscription(db, org.id)
    if not svc.is_configured():
        return {"payment_methods": [], "checkout_enabled": False}
    return {"payment_methods": _stripe_call(svc.list_payment_methods, sub), "checkout_enabled": True}


@router.post("/payment-methods/setup")
async def add_payment_method(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    return {"url": _stripe_call(svc.setup_session_url, db, org, current_user.email)}


@router.post("/payment-methods/{pm_id}/default")
async def make_default_payment_method(
    pm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    _stripe_call(svc.set_default_payment_method, get_subscription(db, org.id), pm_id)
    return {"ok": True}


@router.delete("/payment-methods/{pm_id}")
async def remove_payment_method(
    pm_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    _stripe_call(svc.detach_payment_method, get_subscription(db, org.id), pm_id)
    return {"ok": True}


@router.get("/invoices")
async def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    rows: list[BillingInvoice] = (
        db.query(BillingInvoice)
        .filter(BillingInvoice.organization_id == org.id)
        .order_by(BillingInvoice.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "invoices": [
            {
                "id": r.id,
                "number": r.number,
                "description": r.description,
                "amount": r.amount_cents,
                "currency": r.currency,
                "status": r.status,
                "hosted_url": r.hosted_url,
                "pdf_url": r.pdf_url,
                "period_start": r.period_start,
                "period_end": r.period_end,
                "paid_at": r.paid_at,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@router.post("/cancel")
async def cancel_subscription(
    req: CancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    sub = _stripe_call(svc.set_cancel_at_period_end, db, get_subscription(db, org.id), True)
    log_user_action(db, current_user, "billing.cancel_requested", "subscription", detail={"plan": sub.plan})
    return {"cancel_at_period_end": sub.cancel_at_period_end, "current_period_end": sub.current_period_end}


@router.post("/resume")
async def resume_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    org = _org(db, current_user)
    sub = _stripe_call(svc.set_cancel_at_period_end, db, get_subscription(db, org.id), False)
    log_user_action(db, current_user, "billing.cancel_withdrawn", "subscription", detail={"plan": sub.plan})
    return {"cancel_at_period_end": sub.cancel_at_period_end, "current_period_end": sub.current_period_end}


# ── Platform staff ───────────────────────────────────────────────────────


@router.post("/admin/organizations/{org_id}/plan")
async def set_manual_plan(
    org_id: str,
    req: ManualPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Put an org on a plan without online payment (design partners, bank transfer, staff)."""
    if current_user.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform staff only.")
    if req.plan not in catalog() or catalog()[req.plan].addon:
        raise HTTPException(status_code=400, detail="Unknown plan.")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    sub = svc.get_or_create_subscription_row(db, org)
    plan = get_plan(req.plan)
    sub.plan = plan.id
    sub.status = "active"
    sub.payment_mode = "manual"
    sub.quantity = req.clients if plan.per_client else 1
    sub.extra_domains = req.extra_domains
    sub.current_period_start = datetime.now(UTC)
    sub.current_period_end = req.period_end
    sub.cancel_at_period_end = req.period_end is not None
    sub.note = req.note
    org.plan = plan.id
    db.commit()
    # Recorded in the customer's log, attributed to platform staff.
    log_event(db, action="billing.plan_set_by_staff", organization_id=org.id, actor_id=current_user.id,
              actor_type="staff", target_type="subscription",
              detail={"plan": plan.id, "clients": req.clients, "extra_domains": req.extra_domains,
                      "period_end": req.period_end.isoformat() if req.period_end else None})
    ent = get_entitlement(db, org.id)
    return {"organization_id": org.id, "plan": plan.id, "limits": ent.limits, "period_end": req.period_end}
