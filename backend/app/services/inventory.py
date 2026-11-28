"""Canonical, deduplicated asset inventory with history.

Every completed scan is folded into one organization-wide inventory instead of
being listed again as a fresh set of rows:

* **Assets** (``assets`` table) are unique per organization on
  ``(asset_type, value)``: ``domain`` (registrable root), ``host`` (FQDN),
  ``ip``, ``service`` (``host:port/tcp``), ``certificate`` (serial) and
  ``technology`` (``host|name``). Each keeps ``first_seen`` / ``last_seen``.
* **History** (``asset_changes`` table) records what changed and when: a new
  asset, a new or closed service, a replaced or expiring certificate, a
  technology or IP change, an asset that disappeared or came back, and a new
  serious finding.
* **Lifecycle**: an asset is marked ``missing`` only after
  ``MISSING_AFTER_SCANS`` covering scans in a row did not see it, so one flaky
  probe does not raise a false "disappeared" alert. Quick scans never mark
  anything missing because they do not look at the whole surface.

Tenant isolation: every query here is filtered by ``organization_id`` and the
organization comes from the scan row, never from request input.

Plan limits: hosts beyond the plan's ``hosts`` allowance are not added to the
inventory (see ``_host_budget``); the skipped count is reported so the UI can
say so.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session, selectinload

from app.billing.entitlements import get_entitlement, root_domain
from app.config import settings
from app.models.asset import Subdomain
from app.models.asset_change import AssetChange, InventorySync
from app.models.asset_inventory import Asset
from app.models.scan import Scan
from app.models.vulnerability import Vulnerability

logger = logging.getLogger(__name__)

# Covering scans in a row that must miss an asset before it is "missing".
MISSING_AFTER_SCANS = 2

# Asset kinds the inventory tracks (the graph also stores asn / registrar).
INVENTORY_TYPES = ("domain", "host", "ip", "service", "certificate", "technology")
# Kinds that only the inventory uses; older screens (graph, scoring, shadow
# asset counts) were written before they existed and leave them out.
INVENTORY_ONLY_TYPES = ("domain", "service", "technology")

SEVERITY_RANK = {"info": 0, "unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

# Ports whose appearance on the internet is worth a louder note.
SENSITIVE_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 445: "SMB", 1433: "MSSQL", 1521: "Oracle",
    2375: "Docker API", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    5900: "VNC", 6379: "Redis", 9200: "Elasticsearch", 11211: "Memcached",
    27017: "MongoDB",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, str) and value:
        try:
            return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _norm_host(value: str) -> str:
    return (value or "").strip().strip(".").lower()


# ── What a scan saw ──────────────────────────────────────────────────────


@dataclass
class Observation:
    asset_type: str
    value: str
    label: str
    host: Optional[str] = None  # owning hostname for service/cert/technology
    attributes: Dict[str, Any] = field(default_factory=dict)
    is_alive: bool = True


@dataclass
class SyncResult:
    organization_id: Optional[str] = None
    scan_id: Optional[str] = None
    root: str = ""
    skipped: bool = False
    reason: str = ""
    new_assets: int = 0
    updated_assets: int = 0
    events: List[AssetChange] = field(default_factory=list)
    # Alert groups: alert_type -> list of event dicts (see inventory_alerts).
    alerts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    hosts_over_limit: int = 0
    host_limit: Optional[int] = None
    host_assets: Dict[str, Asset] = field(default_factory=dict)


def cert_key(cert, hostname: str) -> str:
    """Stable identifier for a certificate: its serial when the scan got one."""
    return str(cert.serial_number or cert.subject or f"cert:{hostname}").strip()


def observe_scan(db: Session, scan: Scan) -> List[Observation]:
    """Normalize one scan's stored results into inventory observations."""
    subs = (
        db.query(Subdomain)
        .options(
            selectinload(Subdomain.ports),
            selectinload(Subdomain.ssl_certificates),
            selectinload(Subdomain.technologies),
            selectinload(Subdomain.dns_records),
        )
        .filter(Subdomain.scan_id == scan.id)
        .all()
    )
    out: List[Observation] = []
    seen: set[Tuple[str, str]] = set()

    def add(obs: Observation) -> None:
        key = (obs.asset_type, obs.value)
        if not obs.value or key in seen:
            return
        seen.add(key)
        out.append(obs)

    root = root_domain(scan.domain)
    if root:
        add(Observation("domain", root, root))

    for sub in subs:
        host = _norm_host(sub.hostname)
        if not host:
            continue
        ips = [str(ip).strip().lower() for ip in (sub.ip_addresses or []) if ip]
        if not ips:
            ips = [
                str(r.value).strip().lower()
                for r in sub.dns_records
                if r.record_type in ("A", "AAAA") and r.value
            ]
        ips = sorted(set(ips))
        open_ports = sorted({
            int(p.port_number) for p in sub.ports
            if p.port_number is not None and (p.state or "open") == "open"
        })
        add(Observation(
            "host", host, host,
            attributes={"ip_addresses": ips, "open_ports": open_ports},
            is_alive=bool(sub.is_alive),
        ))
        for ip in ips:
            add(Observation("ip", ip, ip, host=host))
        for p in sub.ports:
            if p.port_number is None or (p.state or "open") != "open":
                continue
            port = int(p.port_number)
            add(Observation(
                "service", f"{host}:{port}/tcp", f"{host}:{port}", host=host,
                attributes={
                    "port": port, "protocol": "tcp",
                    "service": p.service or "", "version": p.version or "",
                    "product": p.banner or "",
                },
            ))
        for c in sub.ssl_certificates:
            key = cert_key(c, host)
            not_after = _aware(c.not_after)
            not_before = _aware(c.not_before)
            add(Observation(
                "certificate", key, c.subject or host, host=host,
                attributes={
                    "issuer": c.issuer, "subject": c.subject,
                    "serial_number": c.serial_number,
                    "not_before": not_before.isoformat() if not_before else None,
                    "not_after": not_after.isoformat() if not_after else None,
                    "grade": c.grade, "san": c.san or [],
                    "is_valid": bool(c.is_valid) if c.is_valid is not None else None,
                },
            ))
        for t in sub.technologies:
            name = (t.name or "").strip()
            if not name:
                continue
            add(Observation(
                "technology", f"{host}|{name.lower()}", name, host=host,
                attributes={"name": name, "version": t.version or "", "category": t.category or ""},
            ))
    return out


