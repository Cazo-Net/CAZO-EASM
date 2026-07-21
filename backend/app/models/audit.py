"""Generic audit event model.

Complements ``AuthAuditLog`` (auth-specific) with a flexible record for all
non-auth actions so operators get a single, queryable audit trail across scans,
discovery, asset changes, scope edits, and admin actions.
"""
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(64), nullable=False, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    actor_id = Column(String(36), nullable=True, index=True)
    actor_type = Column(String(20), default="user")
    target_type = Column(String(40), nullable=True)
    target_id = Column(String(36), nullable=True)
    status = Column(String(20), default="success")
    detail = Column(JSON, default=dict)
    request_id = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
