from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TagCreate(BaseModel):
    name: str
    color: str = "#3B82F6"


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class AssetTagCreate(BaseModel):
    tag_id: str


class AssetTagResponse(BaseModel):
    id: str
    tag_id: str
    asset_type: str
    asset_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    details: str = "{}"
    ip_address: Optional[str] = None
    created_at: datetime
    user_name: Optional[str] = None

    class Config:
        from_attributes = True


class FavoriteResponse(BaseModel):
    id: str
    user_id: str
    asset_type: str
    asset_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class FavoriteCreate(BaseModel):
    asset_type: str
    asset_id: str
