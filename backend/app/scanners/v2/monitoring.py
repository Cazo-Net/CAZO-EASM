"""Continuous monitoring system with DB-backed persistence.

Features:
- Scheduled scan management via monitor_schedules table
- Change detection between scan pairs
- Asset lifecycle tracking via asset_lifecycle table
- Notification triggers via notification_triggers table
"""
from __future__ import annotations

import json
import uuid
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

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
class MonitorScheduleData:
    interval_hours: int = 24
    day_of_week: Optional[int] = None
    time_of_day: Optional[str] = None
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


class ContinuousMonitor:
    """DB-backed continuous monitoring for tracked domains."""

    def __init__(self):
        pass

    def add_target(
        self,
        db: Session,
        domain: str,
        user_id: int,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        schedule: Optional[MonitorScheduleData] = None,
    ) -> dict:
        """Create a monitor schedule in the database."""
        from app.models.v2_scanner import MonitorSchedule

        sched = schedule or MonitorScheduleData()
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(hours=sched.interval_hours)

        if sched.day_of_week is not None:
            days_ahead = sched.day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now + timedelta(days=days_ahead)

        if sched.time_of_day:
            hour, minute = map(int, sched.time_of_day.split(":"))
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)

        row = MonitorSchedule(
            id=str(uuid.uuid4())[:36],
            domain=domain,
            interval_hours=sched.interval_hours,
            scan_type="quick",
            enabled=sched.enabled,
            created_by=user_id,
            organization_id=organization_id,
            project_id=project_id,
            next_run_at=next_run,
        )
        db.add(row)
        db.flush()
        logger.info("Added monitor schedule %s for %s (every %dh)", row.id, domain, sched.interval_hours)
        return {"id": row.id, "domain": domain, "interval_hours": sched.interval_hours}

    def remove_target(self, db: Session, schedule_id: str) -> bool:
        """Delete a monitor schedule from the database."""
        from app.models.v2_scanner import MonitorSchedule

        row = db.query(MonitorSchedule).filter(MonitorSchedule.id == schedule_id).first()
        if row:
            db.delete(row)
            db.flush()
            logger.info("Removed monitor schedule %s", schedule_id)
            return True
        return False

    def list_targets(self, db: Session, organization_id: Optional[int] = None) -> List[dict]:
        """List all monitor schedules, optionally filtered by org."""
        from app.models.v2_scanner import MonitorSchedule

        q = db.query(MonitorSchedule)
        if organization_id:
            q = q.filter(MonitorSchedule.organization_id == organization_id)
        rows = q.order_by(MonitorSchedule.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "domain": r.domain,
                "interval_hours": r.interval_hours,
                "scan_type": r.scan_type,
                "enabled": r.enabled,
                "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
                "next_run_at": r.next_run_at.isoformat() if r.next_run_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def get_targets_due(self, db: Session) -> List[dict]:
        """Get monitor schedules that are due for execution."""
        from app.models.v2_scanner import MonitorSchedule

        now = datetime.now(timezone.utc)
        rows = (
            db.query(MonitorSchedule)
            .filter(
                MonitorSchedule.enabled == True,
                MonitorSchedule.next_run_at <= now,
            )
            .all()
        )
        return [
            {
                "id": r.id,
                "domain": r.domain,
                "interval_hours": r.interval_hours,
                "scan_type": r.scan_type,
                "created_by": r.created_by,
                "organization_id": r.organization_id,
            }
            for r in rows
        ]

    def record_scan(self, db: Session, schedule_id: str) -> None:
        """Record a completed scan and schedule the next one."""
        from app.models.v2_scanner import MonitorSchedule

        row = db.query(MonitorSchedule).filter(MonitorSchedule.id == schedule_id).first()
        if not row:
            return
        now = datetime.now(timezone.utc)
        row.last_run_at = now
        row.next_run_at = now + timedelta(hours=row.interval_hours)
        db.flush()

    def record_scan_history(
        self,
        db: Session,
        domain: str,
        scan_type: str,
        status: str,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        monitor_schedule_id: Optional[str] = None,
        triggered_by: str = "manual",
        results: Optional[Dict[str, Any]] = None,
        duration_ms: float = 0.0,
        error_message: Optional[str] = None,
    ) -> str:
        """Write a scan_history record. Returns the history ID."""
        from app.models.v2_scanner import ScanHistory

        results = results or {}
        risk = results.get("risk_score", {})
        risk_score = risk.get("risk_score", 0) if isinstance(risk, dict) else 0
        risk_severity = risk.get("severity") if isinstance(risk, dict) else None

        subdomains = results.get("subdomains", [])
        ports = results.get("ports", {})
        technologies = results.get("technologies", {})

        open_port_count = 0
        if isinstance(ports, dict):
            for port_list in ports.values():
                if isinstance(port_list, list):
                    open_port_count += len(port_list)

        tech_count = 0
        if isinstance(technologies, dict):
            for tech_list in technologies.values():
                if isinstance(tech_list, list):
                    tech_count += len(tech_list)

        now = datetime.now(timezone.utc)
        history_id = str(uuid.uuid4())[:36]

        row = ScanHistory(
            id=history_id,
            domain=domain,
            scan_type=scan_type,
            scan_engine="v2",
            status=status,
            triggered_by=triggered_by,
            monitor_schedule_id=monitor_schedule_id,
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
            subdomains_found=len(subdomains) if isinstance(subdomains, list) else 0,
            open_ports_found=open_port_count,
            technologies_found=tech_count,
            risk_score=risk_score,
            risk_severity=risk_severity,
            duration_ms=duration_ms,
            result_summary=json.dumps({
                "subdomains": len(subdomains) if isinstance(subdomains, list) else 0,
                "ports": open_port_count,
                "technologies": tech_count,
                "risk_score": risk_score,
            }),
            error_message=error_message,
            started_at=now,
            completed_at=now,
        )
        db.add(row)
        db.flush()
        return history_id

    def update_asset_lifecycle(
        self,
        db: Session,
        domain: str,
        assets: List[Dict[str, Any]],
        scan_history_id: Optional[str] = None,
        organization_id: Optional[int] = None,
    ) -> int:
        """Update asset_lifecycle table with discovered assets. Returns count of new/updated."""
        from app.models.v2_scanner import AssetLifecycle

        now = datetime.now(timezone.utc)
        count = 0

        for asset in assets:
            asset_type = asset.get("type", "subdomain")
            asset_value = asset.get("value", "")
            if not asset_value:
                continue

            existing = (
                db.query(AssetLifecycle)
                .filter(
                    AssetLifecycle.domain == domain,
                    AssetLifecycle.asset_type == asset_type,
                    AssetLifecycle.asset_value == asset_value,
                )
                .first()
            )

            if existing:
                existing.last_seen_at = now
                existing.state = "active"
                existing.scan_history_id = scan_history_id
                existing.updated_at = now
            else:
                row = AssetLifecycle(
                    id=str(uuid.uuid4())[:36],
                    domain=domain,
                    asset_type=asset_type,
                    asset_value=asset_value,
                    state="active",
                    scan_history_id=scan_history_id,
                    organization_id=organization_id,
                )
                db.add(row)
                count += 1

        db.flush()
        return count

    def mark_removed_assets(
        self,
        db: Session,
        domain: str,
        current_asset_values: Set[str],
        asset_type: str = "subdomain",
    ) -> int:
        """Mark assets as removed if they're no longer seen. Returns count."""
        from app.models.v2_scanner import AssetLifecycle

        now = datetime.now(timezone.utc)
        active = (
            db.query(AssetLifecycle)
            .filter(
                AssetLifecycle.domain == domain,
                AssetLifecycle.asset_type == asset_type,
                AssetLifecycle.state == "active",
            )
            .all()
        )

        removed_count = 0
        for row in active:
            if row.asset_value not in current_asset_values:
                row.state = "removed"
                row.removed_at = now
                row.updated_at = now
                removed_count += 1

        if removed_count:
            db.flush()
        return removed_count

    def detect_changes(
        self,
        old_scan_data: Dict[str, Any],
        new_scan_data: Dict[str, Any],
        from_scan_id: str = "",
        to_scan_id: str = "",
    ) -> List[ChangeRecord]:
        """Compare two scan results and return detected changes."""
        changes = []

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

        return changes

    def check_notification_triggers(
        self,
        db: Session,
        domain: str,
        event_type: str,
        organization_id: Optional[int] = None,
    ) -> List[dict]:
        """Check if any notification triggers match the event. Returns triggered rules."""
        from app.models.v2_scanner import NotificationTrigger

        q = (
            db.query(NotificationTrigger)
            .filter(
                NotificationTrigger.enabled == True,
                NotificationTrigger.event_type == event_type,
            )
            .filter(
                (NotificationTrigger.domain == domain) | (NotificationTrigger.domain.is_(None))
            )
        )
        if organization_id:
            q = q.filter(
                (NotificationTrigger.organization_id == organization_id)
                | (NotificationTrigger.organization_id.is_(None))
            )

        triggered = []
        for rule in q.all():
            now = datetime.now(timezone.utc)
            rule.last_triggered_at = now
            triggered.append({
                "id": rule.id,
                "name": rule.name,
                "method": rule.notification_method,
            })

        if triggered:
            db.flush()

        return triggered

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


# Singleton
monitor = ContinuousMonitor()
