from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.schemas.api_key import APIKeyCreate, APIKeyResponse
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.core.security import generate_api_key, hash_api_key
from datetime import datetime, timezone

router = APIRouter()


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user)
):
    """List user's API keys."""
    if current_user.api_key:
        return [APIKeyResponse(
            id="current",
            name="Default API Key",
            created_at=current_user.created_at,
            last_used=None
        )]
    return []


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_API_KEYS))
):
    """Create a new API key (replaces existing)."""
    raw_key = generate_api_key()
    current_user.api_key = hash_api_key(raw_key)
    db.commit()

    return APIKeyResponse(
        id="new",
        name=key_data.name,
        key=raw_key,
        created_at=datetime.now(timezone.utc),
        last_used=None
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Revoke the current API key."""
    if not current_user.api_key:
        raise HTTPException(status_code=404, detail="No API key found")

    current_user.api_key = None
    db.commit()

    return {"message": "API key revoked successfully"}
