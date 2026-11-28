from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserUpdate, PasswordChange, UserProfileResponse
from app.api.deps import get_current_user
from app.core.security import verify_password, get_password_hash
from app.services.notification_service import dispatch_notification
from app.services.audit import log_event, log_user_action

router = APIRouter()


class UserPreferences(BaseModel):
    email_notifications: bool = True
    ssl_expiry_alerts: bool = True
    weekly_reports: bool = False
    scan_complete_alerts: bool = True


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile."""
    return current_user


@router.put("/me", response_model=UserProfileResponse)
async def update_current_user(
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update current user profile.

    Changing the email requires the current password; the new address must be
    re-verified and the old address is notified.
    """
    if user_data.email and user_data.email != (current_user.email or "").lower():
        change_user_email(db, current_user, user_data.email, user_data.current_password)

    if user_data.full_name is not None:
        current_user.full_name = user_data.full_name

    db.commit()
    db.refresh(current_user)
    return current_user


def change_user_email(db: Session, user: User, new_email: str, password: Optional[str]) -> None:
    """Change a user's email after re-checking their password.

    The new address starts unverified and gets a verification link; the old
    address gets a notice so a hijacked session can't silently take over the
    account's recovery email.
    """
    from sqlalchemy import func
    from app.core.security import generate_verification_token
    from app.config import frontend_url
    from app.services.email import get_email_service, templates
    import logging

    new_email = new_email.strip().lower()
    if not password or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter your current password to change your email",
        )
    existing = db.query(User).filter(func.lower(User.email) == new_email, User.id != user.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")

    old_email = user.email
    token = generate_verification_token()
    user.email = new_email
    user.email_verified = False
    user.verification_token = token
    db.commit()

    log = logging.getLogger(__name__)
    try:
        email_service = get_email_service()
        verify_url = frontend_url(f"/auth/verify-email?token={token}")
        subject, html = templates.email_changed(user.full_name or new_email, old_email, new_email, verify_url)
        email_service.send_async(to=new_email, subject=subject, html_body=html)
        email_service.send_async(to=old_email, subject=subject, html_body=html)
    except Exception as e:  # noqa: BLE001
        log.error(f"Failed to send email-change emails: {e}")


@router.put("/me/password")
async def change_password(
    password_data: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change current user's password."""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )

    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    log_user_action(db, current_user, "auth.password_changed", "user", current_user.id)

    # Dispatch password changed notification
    try:
        client_ip = request.client.host if request.client else "unknown"
        dispatch_notification(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            notification_type="password_changed",
            title="Password changed",
            message="Your password was changed.",
            related_entity_type="user",
            related_entity_id=current_user.id,
            data={
                "ip_address": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        pass

    return {"message": "Password changed successfully"}


@router.delete("/me")
async def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete current user account and all associated data."""
    if current_user.role == "owner" and current_user.organization_id:
        others = db.query(User).filter(
            User.organization_id == current_user.organization_id,
            User.id != current_user.id,
        ).count()
        if others:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transfer organization ownership to another member before deleting your account",
            )
    from app.models.scan import Scan
    from app.models.asset import Subdomain
    from app.models.port import Port
    from app.models.ssl import SSLCertificate
    from app.models.technology import Technology
    from app.models.vulnerability import Vulnerability
    from app.models.dns import DNSRecord
    from app.models.whois import WhoisRecord
    from app.models.risk import RiskScore
    from app.models.report import Report

    user_scan_ids = [s.id for s in db.query(Scan.id).filter(Scan.created_by == current_user.id).all()]

    if user_scan_ids:
        db.query(Vulnerability).filter(Vulnerability.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(Port).join(Subdomain).filter(Subdomain.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(Subdomain).filter(Subdomain.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(SSLCertificate).filter(SSLCertificate.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(Technology).filter(Technology.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(DNSRecord).filter(DNSRecord.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(WhoisRecord).filter(WhoisRecord.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(RiskScore).filter(RiskScore.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(Report).filter(Report.scan_id.in_(user_scan_ids)).delete(synchronize_session=False)
        db.query(Scan).filter(Scan.id.in_(user_scan_ids)).delete(synchronize_session=False)

    deleted_id, deleted_email, org_id = current_user.id, current_user.email, current_user.organization_id
    db.delete(current_user)
    db.commit()
    if org_id:
        log_event(db, action="user.delete_account", organization_id=org_id, actor_id=deleted_id,
                  actor_email=deleted_email, target_type="user", target_id=deleted_id,
                  detail={"scans_deleted": len(user_scan_ids)})

    return {"message": "Account deleted successfully"}


@router.get("/me/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user)
):
    """Get user notification preferences."""
    return current_user.preferences or {
        "email_notifications": True,
        "ssl_expiry_alerts": True,
        "weekly_reports": False,
        "scan_complete_alerts": True,
    }


@router.put("/me/preferences")
async def update_preferences(
    prefs: UserPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user notification preferences."""
    current_user.preferences = prefs.model_dump()
    db.commit()
    return {"message": "Preferences updated successfully", "preferences": current_user.preferences}
