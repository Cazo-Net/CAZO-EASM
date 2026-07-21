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
    check_target_authorized, is_valid_scope_value, NoopVerifier, ScopeMatch,
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
    note: Optional[str]
    added_by: Optional[str]
    created_at: Optional[str]

    @classmethod
    def from_model(cls, s: AuthorizedScope) -> "ScopeOut":
        return cls(
            id=s.id,
            organization_id=s.organization_id,
            scope_type=s.scope_type,
            value=s.value,
            verified=s.verified,
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
    return [ScopeOut.from_model(s) for s in scopes]


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
    """Check whether a target is authorized for the current organization."""
    org_id = _org_id_for(current_user)
    match: ScopeMatch = check_target_authorized(
        db, org_id, payload.value, verifier=NoopVerifier()
    )
    return {
        "target": payload.value,
        "authorized": match.authorized,
        "reason": match.reason,
        "matched_scope_id": match.matched_scope_id,
    }
