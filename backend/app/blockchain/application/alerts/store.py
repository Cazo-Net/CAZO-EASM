from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import httpx

from .models import Alert, AlertStatus, AlertSeverity

logger = logging.getLogger(__name__)


class AlertStore:
    _alerts: dict[str, Alert] = {}

    def save(self, alert: Alert) -> None:
        self._alerts[alert.id] = alert

    def save_many(self, alerts: list[Alert]) -> None:
        for a in alerts:
            self._alerts[a.id] = a

    def get(self, alert_id: str) -> Alert | None:
        return self._alerts.get(alert_id)

    def list(
        self,
        org_id: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        results = list(self._alerts.values())
        if org_id:
            results = [a for a in results if a.org_id == org_id]
        if severity:
            results = [a for a in results if a.severity.value == severity]
        if status:
            results = [a for a in results if a.status.value == status]
        results.sort(key=lambda a: a.created_at, reverse=True)
        return [a.to_dict() for a in results[:limit]]

    def acknowledge(self, alert_id: str, user_id: str) -> bool:
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = user_id
            return True
        return False

    def dismiss(self, alert_id: str) -> bool:
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = AlertStatus.DISMISSED
            return True
        return False

    def stats(self, org_id: str | None = None) -> dict[str, Any]:
        alerts = list(self._alerts.values())
        if org_id:
            alerts = [a for a in alerts if a.org_id == org_id]
        return {
            "total": len(alerts),
            "triggered": sum(1 for a in alerts if a.status == AlertStatus.TRIGGERED),
            "acknowledged": sum(1 for a in alerts if a.status == AlertStatus.ACKNOWLEDGED),
            "dismissed": sum(1 for a in alerts if a.status == AlertStatus.DISMISSED),
            "critical": sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL),
            "high": sum(1 for a in alerts if a.severity == AlertSeverity.HIGH),
            "medium": sum(1 for a in alerts if a.severity == AlertSeverity.MEDIUM),
            "low": sum(1 for a in alerts if a.severity == AlertSeverity.LOW),
            "info": sum(1 for a in alerts if a.severity == AlertSeverity.INFO),
        }

    def delete_old(self, max_age_hours: int = 72) -> int:
        cutoff = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        before = len(self._alerts)
        self._alerts = {
            k: v for k, v in self._alerts.items()
            if v.created_at.timestamp() > cutoff
        }
        return before - len(self._alerts)


alert_store = AlertStore()


class AlertRouter:
    async def dispatch_webhook(self, alert: Alert, webhook_url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=alert.to_dict())
                resp.raise_for_status()
                logger.info("Webhook dispatched for alert %s to %s", alert.id, webhook_url)
                return True
        except Exception as e:
            logger.warning("Webhook dispatch failed for alert %s: %s", alert.id, e)
            return False

    async def dispatch_alert(self, alert: Alert, webhook_url: str | None = None) -> None:
        alert_store.save(alert)
        if webhook_url:
            await self.dispatch_webhook(alert, webhook_url)


alert_router = AlertRouter()
