"""Security Center API endpoints.

Premium security dashboard with session management,
device management, login history, and security scoring.
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.auth_models import UserSession, TrustedDevice, RecoveryCode, AuthAuditLog
from app.models.api_key_v2 import ApiKey
from app.services.audit import log_auth_event

logger = logging.getLogger(__name__)

router = APIRouter()


def _compute_security_score(user: User, db: Session) -> dict:
    """Compute a security score (0-100) based on account configuration."""
    score = 0
    factors = []

    # MFA enabled (+20)
    if user.totp_enabled:
        score += 20
        factors.append({"name": "MFA Enabled", "points": 20, "status": "good"})
    else:
        factors.append({"name": "MFA Disabled", "points": 0, "status": "warning",
                        "recommendation": "Enable two-factor authentication"})

    # Email verified (+15)
    if user.email_verified:
        score += 15
        factors.append({"name": "Email Verified", "points": 15, "status": "good"})
    else:
        factors.append({"name": "Email Not Verified", "points": 0, "status": "warning"})

    # Password changed recently (+10)
    if user.password_changed_at:
        days_since = (datetime.now(timezone.utc) - user.password_changed_at).days
        if days_since <= 90:
            score += 10
            factors.append({"name": "Recent Password", "points": 10, "status": "good"})
        else:
            factors.append({"name": "Password Age", "points": 0, "status": "warning",
                            "detail": f"{days_since} days since last change"})
    else:
        score += 5
        factors.append({"name": "Password Age", "points": 5, "status": "info"})

    # No failed logins in 30 days (+10)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    failed_count = db.query(func.count(AuthAuditLog.id)).filter(
        AuthAuditLog.user_id == user.id,
        AuthAuditLog.event_type == "login_failed",
        AuthAuditLog.created_at >= thirty_days_ago,
    ).scalar() or 0

    if failed_count == 0:
        score += 10
        factors.append({"name": "No Recent Failed Logins", "points": 10, "status": "good"})
    else:
        factors.append({"name": "Failed Logins", "points": 0, "status": "warning",
                        "detail": f"{failed_count} failed attempts in 30 days"})

    # Limited active sessions (+10)
    active_sessions = db.query(func.count(UserSession.id)).filter(
        UserSession.user_id == user.id,
        UserSession.is_active,
    ).scalar() or 0

    if active_sessions <= 5:
        score += 10
        factors.append({"name": "Session Count", "points": 10, "status": "good"})
    else:
        factors.append({"name": "Many Active Sessions", "points": 0, "status": "warning",
                        "detail": f"{active_sessions} active sessions"})

    # API keys with expiration (+10)
    active_keys = db.query(ApiKey).filter(
        ApiKey.user_id == user.id,
        ApiKey.is_active,
    ).all()

    if active_keys:
        all_expiring = all(k.expires_at is not None for k in active_keys)
        if all_expiring:
            score += 10
            factors.append({"name": "API Keys Have Expiry", "points": 10, "status": "good"})
        else:
            factors.append({"name": "API Key Expiry", "points": 5, "status": "info",
                            "recommendation": "Set expiration on all API keys"})
    else:
        score += 10
        factors.append({"name": "No Active API Keys", "points": 10, "status": "good"})

    # Recovery codes exist (+10)
    recovery_count = db.query(func.count(RecoveryCode.id)).filter(
        RecoveryCode.user_id == user.id,
        not RecoveryCode.used,
    ).scalar() or 0

    if recovery_count >= 5:
        score += 10
        factors.append({"name": "Recovery Codes Available", "points": 10, "status": "good"})
    elif recovery_count > 0:
        score += 5
        factors.append({"name": "Some Recovery Codes", "points": 5, "status": "info"})
    else:
        factors.append({"name": "No Recovery Codes", "points": 0, "status": "warning",
                        "recommendation": "Generate recovery codes"})

    # Trusted devices limited (+5)
    trusted_count = db.query(func.count(TrustedDevice.id)).filter(
        TrustedDevice.user_id == user.id,
        TrustedDevice.is_active,
    ).scalar() or 0

    if trusted_count <= 3:
        score += 5
        factors.append({"name": "Trusted Devices", "points": 5, "status": "good"})
    else:
        factors.append({"name": "Many Trusted Devices", "points": 0, "status": "info",
                        "detail": f"{trusted_count} trusted devices"})

    # Account not locked (+10)
    if not user.locked_until or user.locked_until < datetime.now(timezone.utc):
        score += 10
        factors.append({"name": "Account Not Locked", "points": 10, "status": "good"})
    else:
        factors.append({"name": "Account Locked", "points": 0, "status": "critical"})

    return {"score": min(score, 100), "factors": factors}


@router.get("/dashboard")
async def security_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get security center dashboard with aggregated security posture."""
    security_score = _compute_security_score(current_user, db)

    active_sessions = db.query(func.count(UserSession.id)).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active,
    ).scalar() or 0

    trusted_devices = db.query(func.count(TrustedDevice.id)).filter(
        TrustedDevice.user_id == current_user.id,
        TrustedDevice.is_active,
    ).scalar() or 0

    active_api_keys = db.query(func.count(ApiKey.id)).filter(
        ApiKey.user_id == current_user.id,
        ApiKey.is_active,
    ).scalar() or 0

    recovery_codes = db.query(func.count(RecoveryCode.id)).filter(
        RecoveryCode.user_id == current_user.id,
        not RecoveryCode.used,
    ).scalar() or 0

    failed_30d = db.query(func.count(AuthAuditLog.id)).filter(
        AuthAuditLog.user_id == current_user.id,
        AuthAuditLog.event_type == "login_failed",
        AuthAuditLog.created_at >= datetime.now(timezone.utc) - timedelta(days=30),
    ).scalar() or 0

    password_age_days = None
    if current_user.password_changed_at:
        password_age_days = (datetime.now(timezone.utc) - current_user.password_changed_at).days

    return {
        "security_score": security_score,
        "mfa_enabled": current_user.totp_enabled,
        "email_verified": current_user.email_verified,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "active_sessions": active_sessions,
        "trusted_devices": trusted_devices,
        "active_api_keys": active_api_keys,
        "recovery_codes_available": recovery_codes,
        "failed_logins_30d": failed_30d,
        "password_age_days": password_age_days,
    }


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all active sessions for the current user."""
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active,
    ).order_by(desc(UserSession.last_activity)).all()

    return {
        "sessions": [
            {
                "id": s.id,
                "browser": s.browser,
                "os": s.os,
                "ip_address": s.ip_address,
                "location_city": s.location_city,
                "location_country": s.location_country,
                "is_trusted": s.is_trusted,
                "last_activity": s.last_activity.isoformat() if s.last_activity else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ]
    }


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a specific session."""
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id,
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_active = False
    db.commit()

    log_auth_event(
        db=db,
        user_id=current_user.id,
        event_type="session_revoked",
        success=True,
        detail={"session_id": session_id},
    )

    return {"message": "Session revoked", "id": session_id}


