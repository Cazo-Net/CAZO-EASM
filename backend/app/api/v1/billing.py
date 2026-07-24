import os
import logging
from datetime import datetime, timezone
from typing import Optional

import stripe
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.models.user import User
from app.models.subscription import Subscription
from app.services.audit import log_event

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

router = APIRouter()

# Plan definitions matching existing system
PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "currency": "usd",
        "features": {
            "scans_per_month": 5,
            "basic_reports": True,
            "api_access": False,
            "advanced_scanning": False,
        },
    },
    "starter": {
        "name": "Starter",
        "price": 29,
        "currency": "usd",
        "features": {
            "scans_per_month": 100,
            "basic_reports": True,
            "api_access": True,
            "advanced_scanning": False,
            "whitelisted_domains": True,
        },
    },
    "professional": {
        "name": "Professional",
        "price": 99,
        "currency": "usd",
        "features": {
            "scans_per_month": 1000,
            "basic_reports": True,
            "api_access": True,
            "advanced_scanning": True,
            "whitelisted_domains": True,
            "priority_support": True,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 499,
        "currency": "usd",
        "features": {
            "scans_per_month": -1,  # unlimited
            "basic_reports": True,
            "api_access": True,
            "advanced_scanning": True,
            "whitelisted_domains": True,
            "priority_support": True,
            "dedicated_account_manager": True,
            "custom_integrations": True,
        },
    },
}

# Customer Portal URLs
CUSTOMER_PORTAL_BASE = os.getenv("FRONTEND_URL", "http://localhost:3000")

def get_stripe_customer_id(user: User, db: Session) -> Optional[str]:
    "Get or create Stripe customer ID for user."
    if user.stripe_customer_id:
        return user.stripe_customer_id

    try:
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name or user.email,
            metadata={"user_id": user.id},
        )

        # Update user
        user.stripe_customer_id = customer.id
        db.commit()

        # Log event
        log_event(
            db,
            action="subscription.customer_created",
            organization_id=user.organization_id,
            actor_id=user.id,
            target_type="user",
            target_id=user.id,
            status="success",
            detail={"stripe_customer_id": customer.id},
        )

        return customer.id
    except Exception as e:
        logger.error(f"Failed to create Stripe customer: {e}")
        return None

@router.get("/billing/plans")
async def list_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    "List all available billing plans."
    from app.models.subscription import Subscription

    user_plan = None

    if current_user.organization_id:
        org_subscription = (
            db.query(Subscription)
            .filter(Subscription.organization_id == current_user.organization_id)
            .first()
        )
        user_plan = org_subscription.plan if org_subscription else None

    plans_response = []
    for plan_id, plan_data in PLANS.items():
        plans_response.append({
            "id": plan_id,
            "name": plan_data["name"],
            "price": plan_data["price"],
            "currency": plan_data["currency"],
            "features": plan_data["features"],
            "current": plan_id == user_plan,
        })

    return {"plans": plans_response}

@router.post("/billing/subscriptions")
async def create_subscription(
    request: dict,
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: Session = Depends(get_db),
):
    "Create new subscription for organization."
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not associated with user",
        )

    plan_id = request.get("plan", "free")

    if plan_id not in PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {plan_id}",
        )

    # Check if organization already has subscription
    existing_subscription = (
        db.query(Subscription)
        .filter(Subscription.organization_id == current_user.organization_id)
        .first()
    )

    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization already has an active subscription",
        )

    # Create Stripe customer if needed
    stripe_customer_id = get_stripe_customer_id(current_user, db)

    # Create subscription record
    subscription = Subscription(
        organization_id=current_user.organization_id,
        plan=plan_id,
        status="active",
        stripe_customer_id=stripe_customer_id,
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    log_event(
        db,
        action="subscription.created",
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        target_type="subscription",
        target_id=subscription.id,
        status="success",
        detail={
            "plan": plan_id,
            "stripe_customer_id": stripe_customer_id,
        },
    )

    return subscription

@router.get("/billing/subscriptions")
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    "Get current organization's subscription."
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not associated with user",
        )

    subscription = (
        db.query(Subscription)
        .filter(Subscription.organization_id == current_user.organization_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found for organization",
        )

    return subscription

@router.put("/billing/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    request: dict,
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: Session = Depends(get_db),
):
    "Update subscription details."
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    if subscription.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this subscription",
        )

    update_fields = ["plan", "status"]
    for field in update_fields:
        if field in request:
            setattr(subscription, field, request[field])

    db.commit()
    db.refresh(subscription)

    log_event(
        db,
        action="subscription.updated",
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        target_type="subscription",
        target_id=subscription.id,
        status="success",
        detail=request,
    )

    return subscription

