from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from app.database import get_db
from app.models.scan import Scan
from app.models.asset import Subdomain
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.technology import Technology
from app.models.vulnerability import Vulnerability
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


@router.get("")
async def compare_scans(
    scan_a: str,
    scan_b: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compare two scans and show differences."""
    # Validate both scans exist and are visible to the caller (org or creator).
    scan1 = db.query(Scan).filter(Scan.id == scan_a).first()
    scan2 = db.query(Scan).filter(Scan.id == scan_b).first()

    org_id = current_user.organization_id

    def _visible(scan):
        if not scan:
            return False
        if org_id:
            return scan.organization_id == org_id
        return scan.created_by == current_user.id

    if not _visible(scan1):
        raise HTTPException(status_code=404, detail=f"Scan A not found: {scan_a}")
    if not _visible(scan2):
        raise HTTPException(status_code=404, detail=f"Scan B not found: {scan_b}")

    # Gather data for both scans
    def get_scan_assets(scan_id: str) -> Dict[str, Any]:
        subdomains = db.query(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        ports = db.query(Port).join(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        techs = db.query(Technology).join(Subdomain).filter(Subdomain.scan_id == scan_id).all()
        vulns = db.query(Vulnerability).filter(Vulnerability.scan_id == scan_id).all()
        ssl_certs = db.query(SSLCertificate).join(Subdomain).filter(Subdomain.scan_id == scan_id).all()

        return {
            "subdomains": {s.hostname for s in subdomains},
            "ports": {(p.subdomain.hostname, p.port_number) for p in ports},
            "technologies": {(t.subdomain.hostname, t.name) for t in techs},
            "vulnerabilities": {(v.host, v.template_id) for v in vulns},
            "ssl_grades": {s.subdomain.hostname: s.grade for s in ssl_certs},
            "counts": {
                "subdomains": len(subdomains),
                "ports": len(ports),
                "technologies": len(techs),
                "vulnerabilities": len(vulns),
                "ssl_certificates": len(ssl_certs),
            }
        }

    assets_a = get_scan_assets(scan_a)
    assets_b = get_scan_assets(scan_b)

    # Compute diffs
    def compute_set_diff(set_a: set, set_b: set) -> Dict[str, List]:
        added = sorted(set_b - set_a)
        removed = sorted(set_a - set_b)
        common = sorted(set_a & set_b)
        return {"added": [list(x) if isinstance(x, tuple) else x for x in added],
                "removed": [list(x) if isinstance(x, tuple) else x for x in removed],
                "unchanged_count": len(common)}

    subdomain_diff = compute_set_diff(assets_a["subdomains"], assets_b["subdomains"])
    port_diff = compute_set_diff(assets_a["ports"], assets_b["ports"])
    tech_diff = compute_set_diff(assets_a["technologies"], assets_b["technologies"])
    vuln_diff = compute_set_diff(assets_a["vulnerabilities"], assets_b["vulnerabilities"])

    return {
        "scan_a": {"id": scan_a, "domain": scan1.domain, "date": scan1.created_at.isoformat()},
        "scan_b": {"id": scan_b, "domain": scan2.domain, "date": scan2.created_at.isoformat()},
        "summary": {
            "scan_a": assets_a["counts"],
            "scan_b": assets_b["counts"],
        },
        "diff": {
            "subdomains": subdomain_diff,
            "ports": port_diff,
            "technologies": tech_diff,
            "vulnerabilities": vuln_diff,
        }
    }
