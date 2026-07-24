from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.vulnerability import Vulnerability, FindingHistory, FindingEvidence
from app.schemas.evidence import (
    VulnerabilityResponse,
    FindingDetailResponse,
    FindingUpdateRequest,
    FindingHistoryAddRequest,
    FindingEvidenceAddRequest,
    FindingSummaryResponse,
    FindingListResponse,
    FindingHistoryEntry,
    FindingEvidenceItem,
)
from app.api.deps import get_current_user
import uuid

router = APIRouter()


def _org_filter(db: Session, user: User):
    """Vulnerabilities are org-scoped. Superusers see all."""
    if getattr(user, "role", None) == "superuser":
        return db.query(Vulnerability)
    return db.query(Vulnerability).filter(Vulnerability.organization_id == user.organization_id)


def _record_history(
    db: Session,
    vuln: Vulnerability,
    actor: User,
    action: str,
    old_value=None,
    new_value=None,
    note: Optional[str] = None,
):
    entry = FindingHistory(
        id=str(uuid.uuid4()),
        vulnerability_id=vuln.id,
        organization_id=vuln.organization_id or actor.organization_id or "",
        actor_id=actor.id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        note=note,
    )
    db.add(entry)
    return entry


@router.get("", response_model=FindingListResponse)
async def list_findings(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    fingerprint: Optional[str] = Query(None, description="Group by fingerprint"),
    scan_id: Optional[str] = Query(None, description="Filter by scan"),
    search: Optional[str] = Query(None, description="Search host/name/template"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List vulnerabilities (findings) with Evidence Center filters."""
    query = _org_filter(db, current_user)

    if status:
        query = query.filter(Vulnerability.status == status)
    if severity:
        query = query.filter(Vulnerability.severity == severity)
    if fingerprint:
        query = query.filter(Vulnerability.fingerprint == fingerprint)
    if scan_id:
        query = query.filter(Vulnerability.scan_id == scan_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Vulnerability.host.ilike(like))
            | (Vulnerability.name.ilike(like))
            | (Vulnerability.template_id.ilike(like))
        )

    total = query.count()
    findings = (
        query.order_by(Vulnerability.found_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return FindingListResponse(
        findings=[VulnerabilityResponse.model_validate(f) for f in findings],
        total=total,
    )


@router.get("/summary", response_model=FindingSummaryResponse)
async def findings_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summary counts by status and severity, plus new/stale indicators."""
    query = _org_filter(db, current_user)
    all_findings = query.all()

    by_status: dict = {}
    by_severity: dict = {}
    new_count = 0
    stale_count = 0

    for f in all_findings:
        by_status[f.status] = by_status.get(f.status, 0) + 1
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        if f.first_seen and f.last_seen:
            if f.first_seen == f.last_seen:
                new_count += 1
            else:
                stale_count += 1

    return FindingSummaryResponse(
        total=len(all_findings),
        by_status=by_status,
        by_severity=by_severity,
        new_count=new_count,
        stale_count=stale_count,
    )


@router.get("/{finding_id}", response_model=FindingDetailResponse)
async def get_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single finding with history, evidence, and confirming scans."""
    vuln = _org_filter(db, current_user).filter(Vulnerability.id == finding_id).first()
    if not vuln:
        raise HTTPException(status_code=404, detail="Finding not found")

    history = (
        db.query(FindingHistory)
        .filter(FindingHistory.vulnerability_id == vuln.id)
        .order_by(FindingHistory.created_at.desc())
        .all()
    )
    evidence = (
        db.query(FindingEvidence)
        .filter(FindingEvidence.vulnerability_id == vuln.id)
        .order_by(FindingEvidence.captured_at.desc())
        .all()
    )

    # Confirming scans: all rows sharing this fingerprint
    confirming_scans = []
    if vuln.fingerprint:
        siblings = (
            db.query(Vulnerability)
            .filter(
                Vulnerability.fingerprint == vuln.fingerprint,
                Vulnerability.id != vuln.id,
            )
            .all()
        )
        for s in siblings:
            confirming_scans.append({
                "scan_id": s.scan_id,
                "found_at": s.found_at,
                "host": s.host,
            })

    return FindingDetailResponse(
        **VulnerabilityResponse.model_validate(vuln).model_dump(),
        history=[FindingHistoryEntry.model_validate(h) for h in history],
        evidence=[FindingEvidenceItem.model_validate(e) for e in evidence],
        confirming_scans=confirming_scans,
    )


@router.patch("/{finding_id}", response_model=VulnerabilityResponse)
async def update_finding(
    finding_id: str,
    payload: FindingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update finding status / assignment. Records an audit history entry."""
    vuln = _org_filter(db, current_user).filter(Vulnerability.id == finding_id).first()
    if not vuln:
        raise HTTPException(status_code=404, detail="Finding not found")

    if payload.status is not None:
        old = vuln.status
        vuln.status = payload.status.value
        vuln.last_seen = datetime.utcnow()
        _record_history(
            db, vuln, current_user,
            action="status_change",
            old_value={"status": old},
            new_value={"status": vuln.status},
            note=payload.note,
        )

    if payload.assigned_to is not None:
        old = vuln.assigned_to
        vuln.assigned_to = payload.assigned_to
        _record_history(
            db, vuln, current_user,
            action="assignment_change",
            old_value={"assigned_to": old},
            new_value={"assigned_to": vuln.assigned_to},
            note=payload.note,
        )

    db.commit()
    db.refresh(vuln)
    return VulnerabilityResponse.model_validate(vuln)


@router.post("/{finding_id}/history", response_model=FindingHistoryEntry)
async def add_history(
    finding_id: str,
    payload: FindingHistoryAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a manual note / annotation to a finding."""
    vuln = _org_filter(db, current_user).filter(Vulnerability.id == finding_id).first()
    if not vuln:
        raise HTTPException(status_code=404, detail="Finding not found")

    entry = _record_history(
        db, vuln, current_user,
        action=payload.action,
        old_value=payload.old_value,
        new_value=payload.new_value,
        note=payload.note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return FindingHistoryEntry.model_validate(entry)


@router.post("/{finding_id}/evidence", response_model=FindingEvidenceItem)
async def add_evidence(
    finding_id: str,
    payload: FindingEvidenceAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach an evidence artifact to a finding."""
    vuln = _org_filter(db, current_user).filter(Vulnerability.id == finding_id).first()
    if not vuln:
        raise HTTPException(status_code=404, detail="Finding not found")

    item = FindingEvidence(
        id=str(uuid.uuid4()),
        vulnerability_id=vuln.id,
        organization_id=vuln.organization_id or current_user.organization_id or "",
        evidence_type=payload.evidence_type.value,
        content=payload.content,
        captured_by=current_user.id,
        scanner_id=payload.scanner_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return FindingEvidenceItem.model_validate(item)
