"""add_scan_options_to_scans

Revision ID: fa19a4187a5f
Revises: g0h1i2j3k4l5
Create Date: 2026-07-16 21:38:12.316554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa19a4187a5f'
down_revision: Union[str, Sequence[str], None] = 'g0h1i2j3k4l5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scan_options column to scans if it doesn't exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("scans")}

    if "scan_options" not in columns:
        with op.batch_alter_table("scans", schema=None) as batch_op:
            batch_op.add_column(sa.Column("scan_options", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove scan_options column if it exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("scans")}

    if "scan_options" in columns:
        with op.batch_alter_table("scans", schema=None) as batch_op:
            batch_op.drop_column("scan_options")
