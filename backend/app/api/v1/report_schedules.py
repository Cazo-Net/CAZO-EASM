"""Scheduled email reports API.

Every route works only on the caller's own organization and needs the
``manage_settings`` permission (owner and administrator by default).

- GET    /report-schedules               — schedules, limits and whether email is set up
- POST   /report-schedules               — add one
- PUT    /report-schedules/{id}          — change one
- DELETE /report-schedules/{id}          — remove one
- POST   /report-schedules/{id}/send-now — email a copy to the caller only
- GET    /report-schedules/{id}/preview.pdf — download the PDF the next email would carry
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.models.report_schedule import ReportSchedule
from app.models.user import User
from app.services import scheduled_reports as reports
from app.services.audit import log_user_action

router = APIRouter()


class ScheduleCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=80)
    frequency: str = Field("weekly", max_length=10)
    weekday: int = 0
    day_of_month: int = 1
    hour: int = 8
    timezone: str = Field("UTC", max_length=64)
    recipients: List[str] = Field(default_factory=list)
    include_pdf: bool = True
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=80)
    frequency: Optional[str] = Field(None, max_length=10)
    weekday: Optional[int] = None
    day_of_month: Optional[int] = None
    hour: Optional[int] = None
    timezone: Optional[str] = Field(None, max_length=64)
    recipients: Optional[List[str]] = None
    include_pdf: Optional[bool] = None
    enabled: Optional[bool] = None


class ScheduleOut(BaseModel):
    id: str
    name: str
    frequency: str
    weekday: int
    day_of_month: int
    hour: int
    timezone: str
    recipients: List[str]
    include_pdf: bool
    enabled: bool
    description: str
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None


def _org_id(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="Create or join an organization first.")
    return user.organization_id


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    # SQLite hands back naive datetimes; they are stored in UTC.
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _out(row: ReportSchedule) -> ScheduleOut:
    return ScheduleOut(
        id=row.id, name=row.name, frequency=row.frequency, weekday=row.weekday,
        day_of_month=row.day_of_month, hour=row.hour, timezone=row.timezone,
        recipients=list(row.recipients or []), include_pdf=bool(row.include_pdf), enabled=bool(row.enabled),
        description=reports.describe(row),
        next_run_at=_utc(row.next_run_at) if row.enabled else None,
        last_run_at=_utc(row.last_run_at), last_status=row.last_status, last_error=row.last_error,
        created_at=_utc(row.created_at),
    )


def _get(db: Session, org_id: str, schedule_id: str) -> ReportSchedule:
    row = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.id == schedule_id, ReportSchedule.organization_id == org_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Report schedule not found.")
    return row


def _validate(frequency: str, weekday: int, day_of_month: int, hour: int, tz: str) -> None:
    if frequency not in ("weekly", "monthly"):
        raise HTTPException(status_code=422, detail="Frequency must be weekly or monthly.")
    if not 0 <= weekday <= 6:
        raise HTTPException(status_code=422, detail="Weekday must be 0 (Monday) to 6 (Sunday).")
    if not 1 <= day_of_month <= 28:
        raise HTTPException(status_code=422, detail="Day of month must be 1 to 28.")
    if not 0 <= hour <= 23:
        raise HTTPException(status_code=422, detail="Hour must be 0 to 23.")
    if not reports.is_valid_zone(tz):
        raise HTTPException(status_code=422, detail="Unknown time zone.")


def _recipients(values: List[str]) -> List[str]:
    try:
        cleaned = reports.clean_recipients(values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not cleaned:
        raise HTTPException(status_code=422, detail="Add at least one recipient.")
    return cleaned


def _name(value: Optional[str], frequency: str) -> str:
    name = " ".join((value or "").split())[:80]
    return name or ("Monthly security report" if frequency == "monthly" else "Weekly security report")


@router.get("")
def list_schedules(
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    rows = (
        db.query(ReportSchedule).filter(ReportSchedule.organization_id == org_id)
        .order_by(ReportSchedule.created_at.asc()).all()
    )
    return {
        "schedules": [_out(r) for r in rows],
        "email_configured": reports.email_configured(),
        "max_schedules": reports.MAX_SCHEDULES_PER_ORG,
        "max_recipients": reports.MAX_RECIPIENTS,
        "your_email": current_user.email,
    }


@router.post("", status_code=201, response_model=ScheduleOut)
def create_schedule(
    payload: ScheduleCreate,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    org_id = _org_id(current_user)
    _validate(payload.frequency, payload.weekday, payload.day_of_month, payload.hour, payload.timezone)
    recipients = _recipients(payload.recipients)
    count = db.query(ReportSchedule).filter(ReportSchedule.organization_id == org_id).count()
    if count >= reports.MAX_SCHEDULES_PER_ORG:
        raise HTTPException(
            status_code=409, detail=f"An organization can have at most {reports.MAX_SCHEDULES_PER_ORG} report schedules.")
    row = ReportSchedule(
        organization_id=org_id, created_by=current_user.id, name=_name(payload.name, payload.frequency),
        frequency=payload.frequency, weekday=payload.weekday, day_of_month=payload.day_of_month,
        hour=payload.hour, timezone=payload.timezone, recipients=recipients,
        include_pdf=payload.include_pdf, enabled=payload.enabled,
        next_run_at=reports.compute_next_run(
            payload.frequency, payload.weekday, payload.day_of_month, payload.hour, payload.timezone),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_user_action(db, current_user, "report_schedule.create", target_type="report_schedule", target_id=row.id,
                    detail={"name": row.name, "frequency": row.frequency, "recipients": len(recipients)})
    return _out(row)


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    row = _get(db, _org_id(current_user), schedule_id)
    data = payload.model_dump(exclude_unset=True)
    frequency = data.get("frequency") or row.frequency
    weekday = data["weekday"] if data.get("weekday") is not None else row.weekday
    day = data["day_of_month"] if data.get("day_of_month") is not None else row.day_of_month
    hour = data["hour"] if data.get("hour") is not None else row.hour
    tz = data.get("timezone") or row.timezone
    _validate(frequency, weekday, day, hour, tz)
    if data.get("recipients") is not None:
        row.recipients = _recipients(data["recipients"])
    if "name" in data:
        row.name = _name(data["name"], frequency)
    if data.get("include_pdf") is not None:
        row.include_pdf = data["include_pdf"]
    if data.get("enabled") is not None:
        row.enabled = data["enabled"]
    row.frequency, row.weekday, row.day_of_month, row.hour, row.timezone = frequency, weekday, day, hour, tz
    # Any edit re-plans the next send from now, so a re-enabled schedule never fires for a time already past.
    row.next_run_at = reports.compute_next_run(frequency, weekday, day, hour, tz)
    db.commit()
    db.refresh(row)
    log_user_action(db, current_user, "report_schedule.update", target_type="report_schedule", target_id=row.id,
                    detail={"changed": sorted(data.keys())})
    return _out(row)


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    row = _get(db, _org_id(current_user), schedule_id)
    name = row.name
    db.delete(row)
    db.commit()
    log_user_action(db, current_user, "report_schedule.delete", target_type="report_schedule", target_id=schedule_id,
                    detail={"name": name})
    return {"deleted": True}


@router.post("/{schedule_id}/send-now")
def send_now(
    schedule_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    """Email one copy to the caller, so they can see the report without mailing the whole list."""
    row = _get(db, _org_id(current_user), schedule_id)
    if not reports.allow_manual_send(row.organization_id):
        raise HTTPException(status_code=429, detail="Too many test sends. Try again in a few minutes.")
    result = reports.send_report(db, row, only_to=current_user.email)
    log_user_action(db, current_user, "report_schedule.send_now", target_type="report_schedule", target_id=row.id,
                    status="success" if result["status"] == "sent" else "failure")
    return {"status": result["status"], "sent_to": current_user.email, "error": result.get("error")}


@router.get("/{schedule_id}/preview.pdf")
def preview_pdf(
    schedule_id: str,
    current_user: User = Depends(require_permission(Permission.MANAGE_SETTINGS)),
    db: Session = Depends(get_db),
):
    row = _get(db, _org_id(current_user), schedule_id)
    start, end = reports.period_for(row.frequency, datetime.now(timezone.utc))
    summary = reports.build_summary(db, row.organization_id, start, end)
    pdf = reports.render_pdf(summary, row.timezone, row.frequency)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="cazo-security-report-preview.pdf"',
        "Cache-Control": "no-store",
    })
