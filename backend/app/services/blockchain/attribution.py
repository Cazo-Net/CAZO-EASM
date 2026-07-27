"""Blockchain attribution service.

Combines curated labels with provider data to build entity attribution.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.schemas.blockchain import (
    Chain,
    EntityAttribution,
    EntityCategory,
    Evidence,
    EvidenceType,
    WalletType,
)
from app.services.blockchain.labels.curated import lookup_address
from app.services.blockchain.providers.base import registry

logger = logging.getLogger(__name__)


async def attribute_address(address: str, chain: Chain) -> EntityAttribution:
    """Build a complete attribution for an address.

    Priority:
    1. Curated labels (highest confidence)
    2. On-chain heuristics (lower confidence)
    """
    curated = lookup_address(address)
    if curated is not None:
        return curated

    provider = registry.get(chain)
    if provider is None:
        return EntityAttribution()

    evidence: list[Evidence] = []
    category = EntityCategory.UNKNOWN
    confidence = 0

    try:
        summary = await provider.get_wallet_summary(address)
        if summary.wallet_type == WalletType.CONTRACT:
            contract = await provider.get_contract_detail(address)
            if contract and contract.verified:
                category = EntityCategory.DEFI_PROTOCOL
                confidence = 40
                evidence.append(Evidence(
                    source="on_chain",
                    type=EvidenceType.VERIFIED_CONTRACT,
                    confidence=40,
                    reason="Verified smart contract",
                ))
    except Exception as e:
        logger.debug("Attribution heuristic failed for %s: %s", address, e)

    return EntityAttribution(
        entity_name=None,
        category=category,
        confidence=confidence,
        evidence=evidence,
        last_updated=datetime.now(timezone.utc),
    )
