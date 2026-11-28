"""Admin team chat tables

Revision ID: s7t8u9v0w1x2
Revises: r6s7t8u9v0w1
Create Date: 2026-11-28

Idempotent: tables may already exist when the database was built by create_all.
"""
from alembic import op
import sqlalchemy as sa

revision = "s7t8u9v0w1x2"
down_revision = "r6s7t8u9v0w1"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("admin_chat_messages"):
        op.create_table(
            "admin_chat_messages",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("author_email", sa.String(255), nullable=False),
            sa.Column("author_name", sa.String(255), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_admin_chat_messages_author_email", "admin_chat_messages", ["author_email"])
        op.create_index("ix_admin_chat_messages_created_at", "admin_chat_messages", ["created_at"])
    if not insp.has_table("admin_chat_reads"):
        op.create_table(
            "admin_chat_reads",
            sa.Column("admin_email", sa.String(255), primary_key=True),
            sa.Column("last_read_at", sa.DateTime(), nullable=True),
        )


def downgrade():
    op.drop_table("admin_chat_reads")
    op.drop_index("ix_admin_chat_messages_created_at", table_name="admin_chat_messages")
    op.drop_index("ix_admin_chat_messages_author_email", table_name="admin_chat_messages")
    op.drop_table("admin_chat_messages")
