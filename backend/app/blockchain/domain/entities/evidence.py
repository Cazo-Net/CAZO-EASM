from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EvidenceType(str, Enum):
    EXCHANGE_TAG = "exchange_tag"
    BLOCKCHAIN_LABEL = "blockchain_label"
    VERIFIED_CONTRACT = "verified_contract"
    KNOWN_PUBLIC_WALLET = "known_public_wallet"
    SANCTIONS_LIST = "sanctions_list"
    BLACKLIST = "blacklist"
    PUBLIC_REPORT = "public_report"
    OSINT = "osint"
    DARKWEB = "darkweb"
    BREACH = "breach"
    FORUM = "forum"
    HEURISTIC = "heuristic"
    CLUSTERING = "clustering"
    THREAT_INTEL = "threat_intel"
    HUMAN_REVIEW = "human_review"
    NETWORK_ANALYSIS = "network_analysis"
    MEMPOOL_ANALYSIS = "mempool_analysis"


@dataclass
class Evidence:
    source: str
    type: EvidenceType = EvidenceType.BLOCKCHAIN_LABEL
    confidence: int = 0
    timestamp: datetime | None = None
    reason: str = ""
    url: str | None = None

    def __post_init__(self) -> None:
        if self.confidence < 0 or self.confidence > 100:
            raise ValueError(f"Confidence must be 0-100: {self.confidence}")
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "type": self.type.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "reason": self.reason,
            "url": self.url,
        }


@dataclass
class EntityAttribution:
    entity_name: str | None = None
    confidence: int = 0
    evidence: list[Evidence] = field(default_factory=list)
    last_updated: datetime | None = None

    def __post_init__(self) -> None:
        if self.last_updated is None:
            self.last_updated = datetime.now()
