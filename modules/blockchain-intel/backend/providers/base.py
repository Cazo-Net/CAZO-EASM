"""Chain provider interface — the core abstraction.

Every blockchain adapter implements this ABC.
Adding a new chain = implementing this interface + registering it.
Zero changes to services, routes, or frontend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..domain.models.base import (
    Chain,
    ContractDetail,
    PaginatedResponse,
    TransactionDetail,
    TransactionSummary,
    WalletSummary,
)


class ChainProviderInterface(ABC):
    """Abstract base class for all chain data providers."""

    @property
    @abstractmethod
    def chain(self) -> Chain:
        """Return which chain this provider supports."""
        ...

    @abstractmethod
    async def validate_address(self, address: str) -> bool:
        """Validate address format for this chain (checksum if applicable)."""
        ...

    @abstractmethod
    async def get_wallet_summary(self, address: str) -> WalletSummary:
        """Return wallet overview: balance, tx count, first/last seen, etc."""
        ...

    @abstractmethod
    async def get_transactions(
        self,
        address: str,
        page: int = 1,
        page_size: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Return paginated transaction history for an address."""
        ...

    @abstractmethod
    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        """Return full transaction detail by hash."""
        ...

    @abstractmethod
    async def get_contract(self, address: str) -> ContractDetail | None:
        """Return contract details if the address is a contract. None otherwise."""
        ...

    @abstractmethod
    async def get_token_balances(self, address: str) -> list[dict[str, Any]]:
        """Return ERC-20 / token balances for an address."""
        ...

    @abstractmethod
    async def search(self, query: str) -> list[dict[str, Any]]:
        """Search for addresses, transactions, or contracts matching query."""
        ...


class ProviderRegistry:
    """Central registry for chain providers."""

    def __init__(self) -> None:
        self._providers: dict[Chain, ChainProviderInterface] = {}

    def register(self, provider: ChainProviderInterface) -> None:
        self._providers[provider.chain] = provider

    def get(self, chain: Chain) -> ChainProviderInterface | None:
        return self._providers.get(chain)

    def supported_chains(self) -> list[Chain]:
        return list(self._providers.keys())

    def all(self) -> dict[Chain, ChainProviderInterface]:
        return dict(self._providers)


# Process-wide singleton
registry = ProviderRegistry()
