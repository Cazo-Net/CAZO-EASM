"""Import OSINT intelligence findings into the canonical Asset Inventory.

After the OSINT engine discovers subdomains, certificates, ports, and CVEs
for a target domain, this module persists them into the same Asset / AssetRelationship
tables used by the scan pipeline, so shadow detection, search, host intelligence,
and change feed all work across both data sources seamlessly.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import logging

from sqlalchemy.orm import Session

from app.models.asset_inventory import Asset, AssetRelationship
from app.models.vulnerability import Vulnerability
from app.models.scan import Scan
from app.services.osint import IntelResult, intel_to_dict

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
) -> None:
    """Create a relationship edge if it doesn't already exist."""
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
        return
    rel = AssetRelationship(
        organization_id=org_id,
        source_asset_id=source_id,
        target_asset_id=target_id,
        relationship_type=rel_type,
        weight={"value": weight},
    )
    db.add(rel)


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
        tags=["osint", "nvd"] + (["kev"] if vuln.get("is_kev") else []),
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
    }

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
            _upsert_relationship(db, org_id, asset.id, ip_asset.id, "resolves_to")
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
                _upsert_relationship(db, org_id, hostname_assets[subject_host].id, cert_asset.id, "serves")
                counts["relationships"] += 1

            # Also link via SAN hostnames
            for san_name in cert.san:
                san_name = san_name.lstrip("*.").lower()
                if san_name in hostname_assets:
                    _upsert_relationship(db, org_id, hostname_assets[san_name].id, cert_asset.id, "serves")
                    counts["relationships"] += 1

    # 5) Vulnerabilities → Vulnerability records (linked to an osint scan)
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

    for vuln in intel.vulnerabilities:
        # Try to find the host asset for this vuln
        vuln_host = None
        if vuln.cve_id:
            # Find a host asset to link to (if possible)
            host_asset = hostname_assets.get(intel.query)  # apex domain
            if host_asset:
                vuln_host = host_asset
        _upsert_vuln(db, org_id, {
            "cve_id": vuln.cve_id,
            "description": vuln.description,
            "severity": vuln.severity,
            "is_kev": vuln.is_kev,
        }, asset_id=vuln_host.id if vuln_host else None, scan_id=osint_scan.id)
        counts["vulnerabilities"] += 1

    db.commit()
    logger.info(
        "OSINT import for %s: %s",
        intel.query,
        counts,
    )
    return counts
