from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class Asset360Score(BaseModel):
    health_score: Optional[float] = None
    exposure_score: Optional[float] = None
    health_factors: Optional[List[Any]] = None
    exposure_factors: Optional[List[Any]] = None
    scored_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Asset360Relationship(BaseModel):
    id: str
    relationship_type: str
    direction: str  # outgoing | incoming
    related_asset_id: str
    related_asset_label: Optional[str] = None
    related_asset_type: Optional[str] = None
    last_seen: Optional[datetime] = None


class Asset360Change(BaseModel):
    id: str
    change_type: str
    entity_type: str
    entity_key: str
    detail: Optional[Dict[str, Any]] = None
    detected_at: Optional[datetime] = None


class Asset360Counts(BaseModel):
    subdomains: int = 0
    ports: int = 0
    vulnerabilities: int = 0
    relationships: int = 0


class Asset360Summary(BaseModel):
    id: str
    organization_id: str
    asset_type: str
    value: str
    label: Optional[str] = None
    is_alive: bool
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class Asset360Response(BaseModel):
    asset: Asset360Summary
    score: Optional[Asset360Score] = None
    relationships: List[Asset360Relationship] = []
    changes: List[Asset360Change] = []
    counts: Asset360Counts
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


class Asset360ListItem(BaseModel):
    id: str
    asset_type: str
    value: str
    label: Optional[str] = None
    is_alive: bool
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True
