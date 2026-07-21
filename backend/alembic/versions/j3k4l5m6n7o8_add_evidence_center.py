"""add evidence center tables and finding lifecycle columns

Revision ID: j3k4l5m6n7o8
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'j3k4l5m6n7o8'
down_revision: Union[str, Sequence[str], None] = 'i2j3k4l5m6n7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Add lifecycle columns to vulnerabilities ──────────────
    with op.batch_alter_table("vulnerabilities") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="open"))
        batch_op.add_column(sa.Column("fingerprint", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()))
        batch_op.add_column(sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()))
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("asset_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("assigned_to", sa.String(36), nullable=True))

        batch_op.create_index("ix_vulnerabilities_status", ["status"])
        batch_op.create_index("ix_vulnerabilities_fingerprint", ["fingerprint"])
        batch_op.create_index("ix_vulnerabilities_org_status", ["organization_id", "status"])
        batch_op.create_index("ix_vulnerabilities_last_seen", ["last_seen"])

        batch_op.create_foreign_key("fk_vuln_org", "organizations", ["organization_id"], ["id"])
        batch_op.create_foreign_key("fk_vuln_asset", "assets", ["asset_id"], ["id"])
        batch_op.create_foreign_key("fk_vuln_assigned", "users", ["assigned_to"], ["id"])

    # ── 2. Create finding_history table ──────────────────────────
    op.create_table(
        "finding_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vulnerability_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("finding_history") as batch_op:
        batch_op.create_index("ix_finding_history_vuln", ["vulnerability_id", "created_at"])
        batch_op.create_index("ix_finding_history_org", ["organization_id"])

    # ── 3. Create finding_evidence table ─────────────────────────
    op.create_table(
        "finding_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vulnerability_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("captured_by", sa.String(length=36), nullable=True),
        sa.Column("scanner_id", sa.String(length=100), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["captured_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("finding_evidence") as batch_op:
        batch_op.create_index("ix_finding_evidence_vuln", ["vulnerability_id"])
        batch_op.create_index("ix_finding_evidence_org", ["organization_id"])


def downgrade() -> None:
    op.drop_table("finding_evidence")
    op.drop_table("finding_history")

    with op.batch_alter_table("vulnerabilities") as batch_op:
        batch_op.drop_index("ix_vulnerabilities_last_seen")
        batch_op.drop_index("ix_vulnerabilities_org_status")
        batch_op.drop_index("ix_vulnerabilities_fingerprint")
        batch_op.drop_index("ix_vulnerabilities_status")
        batch_op.drop_constraint("fk_vuln_assigned", type_="foreignkey")
        batch_op.drop_constraint("fk_vuln_asset", type_="foreignkey")
        batch_op.drop_constraint("fk_vuln_org", type_="foreignkey")
        batch_op.drop_column("assigned_to")
        batch_op.drop_column("asset_id")
        batch_op.drop_column("organization_id")
        batch_op.drop_column("last_seen")
        batch_op.drop_column("first_seen")
        batch_op.drop_column("fingerprint")
        batch_op.drop_column("status")