# ── Helpers ──────────────────────────────────────────────────────────────


def resolve_org_id(db: Session, scan: Scan) -> Optional[str]:
    org_id = getattr(scan, "organization_id", None)
    if org_id:
        return org_id
    if scan.created_by:
        from app.models.user import User

        user = db.query(User).filter(User.id == scan.created_by).first()
        return user.organization_id if user else None
    return None


def _chunks(items: List[str], size: int = 400) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _load_existing(db: Session, org_id: str, observations: List[Observation]) -> Dict[Tuple[str, str], Asset]:
    by_type: Dict[str, List[str]] = {}
    for o in observations:
        by_type.setdefault(o.asset_type, []).append(o.value)
    found: Dict[Tuple[str, str], Asset] = {}
    for asset_type, values in by_type.items():
        for chunk in _chunks(values):
            rows = (
                db.query(Asset)
                .filter(
                    Asset.organization_id == org_id,
                    Asset.asset_type == asset_type,
                    Asset.value.in_(chunk),
                )
                .all()
            )
            for a in rows:
                found[(a.asset_type, a.value)] = a
    return found


def count_inventory_hosts(db: Session, org_id: str) -> int:
    """Hosts that count toward the plan: every host that is not missing."""
    return (
        db.query(Asset)
        .filter(
            Asset.organization_id == org_id,
            Asset.asset_type == "host",
            Asset.state != "missing",
        )
        .count()
    )


