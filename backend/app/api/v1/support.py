"""Support chat API — customer side.

Signed-in users talk to the CAZO team from the dashboard. Website visitors can
start a conversation with a name and email address; they get a random token
(kept in their browser) that lets them read replies and write again.

Every message here is written by a real person. Replies come from the team
through the admin panel; nothing is auto-generated.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import frontend_url, settings
from app.core.client_ip import get_client_ip
from app.database import get_db
from app.models.support import SupportConversation, SupportMessage
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_MESSAGE_LENGTH = 4000
TEAM_NAME = "CAZO Support"

# Per-minute caps (skipped when RATE_LIMIT_ENABLED is off, e.g. in tests).
USER_MESSAGES_PER_MINUTE = 20
GUEST_MESSAGES_PER_MINUTE = 6
# New visitor conversations per IP per 15 minutes.
GUEST_CONVERSATIONS_PER_WINDOW = 3
# The team is emailed about a customer message unless they were already
# emailed about the same conversation this recently.
TEAM_NOTIFY_QUIET = timedelta(minutes=10)
# A customer can send this many messages in a row before the team answers.
# Stops one conversation being used to flood the inbox.
MAX_UNANSWERED_MESSAGES = 30


# ── Schemas ─────────────────────────────────────────────────────────────────

# Control characters (except newline and tab), plus the invisible Unicode
# characters used to reorder or hide text. Chat text is shown to staff in the
# admin panel, so it is stored as plain text with these removed. It is never
# interpreted as HTML or Markdown anywhere, and links are not made clickable.
_UNSAFE_CHARS = re.compile(
    "[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]"
)


def _clean_message(value: str) -> str:
    value = _UNSAFE_CHARS.sub("", (value or "").replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not value:
        raise ValueError("Message cannot be empty")
    if len(value) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message is too long (max {MAX_MESSAGE_LENGTH} characters)")
    return value


def _clean_line(value: Optional[str]) -> Optional[str]:
    """A name or subject: one line, no control or invisible characters."""
    if value is None:
        return None
    return " ".join(_UNSAFE_CHARS.sub(" ", value).split()) or None


class MessageCreate(BaseModel):
    message: str

    _clean = field_validator("message")(_clean_message)


class ConversationCreate(BaseModel):
    subject: Optional[str] = Field(default="Support Request", max_length=200)
    message: str

    _clean = field_validator("message")(_clean_message)
    _clean_subject = field_validator("subject")(_clean_line)


class GuestConversationCreate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    email: EmailStr
    message: str
    # Honeypot: real visitors never see or fill this field.
    website: Optional[str] = Field(default=None, max_length=200)

    _clean = field_validator("message")(_clean_message)
    _clean_name = field_validator("name")(_clean_line)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _iso(dt: Optional[datetime]) -> Optional[str]:
    """Timestamps are stored as naive UTC; send them with an explicit offset."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _throttle(key: str, limit: int, long_window: bool = False) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    from app.core.rate_limit import get_failure_limiter, get_rate_limiter
    limiter = get_failure_limiter() if long_window else get_rate_limiter()
    if not limiter.is_allowed(key, limit):
        raise HTTPException(status_code=429, detail="You're sending messages too quickly. Please wait a moment.")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _message_out(m: SupportMessage, own_name: str = "You") -> dict:
    return {
        "id": m.id,
        "sender_type": m.sender_type,
        "sender_name": TEAM_NAME if m.sender_type == "admin" else own_name,
        "message": m.message,
        "created_at": _iso(m.created_at),
    }


def _conversation_out(db: Session, c: SupportConversation) -> dict:
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
            SupportMessage.is_read.isnot(True),
        )
        .scalar()
    )
    return {
        "id": c.id,
        "subject": c.subject,
        "status": c.status,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
        "last_message": last_msg.message[:100] if last_msg else None,
        "unread_count": unread or 0,
    }


