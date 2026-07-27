"""Dark Web Intelligence — domain models.

Core data types for dark web monitoring, onion service analysis,
marketplace intelligence, and credential exposure tracking.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DarkWebSource(str, Enum):
    """Dark web data sources."""
    TOR_SEARCH = "tor_search"
    ONION_CRAWL = "onion_crawl"
    MARKETPLACE = "marketplace"
    FORUM = "forum"
    PASTE_SITE = "paste_site"
    TELEGRAM = "telegram"
    IRC = "irc"
    FEED = "feed"


class ContentType(str, Enum):
    """Types of content found on dark web."""
    CREDENTIAL = "credential"
    DATA_DUMP = "data_dump"
    MALWARE = "malware"
    EXPLOIT = "exploit"
    MARKETPLACE_LISTING = "marketplace_listing"
    FORUM_POST = "forum_post"
    ANNOUNCEMENT = "announcement"
    CONTACT = "contact"
    OTHER = "other"


class ThreatLevel(str, Enum):
    """Threat severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MonitoringStatus(str, Enum):
    """Status of a monitoring target."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class DarkWebMention(BaseModel):
    """A single mention or finding from the dark web."""
    id: str = Field(..., description="Unique mention ID")
    source: DarkWebSource
    source_url: str = Field(..., description="Onion or clearnet URL of the mention")
    content_type: ContentType
    title: str = ""
    summary: str = ""
    raw_content: str = ""
    discovered_at: datetime
    indexed_at: datetime | None = None
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list, description="Extracted entities (emails, domains, IPs)")
    threat_level: ThreatLevel = ThreatLevel.INFO
    confidence: int = Field(default=0, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OnionService(BaseModel):
    """A .onion service that has been discovered or is being monitored."""
    address: str = Field(..., description="v2/v3 onion address")
    url: str = Field(..., description="Full .onion URL")
    title: str = ""
    description: str = ""
    first_seen: datetime
    last_seen: datetime | None = None
    is_live: bool = True
    port: int = Field(default=80, description="Primary port")
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    hosting_provider: str | None = None
    associated_entities: list[str] = Field(default_factory=list)
    risk_level: ThreatLevel = ThreatLevel.INFO


class CredentialExposure(BaseModel):
    """Credential exposure event — email/password found on dark web."""
    id: str
    email: str
    domain: str | None = None
    password_hash: str | None = None
    password_plaintext: bool = False
    source: DarkWebSource
    source_url: str
    discovered_at: datetime
    breach_name: str = ""
    breach_date: datetime | None = None
    record_count: int | None = None
    data_classes: list[str] = Field(default_factory=list)
    verified: bool = False
    threat_level: ThreatLevel = ThreatLevel.HIGH


class ThreatActor(BaseModel):
    """A threat actor profile discovered through dark web intelligence."""
    id: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    motivation: str = ""
    ttps: list[str] = Field(default_factory=list, description="MITRE ATT&CK TTPs")
    associated_campaigns: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    first_seen: datetime
    last_active: datetime | None = None
    confidence: int = Field(default=0, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MonitoringTarget(BaseModel):
    """A target being monitored on the dark web."""
    id: str
    query: str = Field(..., description="Search query or entity to monitor")
    entity_type: str = Field(..., description="domain, email, brand, etc.")
    sources: list[DarkWebSource] = Field(default_factory=list)
    status: MonitoringStatus = MonitoringStatus.ACTIVE
    created_at: datetime
    last_scan: datetime | None = None
    mention_count: int = 0
    latest_mentions: list[DarkWebMention] = Field(default_factory=list)


class DarkWebReport(BaseModel):
    """Aggregated dark web intelligence report."""
    id: str
    title: str
    generated_at: datetime
    period_start: datetime | None = None
    period_end: datetime | None = None
    summary: str = ""
    total_mentions: int = 0
    mentions_by_source: dict[str, int] = Field(default_factory=dict)
    mentions_by_type: dict[str, int] = Field(default_factory=dict)
    mentions_by_threat_level: dict[str, int] = Field(default_factory=dict)
    top_keywords: list[tuple[str, int]] = Field(default_factory=list)
    credential_exposures: list[CredentialExposure] = Field(default_factory=list)
    onion_services: list[OnionService] = Field(default_factory=list)
    threat_actors: list[ThreatActor] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Search result from dark web query."""
    query: str
    results: list[DarkWebMention]
    total: int
    page: int = 1
    page_size: int = 20
    has_next: bool = False
