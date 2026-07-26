"""Add engine column to scans table to track scanner version.

Revision ID: add_engine_col001
Revises: v2scanner001
Create Date: 2026-07-26
"""
from alembic import op
import sqlalchemy as sa

revision = "add_engine_col001"
down_revision = "v2scanner001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("engine", sa.String(20), nullable=False, server_default="v1"))


def downgrade() -> None:
    op.drop_column("scans", "engine")
