"""Asset inventory API: deduplicated assets, their history and change alerts.

Everything here is scoped to ``current_user.organization_id``. Asset ids from
another organization answer 404, never 403, so ids cannot be probed.
"""
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.asset_change import AssetChange
from app.models.asset_inventory import Asset
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.services import inventory as inv
from app.services import inventory_alerts as alerts
from app.services.audit import log_event

router = APIRouter()

_SORTS = {
    "last_seen": Asset.last_seen,
    "first_seen": Asset.first_seen,
    "value": Asset.value,
    "type": Asset.asset_type,
}


def _org(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="No organization")
    return user.organization_id


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _asset_row(a: Asset, parents: Optional[Dict[str, Asset]] = None) -> Dict[str, Any]:
    parent = (parents or {}).get(a.parent_id) if a.parent_id else None
    return {
        "id": a.id,
        "type": a.asset_type,
        "value": a.value,
        "label": a.label or a.value,
        "state": a.state or "active",
        "is_alive": bool(a.is_alive),
        "root_domain": a.root_domain or None,
        "parent_id": a.parent_id,
        "parent": parent.value if parent is not None else None,
        "first_seen": _iso(a.first_seen),
        "last_seen": _iso(a.last_seen),
        "missing_since": _iso(a.missing_since),
        "last_scan_id": a.last_scan_id,
        "attributes": a.attributes or {},
    }


def _change_row(c: AssetChange) -> Dict[str, Any]:
    return {
        "id": c.id,
        "asset_id": c.asset_id,
        "event": c.event,
        "change_type": c.change_type,
        "entity_type": c.entity_type,
        "entity_key": c.entity_key,
        "severity": c.severity or "info",
        "summary": c.summary or f"{c.change_type} {c.entity_type} {c.entity_key}",
        "root_domain": c.root_domain,
        "detail": c.detail or {},
        "scan_id": c.to_scan_id if c.to_scan_id != "expiry-check" else None,
        "detected_at": _iso(c.detected_at),
    }


def _base_query(db: Session, org_id: str):
    return db.query(Asset).filter(
        Asset.organization_id == org_id, Asset.asset_type.in_(inv.INVENTORY_TYPES)
    )


@router.get("/summary")
async def inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ASSETS)),
):
    """Counts by kind, recent change, and the plan's host allowance."""
    org_id = _org(current_user)
    rows = (
        db.query(Asset.asset_type, Asset.state, func.count(Asset.id))
        .filter(Asset.organization_id == org_id, Asset.asset_type.in_(inv.INVENTORY_TYPES))
        .group_by(Asset.asset_type, Asset.state)
        .all()
    )
    by_type = {t: {"active": 0, "missing": 0} for t in inv.INVENTORY_TYPES}
    for asset_type, state, n in rows:
        by_type[asset_type]["missing" if state == "missing" else "active"] += n

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    new_7d = _base_query(db, org_id).filter(Asset.first_seen >= week_ago).count()
    changes_7d = (
        db.query(AssetChange)
        .filter(AssetChange.organization_id == org_id, AssetChange.event.isnot(None),
                AssetChange.detected_at >= week_ago)
        .count()
    )
    roots = [
        r[0] for r in db.query(Asset.value)
        .filter(Asset.organization_id == org_id, Asset.asset_type == "domain")
        .order_by(Asset.value.asc()).all()
    ]

    # Certificates inside the organization's warning window.
    threshold = inv._cert_expiry_days(db, org_id)
    now = datetime.now(timezone.utc)
    expiring = 0
    for (attrs,) in (
        db.query(Asset.attributes)
        .filter(Asset.organization_id == org_id, Asset.asset_type == "certificate",
                Asset.state == "active")
        .all()
    ):
        not_after = inv._parse_dt((attrs or {}).get("not_after"))
        if not_after is not None and (not_after - now).days <= threshold:
            expiring += 1

    limit = None
    plan_name = None
    if settings.BILLING_ENFORCE_LIMITS:
        try:
            from app.billing.entitlements import get_entitlement

            ent = get_entitlement(db, org_id)
            limit, plan_name = ent.limits.get("hosts"), ent.plan.name
        except Exception:  # noqa: BLE001
            pass
    hosts_used = inv.count_inventory_hosts(db, org_id)

    completed_scans = (
        db.query(Scan.id).filter(Scan.organization_id == org_id, Scan.status == "completed").count()
    )
    return {
        "by_type": by_type,
        "total_active": sum(v["active"] for v in by_type.values()),
        "total_missing": sum(v["missing"] for v in by_type.values()),
        "new_last_7_days": new_7d,
        "changes_last_7_days": changes_7d,
        "certificates_expiring": expiring,
        "cert_expiry_days": threshold,
        "root_domains": roots,
        "plan": {
            "name": plan_name,
            "hosts_limit": limit,
            "hosts_used": hosts_used,
            "at_limit": limit is not None and hosts_used >= limit,
        },
        # True when scans exist but none has been folded into the inventory yet.
        "needs_rebuild": completed_scans > 0 and not roots,
        "missing_after_scans": inv.MISSING_AFTER_SCANS,
    }


