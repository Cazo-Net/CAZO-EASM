"""Organization integrations API: Slack, Microsoft Teams, Jira, Splunk.

Every route works only on the caller's own organization and needs the
``manage_webhooks`` permission (owner and administrator by default).
Credentials are write-only: responses carry ``has_secret`` and a short
destination hint, never the stored values.

- GET    /integrations/catalog   — available types, their fields and events
- GET    /integrations           — the organization's integrations
- POST   /integrations           — add one
- PUT    /integrations/{id}      — change one (blank secret = keep stored)
- DELETE /integrations/{id}      — remove one
- POST   /integrations/{id}/test — send a test (Jira: check access, no issue)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import secret_box
from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.integration import IntegrationDelivery, OrgIntegration
from app.models.user import User
from app.services import integration_delivery as delivery
from app.services.audit import log_user_action

router = APIRouter()


class IntegrationCreate(BaseModel):
    kind: str = Field(..., max_length=20)
    name: Optional[str] = Field(None, max_length=80)
    settings: Dict[str, Any] = Field(default_factory=dict)
    event_types: Optional[List[str]] = None
    enabled: bool = True


class IntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=80)
    settings: Optional[Dict[str, Any]] = None
    event_types: Optional[List[str]] = None
    enabled: Optional[bool] = None


class IntegrationOut(BaseModel):
    id: str
    kind: str
    name: str
    enabled: bool
    settings: Dict[str, Any]
    has_secret: bool
    credentials_readable: bool
    destination: str
    event_types: List[str]
    failure_count: int
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None


def _org_id(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="Create or join an organization first.")
    return user.organization_id


def _secrets(row: OrgIntegration) -> Optional[Dict[str, Any]]:
    try:
        return secret_box.decrypt(row.secret_encrypted)
    except secret_box.SecretUnreadable:
        return None


def _out(row: OrgIntegration) -> IntegrationOut:
    secrets = _secrets(row)
    return IntegrationOut(
        id=row.id,
        kind=row.kind,
        name=row.name,
        enabled=bool(row.enabled),
        settings=dict(row.config or {}),  # non-secret settings only
        has_secret=bool(row.secret_encrypted),
        credentials_readable=secrets is not None,
        destination=delivery.destination_hint(row.kind, row.config or {}, secrets or {}),
        event_types=list(row.event_types or []),
        failure_count=row.failure_count or 0,
        last_success_at=row.last_success_at,
        last_failure_at=row.last_failure_at,
        last_error=row.last_error,
        created_at=row.created_at,
    )


def _get(db: Session, org_id: str, integration_id: str) -> OrgIntegration:
    row = (
        db.query(OrgIntegration)
        .filter(OrgIntegration.id == integration_id, OrgIntegration.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Integration not found.")
    return row


def _name(value: Optional[str], kind: str) -> str:
    name = " ".join((value or "").split())
    return name[:80] or delivery.KINDS[kind]["label"]


@router.get("/catalog")
def catalog(current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS))):
    return {
        "kinds": [
            {"kind": k, "label": v["label"], "description": v["description"],
             "fields": v["fields"], "default_events": v["default_events"]}
            for k, v in delivery.KINDS.items()
        ],
        "events": [{"type": k, "label": v} for k, v in delivery.EVENTS.items()],
        "max_per_organization": delivery.MAX_PER_ORG,
    }


@router.get("", response_model=List[IntegrationOut])
def list_integrations(
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    rows = (
        db.query(OrgIntegration)
        .filter(OrgIntegration.organization_id == org_id)
        .order_by(OrgIntegration.created_at.asc())
        .all()
    )
    return [_out(r) for r in rows]


@router.post("", response_model=IntegrationOut, status_code=201)
def create_integration(
    body: IntegrationCreate,
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    if body.kind not in delivery.KINDS:
        raise HTTPException(status_code=400, detail="Unknown integration type.")
    count = db.query(OrgIntegration).filter(OrgIntegration.organization_id == org_id).count()
    if count >= delivery.MAX_PER_ORG:
        raise HTTPException(status_code=400, detail=f"You can have up to {delivery.MAX_PER_ORG} integrations.")
    try:
        config, secrets = delivery.validate_settings(body.kind, body.settings)
        events = delivery.validate_events(body.kind, body.event_types)
    except delivery.IntegrationConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    row = OrgIntegration(
        organization_id=org_id,
        created_by=current_user.id,
        kind=body.kind,
        name=_name(body.name, body.kind),
        enabled=body.enabled,
        config=config,
        secret_encrypted=secret_box.encrypt(secrets),
        event_types=events,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    out = _out(row)
    log_user_action(db, current_user, "integration.create", "integration", out.id, {
        "kind": out.kind, "name": out.name, "destination": out.destination, "event_types": out.event_types,
    })
    return out


@router.put("/{integration_id}", response_model=IntegrationOut)
def update_integration(
    integration_id: str,
    body: IntegrationUpdate,
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    row = _get(db, org_id, integration_id)
    changed: List[str] = []
    try:
        if body.settings is not None:
            config, secrets = delivery.validate_settings(row.kind, body.settings, _secrets(row) or {})
            row.config = config
            row.secret_encrypted = secret_box.encrypt(secrets)
            changed.append("settings")
        if body.event_types is not None:
            row.event_types = delivery.validate_events(row.kind, body.event_types)
            changed.append("event_types")
    except delivery.IntegrationConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    if body.name is not None:
        row.name = _name(body.name, row.kind)
        changed.append("name")
    if body.enabled is not None and body.enabled != bool(row.enabled):
        row.enabled = body.enabled
        changed.append("enabled")
        if body.enabled:
            row.failure_count = 0  # a fresh start after an automatic switch-off
    db.commit()
    db.refresh(row)
    out = _out(row)
    log_user_action(db, current_user, "integration.update", "integration", out.id, {
        "kind": out.kind, "name": out.name, "updated_fields": changed, "enabled": out.enabled,
    })
    return out


@router.delete("/{integration_id}", status_code=204)
def delete_integration(
    integration_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    row = _get(db, org_id, integration_id)
    kind, name = row.kind, row.name
    db.query(IntegrationDelivery).filter(IntegrationDelivery.integration_id == row.id).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    log_user_action(db, current_user, "integration.delete", "integration", integration_id, {"kind": kind, "name": name})


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_WEBHOOKS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    row = _get(db, org_id, integration_id)
    secrets = _secrets(row)
    if secrets is None:
        raise HTTPException(status_code=400, detail="Stored credentials can no longer be read. Please enter them again.")
    result = await delivery.send_once(row.kind, dict(row.config or {}), secrets, delivery.test_message())
    delivery.record_result(row, result)
    db.commit()
    log_user_action(db, current_user, "integration.test", "integration", integration_id, {
        "kind": row.kind, "result": "ok" if result.ok else "failed",
    }, status="success" if result.ok else "failure")
    return {"success": result.ok, "error": None if result.ok else result.error}
