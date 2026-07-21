from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class FindingStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    ACCEPTED_RISK = "accepted_risk"


class EvidenceType(str, Enum):
    SCREENSHOT = "screenshot"
    CURL = "curl"
    HTTP_RESPONSE = "http_response"
    PORT_SCAN = "port_scan"
    CERT = "cert"
    DNS = "dns"
    NOTE = "note"
    MANUAL = "manual"


class FindingHistoryEntry(BaseModel):
    id: str
    vulnerability_id: str
    organization_id: str
    actor_id: Optional[str] = None
    action: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FindingEvidenceItem(BaseModel):
    id: str
    vulnerability_id: str
    organization_id: str
    evidence_type: str
    content: Optional[str] = None
    captured_by: Optional[str] = None
    scanner_id: Optional[str] = None
    captured_at: datetime

    class Config:
        from_attributes = True


class VulnerabilityResponse(BaseModel):
    id: str
    scan_id: str
    subdomain_id: Optional[str] = None
    template_id: str
    name: str
    severity: str
    vuln_type: Optional[str] = None
    host: str
    matched_at: Optional[str] = None
    description: Optional[str] = None
    reference: List[str] = []
    tags: List[str] = []
    curl_command: Optional[str] = None
    extracted_results: List[str] = []
    found_at: datetime

    # Evidence Center fields
    status: str = "open"
    fingerprint: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    organization_id: Optional[str] = None
    asset_id: Optional[str] = None
    assigned_to: Optional[str] = None

    @field_validator("reference", "tags", "extracted_results", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        return v or []

    class Config:
        from_attributes = True


class FindingDetailResponse(VulnerabilityResponse):
    history: List[FindingHistoryEntry] = []
    evidence: List[FindingEvidenceItem] = []
    # confirming scans: group of (scan_id, found_at) for same fingerprint
    confirming_scans: List[Dict[str, Any]] = []


class FindingUpdateRequest(BaseModel):
    status: Optional[FindingStatus] = None
    assigned_to: Optional[str] = None
    note: Optional[str] = Field(None, description="Optional note recorded in history")


class FindingHistoryAddRequest(BaseModel):
    action: str = Field("note", description="Custom action label")
    note: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class FindingEvidenceAddRequest(BaseModel):
    evidence_type: EvidenceType
    content: str
    scanner_id: Optional[str] = None


class FindingSummaryResponse(BaseModel):
    total: int
    by_status: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    new_count: int = 0
    stale_count: int = 0


class FindingListResponse(BaseModel):
    findings: List[VulnerabilityResponse]
    total: int
