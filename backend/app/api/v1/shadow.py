from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models.user import User
from app.models.asset_inventory import Asset
from app.schemas.shadow import (
    ShadowCandidate,
    ShadowSignal,
    ShadowReviewRequest,
    ShadowReviewResponse,
    ShadowListResponse,
)
from app.api.deps import get_current_user
from app.services.shadow_assets import detect_shadow_assets, review_shadow_asset

logger = logging.getLogger(__name__)

router = APIRouter()


def _org_id(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="User is not part of an organization")
    return user.organization_id


@router.get("", response_model=ShadowListResponse)
async def list_shadow_assets(
    min_confidence: int = Query(0, ge=0, le=100, description="Filter by minimum confidence"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List shadow-asset candidates for the current org, highest confidence first."""
    org_id = _org_id(current_user)
    candidates = detect_shadow_assets(db, org_id)
    if min_confidence:
        candidates = [c for c in candidates if c["confidence"] >= min_confidence]

    known_count = db.query(Asset).filter(
        Asset.organization_id == org_id, Asset.inventory_status == "known"
    ).count()
    discovered_count = db.query(Asset).filter(
        Asset.organization_id == org_id, Asset.inventory_status == "discovered"
    ).count()

    return ShadowListResponse(
        shadows=[
            ShadowCandidate(
                asset_id=c["asset_id"],
                value=c["value"],
                label=c.get("label"),
                first_seen=c.get("first_seen"),
                confidence=c["confidence"],
                signals=[
                    ShadowSignal(type=s["type"], with_=s.get("with", []), cloud=s.get("cloud"))
                    for s in c["signals"]
                ],
                inventory_status="discovered",
            )
            for c in candidates
        ],
        total=len(candidates),
        known_count=known_count,
        discovered_count=discovered_count,
    )


@router.post("/{asset_id}/review", response_model=ShadowReviewResponse)
async def review_asset(
    asset_id: str,
    payload: ShadowReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a review decision (confirm / reject / investigate) to an asset."""
    org_id = _org_id(current_user)
    try:
        asset = review_shadow_asset(
            db, org_id, asset_id, payload.action,
            actor_id=current_user.id, note=payload.note,
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            logger.warning("shadow review: asset %s not found for org %s", asset_id, org_id)
            raise HTTPException(status_code=404, detail="Asset not found")
        raise HTTPException(status_code=400, detail="Invalid action")

    return ShadowReviewResponse(
        asset_id=asset.id,
        inventory_status=asset.inventory_status,
        confirmed=asset.confirmed,
    )


@router.get("/review-log", response_model=list)
async def get_review_log(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Audit trail of shadow-asset review decisions for the org."""
    from app.models.asset_inventory import AssetReviewLog

    org_id = _org_id(current_user)
    rows = (
        db.query(AssetReviewLog)
        .filter(AssetReviewLog.organization_id == org_id)
        .order_by(AssetReviewLog.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": r.id,
            "asset_id": r.asset_id,
            "actor_id": r.actor_id,
            "action": r.action,
            "old_status": r.old_status,
            "new_status": r.new_status,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
