"""Enhanced API Key management with multi-key support.

Replaces the single-key-per-user approach with:
- Multiple keys per user
- Named keys with scopes
- Expiration dates
- Rotation support
- Usage tracking
"""

import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.models.user import User
from app.models.api_key_v2 import ApiKey
from app.schemas.api_key_v2 import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
)
from app.core.security import generate_api_key, hash_api_key
from app.services.audit import log_user_action

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all API keys for the current user."""
    keys = db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id,
        ApiKey.is_active,
    ).order_by(ApiKey.created_at.desc()).all()

    return ApiKeyListResponse(
        api_keys=[
            ApiKeyResponse(
                id=k.id,
                name=k.name,
                prefix=k.prefix,
                scopes=k.scopes or [],
                expires_at=k.expires_at,
                last_used_at=k.last_used_at,
                last_used_ip=k.last_used_ip,
                is_active=k.is_active,
                created_at=k.created_at,
            )
            for k in keys
        ],
        total=len(keys),
    )


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: ApiKeyCreate,
    current_user: User = Depends(require_permission(Permission.MANAGE_API_KEYS)),
    db: Session = Depends(get_db),
):
    """Create a new API key."""
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    prefix = raw_key[:16]

    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

    api_key = ApiKey(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        name=data.name,
        key_hash=key_hash,
        prefix=prefix,
        scopes=data.scopes or [],
        expires_at=expires_at,
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    logger.info(f"API key created: {api_key.id} ({data.name}) for user {current_user.id}")
    log_user_action(db, current_user, "api_key.create", "api_key", api_key.id, {
        "name": data.name, "prefix": prefix, "scopes": data.scopes or [],
        "expires_at": expires_at.isoformat() if expires_at else None,
    })

    return ApiKeyCreateResponse(
        id=api_key.id,
        key=raw_key,
        name=api_key.name,
        prefix=prefix,
        scopes=api_key.scopes or [],
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke an API key."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id,
    ).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    api_key.revoked_at = datetime.now(timezone.utc)
    key_name, key_prefix = api_key.name, api_key.prefix
    db.commit()
    log_user_action(db, current_user, "api_key.revoke", "api_key", key_id, {"name": key_name, "prefix": key_prefix})

    return {"message": "API key revoked successfully", "id": key_id}


@router.put("/{key_id}")
async def update_api_key(
    key_id: str,
    data: ApiKeyCreate,
    current_user: User = Depends(require_permission(Permission.MANAGE_API_KEYS)),
    db: Session = Depends(get_db),
):
    """Update an API key's metadata (name, scopes, expiry)."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id,
        ApiKey.is_active,
    ).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.name = data.name
    api_key.scopes = data.scopes or []

    if data.expires_in_days:
        api_key.expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)
    else:
        api_key.expires_at = None

    db.commit()
    db.refresh(api_key)
    log_user_action(db, current_user, "api_key.update", "api_key", api_key.id, {
        "name": api_key.name, "scopes": api_key.scopes or [],
    })

    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes or [],
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        last_used_ip=api_key.last_used_ip,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
    )


@router.post("/{key_id}/rotate", response_model=ApiKeyCreateResponse)
async def rotate_api_key(
    key_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_API_KEYS)),
    db: Session = Depends(get_db),
):
    """Rotate an API key: revoke old, create new with same settings."""
    old_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id,
        ApiKey.is_active,
    ).first()

    if not old_key:
        raise HTTPException(status_code=404, detail="API key not found")

    old_key.is_active = False
    old_key.revoked_at = datetime.now(timezone.utc)

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    prefix = raw_key[:16]

    new_key = ApiKey(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        name=old_key.name,
        key_hash=key_hash,
        prefix=prefix,
        scopes=old_key.scopes or [],
        expires_at=old_key.expires_at,
        is_active=True,
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    log_user_action(db, current_user, "api_key.rotate", "api_key", new_key.id, {
        "name": new_key.name, "prefix": prefix, "replaced_key_id": key_id,
    })

    return ApiKeyCreateResponse(
        id=new_key.id,
        key=raw_key,
        name=new_key.name,
        prefix=prefix,
        scopes=new_key.scopes or [],
        expires_at=new_key.expires_at,
        created_at=new_key.created_at,
    )


def verify_api_key(db: Session, raw_key: str) -> Optional[User]:
    """Verify an API key and return the associated user.

    Used by the API key authentication dependency.
    """
    key_hash = hash_api_key(raw_key)

    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active,
    ).first()

    if not api_key:
        return None

    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None

    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()

    user = db.query(User).filter(User.id == api_key.user_id).first()
    return user if user and user.is_active else None
