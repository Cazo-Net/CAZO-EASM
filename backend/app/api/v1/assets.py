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
from app.models.asset_inventory import Asset, AssetRelationship
from app.models.asset_score import AssetScore
from app.api.deps import get_current_user
from app.core.permissions import require_permission, Permission
from app.repositories.assets import get_asset_graph as repository_get_asset_graph
from app.services.scoring import compute_asset_scores
from app.services.change_detector import get_timeline

router = APIRouter()


def _assert_scan_belongs_to_org(db: Session, scan_id: str, current_user: User) -> None:
    """Ensure the given scan is visible to the caller.

    A scan is visible when it belongs to the caller's organization (when the
    caller has one) or was created by the caller. Returns 404 otherwise,
    preventing cross-tenant/cross-user access via a guessed scan id.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    org_id = current_user.organization_id
    if org_id:
        if scan.organization_id != org_id:
            raise HTTPException(status_code=404, detail="Scan not found")
    elif scan.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")


@router.get("/subdomains")
async def list_subdomains(
    scan_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 2000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List discovered subdomains visible to the caller's organization."""
    if scan_id:
        _assert_scan_belongs_to_org(db, scan_id, current_user)
        query = db.query(Subdomain).filter(Subdomain.scan_id == scan_id)
    else:
        query = (
            db.query(Subdomain)
            .join(Scan, Subdomain.scan_id == Scan.id)
            .filter(Scan.organization_id == current_user.organization_id)
        )

    subdomains = query.offset(skip).limit(limit).all()

    hostnames = [s.hostname for s in subdomains]
    asset_rows = (
        db.query(Asset)
        .filter(
            Asset.organization_id == current_user.organization_id,
            Asset.value.in_(hostnames),
        )
        .all()
    )
    asset_map = {a.value: a for a in asset_rows}

    return [
        {
            "id": s.id,
            "hostname": s.hostname,
            "ip_addresses": s.ip_addresses,
            "is_alive": s.is_alive,
            "scan_id": s.scan_id,
            "discovered_at": s.discovered_at,
            "first_seen": asset_map[s.hostname].first_seen.isoformat() if s.hostname in asset_map and asset_map[s.hostname].first_seen else None,
        }
        for s in subdomains
    ]


