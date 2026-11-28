"""Blockchain Intelligence — consolidated Pydantic schemas.

Single source of truth for all blockchain data models.
Phase 2 additions: clustering, bridge tracking, graph, ML, monitoring, cases.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

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


class RiskBand(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class EntityCategory(str, Enum):
    EXCHANGE = "exchange"
    DEFI_PROTOCOL = "defi_protocol"
    STABLECOIN_ISSUER = "stablecoin_issuer"
    SANCTIONS = "sanctions"
    KNOWN_SCAM = "known_scam"
    MIXING_SERVICE = "mixing_service"
    MINING_POOL = "mining_pool"
    BRIDGE = "bridge"
    MARKET_MAKER = "market_maker"
    WALLET_PROVIDER = "wallet_provider"
    OTHER = "other"
    UNKNOWN = "unknown"


class ClusterHeuristicType(str, Enum):
    COMMON_INPUT = "common_input"
    CHANGE_ADDRESS = "change_address"
    SHARED_FUNDING = "shared_funding"
    DEPLOYER_REUSE = "deployer_reuse"
    GAS_PAYER = "gas_payer"
    PEELING_CHAIN = "peeling_chain"


class BridgeType(str, Enum):
    LOCK_AND_MINT = "lock_and_mint"
    BURN_AND_MINT = "burn_and_mint"


class AlertType(str, Enum):
    NEW_TRANSACTION = "new_transaction"
    HIGH_RISK_COUNTERPARTY = "high_risk_counterparty"
    RISK_THRESHOLD = "risk_threshold"
    LARGE_TRANSFER = "large_transfer"
    SANCTIONS_MATCH = "sanctions_match"


class CaseStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    CLOSED = "closed"


class CaseMemberRole(str, Enum):
    OWNER = "owner"
    ANALYST = "analyst"
    VIEWER = "viewer"


# ── Core Evidence & Attribution ──────────────────────────────────────────────

class Evidence(BaseModel):
    source: str
    type: EvidenceType = EvidenceType.BLOCKCHAIN_LABEL
    confidence: int = Field(default=0, ge=0, le=100)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    url: str | None = None


class EntityAttribution(BaseModel):
    entity_name: str | None = None
    category: EntityCategory = EntityCategory.UNKNOWN
    confidence: int = Field(default=0, ge=0, le=100)
    evidence: list[Evidence] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Wallet & Transaction Models ─────────────────────────────────────────────

class WalletSummary(BaseModel):
    address: str
    chain: Chain
    wallet_type: WalletType = WalletType.UNKNOWN
    balance: str = "0"
    balance_usd: float | None = None
    token_count: int = 0
    nft_count: int = 0
    # None when the data source cannot give an exact lifetime count; the UI
    # then shows "—" rather than a partial or guessed number.
    tx_count: int | None = None
    first_seen: datetime | None = None
    last_active: datetime | None = None
    inbound_volume: str = "0"
    outbound_volume: str = "0"
    net_flow: str = "0"
    labels: list[str] = Field(default_factory=list)
    risk_score: int | None = None
    risk_band: RiskBand | None = None
    entity_attribution: EntityAttribution | None = None


class TokenBalance(BaseModel):
    contract_address: str
    symbol: str
    name: str
    balance: str
    decimals: int = 18
    usd_value: float | None = None


class TransactionSummary(BaseModel):
    hash: str
    chain: Chain
    status: TransactionStatus = TransactionStatus.PENDING
    block_number: int | None = None
    timestamp: datetime | None = None
    from_address: str = ""
    to_address: str = ""
    value: str = "0"
    fee: str | None = None
    token_symbol: str | None = None
    method: str | None = None


class TransactionDetail(TransactionSummary):
    gas_price: str | None = None
    gas_used: int | None = None
    nonce: int | None = None
    input_data: str = "0x"
    internal_transfers: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[dict[str, Any]] = Field(default_factory=list)
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
    name: str = ""
    symbol: str = ""
    total_supply: str | None = None
    implementation: str | None = None


# ── Risk Models ──────────────────────────────────────────────────────────────

class RiskFactor(BaseModel):
    category: str
    label: str
    weight: float = 1.0
    contribution: int = 0
    evidence: list[Evidence] = Field(default_factory=list)


class RiskScore(BaseModel):
    address: str
    chain: Chain
    score: int = Field(default=0, ge=0, le=100)
    band: RiskBand = RiskBand.UNKNOWN
    factors: list[RiskFactor] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Phase 2: ML anomaly score (independent of rule-based score)
    anomaly_score: float | None = None
    anomaly_explanation: dict[str, float] | None = None
    model_version: str | None = None


# ── Graph Models ─────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    label: str = ""
    chain: Chain
    wallet_type: WalletType = WalletType.UNKNOWN
    balance: str = "0"
    risk_band: RiskBand = RiskBand.UNKNOWN
    entity_name: str | None = None
    tx_count: int = 0
    # Phase 2: community and centrality
    community_id: int | None = None
    centrality_score: float | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    value: str = "0"
    tx_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    weight: float = 1.0


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_volume: str = "0"
    hop_count: int = 0


class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    tx_hash: str | None = None
    address: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Clustering Models (8.1) ─────────────────────────────────────────────────

class ClusteringHeuristic(BaseModel):
    type: ClusterHeuristicType
    confidence: float = Field(default=0, ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    description: str = ""


class AddressCluster(BaseModel):
    id: str | None = None
    chain: Chain
    addresses: list[str] = Field(default_factory=list)
    heuristics: list[ClusteringHeuristic] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Bridge Tracking Models (8.2) ────────────────────────────────────────────

class BridgeContract(BaseModel):
    source_chain: Chain
    dest_chain: Chain
    contract_address: str
    bridge_type: BridgeType
    name: str = ""
    is_active: bool = True
    confidence: int = Field(default=100, ge=0, le=100)


class BridgeHop(BaseModel):
    source_chain: Chain
    source_tx: str
    bridge_contract: str
    dest_chain: Chain
    dest_tx: str | None = None
    amount: str = "0"
    confidence: float = Field(default=0, ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    timestamp: datetime | None = None


# ── Monitoring Models (8.5) ─────────────────────────────────────────────────

class BlockchainWatch(BaseModel):
    id: str | None = None
    org_id: str
    user_id: str
    address: str
    chain: Chain
    alert_on_new_tx: bool = True
    alert_on_risk_change: bool = True
    risk_threshold: int | None = None
    webhook_url: str | None = None
    email_alert: bool = False
    is_active: bool = True
    last_checked_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BlockchainAlert(BaseModel):
    id: str | None = None
    watch_id: str
    org_id: str
    user_id: str
    address: str
    chain: Chain
    alert_type: AlertType
    title: str
    message: str
    severity: str = "info"
    evidence: list[Evidence] = Field(default_factory=list)
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Case Management Models (8.7) ────────────────────────────────────────────

class CaseAnnotation(BaseModel):
    id: str | None = None
    case_id: str
    entity_type: str
    entity_id: str
    content: str
    author_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CaseMember(BaseModel):
    case_id: str
    user_id: str
    role: CaseMemberRole = CaseMemberRole.ANALYST
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    added_by: str | None = None


class CaseRecord(BaseModel):
    id: str | None = None
    org_id: str
    title: str
    description: str = ""
    status: CaseStatus = CaseStatus.OPEN
    created_by: str
    assigned_to: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CaseAuditEntry(BaseModel):
    id: str | None = None
    case_id: str
    user_id: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Report Models ────────────────────────────────────────────────────────────

class ReportSection(BaseModel):
    title: str
    content: str
    evidence: list[Evidence] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    id: str | None = None
    title: str
    addresses: list[str] = Field(default_factory=list)
    chain: Chain
    sections: list[ReportSection] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    evidence_count: int = 0
    risk_summary: dict[str, Any] = Field(default_factory=dict)


# ── Search & Pagination ─────────────────────────────────────────────────────

class SearchResult(BaseModel):
    type: str
    value: str
    chain: str = ""
    label: str = ""
    description: str = ""


class PaginatedResponse(BaseModel):
    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False


# ── Copilot Models (8.6) ────────────────────────────────────────────────────

class CopilotQuery(BaseModel):
    question: str
    address: str
    chain: Chain = Chain.ETHEREUM


class CopilotResponse(BaseModel):
    answer: str
    evidence: list[Evidence] = Field(default_factory=list)
    query_used: str = ""
    confidence: float = 0.0
