from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from secrets import token_urlsafe
from app.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationResponse
from app.api.deps import get_current_user
from app.utils.validators import sanitize_slug

router = APIRouter()


def _require_org_member(org_id: str, current_user: User) -> None:
    """Raise 403 if user does not belong to the organization."""
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization"
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
    db.commit()

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

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    update_data = org_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    db.commit()
    db.refresh(org)
    return org


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an organization."""
    _require_org_member(org_id, current_user)

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    db.delete(org)
    db.commit()
    return {"message": "Organization deleted successfully"}
