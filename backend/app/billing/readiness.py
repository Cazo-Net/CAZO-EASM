"""Go-live readiness check for payments.

Run it on the deployed backend before (and after) switching to live keys::

    python -m app.billing.readiness

or call ``GET /api/v1/billing/admin/readiness`` as a platform superuser.
Each check is ``ok``, ``warn`` or ``fail``; ``ready`` is true when nothing fails.
It only reads configuration and the Stripe account; it never creates charges.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

import stripe

from app.billing import stripe_service as svc
from app.billing.plans import EXTRA_DOMAIN_ADDON_ID, INTERVALS, billing_currency, catalog, purchasable_plans
from app.config import settings

WEBHOOK_EVENTS = [
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.finalized",
    "invoice.payment_failed",
    "invoice.voided",
    "invoice.marked_uncollectible",
]


def _check(name: str, status: str, detail: str) -> Dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def _stripe_account() -> Optional[Dict[str, Any]]:
    try:
        return svc._as_dict(stripe.Account.retrieve(api_key=svc._key()))
    except Exception:  # noqa: BLE001 - reported as a failed check
        return None


def run_checks(db=None, *, call_stripe: bool = True) -> Dict[str, Any]:
    checks: List[Dict[str, str]] = []
    mode = svc.stripe_mode()
    currency = billing_currency()

    # Keys and mode
    if mode == "off":
        checks.append(_check("secret_key", "fail", "STRIPE_SECRET_KEY is empty; checkout is switched off."))
    elif mode == "test":
        checks.append(_check("secret_key", "warn", "A TEST key is set. Real cards cannot be charged."))
    elif not settings.BILLING_ALLOW_LIVE_KEYS:
        checks.append(_check("secret_key", "fail",
                             "A LIVE key is set but BILLING_ALLOW_LIVE_KEYS is not true, so payments are refused."))
    else:
        checks.append(_check("secret_key", "ok", "Live key set and live payments allowed."))

    if mode == "test" and settings.BILLING_ALLOW_LIVE_KEYS:
        checks.append(_check("live_toggle", "warn",
                             "BILLING_ALLOW_LIVE_KEYS is true but the key is a test key."))

    # Webhooks
    if not settings.STRIPE_WEBHOOK_SECRET:
        checks.append(_check("webhook_secret", "fail",
                             "STRIPE_WEBHOOK_SECRET is empty; Stripe events are rejected."))
    else:
        checks.append(_check("webhook_secret", "ok",
                             "Webhook signing secret set. It must be the secret of the endpoint in the same "
                             "mode (test or live) as the key."))

    if db is not None:
        from app.models.billing import BillingEvent

        last = db.query(BillingEvent).order_by(BillingEvent.created_at.desc()).first()
        if last is None:
            checks.append(_check("webhook_delivery", "warn",
                                 "No Stripe webhook has been received yet. Send a test event from the Dashboard."))
        elif last.error:
            checks.append(_check("webhook_delivery", "warn",
                                 f"Last webhook ({last.event_type}) failed: {last.error[:200]}"))
        else:
            checks.append(_check("webhook_delivery", "ok",
                                 f"Last webhook received: {last.event_type} at {last.created_at}."))

    # Prices
    missing = [p.name for p in purchasable_plans() if p.monthly_price(currency) is None]
    if catalog()[EXTRA_DOMAIN_ADDON_ID].monthly_price(currency) is None:
        missing.append("Extra root domain")
    if missing:
        checks.append(_check("prices", "fail",
                             f"No {currency.upper()} price for: {', '.join(missing)}. Add them in BILLING_PLANS_JSON."))
    else:
        checks.append(_check("prices", "ok", f"All plans have {currency.upper()} prices "
                             f"({', '.join(INTERVALS)} terms)."))

    # Return URL
    frontend = settings.FRONTEND_URL or ""
    if not frontend.startswith("https://") or "localhost" in frontend:
        checks.append(_check("frontend_url", "fail" if mode == "live" else "warn",
                             f"FRONTEND_URL is '{frontend}'. Stripe sends customers back here; use the public https URL."))
    else:
        checks.append(_check("frontend_url", "ok", f"Customers return to {frontend}."))

    checks.append(_check("enforce_limits", "ok" if settings.BILLING_ENFORCE_LIMITS else "warn",
                         "Plan limits enforced." if settings.BILLING_ENFORCE_LIMITS
                         else "BILLING_ENFORCE_LIMITS is false; customers get unlimited use."))
    checks.append(_check("tax", "ok" if settings.BILLING_AUTOMATIC_TAX else "warn",
                         "Stripe Tax calculates tax at checkout." if settings.BILLING_AUTOMATIC_TAX
                         else "Tax is not calculated (BILLING_AUTOMATIC_TAX=false). Confirm with your accountant "
                              "whether you must charge SST or other tax."))

    # Stripe account
    account = _stripe_account() if call_stripe and svc.is_configured() else None
    if call_stripe and svc.is_configured():
        if account is None:
            checks.append(_check("stripe_account", "fail", "Could not read the Stripe account with this key."))
        else:
            country = account.get("country")
            charges = account.get("charges_enabled")
            payouts = account.get("payouts_enabled")
            caps = account.get("capabilities") or {}
            checks.append(_check(
                "stripe_account", "ok" if charges and payouts else ("warn" if mode == "test" else "fail"),
                f"Account country {country}, default currency {account.get('default_currency')}, "
                f"charges {'enabled' if charges else 'NOT enabled'}, payouts {'enabled' if payouts else 'NOT enabled'}.",
            ))
            fpx = caps.get("fpx_payments")
            if currency == "myr":
                checks.append(_check(
                    "fpx", "ok" if fpx == "active" else "warn",
                    f"FPX capability: {fpx or 'not requested'}. Turn it on in Settings > Payment methods."
                    if fpx != "active" else "FPX is active; it appears under 'Pay for one term'.",
                ))
            elif country == "MY":
                checks.append(_check("fpx", "warn",
                                     "Malaysian account but BILLING_CURRENCY is not myr, so FPX cannot be offered."))
    return {
        "ready": not any(c["status"] == "fail" for c in checks),
        "mode": mode,
        "currency": currency,
        "webhook_url_path": "/api/v1/billing/webhook",
        "webhook_events": WEBHOOK_EVENTS,
        "checks": checks,
    }


def main() -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        report = run_checks(db)
    finally:
        db.close()
    marks = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
    print(f"Stripe mode: {report['mode']}   currency: {report['currency']}")
    for c in report["checks"]:
        print(f"[{marks[c['status']]}] {c['check']}: {c['detail']}")
    print("\nWebhook endpoint: <your API URL>" + report["webhook_url_path"])
    print("Events: " + ", ".join(report["webhook_events"]))
    print("\nREADY" if report["ready"] else "\nNOT READY")
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, default=str))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