def _filtered(db: Session, org_id: str, asset_type, state, root, q, new_days):
    query = _base_query(db, org_id)
    if asset_type:
        if asset_type not in inv.INVENTORY_TYPES:
            raise HTTPException(status_code=422, detail="Unknown asset type")
        query = query.filter(Asset.asset_type == asset_type)
    if state == "active":
        query = query.filter(Asset.state != "missing")
    elif state == "missing":
        query = query.filter(Asset.state == "missing")
    elif state not in (None, "", "all"):
        raise HTTPException(status_code=422, detail="state must be active, missing or all")
    if root:
        query = query.filter(Asset.root_domain == root.strip().lower())
    if q:
        needle = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{needle}%"
        query = query.filter(or_(
            func.lower(Asset.value).like(like, escape="\\"),
            func.lower(Asset.label).like(like, escape="\\"),
        ))
    if new_days:
        query = query.filter(Asset.first_seen >= datetime.now(timezone.utc) - timedelta(days=new_days))
    return query


@router.get("/assets")
async def list_assets(
    type: Optional[str] = Query(None, description="domain|host|ip|service|certificate|technology"),
    state: Optional[str] = Query("active", description="active|missing|all"),
    root: Optional[str] = Query(None, description="Only assets under this root domain"),
    q: Optional[str] = Query(None, max_length=200),
    new_days: Optional[int] = Query(None, ge=1, le=365, description="First seen within N days"),
    sort: str = Query("last_seen"),
    order: str = Query("desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ASSETS)),
):
    """One row per asset, however many scans have seen it."""
    org_id = _org(current_user)
    query = _filtered(db, org_id, type, state, root, q, new_days)
    total = query.count()
    column = _SORTS.get(sort, Asset.last_seen)
    column = column.asc() if order == "asc" else column.desc()
    rows = query.order_by(column, Asset.id.asc()).offset(skip).limit(limit).all()

    parent_ids = {a.parent_id for a in rows if a.parent_id}
    parents = {
        p.id: p for p in db.query(Asset)
        .filter(Asset.organization_id == org_id, Asset.id.in_(parent_ids)).all()
    } if parent_ids else {}

    # Child counts for hosts (services / technologies currently active).
    host_ids = [a.id for a in rows if a.asset_type == "host"]
    child_counts: Dict[str, Dict[str, int]] = {}
    if host_ids:
        for parent_id, asset_type, n in (
            db.query(Asset.parent_id, Asset.asset_type, func.count(Asset.id))
            .filter(Asset.organization_id == org_id, Asset.parent_id.in_(host_ids),
                    Asset.state != "missing")
            .group_by(Asset.parent_id, Asset.asset_type)
            .all()
        ):
            child_counts.setdefault(parent_id, {})[asset_type] = n

    items = []
    for a in rows:
        row = _asset_row(a, parents)
        if a.asset_type == "host":
            counts = child_counts.get(a.id, {})
            row["services"] = counts.get("service", 0)
            row["technologies"] = counts.get("technology", 0)
        items.append(row)
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/assets/export")
async def export_assets(
    type: Optional[str] = None,
    state: Optional[str] = "active",
    root: Optional[str] = None,
    q: Optional[str] = Query(None, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ASSETS)),
):
    """CSV of the filtered inventory (up to 20,000 rows)."""
    org_id = _org(current_user)
    rows = (
        _filtered(db, org_id, type, state, root, q, None)
        .order_by(Asset.asset_type.asc(), Asset.value.asc())
        .limit(20000)
        .all()
    )

    def safe(value: Any) -> str:
        # Stop spreadsheet formula injection from scanned values.
        text = "" if value is None else str(value)
        return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["type", "asset", "root_domain", "state", "first_seen", "last_seen", "details"])
    for a in rows:
        attrs = a.attributes or {}
        if a.asset_type == "service":
            details = " ".join(x for x in (attrs.get("service"), attrs.get("product"), attrs.get("version")) if x)
        elif a.asset_type == "certificate":
            details = f"issuer={attrs.get('issuer') or ''} expires={attrs.get('not_after') or ''}"
        elif a.asset_type == "technology":
            details = attrs.get("version") or ""
        elif a.asset_type == "host":
            details = " ".join(attrs.get("ip_addresses") or [])
        else:
            details = ""
        writer.writerow([
            a.asset_type, safe(a.label if a.asset_type == "certificate" else a.value),
            safe(a.root_domain or ""), a.state or "active",
            _iso(a.first_seen) or "", _iso(a.last_seen) or "", safe(details),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="asset-inventory.csv"'},
    )


@router.get("/assets/{asset_id}")
async def get_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ASSETS)),
):
    """One asset with what belongs to it and its full history."""
    org_id = _org(current_user)
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.organization_id == org_id).first()
    if not asset or asset.asset_type not in inv.INVENTORY_TYPES:
        raise HTTPException(status_code=404, detail="Asset not found")

    parents: Dict[str, Asset] = {}
    if asset.parent_id:
        parent = db.query(Asset).filter(
            Asset.id == asset.parent_id, Asset.organization_id == org_id
        ).first()
        if parent:
            parents[parent.id] = parent

    children: List[Asset] = []
    if asset.asset_type == "host":
        children = (
            db.query(Asset)
            .filter(Asset.organization_id == org_id, Asset.parent_id == asset.id)
            .order_by(Asset.asset_type.asc(), Asset.value.asc())
            .limit(500)
            .all()
        )
        # Certificates can be shared by several hosts; find them by host name too.
        child_ids = {c.id for c in children}
        for cert in (
            db.query(Asset)
            .filter(Asset.organization_id == org_id, Asset.asset_type == "certificate",
                    Asset.root_domain == asset.root_domain)
            .all()
        ):
            if cert.id not in child_ids and asset.value in ((cert.attributes or {}).get("hosts") or []):
                children.append(cert)
    elif asset.asset_type == "domain":
        children = (
            db.query(Asset)
            .filter(Asset.organization_id == org_id, Asset.asset_type == "host",
                    Asset.root_domain == asset.value)
            .order_by(Asset.state.asc(), Asset.value.asc())
            .limit(500)
            .all()
        )

    child_ids = [c.id for c in children]
    history_filter = [AssetChange.asset_id == asset.id]
    if child_ids:
        history_filter.append(AssetChange.asset_id.in_(child_ids[:400]))
    history = (
        db.query(AssetChange)
        .filter(AssetChange.organization_id == org_id, AssetChange.event.isnot(None),
                or_(*history_filter))
        .order_by(AssetChange.detected_at.desc())
        .limit(200)
        .all()
    )

    findings: List[Dict[str, Any]] = []
    if asset.asset_type in ("host", "domain") and asset.last_scan_id:
        vulns = (
            db.query(Vulnerability)
            .join(Scan, Vulnerability.scan_id == Scan.id)
            .filter(Scan.organization_id == org_id, Vulnerability.scan_id == asset.last_scan_id)
        )
        if asset.asset_type == "host":
            vulns = vulns.filter(func.lower(Vulnerability.host) == asset.value)
        for v in vulns.limit(200).all():
            findings.append({
                "id": v.id, "name": v.name, "severity": (v.severity or "unknown").lower(),
                "host": v.host, "status": v.status, "scan_id": v.scan_id,
            })
        findings.sort(key=lambda f: -inv.SEVERITY_RANK.get(f["severity"], 0))

    return {
        "asset": _asset_row(asset, parents),
        "children": [_asset_row(c) for c in children],
        "history": [_change_row(c) for c in history],
        "findings": findings,
    }


