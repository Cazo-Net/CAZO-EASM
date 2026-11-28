"""Per-organization settings for asset inventory change alerts."""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AlertSettings(Base):
    __tablename__ = "alert_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True
    )
    # Master switch for inventory change alerts.
    enabled = Column(Boolean, nullable=False, default=True)
    # {alert_type: {"in_app": bool, "email": bool}}; missing keys use defaults.
    rules = Column(JSON, default=dict)
    # Warn when a certificate expires within this many days.
    cert_expiry_days = Column(Integer, nullable=False, default=30)
    # Lowest finding severity that raises an alert: critical | high | medium
    finding_min_severity = Column(String(20), nullable=False, default="critical")
    # Who is notified: "admins" (owners and admins) or "all" (every member).
    recipients = Column(String(20), nullable=False, default="admins")
    # Extra mailboxes (a SOC inbox, an MSSP client contact) that get the emails.
    extra_emails = Column(JSON, default=list)
    updated_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
