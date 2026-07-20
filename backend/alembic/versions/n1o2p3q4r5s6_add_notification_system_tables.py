"""add notification system tables and columns

Revision ID: n1o2p3q4r5s6
Revises: m6n7o8p9q0r1
Create Date: 2026-07-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n1o2p3q4r5s6'
down_revision: Union[str, Sequence[str], None] = 'm6n7o8p9q0r1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extend notifications table ---
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("related_entity_type", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("related_entity_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"))
        batch_op.add_column(sa.Column("channel", sa.String(length=20), nullable=False, server_default="in_app"))
        batch_op.add_column(sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_notifications_organization_id", ["organization_id"])
        batch_op.create_index("ix_notifications_related_entity_type", ["related_entity_type"])
        batch_op.create_foreign_key("fk_notifications_organization", "organizations", ["organization_id"], ["id"])

    # --- Create notification_preferences table ---
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "notification_type", name="uq_notification_pref_user_type"),
    )
    with op.batch_alter_table("notification_preferences") as batch_op:
        batch_op.create_index("ix_notification_preferences_user_id", ["user_id"])

    # --- Create notification_email_log table ---
    op.create_table(
        "notification_email_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("notification_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("email_type", sa.String(length=50), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resend_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_id", name="uq_email_log_notification"),
    )
    with op.batch_alter_table("notification_email_log") as batch_op:
        batch_op.create_index("ix_notification_email_log_notification_id", ["notification_id"])
        batch_op.create_index("ix_notification_email_log_user_id", ["user_id"])


def downgrade() -> None:
    op.drop_table("notification_email_log")
    op.drop_table("notification_preferences")

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index("ix_notifications_related_entity_type")
        batch_op.drop_index("ix_notifications_organization_id")
        batch_op.drop_constraint("fk_notifications_organization", type_="foreignkey")
        batch_op.drop_column("email_sent_at")
        batch_op.drop_column("email_sent")
        batch_op.drop_column("channel")
        batch_op.drop_column("priority")
        batch_op.drop_column("related_entity_id")
        batch_op.drop_column("related_entity_type")
        batch_op.drop_column("organization_id")
