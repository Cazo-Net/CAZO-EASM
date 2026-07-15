from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.utils.validators import sanitize_input


class APIKeyCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = sanitize_input(v)
        if len(v) < 1:
            raise ValueError("Name cannot be empty")
        return v


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key: Optional[str] = None
    created_at: datetime
    last_used: Optional[datetime] = None

    class Config:
        from_attributes = True
