from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.asset import Subdomain
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.technology import Technology
from app.models.scan import Scan
from app.models.dns import DNSRecord
from app.models.whois import WhoisRecord
from app.models.vulnerability import Vulnerability
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/subdomains")
async def list_subdomains(
    scan_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all discovered subdomains."""
    query = db.query(Subdomain)

    if scan_id:
        query = query.filter(Subdomain.scan_id == scan_id)

    subdomains = query.offset(skip).limit(limit).all()

    return [
        {
            "id": s.id,
            "hostname": s.hostname,
            "ip_addresses": s.ip_addresses,
            "is_alive": s.is_alive,
            "scan_id": s.scan_id,
            "discovered_at": s.discovered_at
        }
        for s in subdomains
    ]


@router.get("/ports")
async def list_ports(
    scan_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all discovered open ports."""
    query = db.query(Port).join(Subdomain)

    if scan_id:
        query = query.filter(Subdomain.scan_id == scan_id)

    ports = query.offset(skip).limit(limit).all()

    return [
        {
            "id": p.id,
            "subdomain_id": p.subdomain_id,
            "hostname": p.subdomain.hostname,
            "port_number": p.port_number,
            "state": p.state,
            "service": p.service,
            "version": p.version,
            "banner": p.banner,
            "scanned_at": p.scanned_at
        }
        for p in ports
    ]


@router.get("/ssl")
async def list_ssl_certificates(
    scan_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all discovered SSL certificates."""
    query = db.query(SSLCertificate).join(Subdomain)

    if scan_id:
        query = query.filter(Subdomain.scan_id == scan_id)

    certs = query.offset(skip).limit(limit).all()

    return [
        {
            "id": c.id,
            "subdomain_id": c.subdomain_id,
            "hostname": c.subdomain.hostname,
            "issuer": c.issuer,
            "subject": c.subject,
            "not_before": c.not_before,
            "not_after": c.not_after,
            "is_valid": c.is_valid,
            "grade": c.grade,
            "protocol": c.protocol,
            "cipher_suite": c.cipher_suite,
            "scanned_at": c.scanned_at
        }
        for c in certs
    ]


@router.get("/technologies")
async def list_technologies(
    scan_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all discovered technologies."""
    query = db.query(Technology).join(Subdomain)

    if scan_id:
        query = query.filter(Subdomain.scan_id == scan_id)

    techs = query.offset(skip).limit(limit).all()

    return [
        {
            "id": t.id,
            "subdomain_id": t.subdomain_id,
            "hostname": t.subdomain.hostname,
            "name": t.name,
            "category": t.category,
            "version": t.version,
            "confidence": t.confidence,
            "detected_at": t.detected_at
        }
        for t in techs
    ]


@router.get("/dns")
async def list_dns_records(
    scan_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all discovered DNS records."""
    query = db.query(DNSRecord).join(Subdomain)

    if scan_id:
        query = query.filter(Subdomain.scan_id == scan_id)

    records = query.offset(skip).limit(limit).all()

    return [
        {
            "id": r.id,
            "subdomain_id": r.subdomain_id,
            "hostname": r.subdomain.hostname,
            "record_type": r.record_type,
            "value": r.value,
            "ttl": r.ttl,
            "created_at": r.created_at
        }
        for r in records
    ]


@router.get("/whois")
async def list_whois_records(
    scan_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all WHOIS records."""
    query = db.query(WhoisRecord)

    if scan_id:
        query = query.filter(WhoisRecord.scan_id == scan_id)

    records = query.offset(skip).limit(limit).all()

    return [
        {
            "id": r.id,
            "domain": r.domain,
            "scan_id": r.scan_id,
            "registrar": r.registrar,
            "creation_date": r.creation_date,
            "expiration_date": r.expiration_date,
            "name_servers": r.name_servers,
            "registrant_name": r.registrant_name,
            "registrant_org": r.registrant_org,
            "registrant_country": r.registrant_country,
            "scanned_at": r.scanned_at
        }
        for r in records
    ]


@router.get("/graph")
async def get_asset_graph(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get asset relationship graph for visualization."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    subdomains = db.query(Subdomain).filter(Subdomain.scan_id == scan_id).all()

    nodes = []
    edges = []

    nodes.append({
        "id": "root",
        "label": scan.domain,
        "type": "domain"
    })

    for sub in subdomains:
        nodes.append({
            "id": sub.id,
            "label": sub.hostname,
            "type": "subdomain",
            "ips": sub.ip_addresses
        })

        edges.append({
            "source": "root",
            "target": sub.id
        })

        ports = db.query(Port).filter(Port.subdomain_id == sub.id).all()
        for port in ports:
            port_node_id = f"{sub.id}-port-{port.port_number}"
            nodes.append({
                "id": port_node_id,
                "label": f":{port.port_number}",
                "type": "port",
                "service": port.service
            })
            edges.append({
                "source": sub.id,
                "target": port_node_id
            })

        vulns = db.query(Vulnerability).filter(Vulnerability.subdomain_id == sub.id).all()
        for vuln in vulns:
            vuln_node_id = f"{sub.id}-vuln-{vuln.id[:8]}"
            nodes.append({
                "id": vuln_node_id,
                "label": vuln.name[:30],
                "type": "vulnerability",
                "severity": vuln.severity
            })
            edges.append({
                "source": sub.id,
                "target": vuln_node_id
            })

    return {
        "nodes": nodes,
        "edges": edges
    }


@router.get("/vulnerabilities")
async def list_vulnerabilities(
    scan_id: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all discovered vulnerabilities."""
    query = db.query(Vulnerability)

    if scan_id:
        query = query.filter(Vulnerability.scan_id == scan_id)

    if severity:
        query = query.filter(Vulnerability.severity == severity)

    vulns = query.order_by(
        Vulnerability.severity.asc()
    ).offset(skip).limit(limit).all()

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
    vulns.sort(key=lambda v: severity_order.get(v.severity, 5))

    return [
        {
            "id": v.id,
            "scan_id": v.scan_id,
            "subdomain_id": v.subdomain_id,
            "template_id": v.template_id,
            "name": v.name,
            "severity": v.severity,
            "vuln_type": v.vuln_type,
            "host": v.host,
            "matched_at": v.matched_at,
            "description": v.description,
            "reference": v.reference,
            "tags": v.tags,
            "curl_command": v.curl_command,
            "extracted_results": v.extracted_results,
            "found_at": v.found_at,
        }
        for v in vulns
    ]


@router.get("/vulnerabilities/summary")
async def get_vulnerability_summary(
    scan_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get vulnerability count by severity."""
    query = db.query(Vulnerability)

    if scan_id:
        query = query.filter(Vulnerability.scan_id == scan_id)

    all_vulns = query.all()

    summary = {
        "total": len(all_vulns),
        "critical": sum(1 for v in all_vulns if v.severity == "critical"),
        "high": sum(1 for v in all_vulns if v.severity == "high"),
        "medium": sum(1 for v in all_vulns if v.severity == "medium"),
        "low": sum(1 for v in all_vulns if v.severity == "low"),
    }

    return summary
