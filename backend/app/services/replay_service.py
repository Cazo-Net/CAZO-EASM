"""Service layer for the Exposure Replay feature.

Builds timeline snapshots, scan-to-scan diffs, and per-scan exposure
metrics from real persisted data (Scan, Subdomain, Port, Vulnerability,
RiskScore, AssetChange). Designed to be robust when data is partial.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, or_

from app.models.scan import Scan
from app.models.asset import Subdomain
from app.models.port import Port
from app.models.vulnerability import Vulnerability
from app.models.risk import RiskScore
from app.models.asset_change import AssetChange
from app.schemas.replay import (
    ReplaySnapshot,
    ReplayAssetSummary,
    ReplayChangeItem,
    ReplayChangesResponse,
    ReplayExposureResponse,
)


def _severity_counts(db: Session, scan_id: str) -> Tuple[int, int, int, int]:
    """Return (critical, high, medium, low) vulnerability counts for a scan."""
    rows = (
        db.query(Vulnerability.severity, sql_func.count(Vulnerability.id))
        .filter(Vulnerability.scan_id == scan_id)
        .group_by(Vulnerability.severity)
        .all()
    )
    counts = {str(r[0]).lower(): int(r[1]) for r in rows}
    return (
        counts.get("critical", 0),
        counts.get("high", 0),
        counts.get("medium", 0),
        counts.get("low", 0),
    )


def _subdomain_and_port_counts(db: Session, scan_id: str) -> Tuple[int, int]:
    sub_count = (
        db.query(sql_func.count(Subdomain.id))
        .filter(Subdomain.scan_id == scan_id)
        .scalar()
        or 0
    )
    port_count = (
        db.query(sql_func.count(Port.id))
        .join(Subdomain, Port.subdomain_id == Subdomain.id)
        .filter(Subdomain.scan_id == scan_id)
        .scalar()
        or 0
    )
    return int(sub_count), int(port_count)


def _risk_score(db: Session, scan_id: str) -> Optional[int]:
    risk = (
        db.query(RiskScore)
        .filter(RiskScore.scan_id == scan_id)
        .order_by(RiskScore.calculated_at.desc())
        .first()
    )
    return int(risk.overall_score) if risk and risk.overall_score is not None else None


def get_timeline(db: Session, org_id: str) -> List[ReplaySnapshot]:
    """One snapshot per completed scan for the organization, ordered by completed_at."""
    scans = (
        db.query(Scan)
        .filter(Scan.organization_id == org_id, Scan.status == "completed")
        .order_by(Scan.completed_at.asc())
        .all()
    )

    snapshots: List[ReplaySnapshot] = []
    for scan in scans:
        sub_count, port_count = _subdomain_and_port_counts(db, scan.id)
        crit, high, med, low = _severity_counts(db, scan.id)
        risk = _risk_score(db, scan.id)
        subdomains = (
            db.query(Subdomain)
            .filter(Subdomain.scan_id == scan.id)
            .all()
        )
        assets = [
            ReplayAssetSummary(
                id=s.id,
                hostname=s.hostname,
                ip_addresses=s.ip_addresses or [],
                technologies=[t.name for t in s.technologies] if s.technologies else [],
                exposure_score=0,
            )
            for s in subdomains
        ]
        snapshots.append(
            ReplaySnapshot(
                scan_id=scan.id,
                domain=scan.domain or "",
                started_at=scan.started_at.isoformat() if scan.started_at else None,
                completed_at=scan.completed_at.isoformat() if scan.completed_at else None,
                subdomain_count=int(sub_count),
                port_count=int(port_count),
                critical_count=crit,
                high_count=high,
                medium_count=med,
                low_count=low,
                overall_risk_score=risk,
                assets=assets,
            )
        )
    return snapshots


def get_changes(
    db: Session, org_id: str, from_scan_id: Optional[str], to_scan_id: Optional[str]
) -> ReplayChangesResponse:
    """Diff between two scans using persisted AssetChange records."""
    query = db.query(AssetChange).filter(AssetChange.organization_id == org_id)
    if to_scan_id:
        query = query.filter(AssetChange.to_scan_id == to_scan_id)
    if from_scan_id:
        query = query.filter(
            or_(AssetChange.from_scan_id == from_scan_id, AssetChange.from_scan_id.is_(None))
        )

    added: List[ReplayChangeItem] = []
    removed: List[ReplayChangeItem] = []
    modified: List[ReplayChangeItem] = []

    for ch in query.all():
        item = ReplayChangeItem(
            id=ch.id,
            change_type=ch.change_type,
            entity_type=ch.entity_type,
            entity_key=ch.entity_key,
            detail=ch.detail or {},
        )
        if ch.change_type == "added":
            added.append(item)
        elif ch.change_type == "removed":
            removed.append(item)
        elif ch.change_type == "modified":
            modified.append(item)

    summary = (
        f"Added {len(added)}, removed {len(removed)}, "
        f"modified {len(modified)} assets between scans."
    )
    return ReplayChangesResponse(
        from_scan_id=from_scan_id,
        to_scan_id=to_scan_id,
        added=added,
        removed=removed,
        modified=modified,
        summary=summary,
    )


def get_exposure(db: Session, org_id: str, scan_id: str) -> Optional[ReplayExposureResponse]:
    """Exposure metrics for a single scan."""
    scan = (
        db.query(Scan)
        .filter(Scan.id == scan_id, Scan.organization_id == org_id)
        .first()
    )
    if not scan:
        return None

    sub_count, port_count = _subdomain_and_port_counts(db, scan.id)
    crit, high, med, low = _severity_counts(db, scan.id)
    risk = _risk_score(db, scan.id)

    risk_breakdown: dict = {}
    if risk is not None:
        r = (
            db.query(RiskScore)
            .filter(RiskScore.scan_id == scan.id)
            .order_by(RiskScore.calculated_at.desc())
            .first()
        )
        if r:
            risk_breakdown = r.breakdown or {}

    return ReplayExposureResponse(
        scan_id=scan.id,
        domain=scan.domain or "",
        completed_at=scan.completed_at.isoformat() if scan.completed_at else None,
        total_assets=int(sub_count),
        subdomain_count=int(sub_count),
        port_count=int(port_count),
        certificate_count=0,
        technology_count=0,
        critical_count=crit,
        high_count=high,
        medium_count=med,
        low_count=low,
        overall_risk_score=risk,
        risk_breakdown=risk_breakdown,
    )
