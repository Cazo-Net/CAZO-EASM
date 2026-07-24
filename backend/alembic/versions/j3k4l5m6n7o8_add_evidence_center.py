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


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def _safe_add_column(table: str, column: sa.Column) -> None:
    if not _column_exists(table, column.name):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(column)


def _safe_create_index(name: str, table: str, columns: list) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes(table)}
    if name not in existing:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_index(name, columns)


def _safe_create_fk(name: str, table: str, local_cols: list, ref_table: str, ref_cols: list) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {fk["name"] for fk in inspector.get_foreign_keys(table)}
    if name not in existing:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_foreign_key(name, ref_table, local_cols, ref_cols)


def upgrade() -> None:
    # ── 1. Add lifecycle columns to vulnerabilities ──────────────
    _safe_add_column("vulnerabilities", sa.Column("status", sa.String(20), nullable=False, server_default="open"))
    _safe_add_column("vulnerabilities", sa.Column("fingerprint", sa.String(64), nullable=True))
    _safe_add_column("vulnerabilities", sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()))
    _safe_add_column("vulnerabilities", sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()))
    _safe_add_column("vulnerabilities", sa.Column("organization_id", sa.String(36), nullable=True))
    _safe_add_column("vulnerabilities", sa.Column("asset_id", sa.String(36), nullable=True))
    _safe_add_column("vulnerabilities", sa.Column("assigned_to", sa.String(36), nullable=True))

    _safe_create_index("ix_vulnerabilities_status", "vulnerabilities", ["status"])
    _safe_create_index("ix_vulnerabilities_fingerprint", "vulnerabilities", ["fingerprint"])
    _safe_create_index("ix_vulnerabilities_org_status", "vulnerabilities", ["organization_id", "status"])
    _safe_create_index("ix_vulnerabilities_last_seen", "vulnerabilities", ["last_seen"])

    _safe_create_fk("fk_vuln_org", "vulnerabilities", ["organization_id"], "organizations", ["id"])
    _safe_create_fk("fk_vuln_asset", "vulnerabilities", ["asset_id"], "assets", ["id"])
    _safe_create_fk("fk_vuln_assigned", "vulnerabilities", ["assigned_to"], "users", ["id"])

    # ── 2. Create finding_history table ──────────────────────────
    if not _table_exists("finding_history"):
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
    if not _table_exists("finding_evidence"):
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
    if _table_exists("finding_evidence"):
        op.drop_table("finding_evidence")
    if _table_exists("finding_history"):
        op.drop_table("finding_history")

    for idx in ["ix_vulnerabilities_last_seen", "ix_vulnerabilities_org_status",
                "ix_vulnerabilities_fingerprint", "ix_vulnerabilities_status"]:
        try:
            with op.batch_alter_table("vulnerabilities") as batch_op:
                batch_op.drop_index(idx)
        except Exception:
            pass

    for fk in ["fk_vuln_assigned", "fk_vuln_asset", "fk_vuln_org"]:
        try:
            with op.batch_alter_table("vulnerabilities") as batch_op:
                batch_op.drop_constraint(fk, type_="foreignkey")
        except Exception:
            pass

    for col in ["assigned_to", "asset_id", "organization_id", "last_seen",
                "first_seen", "fingerprint", "status"]:
        if _column_exists("vulnerabilities", col):
            with op.batch_alter_table("vulnerabilities") as batch_op:
                batch_op.drop_column(col)
