"""Continuous monitoring system with scheduled scans and change detection.

Features:
- Scheduled scan management (create, update, delete)
- Change detection between scan pairs
- Asset lifecycle tracking
- Notification triggers
"""
from __future__ import annotations

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MonitorStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class ChangeType(str, Enum):
    ASSET_ADDED = "asset_added"
    ASSET_REMOVED = "asset_removed"
    PORT_OPENED = "port_opened"
    PORT_CLOSED = "port_closed"
    CERT_CHANGED = "cert_changed"
    CERT_EXPIRING = "cert_expiring"
    TECH_CHANGED = "tech_changed"
    RISK_INCREASED = "risk_increased"
    RISK_DECREASED = "risk_decreased"


@dataclass
class MonitorSchedule:
    interval_hours: int = 24
    day_of_week: Optional[int] = None  # 0=Mon, 6=Sun
    time_of_day: Optional[str] = None  # "HH:MM" UTC
    enabled: bool = True


@dataclass
class ChangeRecord:
    change_type: ChangeType
    entity_type: str
    entity_key: str
    detail: Dict[str, Any]
    from_scan_id: Optional[str] = None
    to_scan_id: Optional[str] = None
    detected_at: float = field(default_factory=time.time)


@dataclass
class MonitorTarget:
    id: str
    domain: str
    organization_id: str
    schedule: MonitorSchedule
    status: MonitorStatus = MonitorStatus.ACTIVE
    last_scan_id: Optional[str] = None
    last_scan_at: Optional[float] = None
    next_scan_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    config: Dict[str, Any] = field(default_factory=dict)