def _host_budget(db: Session, org_id: str) -> Tuple[Optional[int], Optional[int]]:
    """(limit, remaining) hosts the plan still allows; ``None`` = unlimited."""
    if not settings.BILLING_ENFORCE_LIMITS:
        return None, None
    try:
        limit = get_entitlement(db, org_id).limits.get("hosts")
    except Exception as exc:  # noqa: BLE001 - never let billing break a scan
        logger.warning("Could not read plan limits for %s: %s", org_id, exc)
        return None, None
    if limit is None:
        return None, None
    return limit, max(0, limit - count_inventory_hosts(db, org_id))


def adopt_legacy_assets(db: Session, org_id: str) -> int:
    """Fill inventory fields on assets written before the inventory existed."""
    rows = (
        db.query(Asset)
        .filter(
            Asset.organization_id == org_id,
            Asset.asset_type.in_(("host", "certificate")),
            Asset.root_domain.is_(None),
        )
        .all()
    )
    for a in rows:
        if a.asset_type == "host":
            a.root_domain = root_domain(a.value)
        else:
            host = _norm_host(a.label or "")
            a.root_domain = root_domain(host) if "." in host else None
            attrs = dict(a.attributes or {})
            if host and "." in host and not attrs.get("hosts"):
                attrs["hosts"] = [host]
                a.attributes = attrs
            if a.root_domain is None:
                a.root_domain = ""
    if rows:
        db.flush()
    return len(rows)


def _already_synced(db: Session, scan_id: str) -> bool:
    return db.query(InventorySync.scan_id).filter(InventorySync.scan_id == scan_id).first() is not None


def _newer_sync_exists(db: Session, org_id: str, root: str, when: datetime) -> bool:
    """True when a later scan of this root is already in the inventory."""
    rows = (
        db.query(InventorySync.observed_at)
        .filter(InventorySync.organization_id == org_id, InventorySync.root_domain == root)
        .all()
    )
    return any(o is not None and _aware(o) > when for (o,) in rows)


def _service_label(attrs: Dict[str, Any]) -> str:
    name = attrs.get("service") or SENSITIVE_PORTS.get(attrs.get("port")) or ""
    return f"{attrs.get('port')}/tcp" + (f" ({name})" if name else "")


# ── Sync ─────────────────────────────────────────────────────────────────


