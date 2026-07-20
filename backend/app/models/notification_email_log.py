from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base
import uuid


class NotificationEmailLog(Base):
    """Tracks emails sent for notifications — deduplication + audit trail.

    One email per notification (enforced by UNIQUE on notification_id).
    Stores the provider message ID for delivery tracking.
    """
    __tablename__ = "notification_email_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    notification_id = Column(String(36), ForeignKey("notifications.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    email_type = Column(String(50), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    resend_id = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("notification_id", name="uq_email_log_notification"),
    )