@router.get("/changes")
async def list_changes(
    event: Optional[str] = Query(None, description="Event name, e.g. service_new"),
    alert: Optional[str] = Query(None, description="Alert type, e.g. new_service"),
    entity_type: Optional[str] = None,
    root: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=365),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ASSETS)),
):
    """History of inventory changes, newest first."""
    org_id = _org(current_user)
    query = db.query(AssetChange).filter(
        AssetChange.organization_id == org_id, AssetChange.event.isnot(None)
    )
    alert_events = {
        "new_asset": ("asset_new", "asset_reappeared"),
        "new_service": ("service_new",),
        "new_critical_finding": ("finding_new",),
        "certificate_expiring": ("cert_expiring",),
        "certificate_changed": ("cert_changed",),
        "asset_disappeared": ("asset_missing", "service_closed"),
    }
    if alert:
        if alert not in alert_events:
            raise HTTPException(status_code=422, detail="Unknown alert type")
        query = query.filter(AssetChange.event.in_(alert_events[alert]))
        if alert == "new_asset":
            query = query.filter(AssetChange.entity_type == "host")
    if event:
        query = query.filter(AssetChange.event == event)
    if entity_type:
        query = query.filter(AssetChange.entity_type == entity_type)
    if root:
        query = query.filter(AssetChange.root_domain == root.strip().lower())
    if days:
        query = query.filter(AssetChange.detected_at >= datetime.now(timezone.utc) - timedelta(days=days))
    total = query.count()
    rows = (
        query.order_by(AssetChange.detected_at.desc(), AssetChange.id.asc())
        .offset(skip).limit(limit).all()
    )
    return {"total": total, "skip": skip, "limit": limit, "items": [_change_row(c) for c in rows]}