def sync_scan(db: Session, scan: Scan, *, at: Optional[datetime] = None) -> SyncResult:
    """Fold a completed scan into the organization's inventory.

    Idempotent per scan. Returns what changed; sending alerts is the caller's
    job (``inventory_alerts.dispatch_alerts``) so a rebuild from old scans can
    stay silent.
    """
    result = SyncResult(scan_id=scan.id)
    org_id = resolve_org_id(db, scan)
    if not org_id:
        result.skipped, result.reason = True, "scan has no organization"
        return result
    result.organization_id = org_id
    root = root_domain(scan.domain)
    result.root = root
    if not root:
        result.skipped, result.reason = True, "scan has no domain"
        return result
    if _already_synced(db, scan.id):
        result.skipped, result.reason = True, "already synced"
        return result

    now = _aware(at) or _aware(scan.completed_at) or _utcnow()
    scan_target = _norm_host(scan.domain)
    # A scan processed after a newer one (rebuild from history) may only add
    # what it saw; it must not close ports or hide hosts the newer scan found.
    late = _newer_sync_exists(db, org_id, root, now)
    authoritative = (scan.scan_type or "full") != "quick" and not late
    db.add(InventorySync(scan_id=scan.id, organization_id=org_id, root_domain=root, observed_at=now))

    adopt_legacy_assets(db, org_id)
    observations = observe_scan(db, scan)
    existing = _load_existing(db, org_id, observations)

    # Which kinds already had history under this root? A kind with none is a
    # baseline: it is recorded, but "new ..." alerts would only be noise.
    known_types = {
        t for (t,) in db.query(Asset.asset_type)
        .filter(Asset.organization_id == org_id, Asset.root_domain == root)
        .distinct()
        .all()
    }

    # Plan allowance: only brand-new hosts consume it.
    limit, remaining = _host_budget(db, org_id)
    result.host_limit = limit
    new_hosts = [o for o in observations if o.asset_type == "host" and ("host", o.value) not in existing]
    skipped_hosts: set[str] = set()
    if remaining is not None and len(new_hosts) > remaining:
        # Keep the scan target and live hosts first.
        ordered = sorted(new_hosts, key=lambda o: (o.value != scan_target, not o.is_alive, o.value))
        skipped_hosts = {o.value for o in ordered[remaining:]}
        result.hosts_over_limit = len(skipped_hosts)

    events: List[AssetChange] = []
    alerts: Dict[str, List[Dict[str, Any]]] = {}

    def record(asset: Optional[Asset], change_type: str, entity_type: str, key: str, event: str,
               summary: str, *, severity: str = "info", detail: Optional[dict] = None,
               alert: Optional[str] = None) -> None:
        row = AssetChange(
            organization_id=org_id,
            from_scan_id=None,
            to_scan_id=scan.id,
            change_type=change_type,
            entity_type=entity_type,
            entity_key=key[:512],
            detail=detail or {},
            asset_id=asset.id if asset is not None else None,
            event=event,
            severity=severity,
            root_domain=root,
            summary=summary,
            detected_at=now,
        )
        db.add(row)
        events.append(row)
        if alert:
            alerts.setdefault(alert, []).append({
                "asset_id": row.asset_id, "key": key, "summary": summary,
                "severity": severity, "detail": detail or {},
            })

    host_assets: Dict[str, Asset] = {}
    seen_ids: set[str] = set()
    # Hosts → certificate keys served, before and after this scan.
    prior_certs: Dict[str, Dict[str, Asset]] = {}
    for a in (
        db.query(Asset)
        .filter(
            Asset.organization_id == org_id,
            Asset.asset_type == "certificate",
            Asset.state == "active",
            Asset.root_domain == root,
        )
        .all()
    ):
        for h in (a.attributes or {}).get("hosts") or []:
            prior_certs.setdefault(h, {})[a.value] = a

    order = {"domain": 0, "host": 1, "ip": 2, "service": 3, "certificate": 4, "technology": 5}
    for obs in sorted(observations, key=lambda o: order[o.asset_type]):
        if obs.asset_type == "host" and obs.value in skipped_hosts:
            continue
        if obs.host and obs.host in skipped_hosts:
            continue
        parent = host_assets.get(obs.host) if obs.host else None
        if obs.asset_type in ("service", "certificate", "technology") and parent is None:
            continue

        asset = existing.get((obs.asset_type, obs.value))
        if asset is None:
            attrs = dict(obs.attributes)
            if obs.asset_type == "certificate":
                attrs["hosts"] = [obs.host]
            asset = Asset(
                organization_id=org_id, asset_type=obs.asset_type, value=obs.value,
                label=obs.label or obs.value, is_alive=obs.is_alive,
                first_seen=now, last_seen=now, last_scan_id=scan.id,
                attributes=attrs, state="active", miss_count=0,
                root_domain=root, parent_id=parent.id if parent is not None else None,
            )
            db.add(asset)
            db.flush()
            existing[(obs.asset_type, obs.value)] = asset
            result.new_assets += 1
            baseline = obs.asset_type not in known_types
            if obs.asset_type == "host":
                record(asset, "added", "host", obs.value, "asset_new",
                       f"New host {obs.value}",
                       detail={"ip_addresses": attrs.get("ip_addresses", []), "is_alive": obs.is_alive},
                       alert=None if baseline else "new_asset")
            elif obs.asset_type == "domain":
                record(asset, "added", "domain", obs.value, "asset_new", f"Now monitoring {obs.value}")
            elif obs.asset_type == "ip":
                record(asset, "added", "ip", obs.value, "asset_new",
                       f"New IP address {obs.value} ({obs.host})", detail={"host": obs.host})
            elif obs.asset_type == "service":
                port = attrs.get("port")
                sensitive = port in SENSITIVE_PORTS
                record(asset, "added", "service", obs.value, "service_new",
                       f"New open port {_service_label(attrs)} on {obs.host}",
                       severity="medium" if sensitive else "info",
                       detail={"host": obs.host, **attrs},
                       alert=None if baseline else "new_service")
            elif obs.asset_type == "certificate":
                previous = prior_certs.get(obs.host or "", {})
                if previous:
                    old = next(iter(previous.values()))
                    old_attrs = old.attributes or {}
                    record(asset, "modified", "certificate", obs.value, "cert_changed",
                           f"Certificate replaced on {obs.host}",
                           detail={
                               "host": obs.host,
                               "old": {"serial": old.value, "issuer": old_attrs.get("issuer"),
                                       "not_after": old_attrs.get("not_after")},
                               "new": {"serial": obs.value, "issuer": attrs.get("issuer"),
                                       "not_after": attrs.get("not_after")},
                           },
                           alert="certificate_changed")
                else:
                    record(asset, "added", "certificate", obs.value, "cert_new",
                           f"New certificate on {obs.host}",
                           detail={"host": obs.host, "issuer": attrs.get("issuer"),
                                   "not_after": attrs.get("not_after")})
            elif obs.asset_type == "technology":
                version = attrs.get("version")
                record(asset, "added", "technology", obs.value, "tech_new",
                       f"New technology {attrs.get('name')}{' ' + version if version else ''} on {obs.host}",
                       detail={"host": obs.host, **attrs})
        else:
            result.updated_assets += 1
            old_attrs = dict(asset.attributes or {})
            first = _aware(asset.first_seen)
            if first is None or now < first:
                asset.first_seen = now
            if late:
                # Older data: keep the newer state, attributes and last_seen.
                seen_ids.add(asset.id)
                if obs.asset_type == "host":
                    host_assets[obs.value] = asset
                continue
            if asset.state == "missing":
                record(asset, "added", asset.asset_type, asset.value, "asset_reappeared",
                       f"{asset.label or asset.value} is back",
                       detail={"missing_since": asset.missing_since.isoformat() if asset.missing_since else None},
                       alert="new_asset" if asset.asset_type == "host" else (
                           "new_service" if asset.asset_type == "service" else None))
            asset.state = "active"
            asset.miss_count = 0
            asset.missing_since = None
            asset.last_seen = now
            asset.last_scan_id = scan.id
            asset.is_alive = obs.is_alive
            if not asset.root_domain:
                asset.root_domain = root
            if parent is not None and not asset.parent_id:
                asset.parent_id = parent.id

            merged = dict(old_attrs)
            merged.update(obs.attributes)
            if obs.asset_type == "host":
                old_ips = sorted(old_attrs.get("ip_addresses") or [])
                new_ips = sorted(obs.attributes.get("ip_addresses") or [])
                if not new_ips:
                    merged["ip_addresses"] = old_ips  # a scan without DNS data is not an IP change
                elif old_ips and old_ips != new_ips:
                    record(asset, "modified", "host", asset.value, "ip_changed",
                           f"{asset.value} now resolves to {', '.join(new_ips)}",
                           detail={"old": old_ips, "new": new_ips})
                if not authoritative and not obs.attributes.get("open_ports"):
                    merged["open_ports"] = old_attrs.get("open_ports", [])
            elif obs.asset_type == "certificate":
                hosts = list(old_attrs.get("hosts") or [])
                if obs.host and obs.host not in hosts:
                    hosts.append(obs.host)
                merged["hosts"] = hosts
                if "expiry_alerted" in old_attrs:
                    merged["expiry_alerted"] = old_attrs["expiry_alerted"]
            elif obs.asset_type == "technology":
                old_v, new_v = old_attrs.get("version") or "", obs.attributes.get("version") or ""
                if old_v and new_v and old_v != new_v:
                    record(asset, "modified", "technology", asset.value, "tech_changed",
                           f"{obs.attributes.get('name')} on {obs.host} changed from {old_v} to {new_v}",
                           detail={"host": obs.host, "old": old_v, "new": new_v})
                elif old_v and not new_v:
                    merged["version"] = old_v
            elif obs.asset_type == "service":
                old_s, new_s = old_attrs.get("service") or "", obs.attributes.get("service") or ""
                if old_s and new_s and old_s != new_s:
                    record(asset, "modified", "service", asset.value, "service_changed",
                           f"Service on {asset.label} changed from {old_s} to {new_s}",
                           detail={"host": obs.host, "old": old_s, "new": new_s})
            asset.attributes = merged

        seen_ids.add(asset.id)
        if obs.asset_type == "host":
            host_assets[obs.value] = asset

    db.flush()

    # A host that now serves a different certificate no longer serves the old one.
    seen_cert_by_host: Dict[str, set[str]] = {}
    for obs in observations:
        if obs.asset_type == "certificate" and obs.host in host_assets:
            seen_cert_by_host.setdefault(obs.host, set()).add(obs.value)
    for host, keys in ({} if late else seen_cert_by_host).items():
        for old_key, old in prior_certs.get(host, {}).items():
            if old_key in keys:
                continue
            attrs = dict(old.attributes or {})
            attrs["hosts"] = [h for h in (attrs.get("hosts") or []) if h != host]
            old.attributes = attrs
            if not attrs["hosts"]:
                old.state = "missing"
                old.missing_since = now

    if authoritative:
        _mark_missing(db, org_id, root, scan_target, host_assets, seen_ids, now, record)

    _record_new_findings(db, org_id, scan, host_assets, record)
    if not late:
        _check_expiry(
            [a for (t, _), a in existing.items() if t == "certificate" and a.id in seen_ids],
            now, _cert_expiry_days(db, org_id), record,
        )

    db.commit()
    result.events = events
    result.alerts = alerts
    result.host_assets = host_assets
    return result


