"""Generic audit logging.

Extends the existing auth-focused audit trail (``AuthAuditLog``) with a general
``AuditEvent`` record covering non-auth actions: scan lifecycle, discovery,
asset/report creation, scope changes, and administrative actions. The existing
``log_auth_event`` helper is preserved for auth events.

All audit writes are best-effort: a failure to record an event must never break
the business operation it observes.
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.auth_models import AuthAuditLog

logger = logging.getLogger(__name__)


def log_auth_event(
    db: Session,
    event_type: str,
    user_id: str = None,
    ip_address: str = None,
    user_agent: str = None,
    success: bool = True,
    detail: dict = None,
):
    """Log an authentication event (legacy helper, preserved for auth routers)."""
    entry = AuthAuditLog(
        user_id=user_id,
        event_type=event_type,
        event_detail=detail or {},
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
    )
    db.add(entry)
    db.commit()


def log_event(
    db: Session,
    action: str,
    organization_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_type: str = "user",
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    status: str = "success",
    detail: Optional[dict] = None,
    request_id: Optional[str] = None,
) -> Optional[AuditEvent]:
    """Record a generic audit event (best-effort). Returns the created row or None."""
    try:
        event = AuditEvent(
            action=action,
            organization_id=organization_id,
            actor_id=actor_id,
            actor_type=actor_type,
            target_type=target_type,
            target_id=target_id,
            status=status,
            detail=detail or {},
            request_id=request_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.commit()
        return event
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to write audit event %s: %s", action, exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
