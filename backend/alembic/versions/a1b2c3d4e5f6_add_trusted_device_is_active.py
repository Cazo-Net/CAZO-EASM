"""add is_active to trusted_devices

Revision ID: a1b2c3d4e5f6
Revises: 870f444a6e09
Create Date: 2026-07-16 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '870f444a6e09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    if not _column_exists("trusted_devices", "is_active"):
        with op.batch_alter_table("trusted_devices") as batch_op:
            batch_op.add_column(
                sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true())
            )
    if not _index_exists("trusted_devices", "ix_trusted_devices_is_active"):
        with op.batch_alter_table("trusted_devices") as batch_op:
            batch_op.create_index("ix_trusted_devices_is_active", ["is_active"])


def downgrade() -> None:
    if _index_exists("trusted_devices", "ix_trusted_devices_is_active"):
        with op.batch_alter_table("trusted_devices") as batch_op:
            batch_op.drop_index("ix_trusted_devices_is_active")
    if _column_exists("trusted_devices", "is_active"):
        with op.batch_alter_table("trusted_devices") as batch_op:
            batch_op.drop_column("is_active")
