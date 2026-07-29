"""Add support chat tables

Revision ID: p4q5r6s7t8u9
Revises: o2p3q4r5s6t7
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa

revision = "p4q5r6s7t8u9"
down_revision = "o2p3q4r5s6t7"
branch_labels = None
depends_on = None


def _table_exists(table):
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade():
    if not _table_exists("support_conversations"):
        op.create_table(
            "support_conversations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("subject", sa.String(255), server_default="Support Request"),
            sa.Column("status", sa.String(20), server_default="open", index=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )

    if not _table_exists("support_messages"):
        op.create_table(
            "support_messages",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("conversation_id", sa.String(36), sa.ForeignKey("support_conversations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("sender_type", sa.String(10), nullable=False),
            sa.Column("sender_id", sa.String(36), nullable=False),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("is_read", sa.Boolean, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )


def downgrade():
    if _table_exists("support_messages"):
        op.drop_table("support_messages")
    if _table_exists("support_conversations"):
        op.drop_table("support_conversations")
