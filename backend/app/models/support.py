"""Support chat models — conversations and messages between users and the CAZO team.

A conversation belongs either to a signed-in user (``user_id`` set) or to a
website visitor (``user_id`` is NULL and the ``guest_*`` columns are set). A
visitor proves ownership with a random token; only its SHA-256 hash is stored.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, false
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SupportConversation(Base):
    __tablename__ = "support_conversations"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    # Organization the user belonged to when the conversation started (context
    # for the support team; access is always checked against user_id).
    organization_id = Column(String(36), nullable=True, index=True)
    guest_name = Column(String(120), nullable=True)
    guest_email = Column(String(255), nullable=True, index=True)
    guest_token_hash = Column(String(64), nullable=True, index=True)
    subject = Column(String(255), default="Support Request")
    status = Column(String(20), default="open", index=True)  # open | closed
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    messages = relationship("SupportMessage", back_populates="conversation", order_by="SupportMessage.created_at")


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    conversation_id = Column(
        String(36),
        ForeignKey("support_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type = Column(String(10), nullable=False)  # "user" | "admin"
    sender_id = Column(String(36), nullable=False)
    # Who on the team replied (admin sign-in email). Never sent to customers.
    sender_name = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, server_default=false())
    # When the recipient was emailed about this message (team replies only).
    notified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    conversation = relationship("SupportConversation", back_populates="messages")
