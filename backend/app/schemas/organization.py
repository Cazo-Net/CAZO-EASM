from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from app.utils.validators import sanitize_input, sanitize_slug


class OrganizationCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    plan: str = "free"
    settings: Optional[Dict[str, Any]] = None

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
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
