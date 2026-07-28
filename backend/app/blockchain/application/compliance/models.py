from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any


class VASPStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    UNVERIFIED = "unverified"


class TravelRuleStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class ComplianceCaseStatus(str, Enum):
    OPEN = "open"
    PENDING_INFO = "pending_info"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


@dataclass
class VASP:
    id: str
    name: str
    legal_name: str
    jurisdiction: str
    registration_number: str = ""
    website: str = ""
    api_endpoint: str = ""
    public_key: str = ""
    addresses: list[str] = field(default_factory=list)
    chains: list[str] = field(default_factory=list)
    status: VASPStatus = VASPStatus.UNVERIFIED
    verified_at: datetime | None = None
    risk_score: int = 0
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "legal_name": self.legal_name,
            "jurisdiction": self.jurisdiction,
            "registration_number": self.registration_number,
            "website": self.website,
            "api_endpoint": self.api_endpoint,
            "address_count": len(self.addresses),
            "chains": self.chains,
            "status": self.status.value,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "risk_score": self.risk_score,
        }


@dataclass
class TravelRuleMessage:
    id: str
    case_id: str
    sender_vasp_id: str
    receiver_vasp_id: str
    tx_hash: str
    chain: str
    originator_address: str
    beneficiary_address: str
    value: str
    asset: str = ""
    originator_name: str = ""
    originator_legal_id: str = ""
    beneficiary_name: str = ""
    beneficiary_legal_id: str = ""
    status: TravelRuleStatus = TravelRuleStatus.PENDING
    payload: str = ""
    response_payload: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "sender_vasp_id": self.sender_vasp_id,
            "receiver_vasp_id": self.receiver_vasp_id,
            "tx_hash": self.tx_hash,
            "chain": self.chain,
            "originator_address": self.originator_address,
            "beneficiary_address": self.beneficiary_address,
            "value": self.value,
            "asset": self.asset,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


@dataclass
class ComplianceCase:
    id: str
    tx_hash: str
    chain: str
    originator_address: str
    beneficiary_address: str
    value: str
    asset: str = ""
    originator_vasp_id: str | None = None
    beneficiary_vasp_id: str | None = None
    status: ComplianceCaseStatus = ComplianceCaseStatus.OPEN
    risk_score: int = 0
    notes: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
    resolved_at: datetime | None = None
    assigned_to: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tx_hash": self.tx_hash,
            "chain": self.chain,
            "originator_address": self.originator_address,
            "beneficiary_address": self.beneficiary_address,
            "value": self.value,
            "asset": self.asset,
            "originator_vasp_id": self.originator_vasp_id,
            "beneficiary_vasp_id": self.beneficiary_vasp_id,
            "status": self.status.value,
            "risk_score": self.risk_score,
            "notes_count": len(self.notes),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "assigned_to": self.assigned_to,
        }


@dataclass
class CARFReport:
    id: str
    year: int
    quarter: int
    vasp_id: str
    jurisdiction: str
    total_transactions: int = 0
    total_value: str = "0"
    transactions: list[dict] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    filed: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "year": self.year,
            "quarter": self.quarter,
            "vasp_id": self.vasp_id,
            "jurisdiction": self.jurisdiction,
            "total_transactions": self.total_transactions,
            "total_value": self.total_value,
            "generated_at": self.generated_at.isoformat(),
            "filed": self.filed,
        }
