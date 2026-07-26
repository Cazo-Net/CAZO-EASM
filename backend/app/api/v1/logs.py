"""Platform logs API — admin-only read endpoints + client-error ingestion.

The read endpoints are restricted to platform admins (role == "admin" or "superuser")
and provide the data for the admin panel Logs tab.  The client-error endpoint is
public (no auth) so the frontend ErrorBoundary can POST errors without needing to
pass a token — the endpoint is intentionally open but rate-limited by the existing
middleware.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.platform_log import PlatformLog
from app.api.deps import get_current_user
from app.services.platform_log import log_client_error

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class LogSummary(BaseModel):
    errors_24h: int = 0
    security_24h: int = 0
    total_24h: int = 0
    orgs_active_24h: int = 0
    top_error_types: List[dict] = []
    critical_events: List[dict] = []


class LogRow(BaseModel):
    id: str
    category: str
    severity: str
    message: str
    detail: Optional[dict] = None
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    client_ip: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    created_at: str


class ClientErrorRequest(BaseModel):
    message: str
    stack: Optional[str] = None
    component_stack: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /logs/summary — dashboard cards
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=LogSummary)
async def get_log_summary(
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    now = datetime.now(timezone.utc)
    cutoff_24h = now.replace(hour=0, minute=0, second=0, microsecond=0)

    base_24h = db.query(PlatformLog).filter(PlatformLog.created_at >= cutoff_24h)

    errors_24h = base_24h.filter(
        PlatformLog.severity.in_(["error", "critical"])
    ).count()

    security_24h = base_24h.filter(
        PlatformLog.category == "security_event"
    ).count()

    total_24h = base_24h.count()

    orgs_active_24h = db.query(func.count(func.distinct(PlatformLog.organization_id))).filter(
        PlatformLog.created_at >= cutoff_24h,
        PlatformLog.organization_id.isnot(None),
    ).scalar() or 0

    # Top error types (by message prefix, first 50 chars)
    top_errors = (
        db.query(PlatformLog.message, func.count(PlatformLog.id).label("cnt"))
        .filter(
            PlatformLog.created_at >= cutoff_24h,
            PlatformLog.severity.in_(["error", "critical"]),
        )
        .group_by(PlatformLog.message)
        .order_by(desc("cnt"))
        .limit(5)
        .all()
    )

    # Critical events (last 24h, limit 10)
    critical_rows = (
        db.query(PlatformLog)
        .filter(
            PlatformLog.created_at >= cutoff_24h,
            PlatformLog.severity == "critical",
        )
        .order_by(desc(PlatformLog.created_at))
        .limit(10)
        .all()
    )

    return LogSummary(
        errors_24h=errors_24h,
        security_24h=security_24h,
        total_24h=total_24h,
        orgs_active_24h=orgs_active_24h,
        top_error_types=[{"message": m, "count": c} for m, c in top_errors],
        critical_events=[
            {
                "id": r.id,
                "category": r.category,
                "message": r.message,
                "created_at": str(r.created_at),
            }
            for r in critical_rows
        ],
    )


# ---------------------------------------------------------------------------
# GET /logs/ — filtered, paginated log list
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[LogRow])
async def list_platform_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    category: Optional[str] = None,
    severity: Optional[str] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    search: Optional[str] = None,
    hours: Optional[int] = Query(None, ge=1, le=720),
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    q = db.query(PlatformLog)

    if category:
        q = q.filter(PlatformLog.category == category)
    if severity:
        q = q.filter(PlatformLog.severity == severity)
    if organization_id:
        q = q.filter(PlatformLog.organization_id == organization_id)
    if user_id:
        q = q.filter(PlatformLog.user_id == user_id)
    if search:
        q = q.filter(PlatformLog.message.ilike(f"%{search}%"))
    if hours:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = q.filter(PlatformLog.created_at >= cutoff)

    rows = q.order_by(desc(PlatformLog.created_at)).offset(skip).limit(limit).all()

    return [
        LogRow(
            id=r.id,
            category=r.category,
            severity=r.severity,
            message=r.message,
            detail=r.detail,
            organization_id=r.organization_id,
            user_id=r.user_id,
            request_id=r.request_id,
            client_ip=r.client_ip,
            path=r.path,
            method=r.method,
            status_code=r.status_code,
            duration_ms=r.duration_ms,
            related_entity_type=r.related_entity_type,
            related_entity_id=r.related_entity_id,
            created_at=str(r.created_at),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /logs/{log_id} — single log detail
# ---------------------------------------------------------------------------

@router.get("/{log_id}", response_model=LogRow)
async def get_platform_log(
    log_id: str,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = db.query(PlatformLog).filter(PlatformLog.id == log_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Log entry not found")
    return LogRow(
        id=row.id,
        category=row.category,
        severity=row.severity,
        message=row.message,
        detail=row.detail,
        organization_id=row.organization_id,
        user_id=row.user_id,
        request_id=row.request_id,
        client_ip=row.client_ip,
        path=row.path,
        method=row.method,
        status_code=row.status_code,
        duration_ms=row.duration_ms,
        related_entity_type=row.related_entity_type,
        related_entity_id=row.related_entity_id,
        created_at=str(row.created_at),
    )


# ---------------------------------------------------------------------------
# POST /logs/client-error — frontend ErrorBoundary ingestion (no auth)
# ---------------------------------------------------------------------------

@router.post("/client-error")
async def ingest_client_error(
    body: ClientErrorRequest,
    request: Request,
):
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )

    log_client_error(
        message=body.message[:500],
        detail={
            "source": "client",
            "stack": body.stack,
            "component_stack": body.component_stack,
            "url": body.url,
            "user_agent": body.user_agent,
        },
        client_ip=client_ip,
    )
    return {"ok": True}