def _mark_missing(db, org_id, root, scan_target, host_assets, seen_ids, now, record) -> None:
    """Count a miss for covered assets the scan did not see."""
    covered_all = scan_target == root
    suffix = "." + scan_target

    def bump(asset: Asset) -> bool:
        asset.miss_count = (asset.miss_count or 0) + 1
        if asset.miss_count >= MISSING_AFTER_SCANS:
            asset.state = "missing"
            asset.missing_since = now
            return True
        return False

    gone_host_ids: List[str] = []
    hosts = (
        db.query(Asset)
        .filter(
            Asset.organization_id == org_id, Asset.asset_type == "host",
            Asset.root_domain == root, Asset.state == "active",
        )
        .all()
    )
    for h in hosts:
        if h.id in seen_ids:
            continue
        if not (covered_all or h.value == scan_target or h.value.endswith(suffix)):
            continue
        if bump(h):
            gone_host_ids.append(h.id)
            record(h, "removed", "host", h.value, "asset_missing",
                   f"{h.value} was not found in the last {MISSING_AFTER_SCANS} scans",
                   detail={"last_seen": h.last_seen.isoformat() if h.last_seen else None},
                   alert="asset_disappeared")

    seen_host_ids = {a.id for a in host_assets.values()}
    parent_ids = list(seen_host_ids | set(gone_host_ids))
    for chunk in _chunks(parent_ids):
        children = (
            db.query(Asset)
            .filter(
                Asset.organization_id == org_id,
                Asset.asset_type.in_(("service", "technology")),
                Asset.parent_id.in_(chunk),
                Asset.state == "active",
            )
            .all()
        )
        for c in children:
            if c.id in seen_ids:
                continue
            if c.parent_id in gone_host_ids:
                # The host itself is gone; its services go with it, quietly.
                c.state, c.missing_since = "missing", now
                continue
            if bump(c):
                attrs = c.attributes or {}
                if c.asset_type == "service":
                    record(c, "removed", "service", c.value, "service_closed",
                           f"Port {_service_label(attrs)} on {c.value.split(':')[0]} is no longer open",
                           detail=dict(attrs))
                else:
                    record(c, "removed", "technology", c.value, "tech_removed",
                           f"{attrs.get('name') or c.label} is no longer detected on {c.value.split('|')[0]}",
                           detail=dict(attrs))


