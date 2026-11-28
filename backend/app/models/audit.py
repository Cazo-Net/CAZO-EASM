"""Audit event model: the per-organization record of who did what.

Every row is linked to the one before it in the same organization: ``seq`` is
its position in that organization's log and ``hash`` is a keyed fingerprint
(HMAC-SHA256) of the row's contents plus the previous row's ``hash``. Editing,
deleting or re-ordering rows breaks the chain, which
``app.services.audit.verify_chain`` detects. Rows written before the chain was
introduced have no ``seq``/``hash`` and are shown as "legacy".
"""
from sqlalchemy import Column, String, DateTime, JSON, Integer, Index
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
    # Snapshot of who acted, so the record still reads correctly after the
    # user is renamed or deleted.
    actor_email = Column(String(255), nullable=True)
    target_type = Column(String(40), nullable=True)
    target_id = Column(String(36), nullable=True)
    status = Column(String(20), default="success")
    detail = Column(JSON, default=dict)
    request_id = Column(String(32), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(400), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Tamper-evidence chain (per organization).
    seq = Column(Integer, nullable=True)
    prev_hash = Column(String(64), nullable=True)
    hash = Column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_audit_events_org_seq", "organization_id", "seq"),
    )
