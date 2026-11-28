"""Dark web & threat intelligence API.

Everything returned here is either:

* real data from a named source (each finding has ``source`` and a
  ``reference_url``), or
* sample data from ``/sample``, which is flagged ``is_sample: true`` at the
  top level and on every record, uses reserved example domains, and is never
  stored or mixed with real findings.

Sources that need a key or subscription the operator has not configured are
reported as ``not_configured`` by ``/sources``; they never return results.

Monitors and findings are scoped to the caller's organization, and monitors
can only be created for domains in the organization's authorized scope.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import Permission, require_any_permission
from app.database import get_db
from app.models.threat_intel import ThreatIntelFinding, ThreatIntelMonitor
from app.models.user import User
from app.services import threat_intel as ti

router = APIRouter()

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _org(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=400, detail="No organization linked to your account")
    return user.organization_id


def _monitor_dict(m: ThreatIntelMonitor, counts: Optional[dict] = None) -> dict:
    return {
        "id": m.id, "kind": m.kind, "value": m.value,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "last_checked_at": m.last_checked_at.isoformat() if m.last_checked_at else None,
        "last_status": m.last_status or {},
        "open_findings": (counts or {}).get(m.id, 0),
    }


def _finding_dict(f: ThreatIntelFinding) -> dict:
    return {
        "id": f.id, "is_sample": False, "monitor_id": f.monitor_id,
        "source": f.source, "category": f.category, "subject": f.subject,
        "title": f.title, "summary": f.summary, "severity": f.severity,
        "reference_url": f.reference_url, "observed_at": f.observed_at,
        "data": f.data or {}, "status": f.status, "times_seen": f.times_seen,
        "first_seen": f.first_seen.isoformat() if f.first_seen else None,
        "last_seen": f.last_seen.isoformat() if f.last_seen else None,
    }


def _get_monitor(db: Session, org_id: str, monitor_id: str) -> ThreatIntelMonitor:
    m = (db.query(ThreatIntelMonitor)
         .filter(ThreatIntelMonitor.id == monitor_id, ThreatIntelMonitor.organization_id == org_id)
         .first())
    if not m:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return m


# ── Sources ────────────────────────────────────────────────────────────


@router.get("/sources")
async def list_sources():
    """Which sources are connected, which need a key, and which need a subscription."""
    return {"sources": ti.source_catalog()}


# ── Monitors ───────────────────────────────────────────────────────────


class MonitorCreate(BaseModel):
    kind: Literal["domain", "email"]
    value: str = Field(..., min_length=3, max_length=320)


@router.get("/monitors")
async def list_monitors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _org(current_user)
    monitors = (db.query(ThreatIntelMonitor)
                .filter(ThreatIntelMonitor.organization_id == org_id)
                .order_by(ThreatIntelMonitor.created_at.desc()).all())
    counts: dict = {}
    for (mid,) in (db.query(ThreatIntelFinding.monitor_id)
                   .filter(ThreatIntelFinding.organization_id == org_id,
                           ThreatIntelFinding.status == "open").all()):
        counts[mid] = counts.get(mid, 0) + 1
    return {"monitors": [_monitor_dict(m, counts) for m in monitors], "total": len(monitors)}


@router.post("/monitors", status_code=201)
async def create_monitor(
    body: MonitorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(Permission.MANAGE_ASSETS, Permission.CREATE_SCAN)),
):
    org_id = _org(current_user)
    ok, value, reason = await run_in_threadpool(ti.authorize_monitor_value, db, org_id, body.kind, body.value)
    if not ok:
        raise HTTPException(status_code=403 if value else 400, detail=reason)
    existing = (db.query(ThreatIntelMonitor)
                .filter(ThreatIntelMonitor.organization_id == org_id,
                        ThreatIntelMonitor.kind == body.kind, ThreatIntelMonitor.value == value)
                .first())
    if existing:
        raise HTTPException(status_code=409, detail="That is already being monitored.")
    if db.query(ThreatIntelMonitor).filter(ThreatIntelMonitor.organization_id == org_id).count() >= ti.MAX_MONITORS_PER_ORG:
        raise HTTPException(status_code=400, detail=f"You can monitor at most {ti.MAX_MONITORS_PER_ORG} items.")
    m = ThreatIntelMonitor(organization_id=org_id, kind=body.kind, value=value,
                           created_by=current_user.id, last_status={})
    db.add(m)
    db.commit()
    db.refresh(m)
    try:
        from app.services.audit import log_event
        log_event(db, action="threat_intel.monitor.create", organization_id=org_id, actor_id=current_user.id,
                  target_type="threat_intel_monitor", target_id=m.id, detail={"kind": m.kind, "value": m.value})
    except Exception:  # noqa: BLE001 - auditing must not block the request
        db.rollback()
    return _monitor_dict(m)


@router.delete("/monitors/{monitor_id}", status_code=204)
async def delete_monitor(
    monitor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(Permission.MANAGE_ASSETS, Permission.CREATE_SCAN)),
):
    org_id = _org(current_user)
    m = _get_monitor(db, org_id, monitor_id)
    db.query(ThreatIntelFinding).filter(ThreatIntelFinding.organization_id == org_id,
                                        ThreatIntelFinding.monitor_id == m.id).delete()
    db.delete(m)
    db.commit()
    return None


@router.post("/monitors/{monitor_id}/check")
async def check_monitor(
    monitor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(Permission.MANAGE_ASSETS, Permission.CREATE_SCAN)),
):
    """Query every source for this monitor now and store the results."""
    org_id = _org(current_user)
    m = _get_monitor(db, org_id, monitor_id)
    result = await run_in_threadpool(ti.run_monitor, db, m, False)
    db.refresh(m)
    return {"monitor": _monitor_dict(m), **result}


# ── Findings ───────────────────────────────────────────────────────────


@router.get("/findings")
async def list_findings(
    monitor_id: Optional[str] = None,
    status: Optional[Literal["open", "acknowledged", "resolved"]] = None,
    category: Optional[str] = Query(None, max_length=40),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _org(current_user)
    q = db.query(ThreatIntelFinding).filter(ThreatIntelFinding.organization_id == org_id)
    if monitor_id:
        q = q.filter(ThreatIntelFinding.monitor_id == monitor_id)
    if status:
        q = q.filter(ThreatIntelFinding.status == status)
    if category:
        q = q.filter(ThreatIntelFinding.category == category)
    rows = q.order_by(ThreatIntelFinding.last_seen.desc()).limit(1000).all()
    rows.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))
    return {"is_sample": False, "findings": [_finding_dict(f) for f in rows], "total": len(rows)}


class FindingUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]


@router.patch("/findings/{finding_id}")
async def update_finding(
    finding_id: str,
    body: FindingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(Permission.MANAGE_ASSETS, Permission.CREATE_SCAN)),
):
    org_id = _org(current_user)
    f = (db.query(ThreatIntelFinding)
         .filter(ThreatIntelFinding.id == finding_id, ThreatIntelFinding.organization_id == org_id)
         .first())
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    f.status = body.status
    db.commit()
    return _finding_dict(f)


# ── Exploited vulnerabilities (CISA KEV + FIRST EPSS) ─────────────────


@router.get("/exploited")
async def exploited_vulnerabilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Known-exploited vulnerabilities that match this organization's scan results."""
    org_id = _org(current_user)
    return await run_in_threadpool(ti.exploited_for_org, db, org_id)


# ── Sample data (clearly labelled, never stored) ──────────────────────


@router.get("/sample")
async def sample_data():
    return {"is_sample": True, "notice": ti.SAMPLE_NOTICE, "findings": ti.sample_findings()}
