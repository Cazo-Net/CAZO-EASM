"""Executive reporting API: aggregated org-level security summary."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.asset_inventory import Asset
from app.models.scan import Scan
from app.models.vulnerability import Vulnerability
from app.models.asset_score import AssetScore
from app.api.deps import get_current_user
from app.schemas.report_v2 import (
    ExecutiveReport, ExecAsset, ExecutiveReportRequest, ExecutiveReportGenerated,
)

router = APIRouter()


def _build_summary(
    db: Session, current_user: User, generated_at: Optional[datetime] = None
) -> ExecutiveReport:
    org_id = current_user.organization_id

    total_assets = db.query(Asset).filter(Asset.organization_id == org_id).count()

    # Scans are scoped directly by organization_id (created_by may be NULL for
    # system/orchestrated scans, so we must not infer org via the user join).
    total_scans = (
        db.query(Scan)
        .filter(Scan.organization_id == org_id)
        .count()
    )
    active_scans = (
        db.query(Scan)
        .filter(Scan.organization_id == org_id, Scan.status == "running")
        .count()
    )

    # Vulnerabilities are tied to scans; derive counts per severity.
    sev_rows = (
        db.query(Vulnerability.severity, func.count(Vulnerability.id))
        .join(Scan, Vulnerability.scan_id == Scan.id)
        .filter(Scan.organization_id == org_id)
        .group_by(Vulnerability.severity)
        .all()
    )
    sev_map = {s: c for s, c in sev_rows}
    critical_vulns = sev_map.get("critical", 0)
    high_vulns = sev_map.get("high", 0)
    medium_vulns = sev_map.get("medium", 0)
    low_vulns = sev_map.get("low", 0)

    # Top exposed assets.
    top_rows = (
        db.query(AssetScore)
        .filter(AssetScore.organization_id == org_id)
        .order_by(desc(AssetScore.exposure_score))
        .limit(5)
        .all()
    )
    top_exposed_assets: list[ExecAsset] = []
    if top_rows:
        asset_ids = [r.asset_id for r in top_rows]
        assets = db.query(Asset).filter(Asset.id.in_(asset_ids)).all() if asset_ids else []
        asset_cache = {a.id: a for a in assets}
        for r in top_rows:
            a = asset_cache.get(r.asset_id)
            top_exposed_assets.append(
                ExecAsset(
                    asset_id=r.asset_id,
                    value=a.value if a else None,
                    asset_type=a.asset_type if a else None,
                    exposure_score=float(r.exposure_score or 0.0),
                )
            )

    summary_text = (
        f"Your organization has {total_assets} discovered assets across "
        f"{total_scans} scans ({active_scans} currently active). "
        f"Detected vulnerabilities: {critical_vulns} critical, {high_vulns} high, "
        f"{medium_vulns} medium, {low_vulns} low. "
        f"{len(top_exposed_assets)} asset(s) are flagged as most exposed and require attention."
    )

    return ExecutiveReport(
        total_assets=total_assets,
        total_scans=total_scans,
        active_scans=active_scans,
        critical_vulns=critical_vulns,
        high_vulns=high_vulns,
        medium_vulns=medium_vulns,
        low_vulns=low_vulns,
        top_exposed_assets=top_exposed_assets,
        summary_text=summary_text,
        generated_at=generated_at,
    )


@router.get("", response_model=ExecutiveReport)
async def get_executive_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an aggregated executive summary for the organization."""
    return _build_summary(db, current_user)


@router.post("/generate", response_model=ExecutiveReportGenerated)
async def generate_executive_report(
    payload: ExecutiveReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate the executive report in the requested format.

    PDF/CSV heavy generation is intentionally not implemented server-side; the
    JSON payload is returned with a note so no heavy dependencies are required.
    """
    generated_at = datetime.utcnow()
    report = _build_summary(db, current_user, generated_at)

    note = None
    if payload.format != "json":
        note = (
            f"{payload.format.upper()} export is not generated server-side; "
            "the JSON payload is returned for client-side rendering/export."
        )

    return ExecutiveReportGenerated(
        **report.model_dump(),
        format=payload.format,
        note=note,
    )
