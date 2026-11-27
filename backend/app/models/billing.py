"""Billing models: one subscription per organization, invoices, Stripe events.

These use their own ``billing_*`` tables (created by ``create_all``) rather
than the unused ``subscriptions``/``invoices`` tables from Alembic revision
g0h1i2j3k4l5, whose columns cannot hold plan quantities or prepaid terms and
which may or may not exist depending on how a database was built.
"""
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.database import Base


class BillingSubscription(Base):
    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        Index("ix_billing_subs_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True
    )
    # Plan id from app.billing.plans (essentials, business, plus, mssp, ...)
    plan = Column(String(50), nullable=False, default="free")
    # active | trialing | past_due | canceled | expired | incomplete
    status = Column(String(30), nullable=False, default="active")
    # year | quarter
    billing_interval = Column(String(20), nullable=False, default="year")
    # subscription (auto-renew via Stripe) | prepaid (one-off payment) | manual (set by staff)
    payment_mode = Column(String(20), nullable=False, default="subscription")
    currency = Column(String(3), nullable=False, default="usd")
    # MSSP: number of client organizations paid for. 1 for other plans.
    quantity = Column(Integer, nullable=False, default=1)
    # Extra root domains bought on top of the plan allowance.
    extra_domains = Column(Integer, nullable=False, default=0)

    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, unique=True)

    current_period_start = Column(DateTime(timezone=True), nullable=True)
    # None means no end (manual plans without a term).
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    last_payment_error = Column(Text, nullable=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BillingInvoice(Base):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        Index("ix_billing_invoices_org_created", "organization_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    # Stripe invoice id (in_...) or checkout session id (cs_...) for prepaid terms.
    stripe_id = Column(String(255), nullable=False, unique=True)
    number = Column(String(100), nullable=True)
    description = Column(String(500), nullable=True)
    amount_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="usd")
    # draft | open | paid | void | uncollectible | failed
    status = Column(String(30), nullable=False, default="open")
    hosted_url = Column(String(1000), nullable=True)
    pdf_url = Column(String(1000), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BillingEvent(Base):
    """Processed Stripe webhook events, for idempotency and debugging."""
    __tablename__ = "billing_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stripe_event_id = Column(String(255), nullable=False, unique=True)
    event_type = Column(String(100), nullable=False)
    organization_id = Column(String(36), nullable=True, index=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
