"""Import OSINT intelligence findings into the canonical Asset Inventory.

After the OSINT engine discovers subdomains, certificates, ports, and CVEs
for a target domain, this module persists them into the same Asset / AssetRelationship
tables used by the scan pipeline, so shadow detection, search, host intelligence,
and change feed all work across both data sources seamlessly.

Also creates Subdomain / Port / SSLCertificate / Technology rows so the
scan detail page can display results from OSINT scans.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, Optional
import logging

from sqlalchemy.orm import Session

from app.models.asset_inventory import Asset, AssetRelationship
from app.models.vulnerability import Vulnerability
from app.models.scan import Scan
from app.models.asset import Subdomain
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.technology import Technology
from app.services.osint import IntelResult

logger = logging.getLogger(__name__)


def _upsert_asset(
    db: Session,
    org_id: str,
    asset_type: str,
    value: str,
    source: str = "osint",
    **kwargs,
) -> Asset:
    """Get or create an Asset record. Returns the asset."""
    existing = (
        db.query(Asset)
        .filter(
            Asset.organization_id == org_id,
            Asset.asset_type == asset_type,
            Asset.value == value,
        )
        .first()
    )
    if existing:
        existing.last_seen = datetime.now(timezone.utc)
        if kwargs.get("label") and not existing.label:
            existing.label = kwargs["label"]
        if kwargs.get("is_alive") is not None:
            existing.is_alive = kwargs["is_alive"]
        return existing

    asset = Asset(
        organization_id=org_id,
        asset_type=asset_type,
        value=value,
        label=kwargs.get("label"),
        is_alive=kwargs.get("is_alive", True),
        attributes={"source": source},
    )
    db.add(asset)
    db.flush()
    return asset


def _upsert_relationship(
    db: Session,
    org_id: str,
    source_id: str,
    target_id: str,
    rel_type: str,
    weight: float = 1.0,
    _seen: Optional[set] = None,
) -> None:
    """Create a relationship edge if it doesn't already exist."""
    key = (source_id, target_id, rel_type)
    if _seen is not None and key in _seen:
        return
    existing = (
        db.query(AssetRelationship)
        .filter(
            AssetRelationship.source_asset_id == source_id,
            AssetRelationship.target_asset_id == target_id,
            AssetRelationship.relationship_type == rel_type,
        )
        .first()
    )
    if existing:
        existing.last_seen = datetime.now(timezone.utc)
        if _seen is not None:
            _seen.add(key)
        return
    rel = AssetRelationship(
        organization_id=org_id,
        source_asset_id=source_id,
        target_asset_id=target_id,
        relationship_type=rel_type,
        weight={"value": weight},
    )
    db.add(rel)
    if _seen is not None:
        _seen.add(key)


