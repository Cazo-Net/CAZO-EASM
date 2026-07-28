"""Scheduled scan executor — runs scans on a schedule based on monitor_schedules.

This module provides:
- A background task that periodically checks for due scans
- Functions to create, update, and delete schedules
- Integration with the v2 scanner pipeline
- Database persistence (survives process restarts)
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled scan."""
    id: str
    domain: str
    interval_hours: int
    scan_type: str
    enabled: bool
    created_by: int
    organization_id: Optional[int] = None
    project_id: Optional[int] = None
    last_run: Optional[float] = field(default=None, repr=False)


class ScanScheduler:
    """Manages scheduled scan execution with database persistence."""

    def __init__(self):
        self._schedules: Dict[str, ScheduleConfig] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_schedule(self, config: ScheduleConfig) -> None:
        """Add or update a schedule in memory and persist to DB."""
        self._schedules[config.id] = config
        self._persist_to_db(config)
        logger.info("Added schedule %s for %s (every %dh)", config.id, config.domain, config.interval_hours)

    def remove_schedule(self, schedule_id: str) -> None:
        """Remove a schedule from memory and soft-delete from DB."""
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            self._soft_delete_from_db(schedule_id)
            logger.info("Removed schedule %s", schedule_id)

    def get_due_scans(self) -> List[ScheduleConfig]:
        """Return schedules that are due for execution based on interval_hours."""
        now = time.time()
        due = []
        for config in self._schedules.values():
            if not config.enabled:
                continue
            if config.last_run is None:
                due.append(config)
                continue
            elapsed_hours = (now - config.last_run) / 3600
            if elapsed_hours >= config.interval_hours:
                due.append(config)
        return due

    async def start(self) -> None:
        """Start the scheduler background task."""
        if self._running:
            return
        self._running = True
        self._load_from_db()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scan scheduler started (loaded %d schedules from DB)", len(self._schedules))

    async def stop(self) -> None:
        """Stop the scheduler background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scan scheduler stopped")

    def _load_from_db(self) -> None:
        """Load all active schedules from the database into memory."""
        try:
            from app.database import SessionLocal
            from app.models.v2_scanner import MonitorSchedule

            db = SessionLocal()
            try:
                schedules = db.query(MonitorSchedule).filter(
                    MonitorSchedule.enabled == True
                ).all()

                for s in schedules:
                    config = ScheduleConfig(
                        id=s.id,
                        domain=s.domain,
                        interval_hours=s.interval_hours,
                        scan_type=s.scan_type,
                        enabled=s.enabled,
                        created_by=s.created_by,
                        organization_id=s.organization_id,
                        project_id=s.project_id,
                        last_run=s.last_run_at.timestamp() if s.last_run_at else None,
                    )
                    self._schedules[config.id] = config

                logger.info("Loaded %d schedules from database", len(schedules))
            finally:
                db.close()
        except Exception as e:
            logger.warning("Failed to load schedules from DB (tables may not exist): %s", e)

    def _persist_to_db(self, config: ScheduleConfig) -> None:
        """Persist a schedule to the database."""
        try:
            from app.database import SessionLocal
            from app.models.v2_scanner import MonitorSchedule

            db = SessionLocal()
            try:
                existing = db.query(MonitorSchedule).filter(MonitorSchedule.id == config.id).first()
                if existing:
                    existing.domain = config.domain
                    existing.interval_hours = config.interval_hours
                    existing.scan_type = config.scan_type
                    existing.enabled = config.enabled
                    existing.created_by = config.created_by
                    existing.organization_id = config.organization_id
                    existing.project_id = config.project_id
                    existing.last_run_at = datetime.fromtimestamp(config.last_run, tz=timezone.utc) if config.last_run else None
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    schedule = MonitorSchedule(
                        id=config.id,
                        domain=config.domain,
                        interval_hours=config.interval_hours,
                        scan_type=config.scan_type,
                        enabled=config.enabled,
                        created_by=config.created_by,
                        organization_id=config.organization_id,
                        project_id=config.project_id,
                        last_run_at=datetime.fromtimestamp(config.last_run, tz=timezone.utc) if config.last_run else None,
                    )
                    db.add(schedule)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to persist schedule %s to DB: %s", config.id, e)

    def _soft_delete_from_db(self, schedule_id: str) -> None:
        """Soft-delete a schedule in the database."""
        try:
            from app.database import SessionLocal
            from app.models.v2_scanner import MonitorSchedule

            db = SessionLocal()
            try:
                schedule = db.query(MonitorSchedule).filter(MonitorSchedule.id == schedule_id).first()
                if schedule:
                    schedule.enabled = False
                    schedule.updated_at = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to soft-delete schedule %s from DB: %s", schedule_id, e)

    def _update_last_run_in_db(self, config: ScheduleConfig) -> None:
        """Update last_run_at in the database after executing a scan."""
        try:
            from app.database import SessionLocal
            from app.models.v2_scanner import MonitorSchedule

            db = SessionLocal()
            try:
                schedule = db.query(MonitorSchedule).filter(MonitorSchedule.id == config.id).first()
                if schedule:
                    schedule.last_run_at = datetime.fromtimestamp(config.last_run, tz=timezone.utc) if config.last_run else None
                    schedule.updated_at = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to update last_run for schedule %s: %s", config.id, e)

    async def _run_loop(self) -> None:
        """Main scheduler loop — checks for due scans every 60 seconds."""
        while self._running:
            try:
                due_scans = self.get_due_scans()
                for config in due_scans:
                    try:
                        await self._execute_scheduled_scan(config)
                    except Exception as e:
                        logger.error("Failed to execute scheduled scan %s: %s", config.id, e)
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)
                await asyncio.sleep(60)

    async def _execute_scheduled_scan(self, config: ScheduleConfig) -> None:
        """Execute a scheduled scan."""
        from app.scanners.v2.runner import EnhancedScanRunner

        logger.info("Executing scheduled scan %s for %s", config.id, config.domain)
        config.last_run = time.time()
        self._update_last_run_in_db(config)

        runner = EnhancedScanRunner()
        scan_config = {
            "timeout": 30,
            "top_ports": [80, 443, 8080, 8443, 22, 21, 25, 53, 3306, 5432],
        }

        try:
            if config.scan_type == "quick":
                result = await runner.run_quick_scan(
                    domain=config.domain,
                    config=scan_config,
                )
            else:
                result = await runner.run_scan(
                    domain=config.domain,
                    config=scan_config,
                )

            logger.info(
                "Scheduled scan %s completed: risk_score=%s",
                config.id,
                result.get("risk_score", {}).get("risk_score", "N/A"),
            )

        except Exception as e:
            logger.error("Scheduled scan %s failed: %s", config.id, e)
            raise


# Singleton
scan_scheduler = ScanScheduler()


def get_scheduler() -> ScanScheduler:
    """Get the global scan scheduler instance."""
    return scan_scheduler
