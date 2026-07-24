"""Admin endpoints for user management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.auth_models import UserSession
from app.api.deps import get_current_user

router = APIRouter()


class AdminUserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool
    totp_enabled: bool
    failed_login_attempts: int
    locked_until: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _assert_same_org(target_user: User, admin: User):
    """Ensure the target user belongs to the same organization as the admin.

    Superusers bypass this check (platform-level admin).
    """
    if admin.role == "superuser":
        return
    if not admin.organization_id:
        raise HTTPException(status_code=403, detail="You must belong to an organization")
    if target_user.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/users", response_model=List[AdminUserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all users (admin only)."""
    q = db.query(User)
    if admin.role != "superuser" and admin.organization_id:
        q = q.filter(User.organization_id == admin.organization_id)
    if search:
        q = q.filter(
            (User.email.ilike(f"%{search}%")) | (User.full_name.ilike(f"%{search}%"))
        )
    users = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return [
        AdminUserResponse(
            id=u.id, email=u.email, full_name=u.full_name, role=u.role,
            is_active=u.is_active, email_verified=u.email_verified,
            totp_enabled=u.totp_enabled, failed_login_attempts=u.failed_login_attempts or 0,
            locked_until=str(u.locked_until) if u.locked_until else None,
            created_at=str(u.created_at), last_login=str(u.last_login) if u.last_login else None,
        )
        for u in users
    ]


@router.put("/users/{user_id}/disable")
async def disable_user(
    user_id: str,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Disable a user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_same_org(user, admin)
    user.is_active = False
    db.query(UserSession).filter(UserSession.user_id == user_id).update({"is_active": False})
    db.commit()
    return {"message": "User disabled"}


@router.put("/users/{user_id}/enable")
async def enable_user(
    user_id: str,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Enable a user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_same_org(user, admin)
    user.is_active = True
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return {"message": "User enabled"}


@router.put("/users/{user_id}/unlock")
async def unlock_user(
    user_id: str,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Unlock a locked user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_same_org(user, admin)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return {"message": "User unlocked"}


@router.put("/users/{user_id}/force-password-reset")
async def force_password_reset(
    user_id: str,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Force a user to reset their password on next login (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_same_org(user, admin)
    from secrets import token_urlsafe
    from datetime import datetime, timezone, timedelta
    user.reset_token = token_urlsafe(32)
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(days=7)
    db.commit()
    return {"message": "User must reset password on next login"}


@router.delete("/users/{user_id}/sessions")
async def revoke_user_sessions(
    user_id: str,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Revoke all sessions for a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _assert_same_org(user, admin)
    db.query(UserSession).filter(UserSession.user_id == user_id).update({"is_active": False})
    db.commit()
    return {"message": "All sessions revoked"}