def _cert_expiry_days(db: Session, org_id: str) -> int:
    from app.models.alert_settings import AlertSettings

    row = db.query(AlertSettings).filter(AlertSettings.organization_id == org_id).first()
    days = row.cert_expiry_days if row and row.cert_expiry_days else 30
    return max(1, min(int(days), 365))


def expiry_bucket(days_left: int, threshold: int) -> Optional[int]:
    """Warning step a certificate is in: 0 = expired, then 1/7/14/30/threshold days."""
    if days_left > threshold:
        return None
    if days_left < 0:
        return 0
    for step in sorted({1, 7, 14, 30, threshold}):
        if step <= threshold and days_left <= step:
            return step
    return threshold


def _check_expiry(certs: Iterable[Asset], now: datetime, threshold: int, record) -> None:
    """Record one ``cert_expiring`` event each time a cert enters a tighter step."""
    for cert in certs:
        attrs = dict(cert.attributes or {})
        not_after = _parse_dt(attrs.get("not_after"))
        if not_after is None or cert.state != "active":
            continue
        days_left = (not_after - now).days
        bucket = expiry_bucket(days_left, threshold)
        if bucket is None:
            if "expiry_alerted" in attrs:
                attrs.pop("expiry_alerted", None)
                cert.attributes = attrs
            continue
        last = attrs.get("expiry_alerted")
        if last is not None and last <= bucket:
            continue
        attrs["expiry_alerted"] = bucket
        cert.attributes = attrs
        hosts = attrs.get("hosts") or [cert.label or cert.value]
        where = hosts[0] + (f" and {len(hosts) - 1} more" if len(hosts) > 1 else "")
        if days_left < 0:
            summary, severity = f"Certificate on {where} expired {abs(days_left)} day(s) ago", "high"
        else:
            summary = f"Certificate on {where} expires in {days_left} day(s)"
            severity = "high" if days_left <= 7 else "medium"
        record(cert, "modified", "certificate", cert.value, "cert_expiring", summary,
               severity=severity,
               detail={"hosts": hosts, "not_after": attrs.get("not_after"),
                       "days_left": days_left, "issuer": attrs.get("issuer")},
               alert="certificate_expiring")


