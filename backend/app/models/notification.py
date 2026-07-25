from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, Text, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "read"),
        Index("ix_notifications_user_type", "user_id", "type"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_org_type", "organization_id", "type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    related_entity_type = Column(String(50), nullable=True, index=True)
    related_entity_id = Column(String(36), nullable=True)
    priority = Column(String(20), nullable=False, default="normal")
    channel = Column(String(20), nullable=False, default="in_app")
    data = Column(JSON, default=dict)
    read = Column(Boolean, default=False, index=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