class ContinuousMonitor:
    """Manages continuous monitoring for tracked domains."""

    def __init__(self):
        self._targets: Dict[str, MonitorTarget] = {}
        self._changes: Dict[str, List[ChangeRecord]] = {}

    def add_target(
        self,
        domain: str,
        organization_id: str,
        schedule: Optional[MonitorSchedule] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> MonitorTarget:
        target_id = f"{organization_id}:{domain}"
        target = MonitorTarget(
            id=target_id,
            domain=domain,
            organization_id=organization_id,
            schedule=schedule or MonitorSchedule(),
            config=config or {},
        )
        target.next_scan_at = self._calculate_next_scan(target.schedule)
        self._targets[target_id] = target
        self._changes[target_id] = []
        logger.info("Added monitoring target: %s", domain)
        return target

    def remove_target(self, target_id: str) -> bool:
        if target_id in self._targets:
            del self._targets[target_id]
            self._changes.pop(target_id, None)
            return True
        return False

    def pause_target(self, target_id: str) -> bool:
        target = self._targets.get(target_id)
        if target:
            target.status = MonitorStatus.PAUSED
            return True
        return False

    def resume_target(self, target_id: str) -> bool:
        target = self._targets.get(target_id)
        if target:
            target.status = MonitorStatus.ACTIVE
            target.next_scan_at = self._calculate_next_scan(target.schedule)
            return True
        return False

    def get_targets_due(self) -> List[MonitorTarget]:
        """Get targets that are due for scanning."""
        now = time.time()
        return [
            t for t in self._targets.values()
            if t.status == MonitorStatus.ACTIVE
            and t.next_scan_at is not None
            and t.next_scan_at <= now
        ]

    def record_scan(self, target_id: str, scan_id: str) -> None:
        """Record that a scan was completed for a target."""
        target = self._targets.get(target_id)
        if target:
            target.last_scan_id = scan_id
            target.last_scan_at = time.time()
            target.next_scan_at = self._calculate_next_scan(target.schedule)

    def detect_changes(
        self,
        target_id: str,
        old_scan_data: Dict[str, Any],
        new_scan_data: Dict[str, Any],
        from_scan_id: str = "",
        to_scan_id: str = "",
    ) -> List[ChangeRecord]:
        """Compare two scan results and record changes."""
        changes = []

        # Subdomain changes
        old_subs = set(old_scan_data.get("subdomains", []))
        new_subs = set(new_scan_data.get("subdomains", []))

        for added in new_subs - old_subs:
            changes.append(ChangeRecord(
                change_type=ChangeType.ASSET_ADDED,
                entity_type="subdomain",
                entity_key=added,
                detail={"hostname": added},
                from_scan_id=from_scan_id,
                to_scan_id=to_scan_id,
            ))

        for removed in old_subs - new_subs:
            changes.append(ChangeRecord(
                change_type=ChangeType.ASSET_REMOVED,
                entity_type="subdomain",
                entity_key=removed,
                detail={"hostname": removed},
                from_scan_id=from_scan_id,
                to_scan_id=to_scan_id,
            ))

        # Port changes
        old_ports = self._extract_all_ports(old_scan_data)
        new_ports = self._extract_all_ports(new_scan_data)

        for port_key in new_ports - old_ports:
            host, port = port_key.split(":")
            changes.append(ChangeRecord(
                change_type=ChangeType.PORT_OPENED,
                entity_type="port",
                entity_key=port_key,
                detail={"host": host, "port": int(port)},
                from_scan_id=from_scan_id,
                to_scan_id=to_scan_id,
            ))

        for port_key in old_ports - new_ports:
            host, port = port_key.split(":")
            changes.append(ChangeRecord(
                change_type=ChangeType.PORT_CLOSED,
                entity_type="port",
                entity_key=port_key,
                detail={"host": host, "port": int(port)},
                from_scan_id=from_scan_id,
                to_scan_id=to_scan_id,
            ))

        # Certificate changes
        old_certs = old_scan_data.get("ssl_certificates", {})
        new_certs = new_scan_data.get("ssl_certificates", {})
        if isinstance(old_certs, dict) and isinstance(new_certs, dict):
            for host in set(list(old_certs.keys()) + list(new_certs.keys())):
                old_grade = (old_certs.get(host) or {}).get("grade", "")
                new_grade = (new_certs.get(host) or {}).get("grade", "")
                if old_grade != new_grade:
                    changes.append(ChangeRecord(
                        change_type=ChangeType.CERT_CHANGED,
                        entity_type="certificate",
                        entity_key=host,
                        detail={"host": host, "old_grade": old_grade, "new_grade": new_grade},
                        from_scan_id=from_scan_id,
                        to_scan_id=to_scan_id,
                    ))

        # Risk changes
        old_risk = old_scan_data.get("risk_score", {}).get("risk_score", 0)
        new_risk = new_scan_data.get("risk_score", {}).get("risk_score", 0)
        risk_delta = new_risk - old_risk
        if abs(risk_delta) >= 5:
            changes.append(ChangeRecord(
                change_type=ChangeType.RISK_INCREASED if risk_delta > 0 else ChangeType.RISK_DECREASED,
                entity_type="risk_score",
                entity_key="overall",
                detail={"old_score": old_risk, "new_score": new_risk, "delta": risk_delta},
                from_scan_id=from_scan_id,
                to_scan_id=to_scan_id,
            ))

        # Store changes
        if target_id in self._changes:
            self._changes[target_id].extend(changes)

        return changes

    def get_changes(
        self,
        target_id: str,
        since: Optional[float] = None,
        change_type: Optional[ChangeType] = None,
    ) -> List[ChangeRecord]:
        changes = self._changes.get(target_id, [])
        if since:
            changes = [c for c in changes if c.detected_at >= since]
        if change_type:
            changes = [c for c in changes if c.change_type == change_type]
        return changes

    def get_lifecycle(self, target_id: str) -> Dict[str, Any]:
        """Get asset lifecycle summary for a target."""
        target = self._targets.get(target_id)
        if not target:
            return {}

        changes = self._changes.get(target_id, [])
        return {
            "target": target.__dict__,
            "total_changes": len(changes),
            "changes_by_type": {
                ct.value: len([c for c in changes if c.change_type == ct])
                for ct in ChangeType
            },
            "first_seen": target.created_at,
            "last_scanned": target.last_scan_at,
            "recent_changes": [
                {"type": c.change_type.value, "entity": c.entity_key, "at": c.detected_at}
                for c in sorted(changes, key=lambda x: x.detected_at, reverse=True)[:10]
            ],
        }

    def _extract_all_ports(self, scan_data: Dict[str, Any]) -> Set[str]:
        ports = set()
        port_data = scan_data.get("ports", {})
        if isinstance(port_data, dict):
            for host, port_list in port_data.items():
                if isinstance(port_list, list):
                    for p in port_list:
                        if isinstance(p, dict):
                            ports.add(f"{host}:{p.get('port', 0)}")
        return ports

    def _calculate_next_scan(self, schedule: MonitorSchedule) -> float:
        """Calculate next scan time based on schedule."""
        now = datetime.now(timezone.utc)
        next_scan = now + timedelta(hours=schedule.interval_hours)

        if schedule.day_of_week is not None:
            days_ahead = schedule.day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_scan = now + timedelta(days=days_ahead)

        if schedule.time_of_day:
            hour, minute = map(int, schedule.time_of_day.split(":"))
            next_scan = next_scan.replace(hour=hour, minute=minute, second=0, microsecond=0)

        return next_scan.timestamp()


# Singleton
monitor = ContinuousMonitor()