def _upsert_vuln(
    db: Session,
    org_id: str,
    vuln: dict,
    asset_id: Optional[str] = None,
    scan_id: Optional[str] = None,
) -> Optional[Vulnerability]:
    """Create a Vulnerability record if the CVE doesn't already exist for this org."""
    cve_id = vuln.get("cve_id", "")
    existing = (
        db.query(Vulnerability)
        .filter(
            Vulnerability.organization_id == org_id,
            Vulnerability.template_id == cve_id,
        )
        .first()
    )
    if existing:
        existing.last_seen = datetime.now(timezone.utc)
        return existing

    v = Vulnerability(
        organization_id=org_id,
        scan_id=scan_id,
        asset_id=asset_id,
        template_id=cve_id,
        name=vuln.get("cve_id", "Unknown"),
        severity=vuln.get("severity") or "unknown",
        vuln_type="osint_cve",
        host=vuln.get("host") or "unknown",
        matched_at=vuln.get("matched_at") or "osint",
        description=vuln.get("description") or "",
        reference=vuln.get("reference") or [],
        tags=list(vuln.get("tags") or ["osint"]) + (["kev"] if vuln.get("is_kev") else []),
        status="open",
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db.add(v)
    return v


def import_osint_findings(
    db: Session,
    org_id: str,
    intel: IntelResult,
) -> Dict[str, int]:
    """Import an IntelResult into the canonical Asset Inventory.

    Returns a summary dict with counts of created/updated records.
    """
    counts = {
        "subdomains": 0,
        "ip_assets": 0,
        "cert_assets": 0,
        "relationships": 0,
        "vulnerabilities": 0,
        "scan_subdomains": 0,
        "scan_ports": 0,
        "scan_ssl": 0,
        "scan_technologies": 0,
    }
    _seen_rels: set = set()

    # 1) Upsert each discovered subdomain as a host asset
    hostname_assets: Dict[str, Asset] = {}
    for sub in intel.subdomains:
        host = sub.hostname
        asset = _upsert_asset(db, org_id, "host", host, source="osint", is_alive=True)
        hostname_assets[host] = asset
        counts["subdomains"] += 1

        # 2) Upsert IP assets + resolves_to relationships
        for ip in sub.ips:
            ip_asset = _upsert_asset(db, org_id, "ip", ip, source="osint")
            counts["ip_assets"] += 1
            _upsert_relationship(db, org_id, asset.id, ip_asset.id, "resolves_to", _seen=_seen_rels)
            counts["relationships"] += 1

    # 3) DNS records → store as attributes on the host asset
    for hostname, records in intel.dns_records.items():
        if hostname in hostname_assets:
            a = hostname_assets[hostname]
            attrs = a.attributes or {}
            attrs["dns_records"] = records
            a.attributes = attrs

    # 4) Certificates → certificate assets + serves relationships
    for cert in intel.certificates:
        if cert.subject:
            # Find or create the host asset this cert belongs to
            subject_host = cert.subject.split("CN=")[-1].split(",")[0].strip().lower() if "CN=" in cert.subject else cert.subject.lower()
            cert_value = cert.serial or subject_host
            cert_asset = _upsert_asset(
                db, org_id, "certificate", cert_value, source="osint",
                label=subject_host,
            )
            cert_asset.attributes = {
                "source": "osint",
                "issuer": cert.issuer,
                "subject": cert.subject,
                "san": cert.san,
                "not_before": cert.not_before,
                "not_after": cert.not_after,
            }
            counts["cert_assets"] += 1

            # Link certificate to host via serves relationship
            if subject_host in hostname_assets:
                _upsert_relationship(db, org_id, hostname_assets[subject_host].id, cert_asset.id, "serves", _seen=_seen_rels)
                counts["relationships"] += 1

            # Also link via SAN hostnames
            for san_name in cert.san:
                san_name = san_name.lstrip("*.").lower()
                if san_name in hostname_assets:
                    _upsert_relationship(db, org_id, hostname_assets[san_name].id, cert_asset.id, "serves", _seen=_seen_rels)
                    counts["relationships"] += 1

    # 5) Create or find the OSINT scan record
    osint_scan = (
        db.query(Scan)
        .filter(Scan.organization_id == org_id, Scan.domain == intel.query, Scan.scan_type == "osint")
        .first()
    )
    if not osint_scan:
        osint_scan = Scan(
            domain=intel.query,
            organization_id=org_id,
            status="completed",
            scan_type="osint",
            progress=100,
        )
        db.add(osint_scan)
        db.flush()

    # 6) Create Subdomain rows so the scan detail page can display results
    scan_subdomains: Dict[str, Subdomain] = {}

    # Root domain subdomain
    root_sub = Subdomain(
        scan_id=osint_scan.id,
        hostname=intel.query,
        ip_addresses=[ip for sub in intel.subdomains[:1] for ip in sub.ips],
        is_alive=True,
        status="active",
    )
    db.add(root_sub)
    db.flush()
    scan_subdomains[intel.query] = root_sub
    counts["scan_subdomains"] += 1

    # Child subdomains
    for sub in intel.subdomains:
        host = sub.hostname
        if host in scan_subdomains:
            continue
        child_sub = Subdomain(
            scan_id=osint_scan.id,
            hostname=host,
            ip_addresses=sub.ips,
            is_alive=bool(sub.ips),
            status="active",
        )
        db.add(child_sub)
        db.flush()
        scan_subdomains[host] = child_sub
        counts["scan_subdomains"] += 1

    # 7) Create Port rows linked to the appropriate subdomain
    for port in intel.ports:
        # Try to find a subdomain that matches this port's host
        # Ports from the OSINT engine are typically for the apex domain
        target_sub = next(
            (scan_subdomains[h] for h in (getattr(port, "hostnames", None) or []) if h in scan_subdomains),
            None,
        ) or scan_subdomains.get(intel.query) or root_sub
        existing_port = (
            db.query(Port)
            .filter(Port.subdomain_id == target_sub.id, Port.port_number == port.port)
            .first()
        )
        if not existing_port:
            db.add(Port(
                subdomain_id=target_sub.id,
                port_number=port.port,
                state=port.state,
                service=port.service or "",
                banner=(port.banner or "")[:500],
                version="",
                status="active",
            ))
            counts["scan_ports"] += 1

    # 8) Create SSLCertificate rows linked to the appropriate subdomain
    for cert in intel.certificates:
        subject_host = None
        if cert.subject:
            subject_host = cert.subject.split("CN=")[-1].split(",")[0].strip().lower() if "CN=" in cert.subject else cert.subject.lower()
        target_sub = scan_subdomains.get(subject_host) if subject_host else None
        if not target_sub:
            target_sub = scan_subdomains.get(intel.query) or root_sub

        existing_cert = (
            db.query(SSLCertificate)
            .filter(SSLCertificate.subdomain_id == target_sub.id, SSLCertificate.subject == cert.subject)
            .first()
        )
        if not existing_cert and cert.subject:
            not_before = None
            not_after = None
            try:
                if cert.not_before:
                    not_before = datetime.fromisoformat(cert.not_before.replace("Z", "+00:00"))
                if cert.not_after:
                    not_after = datetime.fromisoformat(cert.not_after.replace("Z", "+00:00"))
            except Exception:
                pass

            db.add(SSLCertificate(
                subdomain_id=target_sub.id,
                issuer=cert.issuer or "",
                subject=cert.subject or "",
                serial_number=cert.serial or "",
                not_before=not_before,
                not_after=not_after,
                is_valid=True,
                san=cert.san,
                status="active",
            ))
            counts["scan_ssl"] += 1

    # 9) Create Technology rows linked to the appropriate subdomain
    for tech_name in intel.technologies:
        target_sub = scan_subdomains.get(intel.query) or root_sub
        existing_tech = (
            db.query(Technology)
            .filter(Technology.subdomain_id == target_sub.id, Technology.name == tech_name)
            .first()
        )
        if not existing_tech:
            db.add(Technology(
                subdomain_id=target_sub.id,
                name=tech_name,
                category="detected",
                confidence=100,
                status="active",
            ))
            counts["scan_technologies"] += 1

    # 10) Vulnerabilities → Vulnerability records (linked to the osint scan)
    for vuln in intel.vulnerabilities:
        vuln_host = None
        if vuln.cve_id:
            host_asset = hostname_assets.get(intel.query)
            if host_asset:
                vuln_host = host_asset
        ips = ", ".join(getattr(vuln, "ips", None) or [])
        _upsert_vuln(db, org_id, {
            "cve_id": vuln.cve_id,
            "description": (
                "Potential: Shodan InternetDB matched this CVE to a software version it observed"
                + (f" on {ips}" if ips else "") + ". Not verified; confirm with a scan. "
                + (vuln.description or "")
            ).strip(),
            "severity": (vuln.severity or "unknown").lower(),
            "is_kev": vuln.is_kev,
            "host": ips or None,
            "reference": [u for u in (getattr(vuln, "reference_url", None), getattr(vuln, "source_url", None)) if u],
            "tags": ["osint", "shodan-internetdb", "potential"],
        }, asset_id=vuln_host.id if vuln_host else None, scan_id=osint_scan.id)
        counts["vulnerabilities"] += 1

    db.commit()
    logger.info(
        "OSINT import for %s: %s",
        intel.query,
        counts,
    )
    return counts
