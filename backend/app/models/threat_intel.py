"""Dark web & threat-intelligence monitoring.

A *monitor* is something an organization watches (one of its own domains or
an address on one of its own domains). Each check asks real, named sources
about it and stores what they returned as *findings*. Every finding records
the source it came from and a reference link, so a customer can always see
where a result came from. Nothing in these tables is generated or simulated.
"""
import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class ThreatIntelMonitor(Base):
    __tablename__ = "threat_intel_monitors"
    __table_args__ = (
        UniqueConstraint("organization_id", "kind", "value", name="uq_ti_monitor_org_kind_value"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    # "domain" (an organization domain) or "email" (an address on one).
    kind = Column(String(20), nullable=False)
    value = Column(String(320), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    # Per-source outcome of the last check, e.g. {"hibp_breaches": "ok"}.
    last_status = Column(JSON, default=dict)


class ThreatIntelFinding(Base):
    __tablename__ = "threat_intel_findings"
    __table_args__ = (
        UniqueConstraint("organization_id", "fingerprint", name="uq_ti_finding_org_fp"),
        Index("ix_ti_findings_org_status", "organization_id", "status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    monitor_id = Column(String(36), ForeignKey("threat_intel_monitors.id", ondelete="CASCADE"),
                        nullable=True, index=True)
    # Where the data came from, e.g. "hibp", "urlhaus", "threatfox", "dns".
    source = Column(String(40), nullable=False)
    # breach_site | breach_account | breach_domain | malware_url | threat_ioc | lookalike_domain
    category = Column(String(40), nullable=False)
    subject = Column(String(320), nullable=False)  # the monitored value it is about
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="medium")
    reference_url = Column(String(1000), nullable=True)
    # When the source says the event happened (breach date, URL added date...).
    observed_at = Column(String(40), nullable=True)
    data = Column(JSON, default=dict)
    fingerprint = Column(String(64), nullable=False)
    # open | acknowledged | resolved
    status = Column(String(20), nullable=False, default="open")
    times_seen = Column(Integer, nullable=False, default=1)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now())
