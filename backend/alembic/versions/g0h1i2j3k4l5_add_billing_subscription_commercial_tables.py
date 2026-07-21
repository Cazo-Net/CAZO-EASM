"""add billing subscription and commercial infrastructure tables

Revision ID: g0h1i2j3k4l5
Revises: f6a7b8c9d0e1
Create Date: 2026-07-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g0h1i2j3k4l5'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Subscriptions ---
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("trial_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default="0"),
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_failed_count", sa.Integer(), server_default="0"),
        sa.Column("last_payment_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.create_index("ix_subscriptions_organization_id", ["organization_id"])
        batch_op.create_index("ix_subscriptions_status", ["status"])
        batch_op.create_index("ix_subscriptions_stripe_customer_id", ["stripe_customer_id"], unique=True)
        batch_op.create_index("ix_subscriptions_stripe_subscription_id", ["stripe_subscription_id"], unique=True)

    # --- Invoices ---
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="usd"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("invoice_url", sa.String(length=500), nullable=True),
        sa.Column("invoice_pdf_url", sa.String(length=500), nullable=True),
        sa.Column("period_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.create_index("ix_invoices_organization_id", ["organization_id"])
        batch_op.create_index("ix_invoices_stripe_invoice_id", ["stripe_invoice_id"], unique=True)

    # --- Invoice Line Items ---
    op.create_table(
        "invoice_line_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("period_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("invoice_line_items") as batch_op:
        batch_op.create_index("ix_invoice_line_items_invoice_id", ["invoice_id"])

    # --- Payment Methods ---
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("stripe_payment_method_id", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=50), nullable=True),
        sa.Column("last4", sa.String(length=4), nullable=True),
        sa.Column("exp_month", sa.Integer(), nullable=True),
        sa.Column("exp_year", sa.Integer(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("payment_methods") as batch_op:
        batch_op.create_index("ix_payment_methods_organization_id", ["organization_id"])
        batch_op.create_index("ix_payment_methods_stripe_payment_method_id", ["stripe_payment_method_id"], unique=True)

    # --- API Keys v2 ---
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.String(length=45), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.create_index("ix_api_keys_user_id", ["user_id"])
        batch_op.create_index("ix_api_keys_organization_id", ["organization_id"])
        batch_op.create_index("ix_api_keys_key_hash", ["key_hash"], unique=True)
        batch_op.create_index("ix_api_keys_is_active", ["is_active"])

    # --- Usage Records ---
    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("period_starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.create_index("ix_usage_records_organization_id", ["organization_id"])
        batch_op.create_index("ix_usage_records_metric_name", ["metric_name"])

    # --- Usage Aggregations ---
    op.create_table(
        "usage_aggregations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("period_starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assets", sa.Integer(), server_default="0"),
        sa.Column("domains", sa.Integer(), server_default="0"),
        sa.Column("subdomains", sa.Integer(), server_default="0"),
        sa.Column("projects", sa.Integer(), server_default="0"),
        sa.Column("scans", sa.Integer(), server_default="0"),
        sa.Column("storage_mb", sa.Float(), server_default="0"),
        sa.Column("ai_requests", sa.Integer(), server_default="0"),
        sa.Column("reports", sa.Integer(), server_default="0"),
        sa.Column("api_calls", sa.Integer(), server_default="0"),
        sa.Column("users", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("usage_aggregations") as batch_op:
        batch_op.create_index("ix_usage_aggregations_organization_id", ["organization_id"])

    # --- Feature Flags ---
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="1"),
        sa.Column("allowed_plans", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("feature_flags") as batch_op:
        batch_op.create_index("ix_feature_flags_key", ["key"], unique=True)

    # --- Webhook Events ---
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("webhook_events") as batch_op:
        batch_op.create_index("ix_webhook_events_stripe_event_id", ["stripe_event_id"], unique=True)
        batch_op.create_index("ix_webhook_events_event_type", ["event_type"])
        batch_op.create_index("ix_webhook_events_processed", ["processed"])

    # --- Roles ---
    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default="0"),
        sa.Column("is_default", sa.Boolean(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("roles") as batch_op:
        batch_op.create_index("ix_roles_organization_id", ["organization_id"])
        batch_op.create_index("ix_roles_slug", ["slug"])

    # --- Enhance organizations table ---
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(sa.Column("billing_email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("tax_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("invoice_prefix", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), server_default="1"))
        batch_op.add_column(sa.Column("is_archived", sa.Boolean(), server_default="0"))
        batch_op.create_index("ix_organizations_stripe_customer_id", ["stripe_customer_id"], unique=True)

    # --- Enhance users table ---
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("password_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("mfa_enforced", sa.Boolean(), server_default="0"))


def downgrade() -> None:
    # Revert user enhancements
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("mfa_enforced")
        batch_op.drop_column("password_expires_at")
        batch_op.drop_column("password_changed_at")

    # Revert organization enhancements
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_index("ix_organizations_stripe_customer_id")
        batch_op.drop_column("is_archived")
        batch_op.drop_column("is_active")
        batch_op.drop_column("trial_ends_at")
        batch_op.drop_column("stripe_customer_id")
        batch_op.drop_column("invoice_prefix")
        batch_op.drop_column("tax_id")
        batch_op.drop_column("billing_email")

    op.drop_table("roles")
    op.drop_table("webhook_events")
    op.drop_table("feature_flags")
    op.drop_table("usage_aggregations")
    op.drop_table("usage_records")
    op.drop_table("api_keys")
    op.drop_table("payment_methods")
    op.drop_table("invoice_line_items")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
