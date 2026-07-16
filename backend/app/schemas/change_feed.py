from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class ChangeFeedItem(BaseModel):
    id: str
    change_type: str  # added | removed | modified
    entity_type: str
    entity_key: str
    detail: Optional[Dict[str, Any]] = None
    from_scan_id: Optional[str] = None
    to_scan_id: Optional[str] = None
    asset_label: Optional[str] = None
    detected_at: Optional[datetime] = None


class ChangeFeedSummary(BaseModel):
    added: int = 0
    removed: int = 0
    modified: int = 0
    total: int = 0
    since: Optional[datetime] = None
