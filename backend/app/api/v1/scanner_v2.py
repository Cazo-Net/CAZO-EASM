"""Scanner v2 API routes — enterprise EASM pipeline endpoints.

Exposes the v2 scanner framework via REST API + WebSocket streaming:
- POST /scan — Execute a full or quick scan
- WS /scan/stream — Real-time pipeline progress via WebSocket
- GET /health — Scanner health checks
- GET /plugins — List available scanner plugins
- POST /monitor — Create monitoring schedule
- GET /monitor — List monitoring schedules
- DELETE /monitor/{id} — Delete a monitoring schedule
- POST /analyze — AI security analyst query
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.core.permissions import require_permission, Permission
from app.services.audit import log_user_action

router = APIRouter()

logger = logging.getLogger(__name__)


# ── Request / Response schemas ──

class ScanV2Request(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255, description="Target domain")
    scan_type: str = Field(
        default="full",
        description="Scan type: 'full' or 'quick'",
    )
    max_subdomains: int = Field(default=0, ge=0, description="0 = unlimited")
    port_mode: str = Field(default="full", description="'full' or 'quick'")
    timeout: int = Field(default=30, ge=5, le=120)
    included_scanners: Optional[List[str]] = Field(
        default=None,
        description="Only run these scanner names",
    )
    excluded_scanners: Optional[List[str]] = Field(
        default=None,
        description="Skip these scanner names",
    )


class ScanV2Response(BaseModel):
    success: bool
    domain: str
    scan_engine: str = "v2"
    subdomains: List[str] = []
    risk_score: Dict[str, Any] = {}
    graph: Dict[str, Any] = {}
    scanner_status: Dict[str, str] = {}
    pipeline_summary: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []


class MonitorCreateRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)
    interval_hours: int = Field(default=24, ge=1, le=720)
    scan_type: str = Field(default="quick")
    enabled: bool = True


class MonitorResponse(BaseModel):
    id: str
    domain: str
    interval_hours: int
    scan_type: str
    enabled: bool
    created_at: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None


class AIAnalystRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)
    question: str = Field(..., min_length=1, max_length=2000)
    scan_data: Optional[Dict[str, Any]] = None


class AIAnalystResponse(BaseModel):
    domain: str
    question: str
    answer: str
    generated_at: str


class HealthResponse(BaseModel):
    status: str
    engine: str = "v2"
    registered_scanners: List[Dict[str, Any]]
    pipeline_stages: List[str]
    version: str = "2.0.0"


# ── Endpoints ──

@router.get("/health", response_model=HealthResponse)
async def scanner_health():
    """Health check — returns registered v2 scanner plugins and pipeline stages."""
    from app.scanners.v2.registry import registry
    from app.scanners.v2.pipeline import PipelineStage

    plugins = []
    for p in registry.all():
        plugins.append({
            "name": p.name,
            "version": p.version,
            "category": p.category.value,
            "priority": p.priority.name,
        })

    return HealthResponse(
        status="healthy",
        registered_scanners=plugins,
        pipeline_stages=[s.value for s in PipelineStage],
    )


@router.get("/plugins")
async def list_plugins():
    """List all registered v2 scanner plugins with metadata."""
    from app.scanners.v2.registry import registry

    plugins = []
    for p in registry.all():
        plugins.append({
            "name": p.name,
            "version": p.version,
            "category": p.category.value,
            "priority": p.priority.name,
            "scanner_class": p.scanner_cls.__name__,
        })

    return {
        "total": len(plugins),
        "plugins": plugins,
    }


@router.post("/scan", response_model=ScanV2Response)
async def run_scan_v2(
    request: ScanV2Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
):
    """Execute a v2 scanner pipeline scan.

    Runs the full enterprise EASM pipeline: asset discovery → DNS intelligence →
    network intelligence → technology fingerprinting → certificate analysis →
    risk evaluation → graph mapping.
    """
    import asyncio
    from app.billing.entitlements import check_root_domain_allowed, check_scan_allowed, record_adhoc_scan
    from app.core.scope import authorize_scan_target

    # Plan allowance before scope auto-registration (HTTP 402 if over).
    check_root_domain_allowed(db, current_user.organization_id, request.domain)
    auth = await asyncio.to_thread(
        authorize_scan_target, db, current_user.organization_id, request.domain,
        actor_id=current_user.id,
    )
    if not auth.authorized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=auth.as_error_detail())
    request.domain = auth.target

    # Ad-hoc v2 scans count toward the monthly quota like any other scan.
    check_scan_allowed(db, current_user.organization_id, request.domain)
    record_adhoc_scan(db, current_user.organization_id, current_user.id, request.domain, request.scan_type)

    from app.scanners.v2.runner import EnhancedScanRunner

    runner = EnhancedScanRunner()

    config = {
        "timeout": request.timeout,
        "max_subdomains": request.max_subdomains,
        "top_ports": [80, 443, 8080, 8443, 22, 21, 25, 53, 3306, 5432],
    }

    try:
        if request.scan_type == "quick":
            result = await runner.run_quick_scan(
                domain=request.domain,
                config=config,
            )
        else:
            result = await runner.run_scan(
                domain=request.domain,
                config=config,
                included_scanners=set(request.included_scanners) if request.included_scanners else None,
                excluded_scanners=set(request.excluded_scanners) if request.excluded_scanners else None,
            )
    except Exception:
        logger.exception("Scan failed for domain %s", request.domain)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scan failed",
        )

    # Extract subdomains — handle both list and dict formats
    subs_raw = result.get("assets", {}).get("subdomains", [])
    if isinstance(subs_raw, dict):
        subdomains = subs_raw.get("discovered_subdomains", sorted(subs_raw.keys()))
    elif isinstance(subs_raw, list):
        subdomains = subs_raw
    else:
        subdomains = []

    # Extract scanner status from pipeline stages
    pipeline_data = result.get("pipeline", {})
    scanner_status = {}
    stages = pipeline_data.get("stages", {}) if isinstance(pipeline_data, dict) else {}
    for stage_name, stage_data in stages.items():
        if isinstance(stage_data, dict):
            total = stage_data.get("total_scanners", 0)
            succeeded = stage_data.get("successful", 0)
            failed = stage_data.get("failed", 0)
            if total == 0:
                scanner_status[stage_name] = "skipped"
            elif failed == 0:
                scanner_status[stage_name] = "ok"
            else:
                scanner_status[stage_name] = f"partial ({succeeded}/{total})"

    return ScanV2Response(
        success=True,
        domain=request.domain,
        subdomains=subdomains,
        risk_score=result.get("risk_score", {}),
        graph=result.get("graph", {}),
        scanner_status=scanner_status,
        pipeline_summary=pipeline_data.get("summary", {})
            if isinstance(pipeline_data, dict) else {},
        errors=pipeline_data.get("errors", [])
            if isinstance(pipeline_data, dict) else [],
    )


# ── WebSocket streaming endpoint ──

@router.websocket("/scan/stream")
async def scan_stream_v2(websocket: WebSocket):
    """Real-time v2 scan progress via WebSocket.

    Connect with a token query parameter for authentication:
    ws://host/ws/scan/stream?token=<jwt>

    Then send a JSON message containing the scan config:
    {"domain": "example.com", "scan_type": "full"}

    Receive progress messages:
    {"type": "progress", "stage": "asset_discovery", "progress": 0.1, "message": "..."}
    {"type": "stage_complete", "stage": "asset_discovery", "duration_ms": 1234}
    {"type": "complete", "result": {...}}
    {"type": "error", "message": "..."}
    """
    # Authenticate via query parameter token
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Authentication required: provide ?token=<jwt>"})
        await websocket.close()
        return

    from app.core.security import decode_token
    payload = decode_token(token)
    if not payload or payload.get("type", "access") != "access":
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Invalid or expired token"})
        await websocket.close()
        return

    # Same checks as the HTTP API: active user, current token version,
    # permission to create scans, and the organization's authorized scope.
    import app.database as _database
    from app.core.permissions import check_custom_permission

    ws_db = _database.SessionLocal()
    try:
        ws_user = ws_db.query(User).filter(User.id == payload.get("sub")).first()
        token_tv = payload.get("tv")
        if (
            not ws_user or not ws_user.is_active
            or (token_tv is not None and token_tv != (ws_user.token_version or 0))
        ):
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "Invalid or expired token"})
            await websocket.close()
            return
        if not check_custom_permission(ws_user.role, Permission.CREATE_SCAN, ws_db, ws_user.organization_id):
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "You do not have permission to run scans"})
            await websocket.close()
            return
        ws_org_id, ws_user_id = ws_user.organization_id, ws_user.id
    finally:
        ws_db.close()

    await websocket.accept()

    try:
        raw = await websocket.receive_text()
        config = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid JSON"})
        await websocket.close()
        return
    except WebSocketDisconnect:
        return

    domain = config.get("domain", "")
    scan_type = config.get("scan_type", "full")
    timeout = config.get("timeout", 30)

    if not domain:
        await websocket.send_json({"type": "error", "message": "domain is required"})
        await websocket.close()
        return

    import asyncio
    from app.billing.entitlements import (
        PlanLimitExceeded, check_root_domain_allowed, check_scan_allowed, record_adhoc_scan,
    )
    from app.core.scope import authorize_scan_target

    ws_db = _database.SessionLocal()
    try:
        try:
            check_root_domain_allowed(ws_db, ws_org_id, domain)
            auth = await asyncio.to_thread(
                authorize_scan_target, ws_db, ws_org_id, domain, actor_id=ws_user_id,
            )
            if auth.authorized:
                # Same plan rules as the REST endpoint; counts toward the monthly quota.
                check_scan_allowed(ws_db, ws_org_id, auth.target)
                record_adhoc_scan(ws_db, ws_org_id, ws_user_id, auth.target, scan_type)
        except PlanLimitExceeded as exc:
            await websocket.send_json({"type": "error", "message": exc.message, "detail": exc.as_detail()})
            await websocket.close()
            return
    finally:
        ws_db.close()
    if not auth.authorized:
        await websocket.send_json({"type": "error", "message": auth.reason, "detail": auth.as_error_detail()})
        await websocket.close()
        return
    domain = auth.target
    try:
        timeout = max(5, min(int(timeout), 120))
    except (TypeError, ValueError):
        timeout = 30

    from app.scanners.v2.runner import EnhancedScanRunner
    from app.scanners.v2.pipeline import PipelineStage

    runner = EnhancedScanRunner()
    pipeline_config = {
        "timeout": timeout,
        "top_ports": [80, 443, 8080, 8443, 22, 21, 25, 53, 3306, 5432],
    }

    async def _progress_callback(stage: str, message: str, progress: float, metadata: dict = None):
        try:
            await websocket.send_json({
                "type": "progress",
                "stage": stage,
                "progress": round(progress, 3),
                "message": message,
            })
        except Exception:
            pass

    try:
        if scan_type == "quick":
            essential_stages = [
                PipelineStage.ASSET_DISCOVERY,
                PipelineStage.DNS_INTELLIGENCE,
                PipelineStage.NETWORK_INTELLIGENCE,
            ]
            from app.scanners.v2.pipeline import ScanPipeline
            pipeline = ScanPipeline(stages=essential_stages, config=pipeline_config)
            pipeline_result = await pipeline.execute(
                target=domain,
                config=pipeline_config,
                progress_callback=_progress_callback,
            )
            all_data = pipeline_result.get_all_data()
            from app.scanners.v2.risk_engine import risk_engine
            risk_result = risk_engine.calculate(all_data)
            result = {
                "domain": domain,
                "scan_type": "quick",
                "pipeline": pipeline_result.to_dict(),
                "risk_score": risk_result,
                "assets": all_data,
            }
        else:
            result = await runner.run_scan(
                domain=domain,
                config=pipeline_config,
                progress_callback=_progress_callback,
            )

        await websocket.send_json({
            "type": "complete",
            "result": {
                "domain": domain,
                "scan_type": scan_type,
                "risk_score": result.get("risk_score", {}),
                "pipeline_summary": result.get("pipeline", {}).get("summary", {})
                    if isinstance(result.get("pipeline"), dict) else {},
            },
        })

    except Exception:
        try:
            await websocket.send_json({"type": "error", "message": "Scan failed"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── Monitoring endpoints ──


@router.post("/monitor", response_model=MonitorResponse)
async def create_monitor(
    request: MonitorCreateRequest,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
    db: Session = Depends(get_db),
):
    """Create a continuous monitoring schedule for a domain."""
    import asyncio
    from app.core.scope import authorize_scan_target
    from app.scanners.v2.monitoring import monitor as v2_monitor, MonitorScheduleData
    from app.billing.entitlements import check_root_domain_allowed, check_schedule_allowed

    check_root_domain_allowed(db, current_user.organization_id, request.domain)
    auth = await asyncio.to_thread(
        authorize_scan_target, db, current_user.organization_id, request.domain,
        actor_id=current_user.id,
    )
    if not auth.authorized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=auth.as_error_detail())
    request.domain = auth.target
    # Monitors are schedules too: root-domain allowance and plan frequency (HTTP 402).
    check_schedule_allowed(db, current_user.organization_id, auth.target, request.interval_hours)

    schedule_data = MonitorScheduleData(
        interval_hours=request.interval_hours,
        enabled=request.enabled,
    )
    result = v2_monitor.add_target(
        db,
        domain=request.domain,
        user_id=current_user.id,
        organization_id=getattr(current_user, "organization_id", None),
        schedule=schedule_data,
        scan_type=request.scan_type,
    )
    db.commit()
    return MonitorResponse(
        id=result["id"],
        domain=result["domain"],
        interval_hours=result["interval_hours"],
        scan_type=request.scan_type,
        enabled=request.enabled,
        created_at=datetime.now(timezone.utc).isoformat(),
        last_run=None,
        next_run=None,
    )


@router.get("/monitor", response_model=List[MonitorResponse])
async def list_monitors(
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
    db: Session = Depends(get_db),
):
    """List all monitoring schedules for the current user's org."""
    from app.scanners.v2.monitoring import monitor as v2_monitor

    if not current_user.organization_id:
        return []
    rows = v2_monitor.list_targets(db, organization_id=current_user.organization_id)
    return [
        MonitorResponse(
            id=r["id"],
            domain=r["domain"],
            interval_hours=r["interval_hours"],
            scan_type=r["scan_type"],
            enabled=r["enabled"],
            created_at=r["created_at"] or datetime.now(timezone.utc).isoformat(),
            last_run=r["last_run_at"],
            next_run=r["next_run_at"],
        )
        for r in rows
    ]