def _record_new_findings(db, org_id, scan, host_assets, record) -> None:
    """History + alert for serious findings this organization has not had before."""
    from app.models.alert_settings import AlertSettings

    row = db.query(AlertSettings).filter(AlertSettings.organization_id == org_id).first()
    min_rank = SEVERITY_RANK.get((row.finding_min_severity if row else None) or "critical", 4)
    record_rank = min(min_rank, SEVERITY_RANK["high"])

    vulns = db.query(Vulnerability).filter(Vulnerability.scan_id == scan.id).all()
    done: set[Tuple[str, str, str]] = set()
    for v in vulns:
        sev = (v.severity or "unknown").lower()
        rank = SEVERITY_RANK.get(sev, 0)
        if rank < record_rank:
            continue
        host = _norm_host(v.host or "")
        key = (v.template_id or "", v.name or "", host)
        if key in done:
            continue
        done.add(key)
        earlier = (
            db.query(Vulnerability.id)
            .join(Scan, Vulnerability.scan_id == Scan.id)
            .filter(
                Scan.organization_id == org_id,
                Vulnerability.scan_id != scan.id,
                Vulnerability.template_id == (v.template_id or ""),
                Vulnerability.name == (v.name or ""),
                Vulnerability.host == v.host,
            )
            .first()
        )
        if earlier:
            continue
        asset = host_assets.get(host)
        record(asset, "added", "finding", f"{host}:{v.template_id or v.name}"[:512], "finding_new",
               f"New {sev} finding on {host or scan.domain}: {v.name}",
               severity=sev,
               detail={"host": host, "name": v.name, "template_id": v.template_id,
                       "matched_at": v.matched_at, "vulnerability_id": v.id},
               alert="new_critical_finding" if rank >= min_rank else None)


