from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
    total: int
