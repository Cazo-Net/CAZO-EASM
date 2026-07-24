"""add user security fields

Revision ID: 2e8108534153
Revises: 2029b771a51e
Create Date: 2026-07-15 22:12:42.916938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e8108534153'
down_revision: Union[str, Sequence[str], None] = '2029b771a51e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_drop_index(batch_op, name):
    """Drop an index only if it exists (defensive for mixed initial schemas)."""
    try:
        batch_op.drop_index(batch_op.f(name))
    except Exception:
        # Index absent in this schema variant — safe to skip.
        pass


def _safe_add_column(table, column):
    """Add a column only if it does not already exist.

    Keeps the migration idempotent when the application's ``init_db()``
    (``Base.metadata.create_all``) has already created the schema — the two
    bootstrap paths can run in either order without error.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column.name in existing:
        return
    op.add_column(table, column)


def _safe_create_index(table, name, columns):
    """Create an index only if it does not already exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {i["name"] for i in inspector.get_indexes(table)}
    if name in existing:
        return
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.create_index(name, columns, unique=False)


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: The auto-generated index drops below referenced indexes that are not
    # present in every initial-schema variant. They are guarded so the migration
    # applies cleanly regardless of which base schema is in use. The real intent
    # of this migration is the user security columns/indexes added afterward.
    _safe_drop_index(op.batch_alter_table('ai_conversations'), 'idx_ai_conv_user')
    _safe_drop_index(op.batch_alter_table('ai_knowledge_articles'), 'idx_ai_knowledge_category')
    _safe_drop_index(op.batch_alter_table('ai_messages'), 'idx_ai_msg_conv')
    _safe_drop_index(op.batch_alter_table('ai_recommendations'), 'idx_ai_rec_dismissed')
    _safe_drop_index(op.batch_alter_table('ai_recommendations'), 'idx_ai_rec_user')
    _safe_drop_index(op.batch_alter_table('ai_usage_logs'), 'idx_ai_usage_action')
    _safe_drop_index(op.batch_alter_table('ai_usage_logs'), 'idx_ai_usage_user')
    _safe_drop_index(op.batch_alter_table('asset_tags'), 'idx_asset_tags_asset')
    _safe_drop_index(op.batch_alter_table('asset_tags'), 'idx_asset_tags_tag_id')
    _safe_drop_index(op.batch_alter_table('audit_logs'), 'idx_audit_logs_action')
    _safe_drop_index(op.batch_alter_table('audit_logs'), 'idx_audit_logs_entity')
    _safe_drop_index(op.batch_alter_table('audit_logs'), 'idx_audit_logs_user_id')
    _safe_drop_index(op.batch_alter_table('canvas_edges'), 'idx_canvas_edge_canvas')
    _safe_drop_index(op.batch_alter_table('canvas_nodes'), 'idx_canvas_node_canvas')
    _safe_drop_index(op.batch_alter_table('canvases'), 'idx_canvas_project')
    _safe_drop_index(op.batch_alter_table('canvases'), 'idx_canvas_user')
    _safe_drop_index(op.batch_alter_table('favorites'), 'idx_favorites_asset')
    _safe_drop_index(op.batch_alter_table('favorites'), 'idx_favorites_user_id')
    _safe_drop_index(op.batch_alter_table('notifications'), 'idx_notifications_read')
    _safe_drop_index(op.batch_alter_table('notifications'), 'idx_notifications_type')
    _safe_drop_index(op.batch_alter_table('notifications'), 'idx_notifications_user_id')
    _safe_drop_index(op.batch_alter_table('tags'), 'idx_tags_user_id')

    # Add user security columns directly. SQLite supports ADD COLUMN natively,
    # and using op.add_column (instead of batch_alter_table) avoids the
    # circular-dependency errors that batch mode can raise when many columns
    # are added alongside an alter_column on the same table. Columns are added
    # defensively so the migration is idempotent with create_all().
    _safe_add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=True))
    _safe_add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    _safe_add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=True))
    _safe_add_column('users', sa.Column('verification_token', sa.String(length=255), nullable=True))
    _safe_add_column('users', sa.Column('reset_token', sa.String(length=255), nullable=True))
    _safe_add_column('users', sa.Column('reset_token_expires', sa.DateTime(timezone=True), nullable=True))
    _safe_add_column('users', sa.Column('totp_enabled', sa.Boolean(), nullable=True))
    _safe_add_column('users', sa.Column('totp_secret', sa.String(length=255), nullable=True))
    # Convert preferences TEXT -> JSON. SQLite cannot ALTER COLUMN type; this
    # is a no-op (already JSON) when the schema was created via create_all, so
    # guard it and skip on failure.
    try:
        op.alter_column('users', 'preferences',
               existing_type=sa.TEXT(),
               type_=sa.JSON(),
               existing_nullable=True)
    except Exception:
        pass
    # Indexes created defensively (may already exist from create_all).
    _safe_create_index('users', 'ix_users_reset_token', ['reset_token'])
    _safe_create_index('users', 'ix_users_verification_token', ['verification_token'])

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("users")}

    # Drop indexes on users (idempotent)
    with op.batch_alter_table('users', schema=None) as batch_op:
        _safe_drop_index(batch_op, 'ix_users_verification_token')
        _safe_drop_index(batch_op, 'ix_users_reset_token')

    # Drop columns (idempotent — SQLite doesn't support ALTER COLUMN TYPE, so skip that)
    for col in ['totp_secret', 'totp_enabled', 'reset_token_expires',
                'reset_token', 'verification_token', 'email_verified',
                'locked_until', 'failed_login_attempts']:
        if col in existing_columns:
            op.drop_column('users', col)

    # NOTE: Do NOT recreate indexes or tables that were removed by dc6f43394004.
    # That cleanup migration permanently removed legacy AI tables and renamed
    # indexes — recreating them on downgrade would be incorrect.
