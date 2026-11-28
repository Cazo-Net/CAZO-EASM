"""Per-organization outbound integrations (Slack, Teams, Jira, Splunk).

Each row belongs to exactly one organization. Credentials (webhook URLs,
API tokens) are stored encrypted in ``secret_encrypted`` and are never
returned by the API; ``config`` holds the non-secret settings.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class OrgIntegration(Base):
    __tablename__ = "org_integrations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(String, nullable=True)

    kind = Column(String(20), nullable=False)  # slack | teams | jira | splunk
    name = Column(String(80), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    config = Column(JSON, nullable=False, default=dict)
    secret_encrypted = Column(Text, nullable=False, default="")
    event_types = Column(JSON, nullable=False, default=list)

    failure_count = Column(Integer, nullable=False, default=0)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(300), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_org_integrations_org_enabled", "organization_id", "enabled"),
    )


class IntegrationDelivery(Base):
    """One row per thing already sent where a repeat would be noise.

    Used for Jira so the same alert does not open a second ticket.
    """
    __tablename__ = "integration_deliveries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    integration_id = Column(String(36), ForeignKey("org_integrations.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String, nullable=False, index=True)
    dedupe_key = Column(String(64), nullable=False)
    external_ref = Column(String(120), nullable=True)  # e.g. the Jira issue key
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("integration_id", "dedupe_key", name="uq_integration_delivery"),
    )
