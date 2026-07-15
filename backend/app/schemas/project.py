from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.utils.validators import sanitize_input


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    organization_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = sanitize_input(v)
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return sanitize_input(v, max_length=1000)
        return v


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = sanitize_input(v)
            if len(v) < 2:
                raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return sanitize_input(v, max_length=1000)
        return v


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    organization_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
