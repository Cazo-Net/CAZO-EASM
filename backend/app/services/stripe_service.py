"""Stripe integration service.

Handles all Stripe API interactions: customers, subscriptions,
checkout sessions, billing portal, webhooks, and payment methods.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import stripe
from sqlalchemy.orm import Session

from app.config import settings
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.invoice import Invoice
from app.models.webhook_event import WebhookEvent
from app.plans import get_plan_info

logger = logging.getLogger(__name__)


class StripeService:
    """Service for Stripe API interactions."""

    def __init__(self, db: Session):
        self.db = db
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY

    def _get_stripe_client(self):
        """Get configured Stripe client."""
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe is not configured. Set STRIPE_SECRET_KEY.")
        return stripe

    # ============================================================
    # Customer Management
    # ============================================================

    def get_or_create_customer(self, org: Organization) -> str:
        """Get or create a Stripe customer for an organization.

        Returns the Stripe customer ID.
        """
        if org.stripe_customer_id:
            return org.stripe_customer_id

        client = self._get_stripe_client()
        customer = client.Customer.create(
            name=org.name,
            metadata={
                "organization_id": org.id,
                "organization_slug": org.slug,
            },
        )

        org.stripe_customer_id = customer.id
        self.db.commit()
        self.db.refresh(org)

        logger.info(f"Created Stripe customer {customer.id} for org {org.id}")
        return customer.id

    def update_customer(self, org: Organization, **kwargs) -> Dict[str, Any]:
        """Update a Stripe customer."""
        if not org.stripe_customer_id:
            raise ValueError("Organization has no Stripe customer")

        client = self._get_stripe_client()
        return client.Customer.modify(org.stripe_customer_id, **kwargs)

    # ============================================================
    # Checkout Sessions
    # ============================================================

    def create_checkout_session(
        self,
        org: Organization,
        plan: str,
        success_url: str,
        cancel_url: str,
        billing_period: str = "monthly",
    ) -> Dict[str, str]:
        """Create a Stripe checkout session for subscription upgrade."""
        client = self._get_stripe_client()
        plan_info = get_plan_info(plan)

        customer_id = self.get_or_create_customer(org)

        price_key = f"stripe_price_id_{billing_period}"
        price_id = plan_info.get(price_key, "")

        if not price_id:
            price_id = getattr(settings, f"STRIPE_PRICE_{plan.upper()}", "")

        if not price_id:
            raise ValueError(f"No Stripe price configured for plan: {plan}")

        metadata = {
            "organization_id": org.id,
            "plan": plan,
            "billing_period": billing_period,
        }

        if plan == "enterprise":
            session = client.Checkout.Session.create(
                customer=customer_id,
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                allow_promotion_codes=True,
            )
        else:
            trial_plan = get_plan_info("free_trial")
            trial_days = trial_plan.get("trial_days", 14) if org.plan == "free" else 0

            session_params = {
                "customer": customer_id,
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata,
                "allow_promotion_codes": True,
            }

            if trial_days > 0:
                session_params["subscription_data"] = {
                    "trial_period_days": trial_days,
                }

            session = client.Checkout.Session.create(**session_params)

        return {"session_id": session.id, "url": session.url}

    # ============================================================
    # Billing Portal
    # ============================================================

    def create_billing_portal_session(
        self, org: Organization, return_url: str
    ) -> Dict[str, str]:
        """Create a Stripe billing portal session."""
        client = self._get_stripe_client()
        customer_id = self.get_or_create_customer(org)

        session = client.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        return {"url": session.url}

    # ============================================================
    # Subscription Management
    # ============================================================

    def create_subscription(
        self, org: Organization, plan: str, price_id: Optional[str] = None
    ) -> Subscription:
        """Create a subscription (for direct upgrades, not checkout)."""
        client = self._get_stripe_client()
        customer_id = self.get_or_create_customer(org)

        if not price_id:
            price_id = getattr(settings, f"STRIPE_PRICE_{plan.upper()}", "")

        if not price_id:
            raise ValueError(f"No Stripe price configured for plan: {plan}")

        stripe_sub = client.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            metadata={
                "organization_id": org.id,
                "plan": plan,
            },
        )

        subscription = self._sync_subscription_from_stripe(org.id, stripe_sub)
        return subscription

    def update_subscription(
        self, org: Organization, new_plan: str
    ) -> Subscription:
        """Update (upgrade/downgrade) an organization's subscription."""
        client = self._get_stripe_client()
        sub = self.db.query(Subscription).filter(
            Subscription.organization_id == org.id,
            Subscription.status.in_(["active", "trialing"]),
        ).first()

        if not sub or not sub.stripe_subscription_id:
            raise ValueError("No active subscription found")

        new_price_id = getattr(settings, f"STRIPE_PRICE_{new_plan.upper()}", "")
        if not new_price_id:
            raise ValueError(f"No Stripe price configured for plan: {new_plan}")

        stripe_sub = client.Subscription.modify(
            sub.stripe_subscription_id,
            items=[{"id": sub.stripe_price_id, "price": new_price_id}],
            proration_behavior="create_prorations",
            metadata={
                "organization_id": org.id,
                "plan": new_plan,
            },
        )

        subscription = self._sync_subscription_from_stripe(org.id, stripe_sub)

        org.plan = new_plan
        self.db.commit()

        return subscription

    def cancel_subscription(
        self, org: Organization, at_period_end: bool = True
    ) -> Subscription:
        """Cancel an organization's subscription."""
        client = self._get_stripe_client()
        sub = self.db.query(Subscription).filter(
            Subscription.organization_id == org.id,
            Subscription.status.in_(["active", "trialing"]),
        ).first()

        if not sub or not sub.stripe_subscription_id:
            raise ValueError("No active subscription found")

        stripe_sub = client.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=at_period_end,
        )

        subscription = self._sync_subscription_from_stripe(org.id, stripe_sub)
        return subscription

    def resume_subscription(self, org: Organization) -> Subscription:
        """Resume a canceled subscription (before period end)."""
        client = self._get_stripe_client()
        sub = self.db.query(Subscription).filter(
            Subscription.organization_id == org.id,
            Subscription.status.in_(["active", "canceled"]),
            Subscription.cancel_at_period_end,
        ).first()

        if not sub or not sub.stripe_subscription_id:
            raise ValueError("No resumable subscription found")

        stripe_sub = client.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        subscription = self._sync_subscription_from_stripe(org.id, stripe_sub)
        return subscription

    # ============================================================
    # Payment Methods
    # ============================================================

    def list_payment_methods(self, org: Organization) -> List[Dict[str, Any]]:
        """List payment methods for an organization."""
        if not org.stripe_customer_id:
            return []

        client = self._get_stripe_client()
        methods = client.PaymentMethod.list(
            customer=org.stripe_customer_id,
            type="card",
        )

        return [
            {
                "id": pm.id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
            }
            for pm in methods.data
        ]

    def attach_payment_method(
        self, org: Organization, payment_method_id: str
    ) -> Dict[str, Any]:
        """Attach a payment method to an organization."""
        client = self._get_stripe_client()

        pm = client.PaymentMethod.attach(
            payment_method_id,
            customer=org.stripe_customer_id,
        )

        return {
            "id": pm.id,
            "brand": pm.card.brand,
            "last4": pm.card.last4,
            "exp_month": pm.card.exp_month,
            "exp_year": pm.card.exp_year,
        }

    def detach_payment_method(self, payment_method_id: str) -> None:
        """Detach a payment method."""
        client = self._get_stripe_client()
        client.PaymentMethod.detach(payment_method_id)

    def set_default_payment_method(
        self, org: Organization, payment_method_id: str
    ) -> None:
        """Set the default payment method for an organization."""
        client = self._get_stripe_client()
        client.Customer.modify(
            org.stripe_customer_id,
            invoice_settings={
                "default_payment_method": payment_method_id,
            },
        )

    # ============================================================
    # Webhook Handling
    # ============================================================

    def verify_webhook_event(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """Verify and parse a Stripe webhook event."""
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise ValueError("Stripe webhook secret not configured")

        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        return event

    def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        """Process a verified Stripe webhook event.

        Returns True if the event was processed successfully.
        """
        event_type = event["type"]
        event_id = event["id"]
        data = event.get("data", {}).get("object", {})

        existing = self.db.query(WebhookEvent).filter(
            WebhookEvent.stripe_event_id == event_id
        ).first()

        if existing and existing.processed:
            logger.info(f"Webhook event {event_id} already processed, skipping")
            return True

        if not existing:
            webhook_event = WebhookEvent(
                stripe_event_id=event_id,
                event_type=event_type,
                payload=event,
                processed=False,
            )
            self.db.add(webhook_event)
            self.db.commit()
        else:
            webhook_event = existing

        try:
            handler = self._get_webhook_handler(event_type)
            if handler:
                handler(data, event)
                webhook_event.processed = True
                self.db.commit()
                logger.info(f"Processed webhook event: {event_type} ({event_id})")
                return True
            else:
                logger.warning(f"No handler for webhook event type: {event_type}")
                webhook_event.processed = True
                self.db.commit()
                return True
        except Exception as e:
            logger.error(f"Error processing webhook {event_type}: {e}")
            webhook_event.error = str(e)
            self.db.commit()
            return False

    def _get_webhook_handler(self, event_type: str):
        """Get the handler function for a webhook event type."""
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.created": self._handle_subscription_updated,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
            "customer.subscription.trial_will_end": self._handle_trial_will_end,
        }
        return handlers.get(event_type)

    def _handle_checkout_completed(self, data: Dict, event: Dict) -> None:
        """Handle checkout.session.completed event."""
        org_id = data.get("metadata", {}).get("organization_id")
        subscription_id = data.get("subscription")

        if not org_id:
            return

        org = self.db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            return

        plan = data.get("metadata", {}).get("plan", "starter")
        org.plan = plan

        if subscription_id:
            client = self._get_stripe_client()
            stripe_sub = client.Subscription.retrieve(subscription_id)
            self._sync_subscription_from_stripe(org_id, stripe_sub)

        self.db.commit()

    def _handle_subscription_updated(self, data: Dict, event: Dict) -> None:
        """Handle subscription created/updated events."""
        org_id = data.get("metadata", {}).get("organization_id")
        if not org_id:
            stripe_sub_id = data.get("id")
            sub = self.db.query(Subscription).filter(
                Subscription.stripe_subscription_id == stripe_sub_id
            ).first()
            if sub:
                org_id = sub.organization_id

        if org_id:
            self._sync_subscription_from_stripe_stripe_data(org_id, data)

    def _handle_subscription_deleted(self, data: Dict, event: Dict) -> None:
        """Handle subscription deleted event."""
        stripe_sub_id = data.get("id")
        sub = self.db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if sub:
            sub.status = "canceled"
            sub.canceled_at = datetime.now(timezone.utc)
            self.db.commit()

            org = self.db.query(Organization).filter(
                Organization.id == sub.organization_id
            ).first()
            if org:
                org.plan = "free"
                self.db.commit()

    def _handle_invoice_paid(self, data: Dict, event: Dict) -> None:
        """Handle invoice.paid event."""
        org_id = data.get("metadata", {}).get("organization_id")
        if not org_id:
            customer_id = data.get("customer")
            if customer_id:
                org = self.db.query(Organization).filter(
                    Organization.stripe_customer_id == customer_id
                ).first()
                if org:
                    org_id = org.id

        if not org_id:
            return

        invoice = Invoice(
            organization_id=org_id,
            stripe_invoice_id=data.get("id"),
            amount_cents=data.get("amount_paid", 0),
            currency=data.get("currency", "usd"),
            status="paid",
            invoice_url=data.get("hosted_invoice_url"),
            invoice_pdf_url=data.get("invoice_pdf"),
            period_starts_at=self._parse_timestamp(data.get("period_start")),
            period_ends_at=self._parse_timestamp(data.get("period_end")),
        )
        self.db.add(invoice)
        self.db.commit()

    def _handle_invoice_payment_failed(self, data: Dict, event: Dict) -> None:
        """Handle invoice.payment_failed event."""
        customer_id = data.get("customer")
        if not customer_id:
            return

        org = self.db.query(Organization).filter(
            Organization.stripe_customer_id == customer_id
        ).first()
        if not org:
            return

        sub = self.db.query(Subscription).filter(
            Subscription.organization_id == org.id
        ).first()

        if sub:
            sub.payment_failed_count = (sub.payment_failed_count or 0) + 1
            sub.last_payment_error = f"Payment failed for invoice {data.get('id')}"
            sub.status = "past_due"
            self.db.commit()

    def _handle_trial_will_end(self, data: Dict, event: Dict) -> None:
        """Handle customer.subscription.trial_will_end event."""
        pass

    # ============================================================
    # Helpers
    # ============================================================

    def _sync_subscription_from_stripe(
        self, org_id: str, stripe_sub: Any
    ) -> Subscription:
        """Sync a Stripe subscription object to our database."""
        return self._sync_subscription_from_stripe_stripe_data(org_id, stripe_sub)

    def _sync_subscription_from_stripe_stripe_data(
        self, org_id: str, data: Dict[str, Any]
    ) -> Subscription:
        """Sync subscription data from Stripe to our database."""
        sub = self.db.query(Subscription).filter(
            Subscription.organization_id == org_id
        ).first()

        plan = data.get("metadata", {}).get("plan", "free")
        status = data.get("status", "active")

        status_map = {
            "active": "active",
            "trialing": "trialing",
            "past_due": "past_due",
            "canceled": "canceled",
            "unpaid": "past_due",
            "incomplete": "active",
            "incomplete_expired": "canceled",
        }
        mapped_status = status_map.get(status, "active")

        if sub:
            sub.stripe_subscription_id = data.get("id", sub.stripe_subscription_id)
            sub.stripe_price_id = (
                data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
                if isinstance(data.get("items"), dict)
                else sub.stripe_price_id
            )
            sub.status = mapped_status
            sub.plan = plan

            trial_start = data.get("trial_start")
            trial_end = data.get("trial_end")
            if trial_start:
                sub.trial_starts_at = self._parse_timestamp(trial_start)
            if trial_end:
                sub.trial_ends_at = self._parse_timestamp(trial_end)

            period_start = data.get("current_period_start")
            period_end = data.get("current_period_end")
            if period_start:
                sub.current_period_starts_at = self._parse_timestamp(period_start)
            if period_end:
                sub.current_period_ends_at = self._parse_timestamp(period_end)

            sub.cancel_at_period_end = data.get("cancel_at_period_end", False)

            if data.get("canceled_at"):
                sub.canceled_at = self._parse_timestamp(data["canceled_at"])

            self.db.commit()
            self.db.refresh(sub)
            return sub
        else:
            sub = Subscription(
                organization_id=org_id,
                plan=plan,
                status=mapped_status,
                stripe_customer_id=data.get("customer"),
                stripe_subscription_id=data.get("id"),
                trial_starts_at=self._parse_timestamp(data.get("trial_start")),
                trial_ends_at=self._parse_timestamp(data.get("trial_end")),
                current_period_starts_at=self._parse_timestamp(
                    data.get("current_period_start")
                ),
                current_period_ends_at=self._parse_timestamp(
                    data.get("current_period_end")
                ),
                cancel_at_period_end=data.get("cancel_at_period_end", False),
                canceled_at=self._parse_timestamp(data.get("canceled_at")),
            )
            self.db.add(sub)
            self.db.commit()
            self.db.refresh(sub)
            return sub

    def _parse_timestamp(self, timestamp) -> Optional[datetime]:
        """Parse a Unix timestamp to datetime."""
        if timestamp is None:
            return None
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return None
