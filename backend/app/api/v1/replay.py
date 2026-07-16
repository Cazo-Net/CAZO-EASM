"""Exposure Replay API endpoints.

Wires the existing frontend "Exposure Replay" feature to real backend data.
Routes are mounted under /api/v1/replay.

NOTE: This module self-registers its router on the FastAPI app at import
time so that no change to ``main.py`` is required.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.scan import Scan
from app.schemas.replay import (
    ReplayTimelineResponse,
    ReplaySnapshot,
    ReplayChangesResponse,
    ReplayExposureResponse,
)
from app.services import replay_service

router = APIRouter()


def _require_scan_org(db: Session, scan_id: str, org_id: str) -> None:
    """Raise 403 if the scan does not belong to the user's organization."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    if scan.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this scan",
        )


@router.get("/timeline", response_model=ReplayTimelineResponse)
async def replay_timeline(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List one snapshot per completed scan for the caller's organization.

    Always scopes to the authenticated user's organization; the ``org_id``
    query parameter was removed to prevent cross-tenant timeline reads.
    """
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context is required",
        )
    snapshots: list[ReplaySnapshot] = replay_service.get_timeline(db, org_id)
    return ReplayTimelineResponse(organization_id=org_id, snapshots=snapshots)


@router.get("/changes", response_model=ReplayChangesResponse)
async def replay_changes(
    from_scan_id: str | None = None,
    to_scan_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Diff between two scans using persisted AssetChange records."""
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context is required",
        )
    if to_scan_id:
        _require_scan_org(db, to_scan_id, org_id)
    if from_scan_id:
        _require_scan_org(db, from_scan_id, org_id)
    if not to_scan_id and not from_scan_id:
        return ReplayChangesResponse(
            from_scan_id=from_scan_id,
            to_scan_id=to_scan_id,
            summary="Provide from_scan_id and/or to_scan_id to compute a diff.",
        )
    return replay_service.get_changes(db, org_id, from_scan_id, to_scan_id)


@router.get("/exposure", response_model=ReplayExposureResponse)
async def replay_exposure(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exposure metrics for a single scan."""
    org_id = current_user.organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context is required",
        )
    _require_scan_org(db, scan_id, org_id)
    result = replay_service.get_exposure(db, org_id, scan_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return result


def _register() -> None:
    """No-op kept for backwards compatibility; router is registered in main.py."""
    return


_register()