# ── Periodic certificate check (no scan needed) ──────────────────────────


def check_certificate_expiry(db: Session, organization_id: Optional[str] = None) -> Dict[str, SyncResult]:
    """Re-check every active certificate against today's date.

    Scans only look at certificates when they run; this catches a certificate
    crossing a warning step between scans. Returns one result per organization
    that has something to alert on.
    """
    q = db.query(Asset).filter(Asset.asset_type == "certificate", Asset.state == "active")
    if organization_id:
        q = q.filter(Asset.organization_id == organization_id)
    by_org: Dict[str, List[Asset]] = {}
    for cert in q.all():
        by_org.setdefault(cert.organization_id, []).append(cert)

    now = _utcnow()
    results: Dict[str, SyncResult] = {}
    for org_id, certs in by_org.items():
        res = SyncResult(organization_id=org_id)

        def record(asset, change_type, entity_type, key, event, summary, *, severity="info",
                   detail=None, alert=None, _org=org_id, _res=res):
            # No scan produced this event; "expiry-check" marks that in history.
            row = AssetChange(
                organization_id=_org, from_scan_id=None, to_scan_id="expiry-check",
                change_type=change_type, entity_type=entity_type, entity_key=key[:512],
                detail=detail or {}, asset_id=asset.id, event=event, severity=severity,
                root_domain=asset.root_domain, summary=summary, detected_at=now,
            )
            db.add(row)
            _res.events.append(row)
            if alert:
                _res.alerts.setdefault(alert, []).append({
                    "asset_id": asset.id, "key": key, "summary": summary,
                    "severity": severity, "detail": detail or {},
                })

        _check_expiry(certs, now, _cert_expiry_days(db, org_id), record)
        if res.events:
            results[org_id] = res
    db.commit()
    return results


# ── Rebuild from scans that ran before the inventory existed ─────────────


def rebuild_from_history(db: Session, organization_id: str, max_scans: int = 300) -> Dict[str, int]:
    """Fold past completed scans into the inventory, oldest first, silently."""
    scans = (
        db.query(Scan)
        .filter(Scan.organization_id == organization_id, Scan.status == "completed")
        .order_by(Scan.completed_at.desc(), Scan.created_at.desc())
        .limit(max_scans)
        .all()
    )
    processed = created = 0
    for scan in reversed(scans):
        res = sync_scan(db, scan, at=scan.completed_at or scan.created_at)
        if res.skipped:
            continue
        processed += 1
        created += res.new_assets
        try:
            from app.repositories.assets import backfill_from_scan

            backfill_from_scan(db, scan, host_assets=res.host_assets)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning("Relationship backfill failed for scan %s: %s", scan.id, exc)
    return {"scans_processed": processed, "assets_created": created}


# ── Entry point used by the scan pipeline ────────────────────────────────


def process_completed_scan(db: Session, scan: Scan) -> Optional[SyncResult]:
    """Inventory sync, graph relationships, then alerts. Never raises."""
    result: Optional[SyncResult] = None
    try:
        result = sync_scan(db, scan)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Inventory sync failed for scan %s: %s", scan.id, exc)

    try:
        from app.repositories.assets import backfill_from_scan

        backfill_from_scan(db, scan, host_assets=result.host_assets if result and not result.skipped else None)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("Asset relationship backfill failed for scan %s: %s", scan.id, exc)

    if result and not result.skipped:
        try:
            from app.services.inventory_alerts import dispatch_alerts

            dispatch_alerts(db, result, scan=scan)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("Inventory alerts failed for scan %s: %s", scan.id, exc)
    return result
