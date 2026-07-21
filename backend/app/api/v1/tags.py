from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import json

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.tag import Tag, AssetTag, AuditLog, Favorite
from app.schemas.tag import (
    TagCreate, TagResponse, AssetTagCreate, AssetTagResponse,
    AuditLogResponse, FavoriteCreate, FavoriteResponse
)

router = APIRouter()


def log_audit(db: Session, user_id: str, action: str, entity_type: str,
              entity_id: str = None, entity_name: str = None, details: dict = None):
    audit = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        details=json.dumps(details or {}),
    )
    db.add(audit)
    db.commit()


# ==================== TAGS ====================

@router.post("", response_model=TagResponse)
def create_tag(data: TagCreate, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    tag = Tag(name=data.name, color=data.color, user_id=current_user.id)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    log_audit(db, current_user.id, "create", "tag", tag.id, tag.name)
    return tag


@router.get("", response_model=List[TagResponse])
def list_tags(db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    return db.query(Tag).filter(Tag.user_id == current_user.id).all()


@router.put("/{tag_id}", response_model=TagResponse)
def update_tag(tag_id: str, data: TagCreate, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.user_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag.name = data.name
    tag.color = data.color
    db.commit()
    db.refresh(tag)
    log_audit(db, current_user.id, "update", "tag", tag.id, tag.name)
    return tag


@router.delete("/{tag_id}")
def delete_tag(tag_id: str, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.user_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.query(AssetTag).filter(AssetTag.tag_id == tag_id).delete()
    db.delete(tag)
    db.commit()
    log_audit(db, current_user.id, "delete", "tag", tag_id, tag.name)
    return {"ok": True}


# ==================== ASSET TAGS ====================

@router.post("/{asset_type}/{asset_id}/tags", response_model=AssetTagResponse)
def add_tag_to_asset(asset_type: str, asset_id: str, data: AssetTagCreate,
                     db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    tag = db.query(Tag).filter(Tag.id == data.tag_id, Tag.user_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    existing = db.query(AssetTag).filter(
        AssetTag.tag_id == data.tag_id,
        AssetTag.asset_type == asset_type,
        AssetTag.asset_id == asset_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tag already applied")
    asset_tag = AssetTag(tag_id=data.tag_id, asset_type=asset_type, asset_id=asset_id)
    db.add(asset_tag)
    db.commit()
    db.refresh(asset_tag)
    log_audit(db, current_user.id, "add_tag", asset_type, asset_id, details={"tag_name": tag.name})
    return asset_tag


@router.get("/{asset_type}/{asset_id}/tags", response_model=List[TagResponse])
def get_asset_tags(asset_type: str, asset_id: str, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    asset_tags = (
        db.query(AssetTag)
        .join(Tag, AssetTag.tag_id == Tag.id)
        .filter(
            AssetTag.asset_type == asset_type,
            AssetTag.asset_id == asset_id,
            Tag.user_id == current_user.id,
        )
        .all()
    )
    tag_ids = [at.tag_id for at in asset_tags]
    return db.query(Tag).filter(Tag.id.in_(tag_ids)).all()


@router.delete("/{asset_type}/{asset_id}/tags/{tag_id}")
def remove_tag_from_asset(asset_type: str, asset_id: str, tag_id: str,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.user_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    asset_tag = db.query(AssetTag).filter(
        AssetTag.tag_id == tag_id,
        AssetTag.asset_type == asset_type,
        AssetTag.asset_id == asset_id
    ).first()
    if not asset_tag:
        raise HTTPException(status_code=404, detail="Tag not found on asset")
    db.delete(asset_tag)
    db.commit()
    log_audit(db, current_user.id, "remove_tag", asset_type, asset_id, details={"tag_id": tag_id})
    return {"ok": True}


# ==================== AUDIT LOGS ====================

@router.get("/audit-logs", response_model=List[AuditLogResponse])
def list_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AuditLog).filter(AuditLog.user_id == current_user.id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    result = []
    for log in logs:
        user_name = None
        if log.user_id:
            user = db.query(User).filter(User.id == log.user_id).first()
            user_name = user.full_name if user else None
        result.append(AuditLogResponse(
            id=log.id, user_id=log.user_id, action=log.action,
            entity_type=log.entity_type, entity_id=log.entity_id,
            entity_name=log.entity_name, details=log.details,
            ip_address=log.ip_address, created_at=log.created_at,
            user_name=user_name
        ))
    return result


# ==================== FAVORITES ====================

@router.post("/favorites", response_model=FavoriteResponse)
def add_favorite(data: FavoriteCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.asset_type == data.asset_type,
        Favorite.asset_id == data.asset_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already favorited")
    fav = Favorite(user_id=current_user.id, asset_type=data.asset_type, asset_id=data.asset_id)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    log_audit(db, current_user.id, "add_favorite", data.asset_type, data.asset_id)
    return fav


@router.get("/favorites", response_model=List[FavoriteResponse])
def list_favorites(
    asset_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Favorite).filter(Favorite.user_id == current_user.id)
    if asset_type:
        query = query.filter(Favorite.asset_type == asset_type)
    return query.all()


@router.delete("/favorites/{asset_type}/{asset_id}")
def remove_favorite(asset_type: str, asset_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    fav = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.asset_type == asset_type,
        Favorite.asset_id == asset_id
    ).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    log_audit(db, current_user.id, "remove_favorite", asset_type, asset_id)
    return {"ok": True}
