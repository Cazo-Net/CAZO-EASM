from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    priority: str = "normal"
    data: Optional[Dict[str, Any]] = None
    read: bool
    email_sent: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
    total: int
