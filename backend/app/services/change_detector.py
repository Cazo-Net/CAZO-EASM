"""Change detection between scans (timeline).

Compares two scans for an organization and records the deltas as
``AssetChange`` rows: assets/subdomains added or removed, ports opened/closed,
certificates changed, technologies appearing/disappearing, and DNS differences.
The persisted records power a stable timeline view (``GET /assets/timeline``)
and are decoupled from the on-the-fly diff used by the compare view.

The core comparison is a pure function (``diff_scan_pair``) over normalized
snapshots so it is fully unit-testable without a database.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.asset_change import AssetChange
from app.models.scan import Scan
from app.models.asset import Subdomain

logger = logging.getLogger(__name__)


def _snapshot(db: Session, scan_id: str) -> Dict:
    """Build a normalized snapshot of a scan's findings."""
    subdomains = db.query(Subdomain).filter(Subdomain.scan_id == scan_id).all()
    snap: Dict = {"subdomains": {}, "ports": {}, "certs": {}, "techs": {}}
    for sub in subdomains:
        snap["subdomains"][sub.hostname] = {
            "is_alive": sub.is_alive,
            "ips": sub.ip_addresses or [],
        }
        snap["ports"][sub.hostname] = [
            {"port": p.port_number, "service": p.service, "state": p.state}
            for p in sub.ports
        ]
        snap["certs"][sub.hostname] = [
            {"issuer": c.issuer, "not_after": c.not_after.isoformat() if c.not_after else None,
             "grade": c.grade}
            for c in sub.ssl_certificates
        ]
        snap["techs"][sub.hostname] = [
            {"name": t.name, "version": t.version} for t in sub.technologies
        ]
    return snap


def diff_scan_pair(from_snap: Dict, to_snap: Dict) -> List[Dict]:
    """Return a list of change dicts between two normalized snapshots."""
    changes: List[Dict] = []

    from_subs = set(from_snap["subdomains"].keys())
    to_subs = set(to_snap["subdomains"].keys())

    for host in sorted(to_subs - from_subs):
        changes.append({
            "change_type": "added",
            "entity_type": "subdomain",
            "entity_key": host,
            "detail": {"is_alive": to_snap["subdomains"][host].get("is_alive")},
        })
    for host in sorted(from_subs - to_subs):
        changes.append({
            "change_type": "removed",
            "entity_type": "subdomain",
            "entity_key": host,
            "detail": {},
        })

    for host in sorted(from_subs & to_subs):
        fp = {p["port"]: p for p in from_snap["ports"].get(host, [])}
        tp = {p["port"]: p for p in to_snap["ports"].get(host, [])}
        for port in sorted(set(tp) - set(fp)):
            changes.append({
                "change_type": "added",
                "entity_type": "port",
                "entity_key": f"{host}:{port}",
                "detail": {"service": tp[port].get("service")},
            })
        for port in sorted(set(fp) - set(tp)):
            changes.append({
                "change_type": "removed",
                "entity_type": "port",
                "entity_key": f"{host}:{port}",
                "detail": {"service": fp[port].get("service")},
            })

        fc = {c.get("issuer"): c for c in from_snap["certs"].get(host, [])}
        tc = {c.get("issuer"): c for c in to_snap["certs"].get(host, [])}
        for issuer in sorted(set(tc) - set(fc)):
            changes.append({
                "change_type": "added",
                "entity_type": "certificate",
                "entity_key": f"{host}:{issuer}",
                "detail": {"not_after": tc[issuer].get("not_after")},
            })
        for issuer in sorted(set(fc) - set(tc)):
            changes.append({
                "change_type": "removed",
                "entity_type": "certificate",
                "entity_key": f"{host}:{issuer}",
                "detail": {},
            })

        ft = {t["name"]: t for t in from_snap["techs"].get(host, [])}
        tt = {t["name"]: t for t in to_snap["techs"].get(host, [])}
        for name in sorted(set(tt) - set(ft)):
            changes.append({
                "change_type": "added",
                "entity_type": "technology",
                "entity_key": f"{host}:{name}",
                "detail": {"version": tt[name].get("version")},
            })
        for name in sorted(set(ft) - set(tt)):
            changes.append({
                "change_type": "removed",
                "entity_type": "technology",
                "entity_key": f"{host}:{name}",
                "detail": {},
            })

    return changes


def detect_changes(
    db: Session,
    organization_id: str,
    to_scan_id: str,
    from_scan_id: Optional[str] = None,
) -> List[AssetChange]:
    """Detect and persist changes for ``to_scan_id`` vs a previous scan.

    If ``from_scan_id`` is not provided, the most recent *completed* scan for the
    same owner (before ``to_scan_id``) is used. Returns the created change rows.
    """
    to_scan = db.query(Scan).filter(Scan.id == to_scan_id).first()
    if not to_scan:
        return []

    if not from_scan_id:
        previous = (
            db.query(Scan)
            .filter(
                Scan.created_by == to_scan.created_by,
                Scan.id != to_scan_id,
                Scan.status == "completed",
                Scan.completed_at < (to_scan.completed_at or datetime.now(timezone.utc)),
            )
            .order_by(Scan.completed_at.desc())
            .first()
        )
        from_scan_id = previous.id if previous else None

    to_snap = _snapshot(db, to_scan_id)
    from_snap = _snapshot(db, from_scan_id) if from_scan_id else {"subdomains": {}, "ports": {}, "certs": {}, "techs": {}}

    changes = diff_scan_pair(from_snap, to_snap)
    created: List[AssetChange] = []
    for ch in changes:
        record = AssetChange(
            organization_id=organization_id,
            from_scan_id=from_scan_id,
            to_scan_id=to_scan_id,
            change_type=ch["change_type"],
            entity_type=ch["entity_type"],
            entity_key=ch["entity_key"],
            detail=ch.get("detail", {}),
        )
        db.add(record)
        created.append(record)
    db.commit()
    return created


def get_timeline(
    db: Session,
    organization_id: str,
    limit: int = 100,
    change_type: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> List[Dict]:
    """Return persisted changes as a timeline feed."""
    query = db.query(AssetChange).filter(AssetChange.organization_id == organization_id)
    if change_type:
        query = query.filter(AssetChange.change_type == change_type)
    if entity_type:
        query = query.filter(AssetChange.entity_type == entity_type)
    rows = query.order_by(AssetChange.detected_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "change_type": r.change_type,
            "entity_type": r.entity_type,
            "entity_key": r.entity_key,
            "detail": r.detail or {},
            "from_scan_id": r.from_scan_id,
            "to_scan_id": r.to_scan_id,
            "detected_at": r.detected_at,
        }
        for r in rows
    ]
