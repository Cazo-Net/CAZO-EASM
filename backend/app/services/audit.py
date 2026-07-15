"""Auth audit logging utility."""

from sqlalchemy.orm import Session
from app.models.auth_models import AuthAuditLog


def log_auth_event(
    db: Session,
    event_type: str,
    user_id: str = None,
    ip_address: str = None,
    user_agent: str = None,
    success: bool = True,
    detail: dict = None,
):
    """Log an authentication event."""
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
