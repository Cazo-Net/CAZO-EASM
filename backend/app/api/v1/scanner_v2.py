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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.core.permissions import require_permission, Permission

router = APIRouter()


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
    current_user: User = Depends(require_permission(Permission.VIEW_SCAN)),
):
    """Execute a v2 scanner pipeline scan.

    Runs the full enterprise EASM pipeline: asset discovery → DNS intelligence →
    network intelligence → technology fingerprinting → certificate analysis →
    risk evaluation → graph mapping.
    """
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan failed: {str(e)}",
        )

    return ScanV2Response(
        success=True,
        domain=request.domain,
        subdomains=result.get("assets", {}).get("subdomains", {}).get("discovered_subdomains", [])
            if isinstance(result.get("assets", {}).get("subdomains"), dict)
            else [],
        risk_score=result.get("risk_score", {}),
        graph=result.get("graph", {}),
        scanner_status=result.get("pipeline", {}).get("summary", {})
            if isinstance(result.get("pipeline"), dict) else {},
        pipeline_summary=result.get("pipeline", {}).get("summary", {})
            if isinstance(result.get("pipeline"), dict) else {},
        errors=result.get("pipeline", {}).get("errors", [])
            if isinstance(result.get("pipeline"), dict) else [],
    )


# ── WebSocket streaming endpoint ──

@router.websocket("/scan/stream")
async def scan_stream_v2(websocket: WebSocket):
    """Real-time v2 scan progress via WebSocket.

    Connect with a JSON message containing the scan config:
    {"domain": "example.com", "scan_type": "full"}

    Receive progress messages:
    {"type": "progress", "stage": "asset_discovery", "progress": 0.1, "message": "..."}
    {"type": "stage_complete", "stage": "asset_discovery", "duration_ms": 1234}
    {"type": "complete", "result": {...}}
    {"type": "error", "message": "..."}
    """
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

    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── Monitoring endpoints ──

_monitor_store: Dict[str, Dict[str, Any]] = {}


@router.post("/monitor", response_model=MonitorResponse)
async def create_monitor(
    request: MonitorCreateRequest,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
):
    """Create a continuous monitoring schedule for a domain."""
    import uuid

    monitor_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)

    schedule = {
        "id": monitor_id,
        "domain": request.domain,
        "interval_hours": request.interval_hours,
        "scan_type": request.scan_type,
        "enabled": request.enabled,
        "created_at": now.isoformat(),
        "last_run": None,
        "next_run": now.isoformat(),
        "created_by": current_user.id,
    }

    _monitor_store[monitor_id] = schedule

    return MonitorResponse(**{k: v for k, v in schedule.items() if k != "created_by"})


@router.get("/monitor", response_model=List[MonitorResponse])
async def list_monitors(
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
):
    """List all monitoring schedules."""
    user_schedules = [
        s for s in _monitor_store.values()
        if s.get("created_by") == current_user.id
    ]
    return [MonitorResponse(**{k: v for k, v in s.items() if k != "created_by"}) for s in user_schedules]


@router.delete("/monitor/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: str,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
):
    """Delete a monitoring schedule."""
    schedule = _monitor_store.get(monitor_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")
    if schedule.get("created_by") != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    del _monitor_store[monitor_id]


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
    answer = await analyst.analyze(request.question, scan_data)

    return AIAnalystResponse(
        domain=request.domain,
        question=request.question,
        answer=answer,
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


@router.post("/schedule", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleCreateRequest,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
):
    """Create a scheduled scan that runs automatically."""
    import uuid
    from app.services.scan_scheduler import get_scheduler, ScheduleConfig

    schedule_id = str(uuid.uuid4())[:12]
    config = ScheduleConfig(
        id=schedule_id,
        domain=request.domain,
        interval_hours=request.interval_hours,
        scan_type=request.scan_type,
        enabled=request.enabled,
        created_by=current_user.id,
        organization_id=getattr(current_user, "organization_id", None),
    )

    scheduler = get_scheduler()
    scheduler.add_schedule(config)

    return ScheduleResponse(
        id=schedule_id,
        domain=request.domain,
        interval_hours=request.interval_hours,
        scan_type=request.scan_type,
        enabled=request.enabled,
    )


@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules(
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
):
    """List all scheduled scans."""
    from app.services.scan_scheduler import get_scheduler

    scheduler = get_scheduler()
    schedules = [
        ScheduleResponse(
            id=c.id,
            domain=c.domain,
            interval_hours=c.interval_hours,
            scan_type=c.scan_type,
            enabled=c.enabled,
        )
        for c in scheduler._schedules.values()
        if c.created_by == current_user.id
    ]
    return schedules


@router.delete("/schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN)),
):
    """Delete a scheduled scan."""
    from app.services.scan_scheduler import get_scheduler

    scheduler = get_scheduler()
    config = scheduler._schedules.get(schedule_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    if config.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    scheduler.remove_schedule(schedule_id)
