"""Blockchain Intelligence — domain models.

Pydantic v2 schemas for all blockchain intel entities.
Every field is typed. Every model is serializable. No ORMs in domain layer.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class Chain(str, Enum):
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    BNB = "bnb"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    AVALANCHE = "avalanche"
    TRON = "tron"
    SOLANA = "solana"


class WalletType(str, Enum):
    EOA = "eoa"
    CONTRACT = "contract"
    EXCHANGE_HOT = "exchange_hot_wallet"
    UNKNOWN = "unknown"


class TransactionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


class ContractType(str, Enum):
    ERC20 = "erc20"
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    PROXY = "proxy"
    UNKNOWN = "unknown"


class EvidenceType(str, Enum):
    EXCHANGE_TAG = "exchange_tag"
    BLOCKCHAIN_LABEL = "blockchain_label"
    VERIFIED_CONTRACT = "verified_contract"
    KNOWN_PUBLIC_WALLET = "known_public_wallet"
    SANCTIONS_LIST = "sanctions_list"
    PUBLIC_REPORT = "public_report"
    OSINT = "osint"
    DARKWEB = "darkweb"
    BREACH = "breach"
    FORUM = "forum"


class RiskBand(str, Enum):
    VERY_LOW = "Very Low"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class EntityCategory(str, Enum):
    EXCHANGE = "exchange"
    STABLECOIN_ISSUER = "stablecoin_issuer"
    DEFI_PROTOCOL = "defi_protocol"
    MARKET_MAKER = "market_maker"
    WALLET_PROVIDER = "wallet_provider"
    SANCTIONS = "sanctions"
    KNOWN_SCAM = "known_scam"
    MIXING_SERVICE = "mixing_service"
    MINING_POOL = "mining_pool"
    BRIDGE = "bridge"
    OTHER = "other"


# ── Core Models ────────────────────────────────────────────────────────────

class Evidence(BaseModel):
    source: str
    type: EvidenceType
    confidence: int = Field(ge=0, le=100)
    timestamp: datetime
    reason: str
    url: str | None = None


class EntityAttribution(BaseModel):
    entity_name: str
    category: EntityCategory
    confidence: int = Field(ge=0, le=100)
    evidence: list[Evidence]
    last_updated: datetime


class WalletSummary(BaseModel):
    address: str
    chain: Chain
    wallet_type: WalletType = WalletType.UNKNOWN
    balance: str = "0"
    balance_usd: float | None = None
    token_count: int = 0
    nft_count: int = 0
    tx_count: int = 0
    first_seen: datetime | None = None
    last_active: datetime | None = None
    inbound_volume: str = "0"
    outbound_volume: str = "0"
    net_flow: str = "0"
    labels: list[str] = []
    risk_score: int | None = None
    risk_band: RiskBand | None = None
    entity_attribution: EntityAttribution | None = None


class TokenBalance(BaseModel):
    contract_address: str
    symbol: str
    name: str
    balance: str
    decimals: int
    usd_value: float | None = None


class TransactionSummary(BaseModel):
    hash: str
    chain: Chain
    status: TransactionStatus
    block_number: int | None = None
    timestamp: datetime | None = None
    from_address: str
    to_address: str
    value: str
    fee: str | None = None
    token_symbol: str | None = None
    method: str | None = None


class TransactionDetail(TransactionSummary):
    gas_price: str | None = None
    gas_used: int | None = None
    nonce: int | None = None
    input_data: str | None = None
    internal_transfers: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    decoded_method: dict[str, Any] | None = None


class ContractDetail(BaseModel):
    address: str
    chain: Chain
    creator: str | None = None
    creation_tx: str | None = None
    creation_date: datetime | None = None
    verified: bool = False
    abi: list[dict[str, Any]] | None = None
    compiler_version: str | None = None
    contract_type: ContractType = ContractType.UNKNOWN
    name: str | None = None
    symbol: str | None = None
    total_supply: str | None = None
    implementation: str | None = None


class RiskFactor(BaseModel):
    category: str
    label: str
    weight: float
    contribution: int
    evidence: list[Evidence] = []


class RiskScore(BaseModel):
    address: str
    chain: Chain
    score: int = Field(ge=0, le=100)
    band: RiskBand
    factors: list[RiskFactor]
    computed_at: datetime


class GraphNode(BaseModel):
    id: str
    label: str
    chain: Chain
    wallet_type: WalletType | None = None
    balance: str | None = None
    risk_band: RiskBand | None = None
    entity_name: str | None = None
    tx_count: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    value: str
    tx_count: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_volume: str = "0"
    hop_count: int = 0


class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    tx_hash: str | None = None
    address: str | None = None
    metadata: dict[str, Any] = {}


class ReportSection(BaseModel):
    title: str
    content: str
    evidence: list[Evidence] = []


class InvestigationReport(BaseModel):
    id: str
    title: str
    addresses: list[str]
    chain: Chain
    sections: list[ReportSection]
    created_at: datetime
    created_by: str | None = None
    evidence_count: int = 0
    risk_summary: str = ""


class SearchResult(BaseModel):
    type: str
    value: str
    chain: Chain | None = None
    label: str | None = None
    description: str | None = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 20
    has_next: bool = False
