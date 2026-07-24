"""Shodan-style search engine over the organization's external attack surface.

Supports query syntax with ``key:value`` filters and free-text terms, e.g.::

    port:443 asn:AS13335 org:"Cloudflare" nginx
    service:ssh tech:WordPress hostname:api.

Filters are case-insensitive. Unknown keys fall back to free-text search.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import re

from app.database import get_db
from app.models.user import User
from app.models.asset import Subdomain
from app.models.port import Port
from app.models.ssl import SSLCertificate
from app.models.technology import Technology
from app.models.scan import Scan
from app.models.vulnerability import Vulnerability
from app.models.asset_inventory import Asset, AssetRelationship
from app.api.deps import get_current_user

router = APIRouter()

_FILTER_KEYS = {
    "port": "port",
    "service": "service",
    "product": "service",
    "asn": "asn",
    "org": "org",
    "isp": "org",
    "ip": "ip",
    "host": "host",
    "hostname": "host",
    "tech": "tech",
    "technology": "tech",
    "cert": "cert",
    "ssl": "cert",
    "status": "status",
    "vuln": "vuln",
    "severity": "vuln",
}

_TERM_RE = re.compile(r'(\w+):"([^"]*)"|(\w+):(\S+)|"([^"]*)"|(\S+)')


def _parse_query(query: str):
    """Return (filters: dict[str,str], terms: list[str])."""
    filters: dict = {}
    terms: list = []
    for m in _TERM_RE.finditer(query or ""):
        key_quoted, val_quoted, key, val, bare_quoted, bare = m.groups()
        if key_quoted is not None:
            k, v = key_quoted, val_quoted
        elif key is not None:
            k, v = key, val
        elif bare_quoted is not None:
            terms.append(bare_quoted.lower())
            continue
        else:
            terms.append(bare.lower())
            continue
        k = k.lower()
        if k in _FILTER_KEYS:
            filters.setdefault(_FILTER_KEYS[k], []).append(v)
        else:
            terms.append(f"{k}:{v}".lower())
    return filters, terms


def _org_scans(db: Session, org_id: str):
    return db.query(Scan.id).filter(Scan.organization_id == org_id).subquery()


def _match_subdomain_ids(db, org_id, filters, terms):
    """Resolve the set of subdomain ids matching the query."""
    q = db.query(Subdomain).join(Scan, Subdomain.scan_id == Scan.id).filter(
        Scan.organization_id == org_id
    )

    port_filter = filters.get("port")
    service_filter = filters.get("service")
    tech_filter = filters.get("tech")
    cert_filter = filters.get("cert")
    status_filter = filters.get("status")
    ip_filter = filters.get("ip")
    host_filter = filters.get("host")
    asn_filter = filters.get("asn")
    org_filter = filters.get("org")
    vuln_filter = filters.get("vuln")

    # Pre-filter subdomains by hostname / ip / status free matches.
    host_conds = []
    if host_filter:
        for h in host_filter:
            host_conds.append(Subdomain.hostname.ilike(f"%{h}%"))
    if ip_filter:
        for ip in ip_filter:
            host_conds.append(Subdomain.ip_addresses.any(ip))
    if status_filter:
        for st in status_filter:
            host_conds.append(Subdomain.status.ilike(f"%{st}%"))
    if terms:
        for t in terms:
            host_conds.append(Subdomain.hostname.ilike(f"%{t}%"))

    sub_q = q
    if host_conds:
        from sqlalchemy import or_
        sub_q = sub_q.filter(or_(*host_conds))

    subs = sub_q.all()
    matched_ids = set()
    for s in subs:
        # ASN / org filtering is done via asset relationships on resolved IPs.
        if asn_filter or org_filter:
            ips = s.ip_addresses or []
            ok = True
            if asn_filter or org_filter:
                if not _asset_matches_asn_org(db, org_id, ips, asn_filter, org_filter):
                    ok = False
            if not ok:
                continue
        # Port / service filtering.
        if port_filter or service_filter:
            if not _sub_has_port(db, s.id, port_filter, service_filter):
                continue
        # Tech filtering.
        if tech_filter:
            if not _sub_has_tech(db, s.id, tech_filter):
                continue
        # Cert filtering.
        if cert_filter:
            if not _sub_has_cert(db, s.id, cert_filter):
                continue
        # Vuln / severity filtering.
        if vuln_filter:
            if not _sub_has_vuln(db, s.id, vuln_filter):
                continue
        matched_ids.add(s.id)
    return matched_ids


def _ip_to_asset_ids(db, org_id, ips):
    if not ips:
        return set()
    assets = (
        db.query(Asset)
        .filter(Asset.organization_id == org_id, Asset.asset_type == "ip", Asset.value.in_(ips))
        .all()
    )
    return {a.id for a in assets}


def _asset_matches_asn_org(db, org_id, ips, asn_filter, org_filter):
    asset_ids = _ip_to_asset_ids(db, org_id, ips)
    if not asset_ids:
        # Hosts may also be linked directly (rare); fall back to host asset.
        return False
    edges = (
        db.query(AssetRelationship)
        .filter(
            AssetRelationship.source_asset_id.in_(asset_ids),
            AssetRelationship.relationship_type == "belongs_to",
        )
        .all()
    )
    target_ids = {e.target_asset_id for e in edges}
    if not target_ids:
        return False
    asn_assets = db.query(Asset).filter(Asset.id.in_(target_ids)).all()
    if asn_filter:
        want = [a.lower() for a in asn_filter]
        if not any(
            (a.value and a.value.lower() in [w.replace("as", "") for w in want])
            or (a.value and a.value.lower() in want)
            or (a.label and a.label.lower() in want)
            for a in asn_assets
        ):
            return False
    if org_filter:
        want = [o.lower() for o in org_filter]
        if not any(
            (a.label and a.label.lower() in want)
            or ((a.attributes or {}).get("provider", "").lower() in want)
            or (a.value and a.value.lower() in want)
            for a in asn_assets
        ):
            return False
    return True


def _sub_has_port(db, sub_id, port_filter, service_filter):
    q = db.query(Port).filter(Port.subdomain_id == sub_id)
    if port_filter:
        nums = []
        for p in port_filter:
            try:
                nums.append(int(p))
            except ValueError:
                pass
        if nums:
            q = q.filter(Port.port_number.in_(nums))
        else:
            return False
    if service_filter:
        for svc in service_filter:
            q = q.filter(Port.service.ilike(f"%{svc}%"))
    return q.first() is not None


def _sub_has_tech(db, sub_id, tech_filter):
    q = db.query(Technology).filter(Technology.subdomain_id == sub_id)
    for t in tech_filter:
        q = q.filter(
            (Technology.name.ilike(f"%{t}%")) | (Technology.category.ilike(f"%{t}%"))
        )
    return q.first() is not None


def _sub_has_cert(db, sub_id, cert_filter):
    q = db.query(SSLCertificate).filter(SSLCertificate.subdomain_id == sub_id)
    for c in cert_filter:
        q = q.filter(
            (SSLCertificate.issuer.ilike(f"%{c}%"))
            | (SSLCertificate.subject.ilike(f"%{c}%"))
        )
    return q.first() is not None


def _sub_has_vuln(db, sub_id, vuln_filter):
    q = db.query(Vulnerability).filter(Vulnerability.subdomain_id == sub_id)
    for v in vuln_filter:
        q = q.filter(
            (Vulnerability.name.ilike(f"%{v}%"))
            | (Vulnerability.severity.ilike(f"%{v}%"))
        )
    return q.first() is not None


@router.get("")
async def search(
    q: str = Query("", description="Shodan-style query (e.g. port:443 asn:AS13335 nginx)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search the external attack surface with Shodan-like filters."""
    if not current_user.organization_id:
        return {"query": q, "total": 0, "results": []}

    filters, terms = _parse_query(q)
    sub_ids = _match_subdomain_ids(db, current_user.organization_id, filters, terms)

    subs = (
        db.query(Subdomain)
        .filter(Subdomain.id.in_(sub_ids))
        .order_by(Subdomain.hostname.asc())
        .limit(limit)
        .all()
    )

    results = []
    for s in subs:
        ips = s.ip_addresses or []
        # Attach a summary of matched ports/techs for the result card.
        ports = (
            db.query(Port)
            .filter(Port.subdomain_id == s.id, Port.state == "open")
            .order_by(Port.port_number.asc())
            .all()
        )
        port_list = [
            {"port": p.port_number, "service": p.service, "version": p.version}
            for p in ports
        ]
        # Resolve ASN/org via IP asset relationships.
        asn_label = None
        org_label = None
        asset_ids = _ip_to_asset_ids(db, current_user.organization_id, ips)
        if asset_ids:
            edges = (
                db.query(AssetRelationship)
                .filter(
                    AssetRelationship.source_asset_id.in_(asset_ids),
                    AssetRelationship.relationship_type == "belongs_to",
                )
                .all()
            )
            asn_assets = (
                db.query(Asset)
                .filter(Asset.id.in_({e.target_asset_id for e in edges}))
                .all()
            )
            if asn_assets:
                asn_label = asn_assets[0].value
                org_label = asn_assets[0].label or (asn_assets[0].attributes or {}).get("provider")

        vuln_count = (
            db.query(Vulnerability)
            .filter(Vulnerability.subdomain_id == s.id)
            .count()
        )

        results.append(
            {
                "asset_id": None,
                "subdomain_id": s.id,
                "hostname": s.hostname,
                "ip_addresses": ips,
                "is_alive": s.is_alive,
                "asn": asn_label,
                "org": org_label,
                "open_ports": port_list,
                "port_count": len(port_list),
                "vulnerability_count": vuln_count,
            }
        )

    return {"query": q, "total": len(results), "results": results}
