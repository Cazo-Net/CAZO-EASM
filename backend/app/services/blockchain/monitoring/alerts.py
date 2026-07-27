"""Blockchain monitoring and alert dispatch.

Manages watch lists and sends alerts when watched addresses
have activity or cross risk thresholds.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.blockchain import (
    AlertType,
    BlockchainAlert,
    BlockchainWatch,
    Chain,
    Evidence,
    RiskBand,
)

logger = logging.getLogger(__name__)

# In-memory store for demo; production would use a database
_watches: dict[str, BlockchainWatch] = {}
_alerts: dict[str, BlockchainAlert] = {}


# ── Watch CRUD ───────────────────────────────────────────────────────────────

def create_watch(
    org_id: str,
    user_id: str,
    address: str,
    chain: Chain,
    alert_on_new_tx: bool = True,
    alert_on_risk_change: bool = True,
    risk_threshold: int | None = None,
    webhook_url: str | None = None,
    email_alert: bool = False,
) -> BlockchainWatch:
    """Create a new watch for an address."""
    watch_id = str(uuid.uuid4())
    watch = BlockchainWatch(
        id=watch_id,
        org_id=org_id,
        user_id=user_id,
        address=address.lower(),
        chain=chain,
        alert_on_new_tx=alert_on_new_tx,
        alert_on_risk_change=alert_on_risk_change,
        risk_threshold=risk_threshold,
        webhook_url=webhook_url,
        email_alert=email_alert,
    )
    _watches[watch_id] = watch
    return watch


def get_watch(watch_id: str) -> BlockchainWatch | None:
    return _watches.get(watch_id)


def list_watches(
    org_id: str | None = None,
    address: str | None = None,
) -> list[BlockchainWatch]:
    """List watches, optionally filtered by org or address."""
    results = list(_watches.values())
    if org_id:
        results = [w for w in results if w.org_id == org_id]
    if address:
        results = [w for w in results if w.address == address.lower()]
    return results


def delete_watch(watch_id: str) -> bool:
    """Delete a watch. Returns True if found and deleted."""
    if watch_id in _watches:
        del _watches[watch_id]
        return True
    return False


def get_watches_for_address(address: str, chain: Chain) -> list[BlockchainWatch]:
    """Get all active watches for a specific address."""
    addr_lower = address.lower()
    return [
        w for w in _watches.values()
        if w.address == addr_lower and w.chain == chain and w.is_active
    ]


# ── Alert Dispatch ───────────────────────────────────────────────────────────

def _create_alert(
    watch: BlockchainWatch,
    alert_type: AlertType,
    title: str,
    message: str,
    severity: str = "info",
    evidence: list[Evidence] | None = None,
) -> BlockchainAlert:
    """Create and store an alert."""
    alert_id = str(uuid.uuid4())
    alert = BlockchainAlert(
        id=alert_id,
        watch_id=watch.id or "",
        org_id=watch.org_id,
        user_id=watch.user_id,
        address=watch.address,
        chain=watch.chain,
        alert_type=alert_type,
        title=title,
        message=message,
        severity=severity,
        evidence=evidence or [],
    )
    _alerts[alert_id] = alert
    logger.info("Alert created: %s for %s [%s]", title, watch.address, severity)
    return alert


async def check_wallet_activity(
    address: str,
    chain: Chain,
    current_tx_count: int,
    previous_tx_count: int,
) -> list[BlockchainAlert]:
    """Check if watched addresses have new activity and dispatch alerts."""
    watches = get_watches_for_address(address, chain)
    alerts: list[BlockchainAlert] = []

    for watch in watches:
        if watch.alert_on_new_tx and current_tx_count > previous_tx_count:
            new_txs = current_tx_count - previous_tx_count
            alert = _create_alert(
                watch=watch,
                alert_type=AlertType.NEW_TRANSACTION,
                title=f"New transaction(s) detected for {address[:16]}...",
                message=f"{new_txs} new transaction(s) detected on {chain.value}.",
                severity="info",
            )
            alerts.append(alert)

    return alerts


async def check_risk_threshold(
    address: str,
    chain: Chain,
    current_risk: int,
    previous_risk: int,
) -> list[BlockchainAlert]:
    """Check if risk score crossed a threshold and dispatch alerts."""
    watches = get_watches_for_address(address, chain)
    alerts: list[BlockchainAlert] = []

    for watch in watches:
        if watch.alert_on_risk_change and watch.risk_threshold is not None:
            if current_risk >= watch.risk_threshold and previous_risk < watch.risk_threshold:
                alert = _create_alert(
                    watch=watch,
                    alert_type=AlertType.RISK_THRESHOLD,
                    title=f"Risk threshold crossed for {address[:16]}...",
                    message=f"Risk score increased from {previous_risk} to {current_risk} (threshold: {watch.risk_threshold}).",
                    severity="high" if current_risk >= 70 else "medium",
                )
                alerts.append(alert)

        if current_risk >= 80 and previous_risk < 80:
            alert = _create_alert(
                watch=watch,
                alert_type=AlertType.HIGH_RISK_COUNTERPARTY,
                title=f"High risk detected for {address[:16]}...",
                message=f"Risk score reached {current_risk} (critical threshold).",
                severity="critical",
            )
            alerts.append(alert)

    return alerts


async def check_sanctions_match(
    address: str,
    chain: Chain,
    entity_name: str,
) -> list[BlockchainAlert]:
    """Dispatch alerts for sanctions matches."""
    watches = get_watches_for_address(address, chain)
    alerts: list[BlockchainAlert] = []

    for watch in watches:
        alert = _create_alert(
            watch=watch,
            alert_type=AlertType.SANCTIONS_MATCH,
            title=f"Sanctions match: {entity_name}",
            message=f"Address {address[:16]}... is associated with sanctioned entity '{entity_name}'.",
            severity="critical",
            evidence=[Evidence(
                source="sanctions",
                type=EvidenceType.SANCTIONS_LIST,
                confidence=95,
                reason=f"OFAC/sanctions match: {entity_name}",
            )],
        )
        alerts.append(alert)

    return alerts


# ── Alert Queries ────────────────────────────────────────────────────────────

def list_alerts(
    org_id: str | None = None,
    user_id: str | None = None,
    address: str | None = None,
    unacknowledged_only: bool = False,
) -> list[BlockchainAlert]:
    """List alerts with optional filters."""
    results = list(_alerts.values())
    if org_id:
        results = [a for a in results if a.org_id == org_id]
    if user_id:
        results = [a for a in results if a.user_id == user_id]
    if address:
        results = [a for a in results if a.address == address.lower()]
    if unacknowledged_only:
        results = [a for a in results if not a.acknowledged]
    return sorted(results, key=lambda a: a.created_at, reverse=True)


def acknowledge_alert(alert_id: str, user_id: str) -> bool:
    """Acknowledge an alert."""
    alert = _alerts.get(alert_id)
    if alert:
        alert.acknowledged = True
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.now(timezone.utc)
        return True
    return False


def alert_stats(org_id: str) -> dict[str, Any]:
    """Get alert statistics for an organization."""
    org_alerts = [a for a in _alerts.values() if a.org_id == org_id]
    return {
        "total": len(org_alerts),
        "unacknowledged": sum(1 for a in org_alerts if not a.acknowledged),
        "critical": sum(1 for a in org_alerts if a.severity == "critical"),
        "high": sum(1 for a in org_alerts if a.severity == "high"),
        "medium": sum(1 for a in org_alerts if a.severity == "medium"),
        "info": sum(1 for a in org_alerts if a.severity == "info"),
    }
