"""Merge the two migration heads; add durable scan queue and scope verification columns.

The history had split into two heads (``add_engine_col001`` and
``p4q5r6s7t8u9``), which made ``alembic upgrade head`` fail. This revision
merges them and adds:

* ``scan_jobs``: ``engine``, ``triggered_by``, ``available_at`` (retry backoff)
  and ``heartbeat_at`` (stale-worker detection) for the durable job queue.
* ``authorized_scopes``: ``verification_token``, ``verification_method`` and
  ``verified_at`` for DNS TXT ownership proof.
* ``periodic_task_state``: one row per periodic job so that only one worker
  runs each job per interval, even with many workers.

Every step checks the live schema first, because many existing databases were
built with ``create_all`` rather than Alembic and may already have some of
these columns.

Revision ID: q5r6s7t8u9v0
Revises: add_engine_col001, p4q5r6s7t8u9
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa

revision = "q5r6s7t8u9v0"
down_revision = ("add_engine_col001", "p4q5r6s7t8u9")
branch_labels = None
depends_on = None


def _columns(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _indexes(table: str) -> set:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return set()
    return {i["name"] for i in insp.get_indexes(table)}


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    # ── scan_jobs: durable queue fields ───────────────────────────────
    cols = _columns("scan_jobs")
    with op.batch_alter_table("scan_jobs") as batch:
        if "engine" not in cols:
            batch.add_column(sa.Column("engine", sa.String(10), nullable=False, server_default="v1"))
        if "triggered_by" not in cols:
            batch.add_column(sa.Column("triggered_by", sa.String(20), nullable=False, server_default="manual"))
        if "available_at" not in cols:
            batch.add_column(sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
        if "heartbeat_at" not in cols:
            batch.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))

    idx = _indexes("scan_jobs")
    if "ix_scan_jobs_claim" not in idx:
        op.create_index("ix_scan_jobs_claim", "scan_jobs", ["status", "available_at", "priority"])
    if "ix_scan_jobs_org_status" not in idx:
        op.create_index("ix_scan_jobs_org_status", "scan_jobs", ["org_id", "status"])
    if "ix_scan_jobs_scan_id" not in idx:
        op.create_index("ix_scan_jobs_scan_id", "scan_jobs", ["scan_id"])

    # ── authorized_scopes: ownership verification ─────────────────────
    cols = _columns("authorized_scopes")
    with op.batch_alter_table("authorized_scopes") as batch:
        if "verification_token" not in cols:
            batch.add_column(sa.Column("verification_token", sa.String(64), nullable=True))
        if "verification_method" not in cols:
            batch.add_column(sa.Column("verification_method", sa.String(20), nullable=True))
        if "verified_at" not in cols:
            batch.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))

    # ── periodic_task_state ───────────────────────────────────────────
    if not _has_table("periodic_task_state"):
        op.create_table(
            "periodic_task_state",
            sa.Column("name", sa.String(100), primary_key=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("locked_by", sa.String(255), nullable=True),
        )

    # ── monitor_schedules: index used by the scheduler tick ───────────
    if _has_table("monitor_schedules") and "ix_monitor_schedules_due" not in _indexes("monitor_schedules"):
        op.create_index("ix_monitor_schedules_due", "monitor_schedules", ["enabled", "next_run_at"])


def downgrade() -> None:
    if _has_table("monitor_schedules") and "ix_monitor_schedules_due" in _indexes("monitor_schedules"):
        op.drop_index("ix_monitor_schedules_due", table_name="monitor_schedules")
    if _has_table("periodic_task_state"):
        op.drop_table("periodic_task_state")
    with op.batch_alter_table("authorized_scopes") as batch:
        batch.drop_column("verified_at")
        batch.drop_column("verification_method")
        batch.drop_column("verification_token")
    idx = _indexes("scan_jobs")
    for name in ("ix_scan_jobs_claim",):
        if name in idx:
            op.drop_index(name, table_name="scan_jobs")
    with op.batch_alter_table("scan_jobs") as batch:
        batch.drop_column("heartbeat_at")
        batch.drop_column("available_at")
        batch.drop_column("triggered_by")
        batch.drop_column("engine")
