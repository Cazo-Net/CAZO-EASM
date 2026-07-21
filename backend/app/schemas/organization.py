from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.utils.validators import sanitize_input, sanitize_slug


class OrganizationCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    plan: str = "free"
    settings: Optional[Dict[str, Any]] = None
    billing_email: Optional[str] = None
    tax_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = sanitize_input(v)
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return sanitize_slug(v)


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    plan: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    billing_email: Optional[str] = None
    tax_id: Optional[str] = None
    invoice_prefix: Optional[str] = None
    mfa_enforced: Optional[bool] = None
    allowed_email_domains: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = sanitize_input(v)
            if len(v) < 2:
                raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return sanitize_slug(v)
        return v


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    settings: Optional[Dict[str, Any]] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    billing_email: Optional[str] = None
    tax_id: Optional[str] = None
    invoice_prefix: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    mfa_enforced: bool = False
    allowed_email_domains: Optional[List[str]] = None
    is_active: bool = True
    is_archived: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationMemberResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationMemberRoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed_roles = ["owner", "admin", "billing_admin", "security_manager", "analyst", "viewer"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class OrganizationStatsResponse(BaseModel):
    member_count: int
    project_count: int
    scan_count: int
    active_scan_count: int
    asset_count: int
    invitation_count: int
    role_distribution: Dict[str, int]
    plan: str
    is_active: bool
    created_at: datetime


class OrganizationActivityResponse(BaseModel):
    events: List[Dict[str, Any]]
    total: int
