"""Webhook CRUD API.

Endpoints:
- POST /webhooks — Create webhook
- GET /webhooks — List webhooks
- GET /webhooks/{id} — Get webhook details
- PUT /webhooks/{id} — Update webhook
- DELETE /webhooks/{id} — Delete webhook
- POST /webhooks/{id}/test — Test webhook delivery
- GET /webhooks/events — List available event types
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.webhook import Webhook, WEBHOOK_EVENT_TYPES
from app.services.webhook_dispatch import dispatch_webhook
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.services.audit import log_user_action

router = APIRouter()


def _validate_webhook_url(url: str) -> str:
    """Only allow http(s) URLs that point at a public host.

    Webhooks are sent from inside the platform's network, so a URL such as
    http://127.0.0.1:6379/ or http://169.254.169.254/ would let any org admin
    reach internal services (SSRF). Delivery checks the host again, because
    DNS can change after the webhook is saved.
    """
    from urllib.parse import urlsplit

    from app.core.target_guard import check_public_target

    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(status_code=400, detail="Webhook URL must start with https:// or http:// and include a host.")
    if parts.username or parts.password:
        raise HTTPException(status_code=400, detail="Webhook URL must not contain a username or password.")
    check = check_public_target(parts.hostname)
    if not check.allowed:
        raise HTTPException(status_code=400, detail="Webhook URL must point at a public internet address, not a private, local or reserved one.")
    return url


def _url_host(url: str) -> str:
    """Host only: webhook URLs often carry a secret in the path or query."""
    from urllib.parse import urlsplit

    try:
        return urlsplit(url or "").hostname or ""
    except ValueError:
        return ""


# ── Schemas ─────────────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    url: str = Field(..., description="Webhook delivery URL")
    description: Optional[str] = Field(None, description="Human-readable description")
    event_types: List[str] = Field(default_factory=list, description="Event types to subscribe to (empty = all)")
    is_active: bool = Field(True, description="Whether webhook is active")
    custom_headers: Dict[str, str] = Field(default_factory=dict, description="Additional HTTP headers")
    max_per_minute: int = Field(30, ge=1, le=100, description="Rate limit per minute")


class WebhookUpdate(BaseModel):
    url: Optional[str] = Field(None, description="Webhook delivery URL")
    description: Optional[str] = Field(None, description="Human-readable description")
    event_types: Optional[List[str]] = Field(None, description="Event types to subscribe to")
    is_active: Optional[bool] = Field(None, description="Whether webhook is active")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Additional HTTP headers")
    max_per_minute: Optional[int] = Field(None, ge=1, le=100, description="Rate limit per minute")


class WebhookResponse(BaseModel):
    id: str
    url: str
    description: Optional[str] = None
    event_types: List[str] = []
    is_active: bool = True
    custom_headers: Dict[str, str] = {}
    max_per_minute: int = 30
    failure_count: int = 0
    last_triggered_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookListResponse(BaseModel):
    webhooks: List[WebhookResponse]
    total: int


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    duration_ms: float = 0


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
):
    """Create a new webhook."""
    # Validate event types
    valid_events = set(WEBHOOK_EVENT_TYPES.keys())
    for event in body.event_types:
        if event not in valid_events:
            # Check wildcard pattern
            if not (event.endswith(".*") and event[:-2] in valid_events):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid event type: {event}. Use GET /webhooks/events for valid types.",
                )

    webhook = Webhook(
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        url=_validate_webhook_url(str(body.url)),
        description=body.description,
        event_types=body.event_types,
        is_active=body.is_active,
        custom_headers=body.custom_headers,
        max_per_minute=body.max_per_minute,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    log_user_action(db, current_user, "webhook.create", "webhook", webhook.id, {
        "host": _url_host(webhook.url), "event_types": webhook.event_types or [], "is_active": webhook.is_active,
    })

    return WebhookResponse.model_validate(webhook)


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List webhooks for the current organization."""
    query = db.query(Webhook).filter(
        Webhook.organization_id == current_user.organization_id,
    )
    if active_only:
        query = query.filter(Webhook.is_active == True)

    total = query.count()
    webhooks = (
        query.order_by(Webhook.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return WebhookListResponse(
        webhooks=[WebhookResponse.model_validate(w) for w in webhooks],
        total=total,
    )


@router.get("/events")
async def list_event_types():
    """List all available webhook event types."""
    return {
        "events": [
            {"type": k, "description": v}
            for k, v in sorted(WEBHOOK_EVENT_TYPES.items())
        ]
    }


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get webhook details."""
    webhook = (
        db.query(Webhook)
        .filter(
            Webhook.id == webhook_id,
            Webhook.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse.model_validate(webhook)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    body: WebhookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
):
    """Update a webhook."""
    webhook = (
        db.query(Webhook)
        .filter(
            Webhook.id == webhook_id,
            Webhook.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "url" and value is not None:
            value = _validate_webhook_url(str(value))
        setattr(webhook, field, value)

    db.commit()
    db.refresh(webhook)
    log_user_action(db, current_user, "webhook.update", "webhook", webhook.id, {
        "host": _url_host(webhook.url), "updated_fields": sorted(update_data.keys()),
    })
    return WebhookResponse.model_validate(webhook)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
):
    """Delete a webhook."""
    webhook = (
        db.query(Webhook)
        .filter(
            Webhook.id == webhook_id,
            Webhook.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    host = _url_host(webhook.url)
    db.delete(webhook)
    db.commit()
    log_user_action(db, current_user, "webhook.delete", "webhook", webhook_id, {"host": host})


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
):
    """Send a test event to the webhook."""
    webhook = (
        db.query(Webhook)
        .filter(
            Webhook.id == webhook_id,
            Webhook.organization_id == current_user.organization_id,
        )
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_payload = {
        "test": True,
        "message": "This is a test webhook delivery from CAZO EASM",
        "domain": "example.com",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    import time
    start = time.time()
    success = await dispatch_webhook(webhook, "scan.completed", test_payload)
    duration = (time.time() - start) * 1000

    return WebhookTestResponse(
        success=success,
        duration_ms=round(duration, 2),
        error=webhook.last_error if not success else None,
    )
