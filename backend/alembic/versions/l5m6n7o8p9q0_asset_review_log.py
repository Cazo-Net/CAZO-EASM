"""Asset review log for Shadow Asset Detection audit trail.

Records every confirm / reject / investigate decision on a discovered asset so
the inventory history is auditable. Additive only.
"""
from alembic import op
import sqlalchemy as sa

revision = "l5m6n7o8p9q0"
down_revision = "k4l5m6n7o8p9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "asset_review_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False, index=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(20), nullable=False, index=True),
        sa.Column("old_status", sa.String(20), nullable=True),
        sa.Column("new_status", sa.String(20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("asset_review_log")
