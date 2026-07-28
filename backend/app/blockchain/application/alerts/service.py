from __future__ import annotations

import logging
from typing import Any

from app.blockchain.domain.entities.transaction import Transaction
from app.blockchain.domain.entities.address import Address
from .evaluator import evaluator
from .store import alert_store, alert_router

logger = logging.getLogger(__name__)


class AlertService:
    async def process_transaction(self, tx: Transaction, webhook_url: str | None = None) -> list[dict]:
        alerts = evaluator.evaluate_transaction(tx)
        for alert in alerts:
            await alert_router.dispatch_alert(alert, webhook_url)
        if alerts:
            logger.info("Processed %d alert(s) for tx %s", len(alerts), tx.hash[:16])
        return [a.to_dict() for a in alerts]

    async def process_address(self, address: Address, webhook_url: str | None = None) -> list[dict]:
        alerts = evaluator.evaluate_address(address)
        for alert in alerts:
            await alert_router.dispatch_alert(alert, webhook_url)
        return [a.to_dict() for a in alerts]

    def list_alerts(
        self,
        org_id: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        return alert_store.list(org_id, severity, status, limit)

    def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        return alert_store.acknowledge(alert_id, user_id)

    def dismiss_alert(self, alert_id: str) -> bool:
        return alert_store.dismiss(alert_id)

    def stats(self, org_id: str | None = None) -> dict[str, Any]:
        return alert_store.stats(org_id)


alert_service = AlertService()
