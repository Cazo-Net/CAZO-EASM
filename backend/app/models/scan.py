from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid
import json


class Scan(Base):
    __tablename__ = "scans"
    __table_args__ = (
        # Composite indexes for 1M+ scan queries
        Index("ix_scans_org_status", "organization_id", "status"),
        Index("ix_scans_org_created", "organization_id", "created_at"),
        Index("ix_scans_domain_status", "domain", "status"),
        Index("ix_scans_created_by", "created_by"),
        Index("ix_scans_project", "project_id"),
        Index("ix_scans_status_started", "status", "started_at"),
        # Partial index for active scans (PostgreSQL)
        Index("ix_scans_active", "status", "started_at", postgresql_where="status IN ('running', 'pending')"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String(255), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True, index=True)
    project_id = Column(String(36), nullable=True)
    status = Column(String(20), default="pending", index=True)
    progress = Column(Integer, default=0)
    scan_type = Column(String(20), default="full")
    scan_options_raw = Column("scan_options", Text, nullable=True)
    engine = Column(String(20), default="v1", nullable=False, server_default="v1")
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_by = Column(String(36), ForeignKey("users.id"))
    error_message = Column(Text)
    scanner_status_raw = Column("scanner_status", Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def scan_options(self):
        if self.scan_options_raw:
            try:
                return json.loads(self.scan_options_raw)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    @scan_options.setter
    def scan_options(self, value):
        if value is None:
            self.scan_options_raw = None
        elif isinstance(value, str):
            self.scan_options_raw = value
        else:
            self.scan_options_raw = json.dumps(value)

    @property
    def scanner_status(self):
        if self.scanner_status_raw:
            try:
                return json.loads(self.scanner_status_raw)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @scanner_status.setter
    def scanner_status(self, value):
        if value is None:
            self.scanner_status_raw = None
        elif isinstance(value, str):
            self.scanner_status_raw = value
        else:
            self.scanner_status_raw = json.dumps(value)

    subdomains = relationship("Subdomain", back_populates="scan", cascade="all, delete-orphan")
    vulnerabilities = relationship("Vulnerability", back_populates="scan", cascade="all, delete-orphan")
    whois_records = relationship("WhoisRecord", back_populates="scan", cascade="all, delete-orphan")
    risk_scores = relationship("RiskScore", back_populates="scan", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="scan", cascade="all, delete-orphan")


class ScanJob(Base):
    """Durable, database-backed scan job queue.

    The API inserts one row per scan; scan workers (``python -m
    app.workers.scan_worker`` or the scan-engine container) claim rows with
    ``SELECT ... FOR UPDATE SKIP LOCKED`` so that each job runs exactly once,
    survives restarts, and is retried with backoff. See
    ``app/services/job_queue.py``.
    """
    __tablename__ = "scan_jobs"
    __table_args__ = (
        Index("ix_scan_jobs_status_priority", "status", "priority"),
        Index("ix_scan_jobs_org_status", "org_id", "status"),
        Index("ix_scan_jobs_created", "created_at"),
        Index("ix_scan_jobs_claim", "status", "available_at", "priority"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(Text, nullable=False)
    scan_type = Column(String(20), nullable=False, default="full")
    scan_options_raw = Column("scan_options", Text, nullable=True)
    org_id = Column(String(36), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    priority = Column(Integer, default=0)
    attempt = Column(Integer, default=0)
    max_attempts = Column(Integer, default=2)
    worker_id = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    # "v1" or "v2" — which scan service executes the job.
    engine = Column(String(10), nullable=False, default="v1", server_default="v1")
    # "manual", "schedule", "rescan", "api"
    triggered_by = Column(String(20), nullable=False, default="manual", server_default="manual")
    # Earliest time the job may be claimed (used for retry backoff).
    available_at = Column(DateTime(timezone=True), nullable=True)
    # Updated periodically by the worker running the job; a stale heartbeat
    # means the worker died and the job can be retried.
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def scan_options(self):
        raw = self.scan_options_raw
        # The initial migration created this column as JSON, so on Postgres
        # the driver may hand back an already-decoded dict.
        if isinstance(raw, dict):
            return raw
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    scan = relationship("Scan")
