"""Asset collaboration comments/annotations (team collaboration)."""
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, Boolean,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AssetComment(Base):
    __tablename__ = "asset_comments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    asset_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    parent_id = Column(
        String(36), ForeignKey("asset_comments.id"), nullable=True, index=True
    )
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author = relationship("User")
    replies = relationship(
        "AssetComment",
        backref=backref("parent", remote_side=[id]),
        cascade="all, delete-orphan",
    )
