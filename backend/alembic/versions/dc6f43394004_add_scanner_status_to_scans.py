"""add scanner_status to scans and clean up legacy AI tables

Revision ID: dc6f43394004
Revises: m6n7o8p9q0r1
Create Date: 2026-07-19 21:42:52.144221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'dc6f43394004'
down_revision: Union[str, Sequence[str], None] = 'm6n7o8p9q0r1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in {idx["name"] for idx in inspector.get_indexes(table)}


def _safe_drop_table(table: str) -> None:
    if _table_exists(table):
        op.drop_table(table)


def _safe_drop_index(table: str, name: str) -> None:
    if _index_exists(table, name):
        op.drop_index(name, table_name=table)


def _safe_create_index(name: str, table: str, columns: list, unique: bool = False) -> None:
    if not _index_exists(table, name):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    """Upgrade schema."""
    # Drop legacy AI tables (idempotent)
    _safe_drop_table('ai_knowledge_articles')
    _safe_drop_table('cazo_knowledge')
    _safe_drop_table('cazo_learnings')
    _safe_drop_table('cazo_behaviors')
    _safe_drop_table('ai_settings')
    _safe_drop_table('ai_workflows')
    _safe_drop_table('ai_messages')
    _safe_drop_table('cazo_workflows')
    _safe_drop_table('ai_conversations')
    _safe_drop_table('ai_usage_logs')
    _safe_drop_table('osint_cache')
    _safe_drop_table('ai_recommendations')
    _safe_drop_table('cazo_profiles')
    _safe_drop_table('cazo_feedback')

    # Indexes on assets (idempotent)
    _safe_create_index('ix_assets_confirmed', 'assets', ['confirmed'])
    _safe_create_index('ix_assets_inventory_status', 'assets', ['inventory_status'])

    # Rename indexes on finding_evidence (drop old, create new)
    _safe_drop_index('finding_evidence', 'ix_finding_evidence_org')
    _safe_drop_index('finding_evidence', 'ix_finding_evidence_vuln')
    _safe_create_index('ix_finding_evidence_organization_id', 'finding_evidence', ['organization_id'])
    _safe_create_index('ix_finding_evidence_vulnerability_id', 'finding_evidence', ['vulnerability_id'])

    # Rename indexes on finding_history (drop old, create new)
    _safe_drop_index('finding_history', 'ix_finding_history_org')
    _safe_drop_index('finding_history', 'ix_finding_history_vuln')
    _safe_create_index('ix_finding_history_organization_id', 'finding_history', ['organization_id'])
    _safe_create_index('ix_finding_history_vulnerability_id', 'finding_history', ['vulnerability_id'])

    # scanner_status on scans (already in initial migration, but guard)
    if not _column_exists('scans', 'scanner_status'):
        with op.batch_alter_table('scans') as batch_op:
            batch_op.add_column(sa.Column('scanner_status', sa.Text(), nullable=True))

    # Make hashed_password nullable (idempotent)
    if _column_exists('users', 'hashed_password'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.alter_column('hashed_password',
                   existing_type=sa.VARCHAR(length=255),
                   nullable=True)

    # Drop old vulnerability indexes (idempotent)
    _safe_drop_index('vulnerabilities', 'ix_vulnerabilities_last_seen')
    _safe_drop_index('vulnerabilities', 'ix_vulnerabilities_org_status')


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate dropped vulnerability indexes
    _safe_create_index('ix_vulnerabilities_org_status', 'vulnerabilities', ['organization_id', 'status'])
    _safe_create_index('ix_vulnerabilities_last_seen', 'vulnerabilities', ['last_seen'])

    # Restore hashed_password NOT NULL
    if _column_exists('users', 'hashed_password'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.alter_column('hashed_password',
                   existing_type=sa.VARCHAR(length=255),
                   nullable=False)

    # Drop scanner_status
    if _column_exists('scans', 'scanner_status'):
        with op.batch_alter_table('scans') as batch_op:
            batch_op.drop_column('scanner_status')

    # Restore old finding indexes
    _safe_drop_index('finding_history', 'ix_finding_history_vulnerability_id')
    _safe_drop_index('finding_history', 'ix_finding_history_organization_id')
    _safe_create_index('ix_finding_history_vuln', 'finding_history', ['vulnerability_id', 'created_at'])
    _safe_create_index('ix_finding_history_org', 'finding_history', ['organization_id'])

    _safe_drop_index('finding_evidence', 'ix_finding_evidence_vulnerability_id')
    _safe_drop_index('finding_evidence', 'ix_finding_evidence_organization_id')
    _safe_create_index('ix_finding_evidence_vuln', 'finding_evidence', ['vulnerability_id'])
    _safe_create_index('ix_finding_evidence_org', 'finding_evidence', ['organization_id'])

    # Drop asset indexes
    _safe_drop_index('assets', 'ix_assets_inventory_status')
    _safe_drop_index('assets', 'ix_assets_confirmed')

    # Recreate legacy AI tables (downgrade only — tables won't exist in fresh DB)
    # Skipped: these were legacy and are not needed for downgrade
