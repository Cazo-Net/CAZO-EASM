from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from app.utils.validators import validate_domain


class ScanTypeEnum(str, Enum):
    FULL = "full"
    QUICK = "quick"
    CUSTOM = "custom"


class ScanOptions(BaseModel):
    scan_size: str = "large"
    max_subdomains: int = 0
    port_mode: str = "full"
    include_nuclei: bool = True
    subdomain_tools: List[str] = ["default", "subfinder", "amass"]


class ScanCreate(BaseModel):
    domain: str
    scan_type: ScanTypeEnum = ScanTypeEnum.FULL
    scan_options: Optional[ScanOptions] = None
    project_id: Optional[str] = None

    @field_validator("domain")
    @classmethod
    def validate_domain_field(cls, v: str) -> str:
        if not validate_domain(v):
            raise ValueError(f"Invalid domain format: {v}")
        return v.lower().strip()


class ScanResponse(BaseModel):
    id: str
    domain: str
    status: str
    progress: int
    scan_type: str
    scan_options: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScanDetail(ScanResponse):
    subdomains_count: int = 0
    ports_count: int = 0
    vulnerabilities_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    risk_score: Optional[int] = None
    error_message: Optional[str] = None
    scanner_status: Optional[Dict[str, str]] = None


class SubdomainResponse(BaseModel):
    id: str
    hostname: str
    ip_addresses: List[str]
    is_alive: bool
    discovered_at: datetime

    class Config:
        from_attributes = True


class PortResponse(BaseModel):
    id: str
    port_number: int
    state: str
    service: Optional[str] = None
    version: Optional[str] = None
    banner: Optional[str] = None
    scanned_at: datetime

    class Config:
        from_attributes = True


class DNSRecordResponse(BaseModel):
    id: str
    record_type: str
    value: str
    ttl: Optional[int] = None

    class Config:
        from_attributes = True


class SSLResponse(BaseModel):
    id: str
    issuer: Optional[str] = None
    subject: Optional[str] = None
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None
    is_valid: bool
    grade: Optional[str] = None
    protocol: Optional[str] = None
    cipher_suite: Optional[str] = None
    scanned_at: datetime

    class Config:
        from_attributes = True


class WhoisResponse(BaseModel):
    id: str
    domain: str
    registrar: Optional[str] = None
    creation_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    name_servers: List[str]
    registrant_name: Optional[str] = None
    registrant_org: Optional[str] = None
    registrant_country: Optional[str] = None
    scanned_at: datetime

    class Config:
        from_attributes = True


class TechnologyResponse(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    version: Optional[str] = None
    confidence: int
    detected_at: datetime

    class Config:
        from_attributes = True


class RiskScoreResponse(BaseModel):
    id: str
    overall_score: int
    breakdown: Dict[str, int]
    factors: List[str]
    calculated_at: datetime

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

    class Config:
        from_attributes = True
