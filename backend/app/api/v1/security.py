"""Security settings endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from secrets import token_urlsafe

from app.database import get_db
from app.models.user import User
from app.models.auth_models import TrustedDevice, RecoveryCode
from app.api.deps import get_current_user
from app.core.security import verify_password, get_password_hash
from app.services.audit import log_auth_event
from app.services.notification_service import dispatch_notification
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter()


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    password: str


class ChangeEmailResponse(BaseModel):
    message: str
    pending_email: Optional[str] = None


class TrustedDeviceResponse(BaseModel):
    id: str
    browser: str
    os: str
    ip_address: str
    trusted_at: str
    last_used: Optional[str] = None


class RecoveryCodeResponse(BaseModel):
    id: str
    code_display: str
    created_at: str
    last_used: Optional[str] = None
    is_active: bool


class GenerateRecoveryCodesResponse(BaseModel):
    codes: List[str]
    count: int


@router.post("/change-email", response_model=ChangeEmailResponse)
async def request_email_change(
    data: ChangeEmailRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change email (password required) — the new address must be re-verified."""
    if not current_user.hashed_password or not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    from app.api.v1.users import change_user_email
    change_user_email(db, current_user, data.new_email, data.password)

    log_auth_event(db, "email_change_requested", current_user.id,
                   ip_address=request.client.host if request.client else None,
                   detail={"new_email": data.new_email})

    # Dispatch email changed notification
    try:
        client_ip = request.client.host if request.client else "unknown"
        dispatch_notification(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            notification_type="email_changed",
            title="Email change requested",
            message=f"Email change requested from {current_user.email} to {data.new_email}.",
            related_entity_type="user",
            related_entity_id=current_user.id,
            data={
                "ip_address": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
                "old_email": current_user.email,
                "new_email": data.new_email,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Failed to dispatch email change notification: {e}")

    return ChangeEmailResponse(
        message="Verification email sent to new address",
        pending_email=data.new_email,
    )


@router.get("/trusted-devices", response_model=List[TrustedDeviceResponse])
async def list_trusted_devices(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List trusted devices."""
    devices = (
        db.query(TrustedDevice)
        .filter(TrustedDevice.user_id == current_user.id, TrustedDevice.is_active)
        .order_by(TrustedDevice.trusted_at.desc())
        .all()
    )
    return [
        TrustedDeviceResponse(
            id=d.id, browser=d.browser, os=d.os, ip_address=d.ip_address,
            trusted_at=str(d.trusted_at), last_used=str(d.last_used) if d.last_used else None,
        )
        for d in devices
    ]


@router.delete("/trusted-devices/{device_id}")
async def revoke_trusted_device(
    device_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    return {"message": "Device removed"}


@router.post("/recovery-codes", response_model=GenerateRecoveryCodesResponse)
async def generate_recovery_codes(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate new recovery codes (replaces existing)."""
    db.query(RecoveryCode).filter(
        RecoveryCode.user_id == current_user.id
    ).update({"used": True})

    new_codes = []
    for _ in range(10):
        code = f"{token_urlsafe(4).upper()}-{token_urlsafe(4).upper()}"
        rc = RecoveryCode(
            user_id=current_user.id,
            code_hash=get_password_hash(code),
        )
        db.add(rc)
        new_codes.append(code)
    db.commit()

    log_auth_event(db, "recovery_codes_generated", current_user.id,
                   detail={"count": len(new_codes)})

    return GenerateRecoveryCodesResponse(codes=new_codes, count=len(new_codes))


@router.get("/recovery-codes", response_model=List[RecoveryCodeResponse])
async def list_recovery_codes(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recovery codes (masked)."""
    codes = (
        db.query(RecoveryCode)
        .filter(RecoveryCode.user_id == current_user.id)
        .order_by(RecoveryCode.created_at.desc())
        .all()
    )
    return [
        RecoveryCodeResponse(
            id=c.id,
            code_display="****-****",
            created_at=str(c.created_at),
            last_used=str(c.used_at) if c.used_at else None,
            is_active=not c.used,
        )
        for c in codes
    ]
