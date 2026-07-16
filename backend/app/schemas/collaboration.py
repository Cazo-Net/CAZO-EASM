"""Pydantic schemas for team collaboration (asset comments)."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[str] = None


class CommentReply(BaseModel):
    id: str
    organization_id: str
    asset_id: str
    user_id: str
    author_email: Optional[str] = None
    author_name: Optional[str] = None
    content: str
    parent_id: Optional[str] = None
    created_at: Optional[datetime] = None


class CommentOut(BaseModel):
    id: str
    organization_id: str
    asset_id: str
    user_id: str
    author_email: Optional[str] = None
    author_name: Optional[str] = None
    content: str
    parent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    replies: list[CommentReply] = []

    model_config = {"from_attributes": True}


class CommentDeleted(BaseModel):
    message: str
    id: str
