"""Chain provider abstraction layer.

Every supported chain has a provider that implements this interface.
The registry auto-discovers and routes calls to the right provider.
"""
from __future__ import annotations

import abc
import logging
from typing import Any

from app.schemas.blockchain import (
    Chain,
    ContractDetail,
    GraphData,
    RiskScore,
    TokenBalance,
    TransactionDetail,
    TransactionSummary,
    WalletSummary,
)

logger = logging.getLogger(__name__)


class DataSourceUnavailable(Exception):
    """Raised when live chain data cannot be fetched.

    The platform never substitutes made-up numbers. ``reason`` is
    ``"not_configured"`` (an API key the operator must add) or
    ``"upstream_error"`` (the public source did not answer).
    """

    def __init__(self, chain: Chain, reason: str, message: str, setting: str | None = None) -> None:
        super().__init__(message)
        self.chain = chain
        self.reason = reason
        self.message = message
        self.setting = setting

    def to_detail(self) -> dict[str, Any]:
        return {
            "code": f"data_source_{self.reason}",
            "chain": self.chain.value,
            "message": self.message,
            "setting": self.setting,
        }


# ── Abstract Base ────────────────────────────────────────────────────────────

class ChainProvider(abc.ABC):
    """All chain providers must implement this interface."""

    chain: Chain

    @abc.abstractmethod
    async def get_wallet_summary(self, address: str) -> WalletSummary:
        ...

    @abc.abstractmethod
    async def get_transactions(
        self, address: str, page: int = 1, page_size: int = 20
    ) -> list[TransactionSummary]:
        ...

    @abc.abstractmethod
    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        ...

    @abc.abstractmethod
    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        ...

    @abc.abstractmethod
    async def get_contract_detail(self, address: str) -> ContractDetail | None:
        ...

    async def get_graph_data(
        self, address: str, depth: int = 2, limit: int = 50
    ) -> GraphData:
        """Override if the provider supports graph traversal."""
        return GraphData()

    async def get_risk_score(self, address: str) -> RiskScore:
        """Override if the provider has native risk data."""
        return RiskScore(address=address, chain=self.chain)

    def is_available(self) -> bool:
        """Health check — override to verify API key, network, etc."""
        return True


# ── Registry ─────────────────────────────────────────────────────────────────

class ProviderRegistry:
    """Singleton that maps chains to providers."""

    _instance: ProviderRegistry | None = None
    _providers: dict[Chain, ChainProvider]

    def __new__(cls) -> ProviderRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def register(self, provider: ChainProvider) -> None:
        self._providers[provider.chain] = provider
        logger.info("Registered provider: %s for chain %s", provider.__class__.__name__, provider.chain.value)

    def get(self, chain: Chain) -> ChainProvider | None:
        return self._providers.get(chain)

    def get_or_raise(self, chain: Chain) -> ChainProvider:
        provider = self._providers.get(chain)
        if provider is None:
            raise ValueError(f"No provider registered for chain: {chain.value}")
        return provider

    @property
    def supported_chains(self) -> list[Chain]:
        return list(self._providers.keys())

    @property
    def available_chains(self) -> list[Chain]:
        return [c for c, p in self._providers.items() if p.is_available()]


# ── Module-level singleton ──────────────────────────────────────────────────

registry = ProviderRegistry()
