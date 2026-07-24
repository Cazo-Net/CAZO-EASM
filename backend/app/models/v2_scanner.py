"""Models for v2 scanner tables — monitor_schedules, scan_history, asset_lifecycle, notification_triggers."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, func
)
from app.database import Base


class MonitorSchedule(Base):
    __tablename__ = "monitor_schedules"

    id = Column(String(36), primary_key=True)
    domain = Column(String(255), nullable=False, index=True)
    interval_hours = Column(Integer, nullable=False, default=24)
    scan_type = Column(String(20), nullable=False, default="quick")
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ScanHistory(Base):
    __tablename__ = "scan_history"

    id = Column(String(36), primary_key=True)
    domain = Column(String(255), nullable=False, index=True)
    scan_type = Column(String(20), nullable=False)
    scan_engine = Column(String(20), nullable=False, default="v2")
    status = Column(String(20), nullable=False, default="pending")
    triggered_by = Column(String(20), nullable=False, default="manual")
    monitor_schedule_id = Column(String(36), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    subdomains_found = Column(Integer, default=0)
    open_ports_found = Column(Integer, default=0)
    technologies_found = Column(Integer, default=0)
    risk_score = Column(Float, default=0.0)
    risk_severity = Column(String(20), nullable=True)
    duration_ms = Column(Float, default=0.0)
    result_summary = Column(Text, nullable=True)
    result_data = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AssetLifecycle(Base):
    __tablename__ = "asset_lifecycle"

    id = Column(String(36), primary_key=True)
    domain = Column(String(255), nullable=False, index=True)
    asset_type = Column(String(50), nullable=False)
    asset_value = Column(String(500), nullable=False)
    state = Column(String(20), nullable=False, default="active")
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    removed_at = Column(DateTime(timezone=True), nullable=True)
    scan_history_id = Column(String(36), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class NotificationTrigger(Base):
    __tablename__ = "notification_triggers"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    domain = Column(String(255), nullable=True)
    event_type = Column(String(50), nullable=False)
    threshold = Column(Integer, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    notification_method = Column(String(20), nullable=False, default="email")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
