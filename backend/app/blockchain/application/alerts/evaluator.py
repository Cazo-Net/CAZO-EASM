from __future__ import annotations

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.blockchain.domain.entities.transaction import Transaction
from app.blockchain.domain.entities.address import Address
from .models import (
    Alert, AlertRule, AlertSeverity, AlertStatus, AlertCategory,
    BUILT_IN_RULES, MIXER_RULE,
)

logger = logging.getLogger(__name__)

_cooldown_cache: dict[str, datetime] = {}


class RuleEvaluator:
    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self._rules = rules or (BUILT_IN_RULES + [MIXER_RULE])

    def evaluate_transaction(self, tx: Transaction) -> list[Alert]:
        alerts: list[Alert] = []
        chain = tx.chain.value if hasattr(tx.chain, 'value') else str(tx.chain)

        for rule in self._rules:
            cache_key = f"{rule.name}:{tx.hash}"
            if cache_key in _cooldown_cache:
                continue

            if rule.matches_transaction(tx):
                value_str = str(tx.value.to_native().value) if tx.value else "0"
                alert = Alert(
                    id=str(uuid.uuid4()),
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    chain=chain,
                    tx_hash=tx.hash,
                    address=tx.from_address or tx.to_address or "",
                    title=rule.name,
                    message=f"{rule.name} triggered: tx {tx.hash[:16]}... value={value_str}",
                    value=value_str,
                    created_at=datetime.utcnow(),
                )
                alerts.append(alert)
                _cooldown_cache[cache_key] = datetime.utcnow()
                logger.debug("Rule '%s' matched tx %s", rule.name, tx.hash[:16])

        return alerts

    def evaluate_address(self, address: Address, txs: list[Transaction] | None = None) -> list[Alert]:
        alerts: list[Alert] = []
        chain = address.chain.value if hasattr(address.chain, 'value') else str(address.chain)

        if address.balance and address.balance.to_native().value > Decimal("1000"):
            alerts.append(Alert(
                id=str(uuid.uuid4()),
                rule_name="High Balance Address",
                category=AlertCategory.LARGE_BALANCE_CHANGE,
                severity=AlertSeverity.MEDIUM,
                chain=chain,
                address=address.hash,
                title="High Balance Address",
                message=f"Address {address.hash[:16]}... holds {address.balance.to_native().value}",
                value=str(address.balance.to_native().value),
                created_at=datetime.utcnow(),
            ))

        return alerts

    def clear_cooldown(self, rule_name: str | None = None) -> None:
        global _cooldown_cache
        if rule_name:
            _cooldown_cache = {k: v for k, v in _cooldown_cache.items() if not k.startswith(f"{rule_name}:")}
        else:
            _cooldown_cache.clear()


evaluator = RuleEvaluator()
