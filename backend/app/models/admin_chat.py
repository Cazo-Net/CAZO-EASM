"""Admin team chat: an internal room for platform staff (admin panel only).

Separate from the customer support chat. Rows are written and read only by the
admin-panel service (admin-panel/backend), which authenticates with its own
JWT secret; the customer API never exposes these tables.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AdminChatMessage(Base):
    __tablename__ = "admin_chat_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    # Admin sign-in email of the author (lower-case).
    author_email = Column(String(255), nullable=False, index=True)
    # Display name at the time of writing (users.full_name, or the email).
    author_name = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_now, index=True)


class AdminChatRead(Base):
    """How far each admin has read the team chat (drives the unread badge)."""

    __tablename__ = "admin_chat_reads"

    admin_email = Column(String(255), primary_key=True)
    last_read_at = Column(DateTime, nullable=True)
