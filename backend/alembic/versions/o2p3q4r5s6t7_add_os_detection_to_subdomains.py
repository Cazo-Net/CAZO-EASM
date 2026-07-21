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


def upgrade() -> None:
    op.add_column("subdomains", sa.Column("os_detection", sa.JSON(), nullable=True))
    op.add_column("subdomains", sa.Column("host_scripts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("subdomains", "host_scripts")
    op.drop_column("subdomains", "os_detection")
