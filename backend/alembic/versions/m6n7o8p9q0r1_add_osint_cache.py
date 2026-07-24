"""Add osint_cache table for OSINT result caching.

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
"""
from alembic import op
import sqlalchemy as sa

revision = "m6n7o8p9q0r1"
down_revision = "l5m6n7o8p9q0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "osint_cache",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False, index=True),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False, server_default="3600"),
    )
    op.create_index("uq_osint_cache_domain", "osint_cache", ["domain"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "osint_cache" in inspector.get_table_names():
        existing = {idx["name"] for idx in inspector.get_indexes("osint_cache")}
        if "uq_osint_cache_domain" in existing:
            op.drop_index("uq_osint_cache_domain", table_name="osint_cache")
        op.drop_table("osint_cache")
