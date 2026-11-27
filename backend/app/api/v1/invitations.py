"""Team invitation endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta
from secrets import token_urlsafe

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.auth_models import Invitation
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.config import frontend_url
from app.core.permissions import SYSTEM_ROLES
from app.services.audit import log_auth_event
from app.services.email import get_email_service
from app.services.email import templates

logger = logging.getLogger(__name__)

router = APIRouter()

INVITATION_EXPIRY_DAYS = 7

# Roles that may be granted via invitation. "owner" is excluded: ownership is
# only transferable through the dedicated ownership-transfer flow, never by
# invitation, to prevent privilege escalation.
INVITABLE_ROLES = [r for r in SYSTEM_ROLES.keys() if r != "owner"]


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = "member"

    def model_post_init(self, __context) -> None:
        if self.role not in INVITABLE_ROLES:
            raise ValueError(
                f"Invalid or non-invitable role: {self.role}. "
                f"Allowed roles: {', '.join(INVITABLE_ROLES)}"
            )


class InvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    invited_by: str
    expires_at: datetime
    created_at: datetime


@router.post("", response_model=InvitationResponse)
async def create_invitation(
    data: InvitationCreate,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVITE_USERS)),
):
    """Invite a user to the organization."""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="You must create an organization first")

    existing = db.query(Invitation).filter(
        Invitation.email == data.email,
        Invitation.organization_id == current_user.organization_id,
        Invitation.status == "pending",
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Invitation already pending for this email")

    token = token_urlsafe(32)
    invitation = Invitation(
        email=data.email,
        invited_by=current_user.id,
        organization_id=current_user.organization_id,
        role=data.role,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    accept_url = frontend_url(f"/invitations/accept?token={token}")

    email_service = get_email_service()
    subject, html = templates.invitation_email(
        current_user.full_name or current_user.email,
        org.name if org else "Organization",
        data.role,
        accept_url,
    )
    email_service.send_async(to=data.email, subject=subject, html_body=html)

    log_auth_event(db, "invitation_sent", current_user.id,
                   ip_address=request.client.host if request.client else None,
                   detail={"email": data.email, "role": data.role})

    return InvitationResponse(
        id=invitation.id, email=invitation.email, role=invitation.role,
        status=invitation.status, invited_by=current_user.id,
        expires_at=invitation.expires_at, created_at=invitation.created_at,
    )


@router.get("", response_model=List[InvitationResponse])
async def list_invitations(
    status: Optional[str] = None,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List invitations for the current user's organization."""
    if not current_user.organization_id:
        return []
    q = db.query(Invitation).filter(Invitation.organization_id == current_user.organization_id)
    if status:
        q = q.filter(Invitation.status == status)
    invitations = q.order_by(Invitation.created_at.desc()).all()
    return [
        InvitationResponse(
            id=i.id, email=i.email, role=i.role, status=i.status,
            invited_by=i.invited_by, expires_at=i.expires_at, created_at=i.created_at,
        )
        for i in invitations
    ]


@router.post("/accept")
async def accept_invitation(
    token: str,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a team invitation."""
    invitation = db.query(Invitation).filter(Invitation.token == token).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Invitation already used")
    expires_at = invitation.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at is not None and expires_at < datetime.now(timezone.utc):
        invitation.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Invitation expired")

    # The invite is for one address: only the account with that email may use it.
    if (invitation.email or "").strip().lower() != (current_user.email or "").strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation was sent to a different email address",
        )
    if current_user.organization_id and current_user.organization_id != invitation.organization_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Leave your current organization before joining another one",
        )

    current_user.organization_id = invitation.organization_id
    # Defense in depth: never grant owner via invitation (ownership is only
    # transferable through the dedicated transfer flow).
    if invitation.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation role",
        )
    current_user.role = invitation.role
    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)
    db.commit()

    email_service = get_email_service()
    org = db.query(Organization).filter(Organization.id == invitation.organization_id).first()
    subject, html = templates.invitation_accepted(
        current_user.full_name or current_user.email,
        org.name if org else "Organization",
    )
    email_service.send_async(to=invitation.email, subject=subject, html_body=html)

    log_auth_event(db, "invitation_accepted", current_user.id,
                   ip_address=request.client.host if request.client else None,
                   detail={"invitation_id": invitation.id})

    return {"message": "Invitation accepted"}


@router.delete("/{invitation_id}")
async def revoke_invitation(
    invitation_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REMOVE_USERS)),
):
    """Revoke a pending invitation."""
    invitation = db.query(Invitation).filter(
        Invitation.id == invitation_id,
        Invitation.organization_id == current_user.organization_id,
    ).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.status = "revoked"
    db.commit()
    return {"message": "Invitation revoked"}


@router.post("/{invitation_id}/resend")
async def resend_invitation(
    invitation_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVITE_USERS)),
):
    """Resend a pending invitation."""
    invitation = db.query(Invitation).filter(
        Invitation.id == invitation_id,
        Invitation.organization_id == current_user.organization_id,
        Invitation.status == "pending",
    ).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS)
    db.commit()

    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    accept_url = frontend_url(f"/invitations/accept?token={invitation.token}")

    email_service = get_email_service()
    subject, html = templates.invitation_email(
        current_user.full_name or current_user.email,
        org.name if org else "Organization",
        invitation.role,
        accept_url,
    )
    email_service.send_async(to=invitation.email, subject=subject, html_body=html)

    return {"message": "Invitation resent"}
