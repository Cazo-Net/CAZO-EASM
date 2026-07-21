"""add assets and asset_relationships tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-16 03:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("asset_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.String(length=512), nullable=False),
        sa.Column("label", sa.String(length=512), nullable=True),
        sa.Column("is_alive", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("last_scan_id", sa.String(length=36), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "asset_type", "value", name="uq_asset_org_type_value"),
    )
    op.create_table(
        "asset_relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("source_asset_id", sa.String(length=36), nullable=False),
        sa.Column("target_asset_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=30), nullable=False),
        sa.Column("weight", sa.JSON(), nullable=True),
        sa.Column("last_scan_id", sa.String(length=36), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["target_asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_asset_id", "target_asset_id", "relationship_type",
            name="uq_asset_rel_src_tgt_type",
        ),
    )
    with op.batch_alter_table("assets") as batch_op:
        batch_op.create_index("ix_assets_organization_id", ["organization_id"])
        batch_op.create_index("ix_assets_asset_type", ["asset_type"])
    with op.batch_alter_table("asset_relationships") as batch_op:
        batch_op.create_index("ix_asset_relationships_organization_id", ["organization_id"])
        batch_op.create_index("ix_asset_relationships_source_asset_id", ["source_asset_id"])
        batch_op.create_index("ix_asset_relationships_target_asset_id", ["target_asset_id"])
        batch_op.create_index("ix_asset_relationships_relationship_type", ["relationship_type"])


def downgrade() -> None:
    op.drop_table("asset_relationships")
    op.drop_table("assets")
