from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ShadowSignal(BaseModel):
    type: str  # shared_ip | shared_cert | shared_asn
    with_: List[str] = Field(default_factory=list, alias="with")
    cloud: Optional[bool] = None

    class Config:
        populate_by_name = True


class ShadowCandidate(BaseModel):
    asset_id: str
    value: str
    label: Optional[str] = None
    first_seen: Optional[str] = None
    confidence: int
    signals: List[ShadowSignal] = []
    inventory_status: Optional[str] = None

    class Config:
        populate_by_name = True


class ShadowReviewRequest(BaseModel):
    action: str = Field(..., description="confirm | reject | investigate")
    note: Optional[str] = None


class ShadowReviewResponse(BaseModel):
    asset_id: str
    inventory_status: str
    confirmed: bool

    class Config:
        from_attributes = True


class ShadowListResponse(BaseModel):
    shadows: List[ShadowCandidate]
    total: int
    # Known-asset inventory summary for context
    known_count: int
    discovered_count: int