# ── Alert settings ───────────────────────────────────────────────────────


class AlertRule(BaseModel):
    in_app: Optional[bool] = None
    email: Optional[bool] = None


class AlertSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    rules: Optional[Dict[str, AlertRule]] = None
    cert_expiry_days: Optional[int] = Field(None, ge=1, le=365)
    finding_min_severity: Optional[str] = None
    recipients: Optional[str] = None
    extra_emails: Optional[List[str]] = Field(None, max_length=alerts.MAX_EXTRA_EMAILS)


def _settings_response(db: Session, org_id: str, cfg: Dict[str, Any], can_edit: bool) -> Dict[str, Any]:
    return {
        **cfg,
        "alert_types": [
            {"key": k, "label": v["label"], "description": v["description"]}
            for k, v in alerts.ALERT_TYPES.items()
        ],
        "email_delivery": alerts.email_delivery_status(),
        "can_edit": can_edit,
        "max_extra_emails": alerts.MAX_EXTRA_EMAILS,
    }


@router.get("/alert-settings")
async def get_alert_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_ASSETS)),
):
    from app.core.permissions import check_custom_permission

    org_id = _org(current_user)
    can_edit = check_custom_permission(
        current_user.role, Permission.MANAGE_SETTINGS, db, current_user.organization_id
    )
    cfg = alerts.get_settings(db, org_id)
    if not can_edit:
        # Extra mailboxes are an admin detail; members only see that some exist.
        cfg["extra_emails"] = []
    return _settings_response(db, org_id, cfg, can_edit)


@router.put("/alert-settings")
async def update_alert_settings(
    body: AlertSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
):
    org_id = _org(current_user)
    payload = body.model_dump(exclude_none=True)
    try:
        cfg = alerts.save_settings(db, org_id, payload, current_user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    log_event(
        db, "inventory.alert_settings_updated", organization_id=org_id,
        actor_id=current_user.id, target_type="organization", target_id=org_id,
        detail={"fields": sorted(payload.keys())},
    )
    return _settings_response(db, org_id, cfg, True)


@router.post("/rebuild")
async def rebuild_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ASSETS)),
):
    """Fold past completed scans into the inventory. Sends no alerts."""
    org_id = _org(current_user)
    stats = inv.rebuild_from_history(db, org_id)
    log_event(
        db, "inventory.rebuilt", organization_id=org_id, actor_id=current_user.id,
        target_type="organization", target_id=org_id, detail=stats,
    )
    return stats
