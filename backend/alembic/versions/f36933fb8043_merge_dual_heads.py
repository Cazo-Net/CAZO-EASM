"""merge dual heads

Revision ID: f36933fb8043
Revises: dc6f43394004, o2p3q4r5s6t7
Create Date: 2026-07-23 23:02:31.832405

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f36933fb8043'
down_revision: Union[str, Sequence[str], None] = ('dc6f43394004', 'o2p3q4r5s6t7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
