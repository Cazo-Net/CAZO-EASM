"""Add os_detection and host_scripts to subdomains

Revision ID: o2p3q4r5s6t7
Revises: n1o2p3q4r5s6
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = "o2p3q4r5s6t7"
down_revision = "n1o2p3q4r5s6"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("subdomains", "os_detection"):
        op.add_column("subdomains", sa.Column("os_detection", sa.JSON(), nullable=True))
    if not _column_exists("subdomains", "host_scripts"):
        op.add_column("subdomains", sa.Column("host_scripts", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _column_exists("subdomains", "host_scripts"):
        op.drop_column("subdomains", "host_scripts")
    if _column_exists("subdomains", "os_detection"):
        op.drop_column("subdomains", "os_detection")