@router.get("/ports")
async def list_ports(
    scan_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 2000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List discovered open ports visible to the caller's organization."""
    query = db.query(Port).join(Subdomain)

    if scan_id:
        _assert_scan_belongs_to_org(db, scan_id, current_user)
        query = query.filter(Subdomain.scan_id == scan_id)
    else:
        query = query.join(Scan, Subdomain.scan_id == Scan.id).filter(
            Scan.organization_id == current_user.organization_id
        )

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
    limit: int = 2000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List discovered SSL certificates visible to the caller's organization."""
    query = db.query(SSLCertificate).join(Subdomain)

    if scan_id:
        _assert_scan_belongs_to_org(db, scan_id, current_user)
        query = query.filter(Subdomain.scan_id == scan_id)
    else:
        query = query.join(Scan, Subdomain.scan_id == Scan.id).filter(
            Scan.organization_id == current_user.organization_id
        )

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
    limit: int = 2000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List discovered technologies visible to the caller's organization."""
    query = db.query(Technology).join(Subdomain)

    if scan_id:
        _assert_scan_belongs_to_org(db, scan_id, current_user)
        query = query.filter(Subdomain.scan_id == scan_id)
    else:
        query = query.join(Scan, Subdomain.scan_id == Scan.id).filter(
            Scan.organization_id == current_user.organization_id
        )

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
    limit: int = 2000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List discovered DNS records visible to the caller's organization."""
    query = db.query(DNSRecord).join(Subdomain)

    if scan_id:
        _assert_scan_belongs_to_org(db, scan_id, current_user)
        query = query.filter(Subdomain.scan_id == scan_id)
    else:
        query = query.join(Scan, Subdomain.scan_id == Scan.id).filter(
            Scan.organization_id == current_user.organization_id
        )

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
    limit: int = 2000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List WHOIS records visible to the caller's organization."""
    if scan_id:
        _assert_scan_belongs_to_org(db, scan_id, current_user)
        query = db.query(WhoisRecord).filter(WhoisRecord.scan_id == scan_id)
    else:
        query = (
            db.query(WhoisRecord)
            .join(Scan, WhoisRecord.scan_id == Scan.id)
            .filter(Scan.organization_id == current_user.organization_id)
        )

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


@router.get("/whois/location")
async def get_domain_location(
    domain: str = Query(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Where a scanned domain is: WHOIS registrant country and the hosting
    location of each IP the latest scan saw for it.

    Only domains that appear in the caller's own scans can be looked up.
    """
    from app.services import geo

    domain = domain.strip().lower().rstrip(".")
    scans = db.query(Scan).filter(Scan.status == "completed")
    if current_user.organization_id:
        scans = scans.filter(Scan.organization_id == current_user.organization_id)
    else:
        scans = scans.filter(Scan.created_by == current_user.id)
    scan_ids = [s.id for s in scans.with_entities(Scan.id).all()]
    if not scan_ids:
        raise HTTPException(status_code=404, detail="Domain not found in your scans")

    whois = (
        db.query(WhoisRecord)
        .filter(WhoisRecord.scan_id.in_(scan_ids), WhoisRecord.domain == domain)
        .order_by(WhoisRecord.scanned_at.desc())
        .first()
    )
    sub = (
        db.query(Subdomain)
        .filter(Subdomain.scan_id.in_(scan_ids), Subdomain.hostname == domain)
        .order_by(Subdomain.discovered_at.desc())
        .first()
    )
    if not whois and not sub:
        raise HTTPException(status_code=404, detail="Domain not found in your scans")

    ips: list = []
    if sub:
        ips.extend(sub.ip_addresses or [])
        ips.extend(
            r.value for r in db.query(DNSRecord)
            .filter(DNSRecord.subdomain_id == sub.id, DNSRecord.record_type.in_(["A", "AAAA"]))
            .all()
        )

    return {
        "domain": domain,
        "registrant_country": (whois.registrant_country or None) if whois else None,
        "provider": geo.PROVIDER,
        "token_configured": geo.configured(),
        "scanned_at": sub.discovered_at if sub else (whois.scanned_at if whois else None),
        "locations": geo.locate(ips),
    }


@router.get("/graph")
async def get_asset_graph(
    scan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get asset relationship graph for visualization."""
    _assert_scan_belongs_to_org(db, scan_id, current_user)
    scan = db.query(Scan).filter(Scan.id == scan_id).first()

    subdomains = db.query(Subdomain).filter(Subdomain.scan_id == scan_id).all()

    nodes = []
    edges = []

    nodes.append({
        "id": "root",
        "label": scan.domain,
        "type": "domain"
    })

    for sub in subdomains:
        ports = db.query(Port).filter(Port.subdomain_id == sub.id).all()
        vulns = db.query(Vulnerability).filter(Vulnerability.subdomain_id == sub.id).all()

        # Compact port summary attached to the subdomain node so the UI can list
        # every port for a host directly on click, without walking edges.
        port_summary = [
            {
                "port": port.port_number,
                "state": port.state,
                "service": port.service,
                "version": port.version,
                "banner": port.banner,
            }
            for port in ports
        ]

        nodes.append({
            "id": sub.id,
            "label": sub.hostname,
            "type": "subdomain",
            "ips": sub.ip_addresses,
            "ports": port_summary,
            "port_count": len(ports),
            "vuln_count": len(vulns),
        })

        edges.append({
            "source": "root",
            "target": sub.id
        })

        for port in ports:
            port_node_id = f"{sub.id}-port-{port.port_number}"
            nodes.append({
                "id": port_node_id,
                "label": f":{port.port_number}",
                "type": "port",
                "port": port.port_number,
                "state": port.state,
                "service": port.service,
                "version": port.version,
                "banner": port.banner,
                "host": sub.hostname,
            })
            edges.append({
                "source": sub.id,
                "target": port_node_id
            })

        for vuln in vulns:
            vuln_node_id = f"{sub.id}-vuln-{vuln.id[:8]}"
            nodes.append({
                "id": vuln_node_id,
                "label": vuln.name[:30],
                "type": "vulnerability",
                "severity": vuln.severity,
                "host": sub.hostname,
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
    """List discovered vulnerabilities visible to the caller's organization."""
    if scan_id:
        _assert_scan_belongs_to_org(db, scan_id, current_user)
        query = db.query(Vulnerability).filter(Vulnerability.scan_id == scan_id)
    else:
        query = (
            db.query(Vulnerability)
            # Join through scan_id: findings on a host that is not one of the
            # scan's subdomains have no subdomain_id and were left out.
            .join(Scan, Vulnerability.scan_id == Scan.id)
            .filter(Scan.organization_id == current_user.organization_id)
        )

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
    """Get vulnerability count by severity for the caller's organization."""
    if scan_id:
        _assert_scan_belongs_to_org(db, scan_id, current_user)
        query = db.query(Vulnerability).filter(Vulnerability.scan_id == scan_id)
    else:
        query = (
            db.query(Vulnerability)
            # Join through scan_id: findings on a host that is not one of the
            # scan's subdomains have no subdomain_id and were left out.
            .join(Scan, Vulnerability.scan_id == Scan.id)
            .filter(Scan.organization_id == current_user.organization_id)
        )

    all_vulns = query.all()

    summary = {
        "total": len(all_vulns),
        "critical": sum(1 for v in all_vulns if v.severity == "critical"),
        "high": sum(1 for v in all_vulns if v.severity == "high"),
        "medium": sum(1 for v in all_vulns if v.severity == "medium"),
        "low": sum(1 for v in all_vulns if v.severity == "low"),
    }

    return summary


@router.get("/host/{asset_id}")
async def get_host_intelligence(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shodan-style host intelligence for a single asset.

    Aggregates, from existing scan data, the fields Shodan surfaces per host:
    ASN / ISP / organization, resolved IPs, open ports (with service + banner),
    web technologies, SSL certificates, and known vulnerabilities. No external
    enrichment is performed; everything is derived from already-collected data.
    """
    if not current_user.organization_id:
        return {
            "asset_id": asset_id,
            "asn": None,
            "isp": None,
            "org": None,
            "ip_addresses": [],
            "ports": [],
            "technologies": [],
            "certificates": [],
            "vulnerabilities": [],
        }

    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.organization_id == current_user.organization_id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # ASN / ISP / organization come from `belongs_to` edges into `asn` assets.
    asn_value = None
    isp = None
    org = asset.label or asset.value
    asn_edges = (
        db.query(AssetRelationship)
        .filter(
            AssetRelationship.source_asset_id == asset_id,
            AssetRelationship.relationship_type == "belongs_to",
        )
        .all()
    )
    for edge in asn_edges:
        asn_asset = (
            db.query(Asset).filter(Asset.id == edge.target_asset_id).first()
        )
        if asn_asset and asn_asset.asset_type == "asn":
            asn_value = asn_asset.value
            isp = (asn_asset.attributes or {}).get("provider") or asn_asset.label
            break

    # Resolve the hostnames / IPs associated with this asset.
    hostnames: List[str] = []
    if asset.asset_type == "ip":
        hostnames = [asset.value]
    elif asset.asset_type == "host":
        hostnames = [asset.value]
        attrs = asset.attributes or {}
        for ip in attrs.get("ip_addresses", []) or []:
            if ip not in hostnames:
                hostnames.append(ip)
    else:
        # domain/certificate/technology: pull hostnames from attributes.
        for h in (asset.attributes or {}).get("hostnames", []) or []:
            hostnames.append(h)

    ip_addresses: List[str] = []
    for h in hostnames:
        if ":" in h or (h.replace(".", "").isdigit() and h.count(".") == 3):
            if h not in ip_addresses:
                ip_addresses.append(h)

    subdomain_ids = [
        s.id
        for s in db.query(Subdomain)
        .join(Scan, Subdomain.scan_id == Scan.id)
        .filter(
            Scan.organization_id == current_user.organization_id,
            Subdomain.hostname.in_(hostnames),
        )
        .all()
    ]
    if not subdomain_ids:
        # Fall back to IPs stored on subdomains when no hostname matched.
        sub_rows = (
            db.query(Subdomain)
            .join(Scan, Subdomain.scan_id == Scan.id)
            .filter(Scan.organization_id == current_user.organization_id)
            .all()
        )
        for s in sub_rows:
            ips = s.ip_addresses or []
            if any(ip in hostnames for ip in ips):
                subdomain_ids.append(s.id)
                for ip in ips:
                    if ip not in ip_addresses:
                        ip_addresses.append(ip)

    ports = []
    if subdomain_ids:
        port_rows = (
            db.query(Port)
            .filter(Port.subdomain_id.in_(subdomain_ids))
            .order_by(Port.port_number.asc())
            .all()
        )
        ports = [
            {
                "port": p.port_number,
                "state": p.state,
                "service": p.service or "unknown",
                "version": p.version or None,
                "banner": p.banner or None,
                "hostname": p.subdomain.hostname if p.subdomain else None,
            }
            for p in port_rows
        ]

        tech_rows = (
            db.query(Technology)
            .filter(Technology.subdomain_id.in_(subdomain_ids))
            .all()
        )
        technologies = [
            {
                "name": t.name,
                "category": t.category or "other",
                "version": t.version or None,
                "confidence": round((t.confidence or 0) * 100),
                "hostname": t.subdomain.hostname if t.subdomain else None,
            }
            for t in tech_rows
        ]

        cert_rows = (
            db.query(SSLCertificate)
            .filter(SSLCertificate.subdomain_id.in_(subdomain_ids))
            .all()
        )
        certificates = [
            {
                "issuer": c.issuer,
                "subject": c.subject,
                "grade": c.grade,
                "protocol": c.protocol,
                "cipher_suite": c.cipher_suite,
                "not_after": c.not_after,
                "hostname": c.subdomain.hostname if c.subdomain else None,
            }
            for c in cert_rows
        ]
    else:
        technologies = []
        certificates = []

    vuln_rows = (
        db.query(Vulnerability)
        .filter(
            Vulnerability.organization_id == current_user.organization_id,
            Vulnerability.asset_id == asset_id,
        )
        .order_by(Vulnerability.severity.desc())
        .all()
    )
    vulnerabilities = [
        {
            "id": v.id,
            "name": v.name,
            "severity": v.severity,
            "host": v.host,
            "matched_at": v.matched_at,
            "status": v.status,
        }
        for v in vuln_rows
    ]

    return {
        "asset_id": asset_id,
        "asset_type": asset.asset_type,
        "asn": asn_value,
        "isp": isp,
        "org": org,
        "ip_addresses": ip_addresses,
        "ports": ports,
        "technologies": technologies,
        "certificates": certificates,
        "vulnerabilities": vulnerabilities,
    }


@router.get("/inventory")
async def list_asset_inventory(
    asset_type: Optional[str] = Query(None, description="host|domain|ip|certificate|technology"),
    only_alive: bool = True,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the canonical, cross-scan asset inventory for the user's organization."""
    if not current_user.organization_id:
        return []
    query = db.query(Asset).filter(Asset.organization_id == current_user.organization_id)
    if asset_type:
        query = query.filter(Asset.asset_type == asset_type)
    else:
        # This older listing predates services/technologies in the inventory;
        # the full inventory lives at /api/v1/inventory.
        query = query.filter(Asset.asset_type.notin_(("domain", "service", "technology")))
    if only_alive:
        query = query.filter(Asset.is_alive == True)  # noqa: E712
    assets = query.order_by(Asset.last_seen.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": a.id,
            "type": a.asset_type,
            "value": a.value,
            "label": a.label,
            "is_alive": a.is_alive,
            "first_seen": a.first_seen,
            "last_seen": a.last_seen,
            "attributes": a.attributes or {},
            "last_scan_id": a.last_scan_id,
        }
        for a in assets
    ]


@router.get("/inventory/graph")
async def get_inventory_graph(
    asset_types: Optional[List[str]] = Query(None),
    relationship_types: Optional[List[str]] = Query(None),
    only_alive: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Organization-wide asset relationship graph (stable across scans).

    Supports filtering by asset/relationship type for the graph inspector and
    clustering. Falls back to an empty graph when the user has no organization.
    """
    if not current_user.organization_id:
        return {"nodes": [], "edges": [], "counts": {"nodes": 0, "edges": 0}}
    return repository_get_asset_graph(
        db,
        current_user.organization_id,
        asset_types=asset_types,
        relationship_types=relationship_types,
        only_alive=only_alive,
    )


@router.post("/scores/recompute")
async def recompute_scores(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ASSETS)),
):
    """Recompute health/exposure scores for the organization's assets."""
    if not current_user.organization_id:
        return {"scored": 0}
    count = compute_asset_scores(db, current_user.organization_id)
    return {"scored": count}


@router.get("/scores")
async def list_asset_scores(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List health/exposure scores for the organization's assets."""
    if not current_user.organization_id:
        return []
    scores = (
        db.query(AssetScore)
        .filter(AssetScore.organization_id == current_user.organization_id)
        .order_by(AssetScore.exposure_score.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "asset_id": s.asset_id,
            "health_score": s.health_score,
            "exposure_score": s.exposure_score,
            "health_factors": s.health_factors or [],
            "exposure_factors": s.exposure_factors or [],
            "scored_at": s.scored_at,
        }
        for s in scores
    ]


@router.get("/timeline")
async def get_asset_timeline(
    change_type: Optional[str] = Query(None, description="added|removed|modified"),
    entity_type: Optional[str] = Query(None, description="subdomain|port|certificate|technology|dns"),
    limit: int = 2000,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Organization-wide change timeline derived from persisted scan diffs."""
    if not current_user.organization_id:
        return []
    return get_timeline(
        db,
        current_user.organization_id,
        limit=limit,
        change_type=change_type,
        entity_type=entity_type,
    )
