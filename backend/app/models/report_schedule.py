"""Scheduled email reports: an organization's recurring summary email."""
from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(String, nullable=True)

    name = Column(String(80), nullable=False)
    frequency = Column(String(10), nullable=False, default="weekly")  # weekly | monthly
    weekday = Column(Integer, nullable=False, default=0)  # 0 = Monday (weekly)
    day_of_month = Column(Integer, nullable=False, default=1)  # 1-28 (monthly)
    hour = Column(Integer, nullable=False, default=8)  # local hour in `timezone`
    timezone = Column(String(64), nullable=False, default="UTC")
    recipients = Column(JSON, nullable=False, default=list)
    include_pdf = Column(Boolean, nullable=False, default=True)
    enabled = Column(Boolean, nullable=False, default=True)

    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(20), nullable=True)  # sent | partial | failed | not_configured
    last_error = Column(String(300), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_report_schedules_due", "enabled", "next_run_at"),
    )
