from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from typing import List
from secrets import token_urlsafe
from app.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.models.scan import Scan
from app.models.project import Project
from app.models.asset_inventory import Asset
from app.models.auth_models import Invitation
from app.schemas.organization import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse,
    OrganizationMemberResponse, OrganizationMemberRoleUpdate,
    OrganizationStatsResponse,
)
from app.api.deps import get_current_user
from app.utils.validators import sanitize_slug
from app.services.audit import log_event
from app.core.permissions import check_custom_permission, Permission

router = APIRouter()


def _require_org_member(org_id: str, current_user: User) -> None:
    """Raise 403 if user does not belong to the organization."""
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization"
        )


def _require_org_admin(current_user: User, db: Session = None) -> None:
    """Raise 403 if the user lacks org-management permissions.

    Uses the permission system (not a raw role string) so that custom roles
    granting ``manage_org`` / ``manage_members`` / ``manage_roles`` are
    correctly honored.
    """
    if db is not None:
        has_perm = (
            check_custom_permission(current_user.role, Permission.MANAGE_ORG, db, current_user.organization_id)
            or check_custom_permission(current_user.role, Permission.MANAGE_MEMBERS, db, current_user.organization_id)
            or check_custom_permission(current_user.role, Permission.MANAGE_ROLES, db, current_user.organization_id)
        )
    else:
        has_perm = current_user.role in ("owner", "admin")
    if not has_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners, admins, or roles with member/management permissions can perform this action"
        )


@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's organizations."""
    if current_user.organization_id:
        org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
        return [org] if org else []
    return []


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new organization."""
    if current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already belong to an organization"
        )

    existing = db.query(Organization).filter(Organization.slug == org_data.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization slug already exists"
        )

    slug = org_data.slug or sanitize_slug(org_data.name)
    if not slug:
        slug = f"org-{token_urlsafe(6).lower()}"

    org = Organization(
        name=org_data.name,
        slug=slug,
        plan=org_data.plan,
        settings=org_data.settings or {}
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    current_user.organization_id = org.id
    current_user.role = "owner"
    db.commit()

    log_event(
        db,
        action="org.create",
        organization_id=org.id,
        actor_id=current_user.id,
        target_type="organization",
        target_id=org.id,
        detail={"name": org.name, "slug": org.slug},
    )

    return org


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization details."""
    _require_org_member(org_id, current_user)

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    org_data: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an organization."""
    _require_org_member(org_id, current_user)
    _require_org_admin(current_user, db)

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    update_data = org_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    db.commit()
    db.refresh(org)

    log_event(
        db,
        action="org.update",
        organization_id=org_id,
        actor_id=current_user.id,
        target_type="organization",
        target_id=org_id,
        detail={"updated_fields": list(update_data.keys())},
    )

    return org


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an organization."""
    _require_org_member(org_id, current_user)

    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the organization owner can delete the organization"
        )

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    log_event(
        db,
        action="org.delete",
        organization_id=org_id,
        actor_id=current_user.id,
        target_type="organization",
        target_id=org_id,
        detail={"name": org.name},
    )

    db.delete(org)
    db.commit()
    return {"message": "Organization deleted successfully"}


# ==================== MEMBERS ====================


@router.get("/{org_id}/members", response_model=List[OrganizationMemberResponse])
async def list_organization_members(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all members of the organization."""
    _require_org_member(org_id, current_user)

    members = (
        db.query(User)
        .filter(User.organization_id == org_id)
        .order_by(User.created_at.desc())
        .all()
    )
    return members


@router.put("/{org_id}/members/{user_id}/role", response_model=OrganizationMemberResponse)
async def update_member_role(
    org_id: str,
    user_id: str,
    role_data: OrganizationMemberRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a member's role in the organization."""
    _require_org_member(org_id, current_user)
    _require_org_admin(current_user, db)

    target_user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")

    if target_user.id == current_user.id and current_user.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )

    old_role = target_user.role
    target_user.role = role_data.role
    db.commit()
    db.refresh(target_user)

    log_event(
        db,
        action="org.member.role_changed",
        organization_id=org_id,
        actor_id=current_user.id,
        target_type="user",
        target_id=user_id,
        detail={"old_role": old_role, "new_role": role_data.role},
    )

    return target_user


@router.delete("/{org_id}/members/{user_id}")
async def remove_organization_member(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a member from the organization."""
    _require_org_member(org_id, current_user)
    _require_org_admin(current_user, db)

    target_user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Member not found")

    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself from the organization"
        )

    log_event(
        db,
        action="org.member.removed",
        organization_id=org_id,
        actor_id=current_user.id,
        target_type="user",
        target_id=user_id,
        detail={"email": target_user.email, "role": target_user.role},
    )

    target_user.organization_id = None
    target_user.role = "analyst"
    db.commit()

    return {"message": "Member removed from organization"}


# ==================== STATS ====================


@router.get("/{org_id}/stats", response_model=OrganizationStatsResponse)
async def get_organization_stats(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization-level statistics."""
    _require_org_member(org_id, current_user)

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    member_count = db.query(User).filter(User.organization_id == org_id).count()
    project_count = db.query(Project).filter(Project.organization_id == org_id).count()
    scan_count = db.query(Scan).join(User).filter(User.organization_id == org_id).count()
    active_scan_count = (
        db.query(Scan)
        .join(User)
        .filter(User.organization_id == org_id, Scan.status == "running")
        .count()
    )
    asset_count = db.query(Asset).filter(Asset.organization_id == org_id).count()
    invitation_count = (
        db.query(Invitation)
        .filter(Invitation.organization_id == org_id, Invitation.status == "pending")
        .count()
    )

    role_rows = (
        db.query(User.role, sql_func.count(User.id))
        .filter(User.organization_id == org_id)
        .group_by(User.role)
        .all()
    )
    role_distribution = {role: count for role, count in role_rows}

    return OrganizationStatsResponse(
        member_count=member_count,
        project_count=project_count,
        scan_count=scan_count,
        active_scan_count=active_scan_count,
        asset_count=asset_count,
        invitation_count=invitation_count,
        role_distribution=role_distribution,
        plan=org.plan,
        is_active=org.is_active,
        created_at=org.created_at,
    )
