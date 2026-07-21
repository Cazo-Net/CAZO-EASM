"""initial schema

Revision ID: 2029b771a51e
Revises: 
Create Date: 2026-07-15 15:51:47.125233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2029b771a51e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    The base tables are created by the application's ``init_db()``
    (``Base.metadata.create_all``) at startup in development/SQLite, and by the
    production deployment's bootstrap before ``alembic upgrade head`` runs. This
    initial revision therefore intentionally performs no DDL; subsequent
    revisions apply additive schema changes on top of that baseline.
    """
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
