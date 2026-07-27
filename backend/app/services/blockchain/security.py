"""Blockchain-specific enterprise hardening.

Adds:
- Rate limiting on blockchain API endpoints
- Audit logging for blockchain actions
- RBAC permission checks
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Rate Limiting ────────────────────────────────────────────────────────────

_rate_limits: dict[str, list[float]] = defaultdict(list)

RATE_LIMITS: dict[str, int] = {
    "wallet": 30,           # per minute
    "transactions": 20,
    "risk": 30,
    "attribution": 30,
    "cluster": 10,
    "bridge": 15,
    "graph": 10,
    "anomaly": 5,
    "copilot": 10,
    "cases": 30,
    "watches": 20,
    "alerts": 20,
    "search": 30,
}

RATE_WINDOW = 60.0  # 1 minute


def check_rate_limit(endpoint: str, identifier: str) -> bool:
    """Check if a request is within rate limits.

    Returns True if allowed, False if rate limited.
    """
    limit = RATE_LIMITS.get(endpoint, 30)
    key = f"{endpoint}:{identifier}"
    now = time.time()

    # Clean old entries
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < RATE_WINDOW]

    if len(_rate_limits[key]) >= limit:
        return False

    _rate_limits[key].append(now)
    return True


def get_rate_limit_info(endpoint: str, identifier: str) -> dict[str, Any]:
    """Get current rate limit status."""
    limit = RATE_LIMITS.get(endpoint, 30)
    key = f"{endpoint}:{identifier}"
    now = time.time()

    recent = [t for t in _rate_limits[key] if now - t < RATE_WINDOW]
    remaining = max(0, limit - len(recent))

    return {
        "limit": limit,
        "remaining": remaining,
        "reset_in": int(RATE_WINDOW - (now - min(recent)) if recent else RATE_WINDOW),
    }


# ── Audit Logging ────────────────────────────────────────────────────────────

_audit_log: list[dict[str, Any]] = []


def log_blockchain_action(
    user_id: str,
    org_id: str,
    action: str,
    resource: str,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Log a blockchain-related action for audit trail."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "org_id": org_id,
        "action": action,
        "resource": resource,
        "detail": detail or {},
        "ip_address": ip_address,
    }
    _audit_log.append(entry)
    logger.info("Audit: %s %s by %s", action, resource, user_id)

    # Keep only last 10000 entries in memory
    if len(_audit_log) > 10000:
        _audit_log[:] = _audit_log[-5000:]


def get_audit_log(
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query audit log entries."""
    results = _audit_log
    if org_id:
        results = [e for e in results if e["org_id"] == org_id]
    if user_id:
        results = [e for e in results if e["user_id"] == user_id]
    if action:
        results = [e for e in results if e["action"] == action]
    return list(reversed(results[-limit:]))


# ── RBAC Permission Checks ──────────────────────────────────────────────────

BLOCKCHAIN_PERMISSIONS = {
    "blockchain:read": [
        "get_wallet", "get_transactions", "get_transaction",
        "get_contract", "get_token_balances", "get_risk_score",
        "get_attribution", "search", "get_cluster", "get_bridge_interactions",
        "get_bridge_volume", "list_known_bridges", "get_graph_analytics",
        "get_anomaly_score", "copilot_ask",
    ],
    "blockchain:write": [
        "create_watch", "delete_watch", "acknowledge_alert",
        "create_case", "update_case", "add_annotation", "add_member",
    ],
    "blockchain:admin": [
        "get_audit_log", "get_alert_stats", "get_case_stats",
    ],
}


def check_permission(user_role: str, action: str) -> bool:
    """Check if a user role has permission for a blockchain action.

    Roles: admin, analyst, viewer
    """
    if user_role == "admin":
        return True

    if user_role == "viewer":
        return action in BLOCKCHAIN_PERMISSIONS.get("blockchain:read", [])

    if user_role == "analyst":
        return action in (
            BLOCKCHAIN_PERMISSIONS.get("blockchain:read", [])
            + BLOCKCHAIN_PERMISSIONS.get("blockchain:write", [])
        )

    return False
