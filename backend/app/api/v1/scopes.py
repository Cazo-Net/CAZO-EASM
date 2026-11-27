"""Authorized-scope management API.

Allows organization admins/members to register, list, and revoke the scopes
that gate discovery. All mutations are audited. Scope values are syntactically
validated on write; out-of-band ownership verification is pluggable via the
core scope ``ScopeVerifier`` interface.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.scope import AuthorizedScope
from app.core.scope import (
    is_valid_scope_value,
    DnsTxtScopeVerifier, ensure_verification_token, verification_instructions,
)
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.services.audit import log_event

router = APIRouter()


class ScopeCreate(BaseModel):
    scope_type: str = Field(..., pattern="^(domain|wildcard|ip|cidr)$")
    value: str = Field(..., min_length=1, max_length=512)
    note: Optional[str] = None


class ScopeUpdate(BaseModel):
    verified: Optional[bool] = None
    note: Optional[str] = None


class ScopeOut(BaseModel):
    id: str
    organization_id: str
    scope_type: str
    value: str
    verified: bool
    verified_at: Optional[str] = None
    verification_method: Optional[str] = None
    # DNS record to publish, while the scope is unverified.
    verification: Optional[dict] = None
    note: Optional[str]
    added_by: Optional[str]
    created_at: Optional[str]

    @classmethod
    def from_model(cls, s: AuthorizedScope) -> "ScopeOut":
        verified_at = getattr(s, "verified_at", None)
        return cls(
            id=s.id,
            organization_id=s.organization_id,
            scope_type=s.scope_type,
            value=s.value,
            verified=s.verified,
            verified_at=verified_at.isoformat() if verified_at else None,
            verification_method=getattr(s, "verification_method", None),
            verification=None if s.verified else verification_instructions(s),
            note=s.note,
            added_by=s.added_by,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )


def _org_id_for(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with an organization.",
        )
    return user.organization_id


@router.get("", response_model=List[ScopeOut])
async def list_scopes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List authorized scopes for the current user's organization."""
    org_id = _org_id_for(current_user)
    scopes = (
        db.query(AuthorizedScope)
        .filter(AuthorizedScope.organization_id == org_id)
        .order_by(AuthorizedScope.created_at.desc())
        .all()
    )
    out = [ScopeOut.from_model(s) for s in scopes]
    db.commit()  # persist verification tokens generated for older scopes
    return out


@router.post("", response_model=ScopeOut, status_code=status.HTTP_201_CREATED)
async def create_scope(
    payload: ScopeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    """Register a new authorized scope."""
    org_id = _org_id_for(current_user)
    if not is_valid_scope_value(payload.scope_type, payload.value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {payload.scope_type} value: '{payload.value}'.",
        )
    scope = AuthorizedScope(
        organization_id=org_id,
        scope_type=payload.scope_type,
        value=payload.value.strip(),
        note=payload.note,
        added_by=current_user.id,
        verified=False,
    )
    ensure_verification_token(scope)
    db.add(scope)
    db.commit()
    db.refresh(scope)
    log_event(
        db,
        action="scope.create",
        organization_id=org_id,
        actor_id=current_user.id,
        target_type="scope",
        target_id=scope.id,
        detail={"scope_type": scope.scope_type, "value": scope.value},
        request_id=request.headers.get("x-request-id"),
    )
    return ScopeOut.from_model(scope)


@router.delete("/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scope(
    scope_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    """Revoke an authorized scope."""
    org_id = _org_id_for(current_user)
    scope = (
        db.query(AuthorizedScope)
        .filter(AuthorizedScope.id == scope_id, AuthorizedScope.organization_id == org_id)
        .first()
    )
    if not scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scope not found.")
    db.delete(scope)
    db.commit()
    log_event(
        db,
        action="scope.delete",
        organization_id=org_id,
        actor_id=current_user.id,
        target_type="scope",
        target_id=scope_id,
        detail={"value": scope.value},
        request_id=request.headers.get("x-request-id"),
    )


@router.post("/check", response_model=dict)
async def check_scope(
    payload: ScopeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check whether the current organization may scan a target right now.

    Uses the same rules as scan creation (public target, scope match and,
    in ``verified`` mode, proven ownership) but never creates a scope. When
    enforcement is off it reports whether the target is in the scope list.
    """
    import asyncio
    from app.core.scope import authorize_scan_target, scope_mode

    org_id = _org_id_for(current_user)
    # With enforcement off, still answer "is this in our scope list?".
    mode = scope_mode()
    auth = await asyncio.to_thread(
        authorize_scan_target, db, org_id, payload.value, auto_register=False,
        mode="registered" if mode == "open" else mode,
    )
    return {
        "target": payload.value,
        "authorized": auth.authorized,
        "reason": auth.reason,
        "matched_scope_id": auth.scope_id,
        "verification": auth.verification,
    }

def _get_org_scope(db: Session, scope_id: str, org_id: str) -> AuthorizedScope:
    scope = (
        db.query(AuthorizedScope)
        .filter(AuthorizedScope.id == scope_id, AuthorizedScope.organization_id == org_id)
        .first()
    )
    if not scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scope not found.")
    return scope


@router.get("/{scope_id}/verification", response_model=dict)
async def get_scope_verification(
    scope_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Show the DNS TXT record that proves ownership of this scope."""
    org_id = _org_id_for(current_user)
    scope = _get_org_scope(db, scope_id, org_id)
    info = verification_instructions(scope)
    db.commit()
    return {"scope_id": scope.id, "verified": scope.verified, **info}


@router.post("/{scope_id}/verify", response_model=ScopeOut)
async def verify_scope(
    scope_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ORG)),
):
    """Check the DNS TXT record now and mark the scope verified if it matches.

    IP and CIDR scopes cannot be proven over DNS; a platform administrator
    verifies those from the admin panel.
    """
    import asyncio
    from datetime import datetime, timezone

    org_id = _org_id_for(current_user)
    scope = _get_org_scope(db, scope_id, org_id)
    if scope.verified:
        return ScopeOut.from_model(scope)
    if scope.scope_type not in ("domain", "wildcard"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IP and CIDR scopes are verified by a platform administrator.",
        )
    ensure_verification_token(scope)
    db.commit()

    ok = await asyncio.to_thread(DnsTxtScopeVerifier().verify, scope)
    log_event(
        db,
        action="scope.verify",
        organization_id=org_id,
        actor_id=current_user.id,
        target_type="scope",
        target_id=scope.id,
        status="success" if ok else "failed",
        detail={"value": scope.value, "method": "dns_txt"},
        request_id=request.headers.get("x-request-id"),
    )
    if not ok:
        info = verification_instructions(scope)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "msg": f"The TXT record was not found yet. {info['instructions']}",
                "verification": info,
            },
        )
    scope.verified = True
    scope.verified_at = datetime.now(timezone.utc)
    scope.verification_method = "dns_txt"
    db.commit()
    db.refresh(scope)
    return ScopeOut.from_model(scope)
