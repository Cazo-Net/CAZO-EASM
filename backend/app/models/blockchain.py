"""Blockchain monitoring and investigations, stored per organization.

Every row carries ``organization_id`` and every API query filters on the
caller's own organization, so one customer can never see or change another
customer's watched wallets, alerts or investigation cases.

Nothing in these tables is generated: watches are added by users, alerts are
raised only from real on-chain data and the live OFAC list.
"""
import uuid

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class BlockchainWatch(Base):
    """A wallet or contract an organization monitors (usually one of its own)."""

    __tablename__ = "blockchain_watches"
    __table_args__ = (
        UniqueConstraint("organization_id", "chain", "address", name="uq_bc_watch_org_chain_addr"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    chain = Column(String(20), nullable=False)
    address = Column(String(128), nullable=False)
    label = Column(String(200), nullable=True)
    alert_on_new_tx = Column(Boolean, default=True, nullable=False)
    alert_on_sanctions = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    # Newest transaction hash seen at the last check; new activity is anything after it.
    last_tx_hash = Column(String(128), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    last_balance = Column(String(64), nullable=True)
    # {"result": "ok" | "not_configured" | "upstream_error", "message": ...}
    last_status = Column(JSON, default=dict)


class BlockchainAlert(Base):
    __tablename__ = "blockchain_alerts"
    __table_args__ = (
        UniqueConstraint("organization_id", "fingerprint", name="uq_bc_alert_org_fp"),
        Index("ix_bc_alerts_org_ack", "organization_id", "acknowledged"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    watch_id = Column(String(36), ForeignKey("blockchain_watches.id", ondelete="SET NULL"), nullable=True, index=True)
    chain = Column(String(20), nullable=False)
    address = Column(String(128), nullable=False)
    # new_transaction | sanctioned_counterparty | address_sanctioned
    alert_type = Column(String(40), nullable=False)
    severity = Column(String(20), nullable=False, default="info")
    title = Column(String(300), nullable=False)
    message = Column(Text, nullable=True)
    tx_hash = Column(String(128), nullable=True)
    counterparty = Column(String(128), nullable=True)
    source = Column(String(120), nullable=True)
    reference_url = Column(String(500), nullable=True)
    data = Column(JSON, default=dict)
    fingerprint = Column(String(200), nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BlockchainCase(Base):
    """An investigation case (e.g. tracing funds from an incident)."""

    __tablename__ = "blockchain_cases"
    __table_args__ = (Index("ix_bc_cases_org_status", "organization_id", "status"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), nullable=False, default="open")
    priority = Column(String(20), nullable=False, default="medium")
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    assigned_to = Column(String(36), ForeignKey("users.id"), nullable=True)
    # [{"chain": "ethereum", "address": "0x...", "note": "..."}]
    addresses = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)


class BlockchainCaseMember(Base):
    __tablename__ = "blockchain_case_members"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_bc_case_member"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("blockchain_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False, default="analyst")
    added_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())


class BlockchainCaseEntry(Base):
    """A note on a case, or an audit-trail event (kind = "note" | "audit")."""

    __tablename__ = "blockchain_case_entries"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("blockchain_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(10), nullable=False, default="note")
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(60), nullable=True)
    content = Column(Text, default="")
    entity_type = Column(String(30), nullable=True)
    entity_id = Column(String(200), nullable=True)
    detail = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


__all__ = [
    "BlockchainWatch", "BlockchainAlert", "BlockchainCase", "BlockchainCaseMember", "BlockchainCaseEntry",
]
