"""Continuous change feed: recent asset changes for the organization."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from typing import List
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models.user import User
from app.models.asset_inventory import Asset
from app.models.asset_change import AssetChange
from app.schemas.change_feed import ChangeFeedItem, ChangeFeedSummary
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=List[ChangeFeedItem])
async def list_change_feed(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent asset changes for the user's org, newest first."""
    if not current_user.organization_id:
        return []
    if limit > 200:
        limit = 200

    changes = (
        db.query(AssetChange)
        .filter(AssetChange.organization_id == current_user.organization_id)
        .order_by(AssetChange.detected_at.desc())
        .limit(limit)
        .all()
    )
    if not changes:
        return []

    keys = {c.entity_key for c in changes}
    label_map = {}
    if keys:
        rows = (
            db.query(Asset.value, Asset.label)
            .filter(
                Asset.organization_id == current_user.organization_id,
                Asset.value.in_(keys),
            )
            .all()
        )
        for value, label in rows:
            label_map[value] = label or value

    return [
        ChangeFeedItem(
            id=c.id,
            change_type=c.change_type,
            entity_type=c.entity_type,
            entity_key=c.entity_key,
            detail=c.detail,
            from_scan_id=c.from_scan_id,
            to_scan_id=c.to_scan_id,
            asset_label=label_map.get(c.entity_key, c.entity_key),
            detected_at=c.detected_at,
        )
        for c in changes
    ]


@router.get("/summary", response_model=ChangeFeedSummary)
async def change_feed_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Counts of changes by change_type over the last 30 days for the org."""
    since = datetime.now(timezone.utc) - timedelta(days=30)
    if not current_user.organization_id:
        return ChangeFeedSummary(added=0, removed=0, modified=0, total=0, since=since)

    rows = (
        db.query(AssetChange.change_type, sql_func.count(AssetChange.id))
        .filter(
            AssetChange.organization_id == current_user.organization_id,
            AssetChange.detected_at >= since,
        )
        .group_by(AssetChange.change_type)
        .all()
    )
    counts = {change_type: count for change_type, count in rows}
    added = counts.get("added", 0)
    removed = counts.get("removed", 0)
    modified = counts.get("modified", 0)
    return ChangeFeedSummary(
        added=added,
        removed=removed,
        modified=modified,
        total=added + removed + modified,
        since=since,
    )
