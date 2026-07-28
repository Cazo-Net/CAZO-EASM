from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class AlertSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"


class AlertCategory(str, Enum):
    HIGH_VALUE_TX = "high_value_tx"
    CONTRACT_CREATION = "contract_creation"
    FIRST_INTERACTION = "first_interaction"
    KNOWN_MIXER = "known_mixer"
    HIGH_RISK_COUNTERPARTY = "high_risk_counterparty"
    RAPID_TX = "rapid_tx"
    LARGE_BALANCE_CHANGE = "large_balance_change"
    SANCTIONS_MATCH = "sanctions_match"
    CUSTOM = "custom"


@dataclass
class AlertRule:
    name: str
    category: AlertCategory
    severity: AlertSeverity
    condition: dict[str, Any]
    cooldown_minutes: int = 60
    enabled: bool = True
    description: str = ""

    def matches_transaction(self, tx: Any) -> bool:
        if not self.enabled:
            return False
        cond = self.condition

        tx_native = tx.value.to_native().value if tx.value else None

        if cond.get("min_value") is not None:
            if tx_native is None or tx_native < Decimal(str(cond["min_value"])):
                return False

        if cond.get("max_value") is not None:
            if tx_native is None or tx_native > Decimal(str(cond["max_value"])):
                return False

        if cond.get("is_contract_creation") is not None:
            if tx.is_contract_creation != cond["is_contract_creation"]:
                return False

        if cond.get("method") is not None:
            if tx.method != cond["method"]:
                return False

        if cond.get("from_in") is not None:
            if tx.from_address not in cond["from_in"]:
                return False

        if cond.get("to_in") is not None:
            if tx.to_address not in cond["to_in"]:
                return False

        if cond.get("status") is not None:
            if tx.status.value != cond["status"]:
                return False

        return True


@dataclass
class Alert:
    id: str
    rule_name: str
    category: AlertCategory
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.TRIGGERED
    chain: str = ""
    address: str = ""
    tx_hash: str = ""
    title: str = ""
    message: str = ""
    value: str = ""
    evidence: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    org_id: str = ""
    watch_id: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "category": self.category.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "chain": self.chain,
            "address": self.address,
            "tx_hash": self.tx_hash,
            "title": self.title,
            "message": self.message,
            "value": self.value,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "org_id": self.org_id,
            "watch_id": self.watch_id,
        }


# ── Built-in Rules ──────────────────────────────────────────────────────────

BUILT_IN_RULES: list[AlertRule] = [
    AlertRule(
        name="High Value Transaction",
        category=AlertCategory.HIGH_VALUE_TX,
        severity=AlertSeverity.HIGH,
        description="Alert on transactions exceeding 100 ETH equivalent",
        condition={"min_value": 100.0},
    ),
    AlertRule(
        name="Contract Creation",
        category=AlertCategory.CONTRACT_CREATION,
        severity=AlertSeverity.MEDIUM,
        description="Alert when a new contract is created",
        condition={"is_contract_creation": True},
    ),
    AlertRule(
        name="Failed Transaction",
        category=AlertCategory.CUSTOM,
        severity=AlertSeverity.LOW,
        description="Alert on failed transactions",
        condition={"status": "failed"},
    ),
]

# Known mixer/tumbler addresses (short list; full list in labels/curated)
KNOWN_MIXER_ADDRESSES: set[str] = {
    "0x23773e65ed146a459791799d01336db55f2dcf88",  # example
}

MIXER_RULE = AlertRule(
    name="Known Mixer Interaction",
    category=AlertCategory.KNOWN_MIXER,
    severity=AlertSeverity.CRITICAL,
    description="Alert when interacting with a known mixer/tumbler",
    condition={"from_in": list(KNOWN_MIXER_ADDRESSES), "to_in": list(KNOWN_MIXER_ADDRESSES)},
)
