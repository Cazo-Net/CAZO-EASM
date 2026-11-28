"""Webhook model for outbound event notifications.

Stores webhook configurations per organization with:
- URL, secret (for HMAC signing), event type filters
- Active/inactive state, failure tracking
- Per-org rate limiting
"""
from __future__ import annotations

import secrets
import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float,
    DateTime, ForeignKey, JSON, Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Webhook(Base):
    """Outbound webhook configuration."""

    __tablename__ = "webhooks"

    id = Column(String, primary_key=True, default=lambda: secrets.token_urlsafe(32))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)

    # Webhook target
    url = Column(Text, nullable=False)
    secret = Column(Text, nullable=False, default=lambda: secrets.token_urlsafe(48))
    description = Column(Text, nullable=True)

    # Event filtering
    event_types = Column(JSON, nullable=False, default=list)  # e.g. ["scan.completed", "finding.critical"]
    is_active = Column(Boolean, default=True, nullable=False)

    # Content configuration
    content_type = Column(String, default="application/json", nullable=False)
    custom_headers = Column(JSON, default=dict)  # Additional headers to send
    payload_template = Column(Text, nullable=True)  # Optional Jinja2 template

    # Reliability tracking
    failure_count = Column(Integer, default=0, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Rate limiting (per org)
    max_per_minute = Column(Integer, default=30, nullable=False)
    _minute_counter = Column(Integer, default=0, nullable=False)
    _minute_reset_at = Column(Float, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_webhooks_org_active", "organization_id", "is_active"),
    )

    def matches_event(self, event_type: str) -> bool:
        """Check if this webhook should fire for the given event type."""
        if not self.is_active:
            return False
        if not self.event_types:
            return True  # Empty = all events
        # Support wildcards: "finding.*" matches "finding.critical"
        for pattern in self.event_types:
            if pattern == event_type:
                return True
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if event_type.startswith(prefix + "."):
                    return True
        return False

    def check_rate_limit(self) -> bool:
        """Check if webhook is within rate limit. Returns True if OK to fire."""
        now = time.time()
        if now - self._minute_reset_at >= 60:
            self._minute_counter = 0
            self._minute_reset_at = now
        if self._minute_counter >= self.max_per_minute:
            return False
        self._minute_counter += 1
        return True

    def record_success(self) -> None:
        self.failure_count = 0
        self.last_success_at = datetime.now(timezone.utc)
        self.last_triggered_at = datetime.now(timezone.utc)

    def record_failure(self, error: str) -> None:
        self.failure_count += 1
        self.last_failure_at = datetime.now(timezone.utc)
        self.last_triggered_at = datetime.now(timezone.utc)
        self.last_error = error[:500]
        # Auto-disable after 20 consecutive failures
        if self.failure_count >= 20:
            self.is_active = False

    def sign_payload(self, payload: bytes) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        return hmac.new(
            self.secret.encode(), payload, hashlib.sha256
        ).hexdigest()


# Known webhook event types
WEBHOOK_EVENT_TYPES = {
    # Scan events
    "scan.started": "Scan started",
    "scan.completed": "Scan completed",
    "scan.failed": "Scan failed",

    # Finding events
    "finding.critical": "Critical finding discovered",
    "finding.high": "High severity finding",
    "finding.medium": "Medium severity finding",

    # Asset events
    "asset.new_subdomain": "New subdomain discovered",
    "asset.new_port": "New open port detected",
    "asset.new_technology": "New technology detected",
    "asset.shadow_asset": "Shadow asset discovered",
    "asset.disappeared": "Asset no longer found",

    # SSL events
    "ssl.certificate_expiring": "SSL certificate expiring soon",
    "ssl.certificate_expired": "SSL certificate expired",
    "ssl.certificate_changed": "SSL certificate replaced",

    # Supply chain events
    "supply_chain.vendor_detected": "New third-party vendor detected",
    "supply_chain.high_risk_vendor": "High-risk vendor detected",

    # Risk events
    "risk.score_changed": "Risk score changed",
    "risk.elevated": "Risk score elevated",

    # CVE events
    "cve.new_match": "New CVE match found",
    "cve.active_exploit": "Active exploit detected",
}