@router.delete("/sessions")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke all sessions except the current one."""
    revoked = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active,
    ).update({"is_active": False})

    db.commit()

    log_auth_event(
        db=db,
        user_id=current_user.id,
        event_type="all_sessions_revoked",
        success=True,
        detail={"count": revoked},
    )

    return {"message": "All sessions revoked", "count": revoked}


@router.get("/devices")
async def list_trusted_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List trusted devices."""
    devices = db.query(TrustedDevice).filter(
        TrustedDevice.user_id == current_user.id,
        TrustedDevice.is_active,
    ).order_by(desc(TrustedDevice.last_used)).all()

    return {
        "devices": [
            {
                "id": d.id,
                "device_name": d.device_name,
                "browser": d.browser,
                "os": d.os,
                "ip_address": d.ip_address,
                "trusted_at": d.trusted_at.isoformat() if d.trusted_at else None,
                "last_used": d.last_used.isoformat() if d.last_used else None,
            }
            for d in devices
        ]
    }


@router.delete("/devices/{device_id}")
async def remove_trusted_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a trusted device."""
    device = db.query(TrustedDevice).filter(
        TrustedDevice.id == device_id,
        TrustedDevice.user_id == current_user.id,
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.is_active = False
    db.commit()

    return {"message": "Device removed", "id": device_id}


@router.get("/login-history")
async def login_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get recent login attempts."""
    events = db.query(AuthAuditLog).filter(
        AuthAuditLog.user_id == current_user.id,
        AuthAuditLog.event_type.in_(["login_success", "login_failed"]),
    ).order_by(desc(AuthAuditLog.created_at)).limit(limit).all()

    return {
        "history": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "success": e.success,
                "ip_address": e.ip_address,
                "user_agent": e.user_agent,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
    }


@router.get("/audit-trail")
async def audit_trail(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's own audit trail."""
    events = db.query(AuthAuditLog).filter(
        AuthAuditLog.user_id == current_user.id,
    ).order_by(desc(AuthAuditLog.created_at)).limit(limit).all()

    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "success": e.success,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
    }
