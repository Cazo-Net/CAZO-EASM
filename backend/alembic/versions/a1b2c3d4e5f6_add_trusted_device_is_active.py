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


def upgrade() -> None:
    with op.batch_alter_table("trusted_devices") as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true())
        )
        batch_op.create_index("ix_trusted_devices_is_active", ["is_active"])


def downgrade() -> None:
    with op.batch_alter_table("trusted_devices") as batch_op:
        batch_op.drop_index("ix_trusted_devices_is_active")
        batch_op.drop_column("is_active")
