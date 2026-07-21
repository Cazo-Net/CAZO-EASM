from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.models.asset import Subdomain
from app.models.port import Port
from app.schemas.scan import ScanCreate, ScanResponse, ScanDetail
from app.services.scan_service import ScanService
from app.services.scan_dispatch import dispatch_scan
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.scanners.registry import discovery_manifest

router = APIRouter()


def _assert_scan_access(db: Session, scan: Optional[Scan], current_user: User) -> None:
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    org_id = current_user.organization_id
    # A scan is visible only if it belongs to the caller's organization (when
    # the caller has one) or was created by the caller. This blocks both
    # cross-tenant and cross-user access even when organization_id is unset.
    if org_id:
        if getattr(scan, "organization_id", None) != org_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    elif getattr(scan, "created_by", None) != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")


@router.post("", response_model=ScanResponse)
async def create_scan(
    scan_data: ScanCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CREATE_SCAN))
):
    """Create and start a new scan (authorized-scope enforced)."""
    service = ScanService(db)
    request_id = request.headers.get("x-request-id")

    try:
        scan = await service.create_scan(
            domain=scan_data.domain,
            user_id=current_user.id,
            scan_type=scan_data.scan_type.value if hasattr(scan_data.scan_type, 'value') else scan_data.scan_type,
            scan_options=scan_data.scan_options.model_dump() if scan_data.scan_options else None,
            project_id=scan_data.project_id,
            organization_id=current_user.organization_id,
            request_id=request_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    dispatch_scan(scan.id, background_tasks)

    return scan


@router.get("/discovery/plugins")
async def list_discovery_plugins(
    current_user: User = Depends(get_current_user),
):
    """List available discovery plugins (the pluggable scanner registry)."""
    return {"plugins": discovery_manifest()}


@router.get("/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard statistics."""
    from app.models.ssl import SSLCertificate
    from app.models.technology import Technology
    from app.models.dns import DNSRecord

    user_scan_ids = [s.id for s in db.query(Scan.id).filter(Scan.created_by == current_user.id).all()]

    if not user_scan_ids:
        return {
            "scans": 0, "subdomains": 0, "ports": 0, "vulnerabilities": 0,
            "running": 0, "completed": 0, "failed": 0,
            "ssl_certificates": 0, "technologies": 0, "dns_records": 0,
        }

    scans_total = len(user_scan_ids)
    running = db.query(Scan).filter(Scan.created_by == current_user.id, Scan.status == "running").count()
    completed = db.query(Scan).filter(Scan.created_by == current_user.id, Scan.status == "completed").count()
    failed = db.query(Scan).filter(Scan.created_by == current_user.id, Scan.status == "failed").count()
    subdomains = db.query(Subdomain).filter(Subdomain.scan_id.in_(user_scan_ids)).count()
    ports = db.query(Port).join(Subdomain).filter(Subdomain.scan_id.in_(user_scan_ids)).count()
    vulns = db.query(Vulnerability).filter(Vulnerability.scan_id.in_(user_scan_ids)).count()
    ssl_certs = db.query(SSLCertificate).join(Subdomain).filter(Subdomain.scan_id.in_(user_scan_ids)).count()
    techs = db.query(Technology).join(Subdomain).filter(Subdomain.scan_id.in_(user_scan_ids)).count()
    dns = db.query(DNSRecord).join(Subdomain).filter(Subdomain.scan_id.in_(user_scan_ids)).count()

    return {
        "scans": scans_total,
        "subdomains": subdomains,
        "ports": ports,
        "vulnerabilities": vulns,
        "running": running,
        "completed": completed,
        "failed": failed,
        "ssl_certificates": ssl_certs,
        "technologies": techs,
        "dns_records": dns,
    }


@router.get("", response_model=List[ScanResponse])
async def list_scans(
    skip: int = 0,
    limit: int = 20,
    scan_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List the caller's own scans (or the organization's when in an org)."""
    if current_user.organization_id:
        query = db.query(Scan).filter(Scan.organization_id == current_user.organization_id)
    else:
        query = db.query(Scan).filter(Scan.created_by == current_user.id)

    if scan_status:
        query = query.filter(Scan.status == scan_status)

    scans = query.order_by(Scan.created_at.desc()).offset(skip).limit(limit).all()
    return scans


@router.get("/importable", response_model=List[ScanResponse])
async def list_importable_scans(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List completed scans available for canvas import within the caller's org/user."""
    if current_user.organization_id:
        scope = Scan.organization_id == current_user.organization_id
    else:
        scope = Scan.created_by == current_user.id
    scans = (
        db.query(Scan)
        .filter(Scan.status == "completed")
        .filter(scope)
        .filter(Scan.organization_id == current_user.organization_id)
        .order_by(Scan.created_at.desc())
        .limit(limit)
        .all()
    )
    return scans


@router.get("/activity")
async def get_recent_activity(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent activity feed from scan history."""
    scans = (
        db.query(Scan)
        .filter(Scan.created_by == current_user.id)
        .order_by(Scan.created_at.desc())
        .limit(limit)
        .all()
    )

    events = []
    for scan in scans:
        status_val = scan.status.value if hasattr(scan.status, 'value') else scan.status
        created = scan.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - created
        seconds = int(diff.total_seconds())

        if seconds < 60:
            time_str = "Just now"
        elif seconds < 3600:
            time_str = f"{seconds // 60}m ago"
        elif seconds < 86400:
            time_str = f"{seconds // 3600}h ago"
        else:
            time_str = f"{seconds // 86400}d ago"

        if status_val == "completed":
            events.append({
                "type": "scan_completed",
                "description": f"Scan completed for {scan.domain}",
                "time": time_str,
                "scan_id": scan.id,
            })
        elif status_val == "running":
            events.append({
                "type": "scan_started",
                "description": f"Scan started for {scan.domain}",
                "time": time_str,
                "scan_id": scan.id,
            })
        elif status_val == "failed":
            events.append({
                "type": "scan_failed",
                "description": f"Scan failed for {scan.domain}",
                "time": time_str,
                "scan_id": scan.id,
            })

    return events


@router.get("/{scan_id}", response_model=ScanDetail)
async def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get scan details with results."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    _assert_scan_access(db, scan, current_user)
    service = ScanService(db)
    result = await service.get_scan_with_results(scan_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )

    scan = result["scan"]
    risk_score = result.get("risk_score")

    ports_count = db.query(Port).join(Subdomain).filter(Subdomain.scan_id == scan_id).count()

    vulns = db.query(Vulnerability).filter(Vulnerability.scan_id == scan_id).all()
    vuln_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for v in vulns:
        if v.severity in vuln_counts:
            vuln_counts[v.severity] += 1

    return ScanDetail(
        id=scan.id,
        domain=scan.domain,
        status=scan.status.value if hasattr(scan.status, 'value') else scan.status,
        progress=scan.progress,
        scan_type=scan.scan_type.value if hasattr(scan.scan_type, 'value') else scan.scan_type,
        scan_options=scan.scan_options,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        created_at=scan.created_at,
        subdomains_count=result.get("subdomains_count", 0),
        ports_count=ports_count,
        vulnerabilities_count=len(vulns),
        critical_count=vuln_counts["critical"],
        high_count=vuln_counts["high"],
        medium_count=vuln_counts["medium"],
        low_count=vuln_counts["low"],
        risk_score=risk_score.overall_score if risk_score else None,
        error_message=scan.error_message,
        scanner_status=scan.scanner_status if hasattr(scan, 'scanner_status') else None
    )


@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DELETE_SCAN))
):
    """Delete a scan."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    _assert_scan_access(db, scan, current_user)

    if scan.status.value == "running" if hasattr(scan.status, 'value') else scan.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running scan"
        )

    db.delete(scan)
    db.commit()

    return {"message": "Scan deleted successfully"}


@router.post("/{scan_id}/rerun", response_model=ScanResponse)
async def rerun_scan(
    scan_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.RERUN_SCAN))
):
    """Re-run a previous scan."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    _assert_scan_access(db, scan, current_user)

    service = ScanService(db)

    stored_options = None
    if scan.scan_options:
        try:
            import json
            stored_options = json.loads(scan.scan_options)
        except (json.JSONDecodeError, TypeError):
            pass

    new_scan = await service.create_scan(
        domain=scan.domain,
        user_id=current_user.id,
        scan_type=scan.scan_type.value if hasattr(scan.scan_type, 'value') else scan.scan_type,
        scan_options=stored_options,
        project_id=scan.project_id,
        organization_id=current_user.organization_id,
    )

    dispatch_scan(new_scan.id, background_tasks)

    return new_scan
