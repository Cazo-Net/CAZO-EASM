"""Team collaboration API: comments/annotations on assets."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

from app.database import get_db
from app.models.user import User
from app.models.comment import AssetComment
from app.api.deps import get_current_user
from app.schemas.collaboration import (
    CommentCreate, CommentOut, CommentReply, CommentDeleted,
)

router = APIRouter()


def _require_org_match(comment: Optional[AssetComment], current_user: User) -> None:
    if not comment or comment.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Comment not found")


def _to_reply(c: AssetComment, author_cache: dict) -> CommentReply:
    author = author_cache.get(c.user_id)
    return CommentReply(
        id=c.id,
        organization_id=c.organization_id,
        asset_id=c.asset_id,
        user_id=c.user_id,
        author_email=author.email if author else None,
        author_name=author.full_name if author else None,
        content=c.content,
        parent_id=c.parent_id,
        created_at=c.created_at,
    )


def _to_out(c: AssetComment, author_cache: dict) -> CommentOut:
    author = author_cache.get(c.user_id)
    return CommentOut(
        id=c.id,
        organization_id=c.organization_id,
        asset_id=c.asset_id,
        user_id=c.user_id,
        author_email=author.email if author else None,
        author_name=author.full_name if author else None,
        content=c.content,
        parent_id=c.parent_id,
        created_at=c.created_at,
        replies=[_to_reply(r, author_cache) for r in c.replies if not r.is_deleted],
    )


@router.get(
    "/assets/{asset_id}/comments",
    response_model=List[CommentOut],
)
async def list_asset_comments(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List top-level comments for an asset (org-guarded), newest first."""
    comments = (
        db.query(AssetComment)
        .filter(
            AssetComment.asset_id == asset_id,
            AssetComment.organization_id == current_user.organization_id,
            AssetComment.parent_id.is_(None),
            AssetComment.is_deleted.is_(False),
        )
        .order_by(desc(AssetComment.created_at))
        .all()
    )
    user_ids = {c.user_id for c in comments}
    for c in comments:
        for r in c.replies:
            user_ids.add(r.user_id)
    authors = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    author_cache = {u.id: u for u in authors}
    return [_to_out(c, author_cache) for c in comments]


@router.post(
    "/assets/{asset_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_asset_comment(
    asset_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a comment (or reply when parent_id is supplied)."""
    if payload.parent_id:
        parent = (
            db.query(AssetComment)
            .filter(AssetComment.id == payload.parent_id)
            .first()
        )
        _require_org_match(parent, current_user)
        # Only one level of nesting: replies cannot have their own replies.
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Nested replies are not allowed (one level only)",
            )

    comment = AssetComment(
        organization_id=current_user.organization_id,
        asset_id=asset_id,
        user_id=current_user.id,
        content=payload.content,
        parent_id=payload.parent_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    author_cache = {current_user.id: current_user}
    return _to_out(comment, author_cache)


@router.delete(
    "/comments/{comment_id}",
    response_model=CommentDeleted,
)
async def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete own comment (or any comment if admin/owner)."""
    comment = db.query(AssetComment).filter(AssetComment.id == comment_id).first()
    _require_org_match(comment, current_user)

    is_admin = current_user.role in ("owner", "admin")
    if comment.user_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments",
        )

    comment.is_deleted = True
    db.commit()
    return CommentDeleted(message="Comment deleted successfully", id=comment.id)
