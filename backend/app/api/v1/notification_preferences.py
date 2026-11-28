"""Notification preferences API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.notification_preference import NotificationPreference
from app.api.deps import get_current_user
from app.services.notification_service import ensure_default_preferences

router = APIRouter()


class NotificationPreferenceResponse(BaseModel):
    id: str
    notification_type: str
    in_app_enabled: bool
    email_enabled: bool

    class Config:
        from_attributes = True


class NotificationPreferenceUpdate(BaseModel):
    notification_type: str
    in_app_enabled: bool
    email_enabled: bool


class NotificationPreferenceSingleUpdate(BaseModel):
    """Body for PUT /{notification_type}: the type is in the path, and the
    settings page sends only the channel it changed."""
    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None


class NotificationPreferencesBulkUpdate(BaseModel):
    preferences: List[NotificationPreferenceUpdate]


class NotificationPreferencesResponse(BaseModel):
    preferences: List[NotificationPreferenceResponse]


@router.get("", response_model=NotificationPreferencesResponse)
async def list_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all notification preferences for the current user."""
    ensure_default_preferences(db, current_user.id)

    prefs = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id,
    ).order_by(NotificationPreference.notification_type).all()

    return NotificationPreferencesResponse(
        preferences=[NotificationPreferenceResponse.model_validate(p) for p in prefs]
    )


@router.put("", response_model=NotificationPreferencesResponse)
async def update_preferences(
    body: NotificationPreferencesBulkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update notification preferences in bulk.

    Accepts a list of preference updates. Only the provided types are updated;
    unmentioned types retain their current values.
    """
    ensure_default_preferences(db, current_user.id)

    updated_types = set()
    for pref_update in body.preferences:
        pref = db.query(NotificationPreference).filter(
            NotificationPreference.user_id == current_user.id,
            NotificationPreference.notification_type == pref_update.notification_type,
        ).first()

        if not pref:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown notification type: {pref_update.notification_type}",
            )

        pref.in_app_enabled = pref_update.in_app_enabled
        pref.email_enabled = pref_update.email_enabled
        updated_types.add(pref_update.notification_type)

    db.commit()

    # Return all preferences
    prefs = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id,
    ).order_by(NotificationPreference.notification_type).all()

    return NotificationPreferencesResponse(
        preferences=[NotificationPreferenceResponse.model_validate(p) for p in prefs]
    )


@router.put("/{notification_type}")
async def update_single_preference(
    notification_type: str,
    body: NotificationPreferenceSingleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a single notification preference."""
    ensure_default_preferences(db, current_user.id)

    pref = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id,
        NotificationPreference.notification_type == notification_type,
    ).first()

    if not pref:
        raise HTTPException(
            status_code=404,
            detail=f"Notification type not found: {notification_type}",
        )

    if body.in_app_enabled is not None:
        pref.in_app_enabled = body.in_app_enabled
    if body.email_enabled is not None:
        pref.email_enabled = body.email_enabled
    db.commit()

    return NotificationPreferenceResponse.model_validate(pref)
