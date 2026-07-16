"""Pydantic schemas for the Exposure Replay feature."""
from typing import List, Optional
from pydantic import BaseModel, Field


class ReplayAssetSummary(BaseModel):
    """Lightweight asset view used by the replay diff engine."""

    id: str
    hostname: str
    ip_addresses: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    exposure_score: int = 0


class ReplaySnapshot(BaseModel):
    """A single completed scan snapshot for an organization."""

    scan_id: str
    domain: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    subdomain_count: int = 0
    port_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    overall_risk_score: Optional[int] = None
    assets: List[ReplayAssetSummary] = Field(default_factory=list)


class ReplayTimelineResponse(BaseModel):
    organization_id: str
    snapshots: List[ReplaySnapshot] = Field(default_factory=list)


class ReplayChangeItem(BaseModel):
    """A single added / removed / modified asset based on AssetChange records."""

    id: str
    change_type: str  # added | removed | modified
    entity_type: str
    entity_key: str
    detail: dict = Field(default_factory=dict)


class ReplayChangesResponse(BaseModel):
    from_scan_id: Optional[str] = None
    to_scan_id: Optional[str] = None
    added: List[ReplayChangeItem] = Field(default_factory=list)
    removed: List[ReplayChangeItem] = Field(default_factory=list)
    modified: List[ReplayChangeItem] = Field(default_factory=list)
    summary: str = ""


class ReplayExposureResponse(BaseModel):
    """Exposure metrics for a single scan."""

    scan_id: str
    domain: str
    completed_at: Optional[str] = None
    total_assets: int = 0
    subdomain_count: int = 0
    port_count: int = 0
    certificate_count: int = 0
    technology_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    overall_risk_score: Optional[int] = None
    risk_breakdown: dict = Field(default_factory=dict)
