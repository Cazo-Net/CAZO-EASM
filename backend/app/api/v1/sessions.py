"""Session management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func
from typing import List
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models.user import User
from app.models.auth_models import UserSession
from app.api.deps import get_current_user
from app.core.security import decode_token, hash_api_key
import hashlib

router = APIRouter()


class SessionResponse(BaseModel):
    id: str
    browser: str
    os: str
    ip_address: str
    location_city: str | None = None
    location_country: str | None = None
    is_current: bool = False
    last_activity: datetime
    created_at: datetime


def _parse_user_agent(ua: str) -> tuple[str, str]:
    """Simple user-agent parser returning (browser, os)."""
    browser = "Unknown Browser"
    os_name = "Unknown OS"

    ua_lower = (ua or "").lower()
    if "firefox" in ua_lower:
        browser = "Firefox"
    elif "edg" in ua_lower:
        browser = "Edge"
    elif "chrome" in ua_lower:
        browser = "Chrome"
    elif "safari" in ua_lower:
        browser = "Safari"

    if "windows" in ua_lower:
        os_name = "Windows"
    elif "mac os" in ua_lower or "macos" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"

    return browser, os_name


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active sessions for the current user."""
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == current_user.id, UserSession.is_active == True)
        .order_by(UserSession.last_activity.desc())
        .all()
    )
    result = []
    for s in sessions:
        browser, os_name = _parse_user_agent(s.user_agent)
        result.append(SessionResponse(
            id=s.id,
            browser=s.browser or browser,
            os=s.os or os_name,
            ip_address=s.ip_address or "Unknown",
            location_city=s.location_city,
            location_country=s.location_country,
            last_activity=s.last_activity,
            created_at=s.created_at,
        ))
    return result


@router.delete("/{session_id}")
async def revoke_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    return {"message": "Session revoked"}


@router.delete("")
async def revoke_all_sessions(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke all sessions except the current one."""
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True,
    ).update({"is_active": False})
    db.commit()
    return {"message": "All sessions revoked"}
