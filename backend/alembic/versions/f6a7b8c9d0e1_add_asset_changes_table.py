"""add asset_changes table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-16 03:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_changes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("from_scan_id", sa.String(length=36), nullable=True),
        sa.Column("to_scan_id", sa.String(length=36), nullable=False),
        sa.Column("change_type", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_key", sa.String(length=512), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("asset_changes") as batch_op:
        batch_op.create_index("ix_asset_changes_organization_id", ["organization_id"])
        batch_op.create_index("ix_asset_changes_from_scan_id", ["from_scan_id"])
        batch_op.create_index("ix_asset_changes_to_scan_id", ["to_scan_id"])
        batch_op.create_index("ix_asset_changes_change_type", ["change_type"])
        batch_op.create_index("ix_asset_changes_detected_at", ["detected_at"])


def downgrade() -> None:
    op.drop_table("asset_changes")
