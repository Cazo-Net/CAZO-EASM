"""Support chat API routes — user-facing endpoints for conversations and messages."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.support import SupportConversation, SupportMessage
from app.models.user import User

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    message: str


class ConversationCreate(BaseModel):
    subject: Optional[str] = "Support Request"
    message: str


# ── Routes ──────────────────────────────────────────────────────────────────

@router.post("/conversations")
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation with an initial message."""
    conv = SupportConversation(
        user_id=user.id,
        subject=body.subject or "Support Request",
        status="open",
    )
    db.add(conv)
    db.flush()

    msg = SupportMessage(
        conversation_id=conv.id,
        sender_type="user",
        sender_id=user.id,
        message=body.message,
    )
    db.add(msg)
    db.commit()
    db.refresh(conv)

    return {
        "id": conv.id,
        "subject": conv.subject,
        "status": conv.status,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


@router.get("/conversations")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List current user's conversations."""
    convs = (
        db.query(SupportConversation)
        .filter(SupportConversation.user_id == user.id)
        .order_by(SupportConversation.updated_at.desc())
        .all()
    )
    results = []
    for c in convs:
        last_msg = (
            db.query(SupportMessage)
            .filter(SupportMessage.conversation_id == c.id)
            .order_by(SupportMessage.created_at.desc())
            .first()
        )
        unread = (
            db.query(func.count(SupportMessage.id))
            .filter(
                SupportMessage.conversation_id == c.id,
                SupportMessage.sender_type == "admin",
                SupportMessage.is_read == False,
            )
            .scalar()
        )
        results.append({
            "id": c.id,
            "subject": c.subject,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "last_message": last_msg.message[:100] if last_msg else None,
            "unread_count": unread or 0,
        })
    return {"conversations": results}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get messages for a conversation."""
    conv = db.query(SupportConversation).filter(
        SupportConversation.id == conversation_id,
        SupportConversation.user_id == user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Mark admin messages as read
    db.query(SupportMessage).filter(
        SupportMessage.conversation_id == conversation_id,
        SupportMessage.sender_type == "admin",
    ).filter(SupportMessage.is_read.is_(False)).update({"is_read": True})
    db.commit()

    msgs = (
        db.query(SupportMessage)
        .filter(SupportMessage.conversation_id == conversation_id)
        .order_by(SupportMessage.created_at)
        .all()
    )

    # Resolve sender names
    user_ids = list(set(m.sender_id for m in msgs if m.sender_type == "user"))
    user_map = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.full_name or u.email for u in users}

    return {
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_name": "Support Team" if m.sender_type == "admin" else user_map.get(m.sender_id, "You"),
                "message": m.message,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ]
    }


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message in a conversation."""
    conv = db.query(SupportConversation).filter(
        SupportConversation.id == conversation_id,
        SupportConversation.user_id == user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.status == "closed":
        raise HTTPException(status_code=400, detail="Conversation is closed")

    msg = SupportMessage(
        conversation_id=conversation_id,
        sender_type="user",
        sender_id=user.id,
        message=body.message,
    )
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "id": msg.id,
        "sender_type": msg.sender_type,
        "message": msg.message,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.get("/unread")
async def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get total unread admin messages across all user conversations."""
    count = (
        db.query(func.count(SupportMessage.id))
        .join(SupportConversation)
        .filter(
            SupportConversation.user_id == user.id,
            SupportMessage.sender_type == "admin",
        )
        .filter(SupportMessage.is_read.is_(False))
        .scalar()
    )
    return {"count": count or 0}
