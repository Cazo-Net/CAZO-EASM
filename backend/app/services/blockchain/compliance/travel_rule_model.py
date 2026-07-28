"""Travel Rule compliance data model.

FATF Recommendation 16 requires VASPs to share originator/beneficiary
information for transactions above a threshold. This module tracks
compliance status for blockchain transactions.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, JSON, Index, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class TravelRuleStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    EXEMPT = "exempt"  # Below threshold
    UNKNOWN = "unknown"
    ERROR = "error"


class VASPClassification(str, enum.Enum):
    REGULATED = "regulated"
    UNREGULATED = "unregulated"
    SELF_HOSTED = "self_hosted"
    MIXER = "mixer"
    UNKNOWN = "unknown"


class TravelRuleRecord(Base):
    """Travel Rule compliance record for a transaction."""

    __tablename__ = "travel_rule_records"

    id = Column(String, primary_key=True, default=lambda: secrets.token_urlsafe(32))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    investigation_id = Column(String, nullable=True, index=True)

    # Transaction details
    chain = Column(String, nullable=False)
    tx_hash = Column(String, nullable=False, index=True)
    from_address = Column(String, nullable=False, index=True)
    to_address = Column(String, nullable=False, index=True)
    amount = Column(String, nullable=False)  # String to avoid precision loss
    amount_usd = Column(Float, nullable=True)
    currency = Column(String, default="ETH")
    timestamp = Column(DateTime(timezone=True), nullable=False)

    # Originator info (sender VASP)
    originator_vasp_name = Column(String, nullable=True)
    originator_vasp_id = Column(String, nullable=True)  # LEI or registration
    originator_name = Column(String, nullable=True)
    originator_account = Column(String, nullable=True)
    originator_address = Column(Text, nullable=True)
    originator_date_of_birth = Column(String, nullable=True)
    originator_national_id = Column(String, nullable=True)

    # Beneficiary info (receiver VASP)
    beneficiary_vasp_name = Column(String, nullable=True)
    beneficiary_vasp_id = Column(String, nullable=True)
    beneficiary_name = Column(String, nullable=True)
    beneficiary_account = Column(String, nullable=True)

    # Compliance status
    status = Column(SAEnum(TravelRuleStatus), default=TravelRuleStatus.PENDING, nullable=False)
    compliance_score = Column(Float, default=0.0)  # 0-100
    missing_fields = Column(JSON, default=list)  # List of missing required fields
    notes = Column(Text, nullable=True)

    # Threshold
    threshold_usd = Column(Float, default=1000.0)
    below_threshold = Column(Boolean, default=False)

    # VASP classification
    originator_vasp_type = Column(SAEnum(VASPClassification), default=VASPClassification.UNKNOWN)
    beneficiary_vasp_type = Column(SAEnum(VASPClassification), default=VASPClassification.UNKNOWN)

    # Audit trail
    checked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_travel_rule_org_status", "organization_id", "status"),
        Index("ix_travel_rule_tx", "tx_hash", "chain"),
    )


class ComplianceConfig(Base):
    """Organization-level compliance configuration."""

    __tablename__ = "compliance_config"

    id = Column(String, primary_key=True, default=lambda: secrets.token_urlsafe(32))
    organization_id = Column(String, ForeignKey("organizations.id"), unique=True, nullable=False)

    # Travel Rule settings
    travel_rule_enabled = Column(Boolean, default=True)
    travel_rule_threshold_usd = Column(Float, default=1000.0)
    auto_check_enabled = Column(Boolean, default=True)

    # Jurisdiction
    jurisdiction = Column(String, default="US")  # ISO country code
    regulatory_framework = Column(String, default="FATF")  # FATF, EU, MAS, etc.

    # Sanctions screening
    sanctions_screening_enabled = Column(Boolean, default=True)
    sanctions_auto_block = Column(Boolean, default=False)

    # Audit settings
    audit_retention_days = Column(Integer, default=2555)  # ~7 years
    immutable_audit_log = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
