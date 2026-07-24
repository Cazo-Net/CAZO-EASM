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


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def _safe_add_column(table: str, column: sa.Column) -> None:
    if not _column_exists(table, column.name):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(column)


def _safe_create_index(name: str, table: str, columns: list) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes(table)}
    if name not in existing:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_index(name, columns)


def _safe_create_fk(name: str, table: str, local_cols: list, ref_table: str, ref_cols: list) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {fk["name"] for fk in inspector.get_foreign_keys(table)}
    if name not in existing:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_foreign_key(name, ref_table, local_cols, ref_cols)


def upgrade() -> None:
    # --- Extend notifications table ---
    _safe_add_column("notifications", sa.Column("organization_id", sa.String(length=36), nullable=True))
    _safe_add_column("notifications", sa.Column("related_entity_type", sa.String(length=50), nullable=True))
    _safe_add_column("notifications", sa.Column("related_entity_id", sa.String(length=36), nullable=True))
    _safe_add_column("notifications", sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"))
    _safe_add_column("notifications", sa.Column("channel", sa.String(length=20), nullable=False, server_default="in_app"))
    _safe_add_column("notifications", sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.false()))
    _safe_add_column("notifications", sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True))
    _safe_create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    _safe_create_index("ix_notifications_related_entity_type", "notifications", ["related_entity_type"])
    _safe_create_fk("fk_notifications_organization", "notifications", ["organization_id"], "organizations", ["id"])

    # --- Create notification_preferences table ---
    if not _table_exists("notification_preferences"):
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
    if not _table_exists("notification_email_log"):
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
    if _table_exists("notification_email_log"):
        op.drop_table("notification_email_log")
    if _table_exists("notification_preferences"):
        op.drop_table("notification_preferences")

    for idx in ["ix_notifications_related_entity_type", "ix_notifications_organization_id"]:
        try:
            with op.batch_alter_table("notifications") as batch_op:
                batch_op.drop_index(idx)
        except Exception:
            pass

    try:
        with op.batch_alter_table("notifications") as batch_op:
            batch_op.drop_constraint("fk_notifications_organization", type_="foreignkey")
    except Exception:
        pass

    for col in ["email_sent_at", "email_sent", "channel", "priority",
                "related_entity_id", "related_entity_type", "organization_id"]:
        if _column_exists("notifications", col):
            with op.batch_alter_table("notifications") as batch_op:
                batch_op.drop_column(col)
