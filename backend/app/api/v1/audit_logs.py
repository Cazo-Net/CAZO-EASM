"""Organization audit log API.

Every route is limited to the caller's own organization and needs the
``view_audit_logs`` permission (owner, admin and security manager by default).

- GET /audit-logs          — filtered, paginated list (newest first)
- GET /audit-logs/actions  — action names present, for the filter menu
- GET /audit-logs/export   — CSV or JSON Lines download of the filtered log
- GET /audit-logs/verify   — re-check the tamper-evidence chain
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Iterator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.audit import AuditEvent
from app.models.user import User
from app.services.audit import log_event, verify_chain, _ts

router = APIRouter()

EXPORT_MAX_ROWS = 100_000


class AuditEntry(BaseModel):
    id: str
    seq: Optional[int] = None
    action: str
    status: Optional[str] = None
    actor_id: Optional[str] = None
    actor_type: Optional[str] = None
    actor_email: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    detail: dict = {}
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    created_at: Optional[str] = None
    hash: Optional[str] = None


class AuditListResponse(BaseModel):
    items: List[AuditEntry]
    total: int
    limit: int
    offset: int


def _entry(row: AuditEvent) -> dict:
    return {
        "id": row.id,
        "seq": row.seq,
        "action": row.action,
        "status": row.status,
        "actor_id": row.actor_id,
        "actor_type": row.actor_type,
        "actor_email": row.actor_email,
        "target_type": row.target_type,
        # Ids longer than the column are kept whole in detail.
        "target_id": (row.detail or {}).get("target_id_full") or row.target_id,
        "detail": row.detail or {},
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "request_id": row.request_id,
        "created_at": _ts(row.created_at) or None,
        "hash": row.hash,
    }


def _require_org(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="You are not part of an organization yet.")
    return user.organization_id


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filtered(
    db: Session,
    org_id: str,
    action: Optional[str],
    actor: Optional[str],
    status: Optional[str],
    target_type: Optional[str],
    target_id: Optional[str],
    since: Optional[datetime],
    until: Optional[datetime],
):
    # The organization filter is applied here, once, for every route.
    q = db.query(AuditEvent).filter(AuditEvent.organization_id == org_id)
    if action:
        action = action.strip()
        if action.endswith("*"):
            q = q.filter(AuditEvent.action.like(_like_escape(action[:-1]) + "%", escape="\\"))
        else:
            q = q.filter(AuditEvent.action == action)
    if actor:
        actor = actor.strip()
        q = q.filter(or_(
            AuditEvent.actor_id == actor,
            AuditEvent.actor_email.ilike("%" + _like_escape(actor) + "%", escape="\\"),
        ))
    if status:
        q = q.filter(AuditEvent.status == status)
    if target_type:
        q = q.filter(AuditEvent.target_type == target_type)
    if target_id:
        q = q.filter(AuditEvent.target_id == target_id[:36])
    if since:
        q = q.filter(AuditEvent.created_at >= since)
    if until:
        q = q.filter(AuditEvent.created_at <= until)
    return q


@router.get("", response_model=AuditListResponse)
def list_audit_log(
    action: Optional[str] = Query(None, max_length=64, description="Exact action, or a prefix ending in * (e.g. auth.*)"),
    actor: Optional[str] = Query(None, max_length=255, description="User id or part of an email"),
    status: Optional[str] = Query(None, max_length=20),
    target_type: Optional[str] = Query(None, max_length=40),
    target_id: Optional[str] = Query(None, max_length=128),
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    db: Session = Depends(get_db),
):
    org_id = _require_org(current_user)
    q = _filtered(db, org_id, action, actor, status, target_type, target_id, since, until)
    total = q.count()
    rows = (
        q.order_by(AuditEvent.created_at.desc(), AuditEvent.seq.desc())
        .offset(offset).limit(limit).all()
    )
    return {"items": [_entry(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/actions")
def list_actions(
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    db: Session = Depends(get_db),
):
    org_id = _require_org(current_user)
    rows = (
        db.query(AuditEvent.action)
        .filter(AuditEvent.organization_id == org_id)
        .distinct().order_by(AuditEvent.action.asc()).limit(500).all()
    )
    return {"actions": [r[0] for r in rows]}


@router.get("/verify")
def verify_audit_log(
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    db: Session = Depends(get_db),
):
    """Re-compute the chain and report whether any entry was changed or removed."""
    org_id = _require_org(current_user)
    result = verify_chain(db, org_id)
    result["verified_at"] = _ts(datetime.now(timezone.utc))
    return result


_CSV_COLUMNS = [
    "seq", "created_at", "action", "status", "actor_email", "actor_id", "actor_type",
    "target_type", "target_id", "ip_address", "user_agent", "request_id", "detail", "id", "hash",
]


def _csv_safe(value) -> str:
    """Stop spreadsheet apps from running a cell as a formula."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def _stream(rows: Iterator[dict], fmt: str) -> Iterator[str]:
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_CSV_COLUMNS)
        yield buf.getvalue()
        for row in rows:
            buf.seek(0)
            buf.truncate(0)
            entry = dict(row)
            entry["detail"] = json.dumps(entry["detail"], sort_keys=True, ensure_ascii=False)
            writer.writerow([_csv_safe(entry[c]) for c in _CSV_COLUMNS])
            yield buf.getvalue()
    else:
        for row in rows:
            yield json.dumps(row, ensure_ascii=False) + "\n"


@router.get("/export")
def export_audit_log(
    format: str = Query("csv", pattern="^(csv|jsonl)$"),
    action: Optional[str] = Query(None, max_length=64),
    actor: Optional[str] = Query(None, max_length=255),
    status: Optional[str] = Query(None, max_length=20),
    target_type: Optional[str] = Query(None, max_length=40),
    target_id: Optional[str] = Query(None, max_length=36),
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    db: Session = Depends(get_db),
):
    """Download the filtered log, oldest first. Exporting is itself recorded."""
    org_id = _require_org(current_user)
    q = _filtered(db, org_id, action, actor, status, target_type, target_id, since, until)
    total = q.count()
    rows = (
        q.order_by(AuditEvent.created_at.asc(), AuditEvent.seq.asc())
        .limit(EXPORT_MAX_ROWS).all()
    )
    # Read the rows out before log_event commits (a commit expires them).
    entries = [_entry(r) for r in rows]
    filters = {k: v for k, v in {
        "action": action, "actor": actor, "status": status, "target_type": target_type,
        "target_id": target_id, "since": since, "until": until,
    }.items() if v}
    log_event(
        db,
        action="audit.export",
        organization_id=org_id,
        actor_id=current_user.id,
        target_type="audit_log",
        detail={"format": format, "rows": len(entries), "filters": filters},
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    media = "text/csv; charset=utf-8" if format == "csv" else "application/x-ndjson"
    headers = {
        "Content-Disposition": f'attachment; filename="audit-log-{stamp}.{format}"',
        "X-Total-Count": str(total),
        "X-Truncated": "true" if total > len(entries) else "false",
        "Cache-Control": "no-store",
    }
    return StreamingResponse(_stream(iter(entries), format), media_type=media, headers=headers)