@router.delete("/monitor/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: str,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
    db: Session = Depends(get_db),
):
    """Delete a monitoring schedule."""
    from app.scanners.v2.monitoring import monitor as v2_monitor

    removed = v2_monitor.remove_target(db, monitor_id, organization_id=current_user.organization_id or "")
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")
    db.commit()


# ── AI Analyst endpoint ──

@router.post("/analyze", response_model=AIAnalystResponse)
async def ai_analyze(
    request: AIAnalystRequest,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
):
    """AI security analyst — answer natural language questions about a domain's attack surface."""
    from app.scanners.v2.ai_analyst import SecurityAnalyst

    analyst = SecurityAnalyst()

    scan_data = request.scan_data or {}
    raw_answer = analyst.answer_question(request.question, scan_data)

    # answer_question() may return a dict with "answer" key or a plain string
    if isinstance(raw_answer, dict):
        answer_text = raw_answer.get("answer", str(raw_answer))
    else:
        answer_text = str(raw_answer)

    return AIAnalystResponse(
        domain=request.domain,
        question=request.question,
        answer=answer_text,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Scheduler endpoints ──

class ScheduleCreateRequest(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)
    interval_hours: int = Field(default=24, ge=1, le=720)
    scan_type: str = Field(default="quick")
    enabled: bool = True


class ScheduleResponse(BaseModel):
    id: str
    domain: str
    interval_hours: int
    scan_type: str
    enabled: bool


def _schedule_out(row) -> "ScheduleResponse":
    return ScheduleResponse(
        id=row.id,
        domain=row.domain,
        interval_hours=row.interval_hours,
        scan_type=row.scan_type,
        enabled=bool(row.enabled),
    )


@router.post("/schedule", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleCreateRequest,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
    db: Session = Depends(get_db),
):
    """Create a scheduled scan that runs automatically.

    Schedules are stored in the database and run by scan workers, which
    create a normal scan (with saved results) each time one is due. The
    first run happens on the next scheduler tick (about a minute).
    """
    import asyncio
    import uuid
    from app.core.scope import authorize_scan_target
    from app.models.v2_scanner import MonitorSchedule
    from app.billing.entitlements import check_root_domain_allowed

    check_root_domain_allowed(db, current_user.organization_id, request.domain)
    auth = await asyncio.to_thread(
        authorize_scan_target, db, current_user.organization_id, request.domain,
        actor_id=current_user.id,
    )
    if not auth.authorized:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=auth.as_error_detail())

    # Plan allowance: root domains and scan frequency (HTTP 402 if over).
    from app.billing.entitlements import check_schedule_allowed
    check_schedule_allowed(db, current_user.organization_id, auth.target, request.interval_hours)

    now = datetime.now(timezone.utc)
    row = MonitorSchedule(
        id=str(uuid.uuid4()),
        domain=auth.target,
        interval_hours=request.interval_hours,
        scan_type=request.scan_type if request.scan_type in ("quick", "full") else "quick",
        enabled=request.enabled,
        created_by=current_user.id,
        organization_id=current_user.organization_id,
        next_run_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    log_user_action(db, current_user, "scan.schedule.create", "schedule", row.id, {
        "domain": row.domain, "interval_hours": row.interval_hours,
    })
    return _schedule_out(row)


@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules(
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
    db: Session = Depends(get_db),
):
    """List the organization's active scheduled scans."""
    from app.models.v2_scanner import MonitorSchedule

    if not current_user.organization_id:
        return []
    rows = (
        db.query(MonitorSchedule)
        .filter(
            MonitorSchedule.organization_id == current_user.organization_id,
            MonitorSchedule.enabled.is_(True),
        )
        .order_by(MonitorSchedule.created_at.desc())
        .all()
    )
    return [_schedule_out(r) for r in rows]


@router.delete("/schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
    db: Session = Depends(get_db),
):
    """Stop a scheduled scan (it is disabled, not deleted, to keep its history)."""
    from app.models.v2_scanner import MonitorSchedule

    row = (
        db.query(MonitorSchedule)
        .filter(
            MonitorSchedule.id == schedule_id,
            MonitorSchedule.organization_id == (current_user.organization_id or ""),
            MonitorSchedule.enabled.is_(True),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    row.enabled = False
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    log_user_action(db, current_user, "scan.schedule.delete", "schedule", schedule_id, {"domain": row.domain})