def _mark_team_messages_read(db: Session, conversation_id: str) -> None:
    db.query(SupportMessage).filter(
        SupportMessage.conversation_id == conversation_id,
        SupportMessage.sender_type == "admin",
        SupportMessage.is_read.isnot(True),
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()


def _messages(db: Session, conversation_id: str) -> list[SupportMessage]:
    return (
        db.query(SupportMessage)
        .filter(SupportMessage.conversation_id == conversation_id)
        .order_by(SupportMessage.created_at, SupportMessage.id)
        .all()
    )


def _add_customer_message(db: Session, conv: SupportConversation, sender_id: str, text_: str) -> SupportMessage:
    """Store a customer message, reopen the conversation and tell the team."""
    now = datetime.now(timezone.utc)
    previous = (
        db.query(SupportMessage)
        .filter(SupportMessage.conversation_id == conv.id)
        .order_by(SupportMessage.created_at.desc())
        .first()
    )
    last_reply_at = (
        db.query(func.max(SupportMessage.created_at))
        .filter(SupportMessage.conversation_id == conv.id, SupportMessage.sender_type == "admin")
        .scalar()
    )
    waiting = db.query(func.count(SupportMessage.id)).filter(
        SupportMessage.conversation_id == conv.id, SupportMessage.sender_type == "user"
    )
    if last_reply_at is not None:
        waiting = waiting.filter(SupportMessage.created_at > last_reply_at)
    if (waiting.scalar() or 0) >= MAX_UNANSWERED_MESSAGES:
        db.rollback()
        raise HTTPException(
            status_code=429,
            detail="We have your messages and will reply soon. You can write again after we answer.",
        )
    msg = SupportMessage(
        conversation_id=conv.id,
        sender_type="user",
        sender_id=sender_id,
        message=text_,
        is_read=False,
        created_at=now,
    )
    db.add(msg)
    conv.status = "open"
    conv.updated_at = now

    # Email the team once per burst: on the first message, after a team reply,
    # or when the customer writes again after a quiet period.
    notify = True
    if previous is not None and previous.sender_type == "user":
        prev_at = previous.created_at
        if prev_at is not None and prev_at.tzinfo is None:
            prev_at = prev_at.replace(tzinfo=timezone.utc)
        notify = prev_at is None or now - prev_at > TEAM_NOTIFY_QUIET
    db.commit()
    db.refresh(msg)
    if notify:
        _notify_team(db, conv, msg)
    return msg


def _notify_team(db: Session, conv: SupportConversation, msg: SupportMessage) -> None:
    recipients = [a.strip() for a in (settings.SUPPORT_NOTIFY_EMAIL or "").split(",") if a.strip()]
    if not recipients:
        return
    try:
        if conv.user_id:
            user = db.query(User).filter(User.id == conv.user_id).first()
            who = f"{(user.full_name or '').strip()} <{user.email}>".strip() if user else "A customer"
        else:
            who = f"{(conv.guest_name or 'Website visitor').strip()} <{conv.guest_email}> (website visitor)"
        from app.services.email import templates
        from app.services.email.sender import get_email_service

        body = (
            f"<h1>New support message</h1>"
            f"<p><strong>From:</strong> {html.escape(who)}</p>"
            f'<div class="card"><p style="white-space:pre-wrap;margin:0">{html.escape(msg.message)}</p></div>'
            f"<p>Reply from the Support tab of the admin panel.</p>"
        )
        subject = _clean_line(f"Support message from {who}")[:180]
        html_body = templates._base(html.escape(subject), body, html.escape(msg.message[:120]))
        service = get_email_service()
        for to in recipients:
            service.send_async(to=to, subject=subject, html_body=html_body)
    except Exception:  # noqa: BLE001 — a mail problem must never lose the message
        logger.exception("Could not email the team about support conversation %s", conv.id)


# ── Signed-in users ─────────────────────────────────────────────────────────

def _own_conversation(db: Session, conversation_id: str, user: User) -> SupportConversation:
    conv = db.query(SupportConversation).filter(
        SupportConversation.id == conversation_id,
        SupportConversation.user_id == user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/conversations")
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation with an initial message."""
    _throttle(f"support-user:{user.id}", USER_MESSAGES_PER_MINUTE)
    conv = SupportConversation(
        user_id=user.id,
        organization_id=user.organization_id,
        subject=(body.subject or "").strip() or "Support Request",
        status="open",
    )
    db.add(conv)
    db.flush()
    _add_customer_message(db, conv, user.id, body.message)
    db.refresh(conv)

    return {
        "id": conv.id,
        "subject": conv.subject,
        "status": conv.status,
        "created_at": _iso(conv.created_at),
    }


@router.get("/conversations")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List current user's conversations, most recently active first."""
    convs = (
        db.query(SupportConversation)
        .filter(SupportConversation.user_id == user.id)
        .order_by(SupportConversation.updated_at.desc())
        .limit(50)
        .all()
    )
    return {"conversations": [_conversation_out(db, c) for c in convs]}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get messages for a conversation and mark the team's replies as read."""
    conv = _own_conversation(db, conversation_id, user)
    _mark_team_messages_read(db, conv.id)
    return {
        "status": conv.status,
        "messages": [_message_out(m) for m in _messages(db, conv.id)],
    }


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message in a conversation. Writing to a closed one reopens it."""
    _throttle(f"support-user:{user.id}", USER_MESSAGES_PER_MINUTE)
    conv = _own_conversation(db, conversation_id, user)
    msg = _add_customer_message(db, conv, user.id, body.message)
    return _message_out(msg)


@router.get("/unread")
async def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get total unread team replies across all of the user's conversations."""
    count = (
        db.query(func.count(SupportMessage.id))
        .join(SupportConversation)
        .filter(
            SupportConversation.user_id == user.id,
            SupportMessage.sender_type == "admin",
            SupportMessage.is_read.isnot(True),
        )
        .scalar()
    )
    return {"count": count or 0}


# ── Website visitors (no account) ───────────────────────────────────────────

def _guest_conversation(db: Session, conversation_id: str, token: Optional[str]) -> SupportConversation:
    conv = db.query(SupportConversation).filter(
        SupportConversation.id == conversation_id,
        SupportConversation.user_id.is_(None),
    ).first()
    expected = (conv.guest_token_hash if conv else None) or ""
    supplied = _hash_token(token or "")
    # Same answer for "no such conversation" and "wrong token".
    if not conv or not token or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/guest/conversations")
async def guest_create_conversation(
    body: GuestConversationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Start a conversation from the public website (no account needed)."""
    ip = get_client_ip(request)
    _throttle(f"support-guest-new:{ip}", GUEST_CONVERSATIONS_PER_WINDOW, long_window=True)

    token = secrets.token_urlsafe(32)
    if body.website:
        # A bot filled the hidden field. Answer as if it worked, store nothing.
        return {"id": secrets.token_hex(16), "token": token, "status": "open"}

    conv = SupportConversation(
        user_id=None,
        guest_name=(body.name or "").strip() or None,
        guest_email=str(body.email).strip().lower(),
        guest_token_hash=_hash_token(token),
        subject="Website enquiry",
        status="open",
    )
    db.add(conv)
    db.flush()
    _add_customer_message(db, conv, "guest", body.message)
    return {"id": conv.id, "token": token, "status": conv.status}


@router.get("/guest/conversations/{conversation_id}/messages")
async def guest_get_messages(
    conversation_id: str,
    x_support_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    conv = _guest_conversation(db, conversation_id, x_support_token)
    unread = (
        db.query(func.count(SupportMessage.id))
        .filter(
            SupportMessage.conversation_id == conv.id,
            SupportMessage.sender_type == "admin",
            SupportMessage.is_read.isnot(True),
        )
        .scalar()
    ) or 0
    _mark_team_messages_read(db, conv.id)
    return {
        "status": conv.status,
        "unread_count": unread,
        "messages": [_message_out(m) for m in _messages(db, conv.id)],
    }


@router.get("/guest/conversations/{conversation_id}/unread")
async def guest_unread_count(
    conversation_id: str,
    x_support_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Unread team replies, without marking them read (drives the badge)."""
    conv = _guest_conversation(db, conversation_id, x_support_token)
    count = (
        db.query(func.count(SupportMessage.id))
        .filter(
            SupportMessage.conversation_id == conv.id,
            SupportMessage.sender_type == "admin",
            SupportMessage.is_read.isnot(True),
        )
        .scalar()
    )
    return {"count": count or 0}


@router.post("/guest/conversations/{conversation_id}/messages")
async def guest_send_message(
    conversation_id: str,
    body: MessageCreate,
    request: Request,
    x_support_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _throttle(f"support-guest-msg:{get_client_ip(request)}", GUEST_MESSAGES_PER_MINUTE)
    conv = _guest_conversation(db, conversation_id, x_support_token)
    msg = _add_customer_message(db, conv, "guest", body.message)
    return _message_out(msg)


# ── Email customers about replies they have not seen ────────────────────────

REPLY_EMAIL_DELAY = timedelta(minutes=3)


def send_reply_notifications(db: Session, now: Optional[datetime] = None) -> int:
    """Email customers whose team reply is still unread after a few minutes.

    One email per conversation, covering every unread reply not yet emailed.
    Run by the periodic worker. Returns the number of emails queued.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = (now - REPLY_EMAIL_DELAY).replace(tzinfo=None)
    pending = (
        db.query(SupportMessage)
        .filter(
            SupportMessage.sender_type == "admin",
            SupportMessage.is_read.isnot(True),
            SupportMessage.notified_at.is_(None),
            SupportMessage.created_at <= cutoff,
        )
        .order_by(SupportMessage.created_at)
        .limit(500)
        .all()
    )
    by_conv: dict[str, list[SupportMessage]] = {}
    for m in pending:
        by_conv.setdefault(m.conversation_id, []).append(m)

    from app.services.email import templates
    from app.services.email.sender import get_email_service

    sent = 0
    for conv_id, msgs in by_conv.items():
        conv = db.query(SupportConversation).filter(SupportConversation.id == conv_id).first()
        to = name = None
        if conv is not None and conv.user_id:
            user = db.query(User).filter(User.id == conv.user_id).first()
            if user is not None and user.is_active:
                to, name = user.email, user.full_name
        elif conv is not None:
            to, name = conv.guest_email, conv.guest_name
        if to:
            quoted = "".join(
                f'<div class="card"><p style="white-space:pre-wrap;margin:0">{html.escape(m.message)}</p></div>'
                for m in msgs
            )
            link = frontend_url("/dashboard" if conv.user_id else "/")
            body = (
                f"<h1>You have a reply from {TEAM_NAME}</h1>"
                f"<p>Hi {html.escape((name or '').strip() or 'there')}, we answered your message:</p>"
                f"{quoted}"
                f'<p style="text-align:center;margin:24px 0"><a class="btn" href="{link}">Open the chat to reply</a></p>'
                f"<p>This mailbox is not monitored, so please answer in the chat.</p>"
            )
            subject = f"{TEAM_NAME} replied to your message"
            try:
                get_email_service().send_async(
                    to=to, subject=subject, html_body=templates._base(html.escape(subject), body, html.escape(msgs[-1].message[:120]))
                )
                sent += 1
            except Exception:  # noqa: BLE001
                logger.exception("Could not queue reply email for support conversation %s", conv_id)
                continue
        stamp = now.replace(tzinfo=None)
        for m in msgs:
            m.notified_at = stamp
        db.commit()
    return sent