@router.delete("/billing/subscriptions/{subscription_id}")
async def cancel_subscription(
    subscription_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: Session = Depends(get_db),
):
    "Cancel subscription."
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    if subscription.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this subscription",
        )

    try:
        # Update Stripe subscription if exists
        if subscription.stripe_subscription_id:
            stripe_subscription = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )
            stripe_subscription.delete()

        # Mark as canceled
        subscription.status = "canceled"
        subscription.canceled_at = datetime.now(timezone.utc)
        subscription.cancel_at_period_end = True

        db.commit()
        db.refresh(subscription)

        log_event(
            db,
            action="subscription.canceled",
            organization_id=current_user.organization_id,
            actor_id=current_user.id,
            target_type="subscription",
            target_id=subscription.id,
            status="success",
            detail={},
        )

        return {"message": "Subscription canceled successfully"}

    except stripe.error.StripeError as e:
        db.rollback()
        logger.error(f"Stripe error during subscription cancellation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel subscription in Stripe: {str(e)}",
        )

@router.post("/billing/subscriptions/{subscription_id}/upgrade")
async def upgrade_subscription(
    subscription_id: str,
    request: dict,
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: Session = Depends(get_db),
):
    "Upgrade subscription to a higher plan."
    subscription = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    if subscription.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upgrade this subscription",
        )

    new_plan = request.get("plan")
    if not new_plan or new_plan not in PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan specified for upgrade",
        )

    # Determine if immediate or end of billing cycle
    immediate = request.get("immediate", False)

    try:
        # Update Stripe subscription if exists
        if subscription.stripe_subscription_id:
            stripe_subscription = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )

            # Map plan to Stripe price
            plan_to_price = {"professional": "price_pro", "enterprise": "price_ent"}
            stripe_price_id = plan_to_price.get(new_plan, None)

            if stripe_price_id:
                if immediate:
                    # Change plan immediately
                    stripe_subscription.items.data[0].price = stripe_price_id
                    stripe_subscription.save()
                else:
                    # Schedule for end of billing period
                    stripe_subscription.items.create(
                        price=stripe_price_id,
                        quantity=1,
                    )

        # Update local subscription
        subscription.plan = new_plan

        db.commit()
        db.refresh(subscription)

        log_event(
            db,
            action="subscription.upgraded",
            organization_id=current_user.organization_id,
            actor_id=current_user.id,
            target_type="subscription",
            target_id=subscription.id,
            status="success",
            detail={"plan": new_plan, "immediate": immediate},
        )

        return subscription

    except stripe.error.StripeError as e:
        db.rollback()
        logger.error(f"Stripe error during subscription upgrade: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to upgrade subscription in Stripe: {str(e)}",
        )

@router.get("/billing/portal")
async def get_billing_portal(
    return_url: str = "/billing",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    "Get billing portal URL for customer."
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not associated with user",
        )

    subscription = (
        db.query(Subscription)
        .filter(Subscription.organization_id == current_user.organization_id)
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found for organization",
        )

    try:
        # Create Stripe billing portal session
        portal_session = stripe.BillingPortal.Session.create(
            customer=subscription.stripe_customer_id or "",
            return_url=f"{CUSTOMER_PORTAL_BASE}{return_url}",
            subscription_data={
                "subscription": subscription.stripe_subscription_id or "",
            } if subscription.stripe_subscription_id else None,
        )

        return {"url": portal_session.url}

    except stripe.error.StripeError as e:
        logger.error(f"Failed to create billing portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session",
        )

@router.post("/billing/checkout")
async def create_checkout_session(
    request: dict,
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
    db: Session = Depends(get_db),
):
    "Create Stripe checkout session."
    plan_id = request.get("plan")
    success_url = request.get("success_url")
    cancel_url = request.get("cancel_url")

    if not plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan is required",
        )

    if not PLANS[plan_id]["price"] > 0:
        # If free plan, redirect directly
        return {"message": "Free plan activated immediately", "plan": plan_id}

    try:
        # Create Stripe checkout session
        checkout_session = stripe.Checkout.Session.create(
            customer_email=current_user.email,
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": PLANS[plan_id]["price"] * 100,
                        "product_data": {
                            "name": PLANS[plan_id]["name"],
                            "description": f"{PLANS[plan_id]['name']} plan",
                        },
                        "billing_cycle_anchor": "now",
                        "repeat": False,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url or f"{CUSTOMER_PORTAL_BASE}/billing?success=true",
            cancel_url=cancel_url or f"{CUSTOMER_PORTAL_BASE}/billing?canceled=true",
            metadata={"user_id": current_user.id},
        )

        return {"url": checkout_session.url, "session_id": checkout_session.id}

    except stripe.error.StripeError as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )
