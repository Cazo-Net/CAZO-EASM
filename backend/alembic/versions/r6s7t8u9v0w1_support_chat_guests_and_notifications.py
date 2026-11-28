"""Support chat: website visitors, organization context, reply notifications

Revision ID: r6s7t8u9v0w1
Revises: q5r6s7t8u9v0
Create Date: 2026-11-28

Idempotent: every step checks the live schema first, because databases in the
wild were built by Alembic, by ``create_all``, or by both.
"""
from alembic import op
import sqlalchemy as sa

revision = "r6s7t8u9v0w1"
down_revision = "q5r6s7t8u9v0"
branch_labels = None
depends_on = None

_CONV_COLUMNS = [
    ("organization_id", sa.String(36)),
    ("guest_name", sa.String(120)),
    ("guest_email", sa.String(255)),
    ("guest_token_hash", sa.String(64)),
]
_MSG_COLUMNS = [
    ("sender_name", sa.String(255)),
    ("notified_at", sa.DateTime()),
]


def _columns(table):
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return None
    return {c["name"]: c for c in insp.get_columns(table)}


def upgrade():
    conv = _columns("support_conversations")
    if conv is not None:
        for name, type_ in _CONV_COLUMNS:
            if name not in conv:
                op.add_column("support_conversations", sa.Column(name, type_, nullable=True))
        indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("support_conversations")}
        if "ix_support_conversations_guest_token_hash" not in indexes:
            op.create_index(
                "ix_support_conversations_guest_token_hash",
                "support_conversations",
                ["guest_token_hash"],
            )
        # Visitor conversations have no user account.
        if not conv["user_id"]["nullable"]:
            with op.batch_alter_table("support_conversations") as batch:
                batch.alter_column("user_id", existing_type=sa.String(36), nullable=True)

    msg = _columns("support_messages")
    if msg is not None:
        first_run = "notified_at" not in msg
        for name, type_ in _MSG_COLUMNS:
            if name not in msg:
                op.add_column("support_messages", sa.Column(name, type_, nullable=True))
        # Rows inserted without a value (older admin replies) count as unread.
        op.execute(sa.text("UPDATE support_messages SET is_read = false WHERE is_read IS NULL"))
        # The old chat answered every message with three canned "agent" lines.
        # They were never written by a person, so they are removed.
        op.execute(sa.text("DELETE FROM support_messages WHERE sender_id = 'auto-reply'"))
        if first_run:
            # Reply emails start with this release; do not email the backlog.
            op.execute(sa.text(
                "UPDATE support_messages SET notified_at = CURRENT_TIMESTAMP "
                "WHERE sender_type = 'admin' AND notified_at IS NULL"
            ))


def downgrade():
    # Columns are left in place: dropping them would delete visitor conversations.
    pass
