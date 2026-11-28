"""Add v2 scanner tables — monitor_schedules, scan_history, asset_lifecycle.

Revision ID: v2scanner001
Revises: f36933fb8043
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "v2scanner001"
down_revision = "f36933fb8043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # monitor_schedules — stores continuous monitoring configuration
    op.create_table(
        "monitor_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False, index=True),
        sa.Column("interval_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("scan_type", sa.String(20), nullable=False, server_default="quick"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # scan_history — stores v2 scan execution records
    op.create_table(
        "scan_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False, index=True),
        sa.Column("scan_type", sa.String(20), nullable=False),
        sa.Column("scan_engine", sa.String(20), nullable=False, server_default="v2"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("triggered_by", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("monitor_schedule_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("subdomains_found", sa.Integer, server_default="0"),
        sa.Column("open_ports_found", sa.Integer, server_default="0"),
        sa.Column("technologies_found", sa.Integer, server_default="0"),
        sa.Column("risk_score", sa.Float, server_default="0.0"),
        sa.Column("risk_severity", sa.String(20), nullable=True),
        sa.Column("duration_ms", sa.Float, server_default="0.0"),
        sa.Column("result_summary", sa.Text, nullable=True),
        sa.Column("result_data", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # asset_lifecycle — tracks asset state changes over time
    op.create_table(
        "asset_lifecycle",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False, index=True),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("asset_value", sa.String(500), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="active"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_history_id", sa.String(36), nullable=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # notification_triggers — event-driven alerting rules
    op.create_table(
        "notification_triggers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("threshold", sa.Integer, server_default="1"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("notification_method", sa.String(20), nullable=False, server_default="email"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notification_triggers")
    op.drop_table("asset_lifecycle")
    op.drop_table("scan_history")
    op.drop_table("monitor_schedules")
