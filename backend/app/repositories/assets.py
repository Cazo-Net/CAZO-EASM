"""Asset repository.

Decouples the API/domain layers from direct ORM queries for the canonical asset
inventory. Provides idempotent upserts (so repeated scans converge on the same
``Asset`` rows) and graph extraction. This is the first of a ``repositories``
package intended to replace ad-hoc ``db.query`` calls scattered across routers.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.asset_inventory import Asset, AssetRelationship
from app.models.asset import Subdomain
from app.utils.asn import resolve_asn

logger = logging.getLogger(__name__)


def upsert_asset(
    db: Session,
    organization_id: str,
    asset_type: str,
    value: str,
    *,
    label: Optional[str] = None,
    is_alive: bool = True,
    last_scan_id: Optional[str] = None,
    attributes: Optional[dict] = None,
    touch: bool = True,
) -> Asset:
    """Insert or update a canonical asset (idempotent on org+type+value).

    ``touch=False`` only enriches attributes of an existing asset: sightings
    (``last_seen``, liveness, label) are then owned by the inventory sync.
    """
    value = value.strip().lower() if asset_type in ("host", "domain", "ip") else value.strip()
    existing = (
        db.query(Asset)
        .filter(
            Asset.organization_id == organization_id,
            Asset.asset_type == asset_type,
            Asset.value == value,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        if touch:
            existing.is_alive = is_alive
            existing.last_seen = now
            if label:
                existing.label = label
            if last_scan_id:
                existing.last_scan_id = last_scan_id
        if attributes:
            merged = dict(existing.attributes or {})
            merged.update(attributes)
            existing.attributes = merged
        return existing

    asset = Asset(
        organization_id=organization_id,
        asset_type=asset_type,
        value=value,
        label=label or value,
        is_alive=is_alive,
        last_scan_id=last_scan_id,
        first_seen=now,
        last_seen=now,
        attributes=attributes or {},
    )
    db.add(asset)
    db.flush()
    return asset


def upsert_relationship(
    db: Session,
    organization_id: str,
    source_asset_id: str,
    target_asset_id: str,
    relationship_type: str,
    *,
    weight: Optional[float] = 1.0,
    last_scan_id: Optional[str] = None,
) -> Optional[AssetRelationship]:
    """Insert or refresh an asset relationship (idempotent on the unique triple)."""
    if source_asset_id == target_asset_id:
        return None
    existing = (
        db.query(AssetRelationship)
        .filter(
            AssetRelationship.source_asset_id == source_asset_id,
            AssetRelationship.target_asset_id == target_asset_id,
            AssetRelationship.relationship_type == relationship_type,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.last_seen = now
        existing.last_scan_id = last_scan_id
        if weight is not None:
            existing.weight = {"value": weight}
        return existing
    rel = AssetRelationship(
        organization_id=organization_id,
        source_asset_id=source_asset_id,
        target_asset_id=target_asset_id,
        relationship_type=relationship_type,
        weight={"value": weight or 1.0},
        last_scan_id=last_scan_id,
        last_seen=now,
    )
    db.add(rel)
    db.flush()
    return rel


def get_asset_graph(
    db: Session,
    organization_id: str,
    *,
    asset_types: Optional[List[str]] = None,
    relationship_types: Optional[List[str]] = None,
    only_alive: bool = True,
) -> dict:
    """Return a graph of assets (nodes) and relationships (edges).

    Supports filtering by asset/relationship type for the frontend graph
    inspector and clustering. Stable across scans because it reads the canonical
    ``Asset``/``AssetRelationship`` tables rather than per-scan rows.
    """
    query = db.query(Asset).filter(Asset.organization_id == organization_id)
    if only_alive:
        query = query.filter(Asset.is_alive == True)  # noqa: E712
    if asset_types:
        query = query.filter(Asset.asset_type.in_(asset_types))
    else:
        # Services, technologies and root-domain records belong to the
        # inventory; they have no edges and would only clutter the graph.
        from app.services.inventory import INVENTORY_ONLY_TYPES

        query = query.filter(Asset.asset_type.notin_(INVENTORY_ONLY_TYPES))
    assets = query.all()
    asset_ids = {a.id for a in assets}

    rel_query = db.query(AssetRelationship).filter(
        AssetRelationship.organization_id == organization_id,
        AssetRelationship.source_asset_id.in_(asset_ids),
        AssetRelationship.target_asset_id.in_(asset_ids),
    )
    if relationship_types:
        rel_query = rel_query.filter(
            AssetRelationship.relationship_type.in_(relationship_types)
        )
    relationships = rel_query.all()

    nodes = [
        {
            "id": a.id,
            "type": a.asset_type,
            "label": a.label or a.value,
            "value": a.value,
            "is_alive": a.is_alive,
            "attributes": a.attributes or {},
        }
        for a in assets
    ]
    edges = [
        {
            "id": r.id,
            "source": r.source_asset_id,
            "target": r.target_asset_id,
            "type": r.relationship_type,
            "weight": (r.weight or {}).get("value", 1.0),
        }
        for r in relationships
    ]
    return {"nodes": nodes, "edges": edges, "counts": {"nodes": len(nodes), "edges": len(edges)}}


def backfill_from_scan(db: Session, scan, host_assets: Optional[dict] = None) -> None:
    """Create/update graph relationships (and enrichment) from a completed scan.

    Called after ``inventory.sync_scan``. When ``host_assets`` (hostname ->
    Asset, from the inventory sync) is given, only those hosts are linked, so
    hosts the plan did not admit get no graph nodes either. Non-destructive: it
    only inserts/updates Asset rows and never touches raw scan tables.
    """
    org_id = getattr(scan, "organization_id", None)
    if not org_id:
        # Scans are user-scoped; derive org from the owning user when missing.
        user = db.query(__import__("app.models.user", fromlist=["User"]).User).filter_by(
            id=scan.created_by
        ).first()
        org_id = user.organization_id if user else None
    if not org_id:
        logger.info("Skipping asset backfill: no organization for scan %s", scan.id)
        return

    touch = host_assets is None
    subdomains = db.query(Subdomain).filter(Subdomain.scan_id == scan.id).all()
    asset_by_host: dict[str, Asset] = {}
    ip_assets: dict[str, Asset] = {}

    # Load WHOIS registrar keyed by domain to enrich host assets (registrar clustering).
    from app.models.whois import WhoisRecord

    whois_records = db.query(WhoisRecord).filter(WhoisRecord.scan_id == scan.id).all()
    registrar_by_domain: dict[str, str] = {
        wr.domain.lower(): wr.registrar for wr in whois_records if wr.registrar
    }
    parent_domain = (scan.domain or "").lower()

    for sub in subdomains:
        if host_assets is not None and sub.hostname.strip().strip(".").lower() not in host_assets:
            continue
        host_attrs = {"ip_addresses": sub.ip_addresses or []} if sub.ip_addresses else {}
        # Registrar for the scanned (apex) domain enriches clustering.
        if sub.hostname.lower() == parent_domain or sub.hostname.lower().endswith(f".{parent_domain}"):
            reg = registrar_by_domain.get(parent_domain)
            if reg:
                host_attrs["registrar"] = reg
        # Nmap OS detection and host scripts (enriches Node Intel panel).
        if sub.os_detection:
            host_attrs["os_detection"] = sub.os_detection
        if sub.host_scripts:
            host_attrs["host_scripts"] = sub.host_scripts

        host_asset = upsert_asset(
            db, org_id, "host", sub.hostname,
            label=sub.hostname, is_alive=bool(sub.is_alive),
            last_scan_id=scan.id, touch=touch,
            attributes=host_attrs,
        )
        asset_by_host[sub.hostname.lower()] = host_asset

        for ip in (sub.ip_addresses or []):
            ip_str = str(ip)
            ip_asset = ip_assets.get(ip_str) or upsert_asset(
                db, org_id, "ip", ip_str, label=ip_str, last_scan_id=scan.id, touch=touch
            )
            ip_assets[ip_str] = ip_asset
            upsert_relationship(db, org_id, host_asset.id, ip_asset.id, "resolves_to")

            # ASN grouping: host/ip belongs_to an ASN asset (weak ownership signal).
            asn_info = resolve_asn(ip_str)
            if asn_info:
                asn_asset = upsert_asset(
                    db, org_id, "asn", asn_info["asn"],
                    label=asn_info["provider"], last_scan_id=scan.id, touch=touch,
                    attributes={"provider": asn_info["provider"]},
                )
                upsert_relationship(db, org_id, host_asset.id, asn_asset.id, "belongs_to")
                upsert_relationship(db, org_id, ip_asset.id, asn_asset.id, "belongs_to")

        # Certificate -> host (serves); persist SANs for overlap matching.
        for cert in sub.ssl_certificates:
            cert_id_val = cert.serial_number or cert.subject or f"cert:{sub.hostname}"
            cert_asset = upsert_asset(
                db, org_id, "certificate", str(cert_id_val),
                label=sub.hostname, last_scan_id=scan.id, touch=touch,
                attributes={
                    "grade": cert.grade,
                    "issuer": cert.issuer,
                    "san": cert.san or [],
                    "not_after": cert.not_after.isoformat() if cert.not_after else None,
                },
            )
            upsert_relationship(db, org_id, host_asset.id, cert_asset.id, "serves")

        # Ports -> host (open port attribute). The inventory sync already set
        # the current list; only fill it in when running without the inventory.
        if host_assets is None:
            attrs = dict(host_asset.attributes or {})
            attrs["open_ports"] = sorted({p.port_number for p in sub.ports if p.port_number is not None})
            host_asset.attributes = attrs

    # Shared-hosting edges: hosts resolving to the same IP are co-located.
    for ip_str, ip_asset in ip_assets.items():
        cohosts = [
            a.id for a in asset_by_host.values()
            if ip_str in [str(x) for x in (a.attributes or {}).get("ip_addresses", [])]
        ]
        for other_id in cohosts:
            if other_id != ip_asset.id:
                upsert_relationship(db, org_id, ip_asset.id, other_id, "shared_hosting")

    # Shared-registrar clustering: one registrar asset node per registrar, with
    # belongs_to edges from each host (same pattern as ASN grouping). Avoids the
    # O(n^2) pairwise shared_registrar edge explosion as subdomain counts grow.
    registrar_map: dict[str, list] = {}
    for host_asset in asset_by_host.values():
        reg = (host_asset.attributes or {}).get("registrar")
        if reg:
            registrar_map.setdefault(reg, []).append(host_asset.id)
    for reg, host_ids in registrar_map.items():
        # Slugify registrar name into a stable asset value.
        reg_slug = reg.strip().lower().replace(" ", "-")
        registrar_asset = upsert_asset(
            db, org_id, "registrar", reg_slug,
            label=reg, last_scan_id=scan.id, touch=touch,
            attributes={"registrar": reg},
        )
        for host_id in host_ids:
            upsert_relationship(db, org_id, host_id, registrar_asset.id, "belongs_to")

    db.commit()
