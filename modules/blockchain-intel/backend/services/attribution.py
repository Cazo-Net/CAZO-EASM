"""Entity attribution service — links addresses to real-world entities.

Combines curated labels, heuristics, and chain analysis to build
EntityAttribution objects with evidence chains.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..providers.base import registry
from ...labels.curated import get_labels_by_chain, search_labels
from ..domain.models.base import (
    Chain,
    EntityAttribution,
    EntityCategory,
    Evidence,
    EvidenceType,
    RiskBand,
    WalletSummary,
)

logger = logging.getLogger(__name__)


class AttributionService:
    """Service for attributing addresses to real-world entities."""

    async def attribute(self, address: str, chain: Chain) -> EntityAttribution:
        """Build attribution record for an address."""
        provider = registry.get(chain)
        if not provider:
            raise ValueError(f"Chain not supported: {chain}")

        # Get wallet summary
        wallet = await provider.get_wallet_summary(address)

        # Combine curated labels + heuristics
        attributions = await asyncio.gather(
            self._check_curated_labels(address, chain),
            self._check_exchange_patterns(address, wallet),
            self._check_protocol_patterns(address, chain),
            return_exceptions=True,
        )

        # Flatten results
        evidence_list: list[Evidence] = []
        entity_name = None
        category = EntityCategory.UNKNOWN
        risk_band = RiskBand.UNKNOWN

        for result in attributions:
            if isinstance(result, Exception):
                logger.warning("Attribution check failed: %s", result)
                continue
            if result:
                e = result
                evidence_list.extend(e.get("evidence", []))
                if e.get("entity"):
                    entity_name = e["entity"]
                if e.get("category"):
                    category = e["category"]
                if e.get("risk_band"):
                    risk_band = e["risk_band"]

        # Calculate risk band from evidence
        if not risk_band or risk_band == RiskBand.UNKNOWN:
            risk_band = self._calculate_risk_band(evidence_list)

        return EntityAttribution(
            address=address,
            chain=chain,
            entity=entity_name,
            category=category,
            confidence=max((e.confidence for e in evidence_list), default=0),
            evidence=evidence_list,
        )

    async def attribute_batch(
        self, addresses: list[str], chain: Chain
    ) -> list[EntityAttribution]:
        """Attribute a batch of addresses concurrently."""
        tasks = [self.attribute(addr, chain) for addr in addresses]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _check_curated_labels(
        self, address: str, chain: Chain
    ) -> dict[str, Any] | None:
        """Check address against curated label database."""
        labels = get_labels_by_chain(chain.value)
        for label in labels:
            if label["address"].lower() == address.lower():
                return {
                    "entity": label["entity"],
                    "category": label["category"],
                    "evidence": label.get("evidence", []),
                    "risk_band": self._category_risk_band(label["category"]),
                }
        return None

    async def _check_exchange_patterns(
        self, address: str, wallet: WalletSummary
    ) -> dict[str, Any] | None:
        """Heuristic: high tx count + large balance = likely exchange."""
        if wallet.tx_count > 100000 and float(wallet.balance) > 100:
            return {
                "entity": f"Unknown Exchange ({address[:8]}...)",
                "category": EntityCategory.EXCHANGE,
                "evidence": [
                    Evidence(
                        source="heuristic",
                        type=EvidenceType.NETWORK_ANALYSIS,
                        confidence=40,
                        reason=f"High tx count ({wallet.tx_count}) + large balance ({wallet.balance} ETH)",
                    )
                ],
                "risk_band": RiskBand.MEDIUM,
            }
        return None

    async def _check_protocol_patterns(
        self, address: str, chain: Chain
    ) -> dict[str, Any] | None:
        """Check if address matches known protocol patterns."""
        provider = registry.get(chain)
        if not provider:
            return None

        try:
            contract = await provider.get_contract(address)
            if contract and contract.verified:
                return {
                    "entity": contract.name or None,
                    "category": EntityCategory.DEFI_PROTOCOL if contract.contract_type.value in ("erc20", "erc721") else EntityCategory.UNKNOWN,
                    "evidence": [
                        Evidence(
                            source="contract_analysis",
                            type=EvidenceType.VERIFIED_CONTRACT,
                            confidence=70,
                            reason=f"Verified contract: {contract.name} ({contract.contract_type.value})",
                        )
                    ],
                }
        except Exception as e:
            logger.debug("Contract check failed: %s", e)

        return None

    def _category_risk_band(self, category: EntityCategory) -> RiskBand:
        """Map entity category to risk band."""
        risk_map = {
            EntityCategory.SANCTIONS: RiskBand.CRITICAL,
            EntityCategory.MIXING_SERVICE: RiskBand.HIGH,
            EntityCategory.EXCHANGE: RiskBand.MEDIUM,
            EntityCategory.STABLECOIN_ISSUER: RiskBand.LOW,
            EntityCategory.DEFI_PROTOCOL: RiskBand.LOW,
            EntityCategory.MINING_POOL: RiskBand.LOW,
        }
        return risk_map.get(category, RiskBand.UNKNOWN)

    def _calculate_risk_band(self, evidence: list[Evidence]) -> RiskBand:
        """Calculate risk band from evidence confidence scores."""
        if not evidence:
            return RiskBand.UNKNOWN

        # Weight by evidence type
        total_weight = 0
        weighted_score = 0

        for e in evidence:
            weight = self._evidence_weight(e.type)
            total_weight += weight
            weighted_score += e.confidence * weight

        if total_weight == 0:
            return RiskBand.UNKNOWN

        avg = weighted_score / total_weight

        if avg >= 90:
            return RiskBand.CRITICAL
        elif avg >= 70:
            return RiskBand.HIGH
        elif avg >= 50:
            return RiskBand.MEDIUM
        elif avg >= 30:
            return RiskBand.LOW
        return RiskBand.UNKNOWN

    def _evidence_weight(self, evidence_type: EvidenceType) -> float:
        """Weight factors by evidence type reliability."""
        weights = {
            EvidenceType.SANCTIONS_LIST: 5.0,
            EvidenceType.EXCHANGE_TAG: 3.0,
            EvidenceType.LABEL_SOURCE: 2.5,
            EvidenceType.VERIFIED_CONTRACT: 2.0,
            EvidenceType.NETWORK_ANALYSIS: 1.0,
            EvidenceType.MEMPOOL_ANALYSIS: 0.8,
            EvidenceType.HUMAN_REVIEW: 4.0,
        }
        return weights.get(evidence_type, 1.0)


# Process-wide singleton
attribution_service = AttributionService()
