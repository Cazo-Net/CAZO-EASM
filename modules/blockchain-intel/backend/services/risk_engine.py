"""Risk scoring engine — multi-factor risk assessment.

Computes RiskScore from attribution, transaction patterns, and heuristics.
"""
from __future__ import annotations

import logging
from typing import Any

from ..domain.models.base import (
    Chain,
    Evidence,
    RiskBand,
    RiskFactor,
    RiskScore,
    WalletSummary,
)

logger = logging.getLogger(__name__)


class RiskEngine:
    """Multi-factor risk scoring engine for blockchain addresses."""

    async def score(
        self,
        address: str,
        chain: Chain,
        wallet: WalletSummary | None = None,
        attribution: Any = None,
        transactions: list[dict[str, Any]] | None = None,
    ) -> RiskScore:
        """Compute composite risk score for an address."""
        factors: list[RiskFactor] = []

        # Attribution-based factors
        if attribution:
            factors.extend(self._attribution_factors(attribution))

        # Wallet-based factors
        if wallet:
            factors.extend(self._wallet_factors(wallet))

        # Transaction-based factors
        if transactions:
            factors.extend(self._transaction_factors(transactions))

        # Compute composite score
        if not factors:
            return RiskScore(
                address=address,
                chain=chain,
                score=0,
                band=RiskBand.UNKNOWN,
                factors=[],
                evidence=[],
            )

        # Weighted average of factor scores
        total_weight = sum(f.weight for f in factors)
        weighted_score = sum(f.score * f.weight for f in factors) if total_weight > 0 else 0
        composite = round(weighted_score / total_weight) if total_weight > 0 else 0

        band = self._score_to_band(composite)

        evidence = [
            Evidence(
                source="risk_engine",
                confidence=composite,
                reason=f"Factor: {f.name} (score={f.score}, weight={f.weight})",
            )
            for f in factors
        ]

        return RiskScore(
            address=address,
            chain=chain,
            score=composite,
            band=band,
            factors=factors,
            evidence=evidence,
        )

    def _attribution_factors(self, attribution: Any) -> list[RiskFactor]:
        """Extract risk factors from attribution data."""
        factors = []

        category = getattr(attribution, "category", None)
        if category:
            from ...domain.models.base import EntityCategory
            category_risk = {
                EntityCategory.SANCTIONS: ("Sanctioned entity", 100, 10.0),
                EntityCategory.MIXING_SERVICE: ("Mixing service", 85, 5.0),
                EntityCategory.EXCHANGE: ("Exchange wallet", 30, 1.0),
                EntityCategory.DEFI_PROTOCOL: ("DeFi protocol", 10, 0.5),
                EntityCategory.STABLECOIN_ISSUER: ("Stablecoin issuer", 5, 0.5),
            }
            if category in category_risk:
                name, score, weight = category_risk[category]
                factors.append(RiskFactor(name=name, score=score, weight=weight))

        confidence = getattr(attribution, "confidence", 0)
        if confidence > 0:
            factors.append(RiskFactor(
                name="Attribution confidence",
                score=min(confidence, 100),
                weight=2.0,
            ))

        return factors

    def _wallet_factors(self, wallet: WalletSummary) -> list[RiskFactor]:
        """Extract risk factors from wallet data."""
        factors = []
        balance = float(wallet.balance) if wallet.balance else 0
        tx_count = wallet.tx_count or 0

        # Very high balance — potential whale/exchange
        if balance > 10000:
            factors.append(RiskFactor(
                name="Large balance",
                score=40,
                weight=1.5,
            ))
        elif balance > 1000:
            factors.append(RiskFactor(
                name="Moderate balance",
                score=20,
                weight=1.0,
            ))

        # Very high tx count
        if tx_count > 100000:
            factors.append(RiskFactor(
                name="Very high tx count",
                score=50,
                weight=1.2,
            ))
        elif tx_count > 10000:
            factors.append(RiskFactor(
                name="High tx count",
                score=30,
                weight=0.8,
            ))

        # Contract vs EOA
        from ...domain.models.base import WalletType
        if wallet.wallet_type == WalletType.CONTRACT:
            factors.append(RiskFactor(
                name="Contract address",
                score=10,
                weight=0.5,
            ))

        return factors

    def _transaction_factors(self, transactions: list[dict[str, Any]]) -> list[RiskFactor]:
        """Extract risk factors from transaction patterns."""
        factors = []

        if not transactions:
            return factors

        # High gas price (potential MEV)
        for tx in transactions[:10]:
            gas_price = tx.get("gas_price", "0")
            try:
                gas_price_eth = float(gas_price) / 1e18
                if gas_price_eth > 200:  # > 200 Gwei
                    factors.append(RiskFactor(
                        name="High gas price (potential MEV)",
                        score=60,
                        weight=1.0,
                    ))
                    break
            except (ValueError, TypeError):
                pass

        # Interaction with known risky addresses
        risky_interactions = 0
        for tx in transactions[:50]:
            to_addr = tx.get("to_address", "")
            if to_addr and self._is_known_risky(to_addr):
                risky_interactions += 1

        if risky_interactions > 0:
            factors.append(RiskFactor(
                name="Interacts with known risky addresses",
                score=min(risky_interactions * 20, 100),
                weight=2.0,
            ))

        return factors

    def _is_known_risky(self, address: str) -> bool:
        """Check if address is known risky (placeholder for production)."""
        known_risky = {
            "0x8589427373D6D84E98730D7795D8f6f8731FDA16",  # Lazarus Group
            "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",  # Sinbad mixer
        }
        return address.lower() in {a.lower() for a in known_risky}

    def _score_to_band(self, score: int) -> RiskBand:
        """Convert numeric score to risk band."""
        if score >= 90:
            return RiskBand.CRITICAL
        elif score >= 70:
            return RiskBand.HIGH
        elif score >= 50:
            return RiskBand.MEDIUM
        elif score >= 30:
            return RiskBand.LOW
        elif score > 0:
            return RiskBand.INFO
        return RiskBand.UNKNOWN


# Process-wide singleton
risk_engine = RiskEngine()
