"""Blockchain risk scoring engine.

Rule-based risk scoring with curated labels integration.
Phase 2: ML anomaly scoring via separate ml/ module.
"""
from __future__ import annotations

import logging

from app.schemas.blockchain import (
    Chain,
    Evidence,
    EvidenceType,
    RiskBand,
    RiskFactor,
    RiskScore,
)
from app.services.blockchain.labels.curated import lookup_address
from app.services.blockchain.providers.base import registry

logger = logging.getLogger(__name__)


async def compute_risk(address: str, chain: Chain) -> RiskScore:
    """Compute risk score for an address.

    Combines:
    1. Curated label risk (sanctions = critical, mixers = high, etc.)
    2. Provider-native risk score (if available)
    3. Rule-based heuristics
    """
    curated = lookup_address(address)

    if curated and curated.entity_name:
        if curated.category.value == "sanctions":
            return RiskScore(
                address=address,
                chain=chain,
                score=95,
                band=RiskBand.CRITICAL,
                factors=[
                    RiskFactor(
                        category="sanctions",
                        label=f"Sanctioned entity: {curated.entity_name}",
                        weight=5.0,
                        contribution=85,
                        evidence=curated.evidence,
                    )
                ],
            )
        if curated.category.value == "mixing_service":
            return RiskScore(
                address=address,
                chain=chain,
                score=85,
                band=RiskBand.HIGH,
                factors=[
                    RiskFactor(
                        category="mixer",
                        label=f"Mixer service: {curated.entity_name}",
                        weight=4.0,
                        contribution=75,
                        evidence=curated.evidence,
                    )
                ],
            )
        if curated.category.value == "exchange":
            return RiskScore(
                address=address,
                chain=chain,
                score=5,
                band=RiskBand.INFO,
                factors=[
                    RiskFactor(
                        category="exchange",
                        label=f"Known exchange: {curated.entity_name}",
                        weight=0.5,
                        contribution=0,
                        evidence=curated.evidence,
                    )
                ],
            )

    provider = registry.get(chain)
    if provider:
        try:
            return await provider.get_risk_score(address)
        except Exception as e:
            logger.debug("Provider risk score failed for %s: %s", address, e)

    return RiskScore(
        address=address,
        chain=chain,
        score=0,
        band=RiskBand.UNKNOWN,
        factors=[],
    )
