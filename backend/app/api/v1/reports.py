from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.scan import Scan
from app.models.report import Report
from app.models.user import User
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.services.report_service import ReportService
import os

router = APIRouter()


def _assert_scan_belongs_to_org(db: Session, scan_id: str, current_user: User) -> None:
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    org_id = current_user.organization_id
    if org_id:
        if scan.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Scan not found")
    elif scan.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")


def _assert_report_access(db: Session, report: Optional[Report], current_user: User) -> None:
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    scan = db.query(Scan).filter(Scan.id == report.scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Report not found")
    org_id = current_user.organization_id
    if org_id:
        if scan.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Report not found")
    elif scan.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Report not found")


@router.post("")
async def generate_report(
    scan_id: str,
    format: str = "json",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.GENERATE_REPORT))
):
    """Generate a report for a scan."""
    _assert_scan_belongs_to_org(db, scan_id, current_user)

    try:
        service = ReportService(db)
        file_path = service.generate_report(scan_id, format)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

    report = Report(
        scan_id=scan_id,
        format=format,
        generated_by=current_user.id,
        file_path=file_path,
        file_size=file_size
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "id": report.id,
        "scan_id": scan_id,
        "format": format,
        "status": "generated",
        "file_size": file_size,
        "download_url": f"/api/v1/reports/{report.id}/download"
    }


@router.get("")
async def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List reports for the caller's organization (or own scans when org-less)."""
    if current_user.organization_id:
        scope = Scan.organization_id == current_user.organization_id
    else:
        scope = Scan.created_by == current_user.id
    reports = (
        db.query(Report)
        .join(Scan, Report.scan_id == Scan.id)
        .filter(scope)
        .order_by(Report.generated_at.desc())
        .all()
    )

    return [
        {
            "id": r.id,
            "scan_id": r.scan_id,
            "format": r.format,
            "file_size": r.file_size,
            "generated_at": r.generated_at
        }
        for r in reports
    ]


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get report details."""
    report = db.query(Report).filter(Report.id == report_id).first()
    _assert_report_access(db, report, current_user)

    return {
        "id": report.id,
        "scan_id": report.scan_id,
        "format": report.format,
        "file_size": report.file_size,
        "generated_at": report.generated_at,
        "download_url": f"/api/v1/reports/{report.id}/download"
    }


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download a report file."""
    report = db.query(Report).filter(Report.id == report_id).first()
    _assert_report_access(db, report, current_user)

    if report.file_path and os.path.exists(report.file_path):
        media_types = {
            "json": "application/json",
            "csv": "text/csv",
            "pdf": "application/pdf",
        }
        return FileResponse(
            path=report.file_path,
            filename=f"cazo-report.{report.format}",
            media_type=media_types.get(report.format, "application/octet-stream")
        )

    raise HTTPException(status_code=404, detail="Report file not found on disk")


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EXPORT_REPORTS))
):
    """Delete a report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    _assert_report_access(db, report, current_user)

    if report.file_path and os.path.exists(report.file_path):
        try:
            os.remove(report.file_path)
        except OSError as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to delete report file %s: %s", report.file_path, exc)

    db.delete(report)
    db.commit()

    return {"message": "Report deleted successfully"}
