"""Platform log write helpers.

All functions are **best-effort**: a failure to record a log entry must never
break the business operation it observes.  Writes go through a short-lived
session so callers don't need to manage transactions.
"""
import logging
import traceback
from typing import Optional, Any

from sqlalchemy.orm import Session

from app.models.platform_log import PlatformLog
from app.database import WriteSession

logger = logging.getLogger("app.platform_log")

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
CAT_APPLICATION_ERROR = "application_error"
CAT_SCAN_EVENT = "scan_event"
CAT_AUTH_EVENT = "auth_event"
CAT_SECURITY_EVENT = "security_event"
CAT_NOTIFICATION = "notification"
CAT_API_REQUEST = "api_request"
CAT_UNEXPECTED = "unexpected"

# ---------------------------------------------------------------------------
# Severity levels
# ---------------------------------------------------------------------------
SEV_INFO = "info"
SEV_WARNING = "warning"
SEV_ERROR = "error"
SEV_CRITICAL = "critical"


def _write(log: PlatformLog) -> None:
    """Commit a single log row. Swallows all exceptions."""
    db: Optional[Session] = None
    try:
        db = WriteSession()
        db.add(log)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to write platform log: %s", exc)
        try:
            if db:
                db.rollback()
        except Exception:
            pass
    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# High-level helpers — one per category
# ---------------------------------------------------------------------------

def log_application_error(
    message: str,
    *,
    exception: Optional[BaseException] = None,
    detail: Optional[dict] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
) -> None:
    """Record an application-level error (handled 500s, known failure modes)."""
    d = dict(detail or {})
    if exception:
        d["exception"] = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc(),
        }
    _write(PlatformLog(
        category=CAT_APPLICATION_ERROR,
        severity=SEV_ERROR,
        message=message,
        detail=d,
        organization_id=organization_id,
        user_id=user_id,
        request_id=request_id,
        client_ip=client_ip,
        path=path,
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
    ))


def log_scan_event(
    message: str,
    *,
    severity: str = SEV_INFO,
    scan_id: Optional[str] = None,
    domain: Optional[str] = None,
    detail: Optional[dict] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """Record a scan lifecycle event (started, completed, failed, scanner status)."""
    d = dict(detail or {})
    if scan_id:
        d["scan_id"] = scan_id
    if domain:
        d["domain"] = domain
    _write(PlatformLog(
        category=CAT_SCAN_EVENT,
        severity=severity,
        message=message,
        detail=d,
        organization_id=organization_id,
        user_id=user_id,
        request_id=request_id,
        related_entity_type="scan",
        related_entity_id=scan_id,
    ))


def log_auth_event(
    message: str,
    *,
    severity: str = SEV_INFO,
    detail: Optional[dict] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
) -> None:
    """Record an auth event (login, logout, lockout, password reset, MFA)."""
    _write(PlatformLog(
        category=CAT_AUTH_EVENT,
        severity=severity,
        message=message,
        detail=detail or {},
        user_id=user_id,
        request_id=request_id,
        client_ip=client_ip,
        path=path,
        method=method,
        status_code=status_code,
    ))


def log_security_event(
    message: str,
    *,
    severity: str = SEV_WARNING,
    detail: Optional[dict] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
) -> None:
    """Record a security-relevant event (rate-limit, SSRF block, 403, admin action)."""
    _write(PlatformLog(
        category=CAT_SECURITY_EVENT,
        severity=severity,
        message=message,
        detail=detail or {},
        organization_id=organization_id,
        user_id=user_id,
        request_id=request_id,
        client_ip=client_ip,
        path=path,
        method=method,
        status_code=status_code,
    ))


def log_notification_event(
    message: str,
    *,
    severity: str = SEV_INFO,
    detail: Optional[dict] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    notification_id: Optional[str] = None,
) -> None:
    """Record notification delivery success/failure."""
    _write(PlatformLog(
        category=CAT_NOTIFICATION,
        severity=severity,
        message=message,
        detail=detail or {},
        organization_id=organization_id,
        user_id=user_id,
        related_entity_type="notification",
        related_entity_id=notification_id,
    ))


def log_api_request(
    message: str,
    *,
    severity: str = SEV_INFO,
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """Record a request-level log entry for non-2xx responses."""
    _write(PlatformLog(
        category=CAT_API_REQUEST,
        severity=severity,
        message=message,
        detail=detail or {},
        request_id=request_id,
        client_ip=client_ip,
        path=path,
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
        organization_id=organization_id,
        user_id=user_id,
    ))


def log_unexpected(
    message: str,
    *,
    exception: Optional[BaseException] = None,
    detail: Optional[dict] = None,
    request_id: Optional[str] = None,
    client_ip: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Record an unexpected/catch-all error — gets priority attention."""
    d = dict(detail or {})
    if exception:
        d["exception"] = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc(),
        }
    _write(PlatformLog(
        category=CAT_UNEXPECTED,
        severity=SEV_CRITICAL,
        message=message,
        detail=d,
        request_id=request_id,
        client_ip=client_ip,
        path=path,
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
        organization_id=organization_id,
        user_id=user_id,
    ))


def log_client_error(
    message: str,
    *,
    detail: Optional[dict] = None,
    client_ip: Optional[str] = None,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> None:
    """Record a client-side JS error POSTed from the frontend ErrorBoundary."""
    _write(PlatformLog(
        category=CAT_UNEXPECTED,
        severity=SEV_ERROR,
        message=message,
        detail=dict(detail or {}),
        client_ip=client_ip,
        user_id=user_id,
        organization_id=organization_id,
    ))
