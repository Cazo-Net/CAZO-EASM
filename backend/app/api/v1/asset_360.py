"""Asset 360 view: unified single-asset intelligence aggregation."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.asset_inventory import Asset, AssetRelationship
from app.models.asset_score import AssetScore
from app.models.asset_change import AssetChange
from app.schemas.asset_360 import (
    Asset360Response,
    Asset360Summary,
    Asset360Score,
    Asset360Relationship,
    Asset360Change,
    Asset360Counts,
    Asset360ListItem,
)
from app.api.deps import get_current_user

router = APIRouter()


def _require_asset_org(asset: Asset, current_user: User) -> None:
    """Raise 403 if the asset does not belong to the user's organization."""
    if asset.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this asset",
        )


def _int_from_attr(attributes: dict, *keys: str) -> int:
    """Best-effort count from attributes: sum list lengths or numeric values."""
    if not attributes:
        return 0
    for key in keys:
        if key in attributes:
            val = attributes[key]
            if isinstance(val, list):
                return len(val)
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, dict):
                return len(val)
    return 0


@router.get("", response_model=List[Asset360ListItem])
async def list_assets_360(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all assets for the user's organization, most-recently-seen first."""
    if not current_user.organization_id:
        return []
    if limit > 200:
        limit = 200
    assets = (
        db.query(Asset)
        .filter(Asset.organization_id == current_user.organization_id)
        .order_by(Asset.last_seen.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return assets


@router.get("/{asset_id}", response_model=Asset360Response)
async def get_asset_360(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate a single asset's intelligence: score, relationships, changes."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    _require_asset_org(asset, current_user)

    score_row = (
        db.query(AssetScore)
        .filter(AssetScore.asset_id == asset_id)
        .order_by(AssetScore.scored_at.desc())
        .first()
    )
    score = Asset360Score.model_validate(score_row) if score_row else None

    relationships: List[Asset360Relationship] = []

    outgoing = (
        db.query(AssetRelationship)
        .filter(AssetRelationship.source_asset_id == asset_id)
        .all()
    )
    incoming = (
        db.query(AssetRelationship)
        .filter(AssetRelationship.target_asset_id == asset_id)
        .all()
    )

    related_ids = set()
    for rel in outgoing:
        related_ids.add(rel.target_asset_id)
    for rel in incoming:
        related_ids.add(rel.source_asset_id)

    related_map = {}
    if related_ids:
        for related in (
            db.query(Asset)
            .filter(
                Asset.id.in_(related_ids),
                Asset.organization_id == asset.organization_id,
            )
            .all()
        ):
            related_map[related.id] = related

    for rel in outgoing:
        related = related_map.get(rel.target_asset_id)
        relationships.append(
            Asset360Relationship(
                id=rel.id,
                relationship_type=rel.relationship_type,
                direction="outgoing",
                related_asset_id=rel.target_asset_id,
                related_asset_label=(related.label or related.value) if related else None,
                related_asset_type=related.asset_type if related else None,
                last_seen=rel.last_seen,
            )
        )
    for rel in incoming:
        related = related_map.get(rel.source_asset_id)
        relationships.append(
            Asset360Relationship(
                id=rel.id,
                relationship_type=rel.relationship_type,
                direction="incoming",
                related_asset_id=rel.source_asset_id,
                related_asset_label=(related.label or related.value) if related else None,
                related_asset_type=related.asset_type if related else None,
                last_seen=rel.last_seen,
            )
        )

    change_rows = (
        db.query(AssetChange)
        .filter(
            AssetChange.organization_id == asset.organization_id,
            AssetChange.entity_key == asset.value,
        )
        .order_by(AssetChange.detected_at.desc())
        .limit(50)
        .all()
    )
    changes = [
        Asset360Change(
            id=c.id,
            change_type=c.change_type,
            entity_type=c.entity_type,
            entity_key=c.entity_key,
            detail=c.detail,
            detected_at=c.detected_at,
        )
        for c in change_rows
    ]

    attributes = asset.attributes or {}
    counts = Asset360Counts(
        subdomains=_int_from_attr(attributes, "subdomains", "subdomain_count"),
        ports=_int_from_attr(attributes, "ports", "port_count", "open_ports"),
        vulnerabilities=_int_from_attr(
            attributes, "vulnerabilities", "vuln_count", "vulns"
        ),
        relationships=len(relationships),
    )

    return Asset360Response(
        asset=Asset360Summary.model_validate(asset),
        score=score,
        relationships=relationships,
        changes=changes,
        counts=counts,
        first_seen=asset.first_seen,
        last_seen=asset.last_seen,
    )
