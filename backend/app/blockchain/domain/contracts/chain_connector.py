from __future__ import annotations

from typing import AsyncIterator, Protocol

from ...domain.entities.address import Address
from ...domain.entities.transaction import Transaction
from ...domain.entities.token import TokenBalance, Contract
from ...domain.entities.block import Block
from ...domain.entities.evidence import Evidence
from ..value_objects.chain import Chain


class ChainConnector(Protocol):
    chain_id: str

    async def validate_address(self, address: str) -> bool:
        ...

    async def get_wallet(self, address: str) -> Address:
        ...

    async def get_transaction(self, tx_hash: str) -> Transaction:
        ...

    async def get_contract(self, address: str) -> Contract | None:
        ...

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        ...

    async def get_current_block(self) -> int:
        ...

    async def get_block(self, number: int) -> Block:
        ...

    async def stream_new_activity(self, address: str) -> AsyncIterator[Transaction]:
        """Stream new transactions for a watched address."""
        if False:
            yield


class Collector(Protocol):
    chain: Chain

    async def collect_block(self, block_number: int) -> dict:
        """Collect raw block data from the chain."""
        ...

    async def collect_address_txs(self, address: str, start_block: int = 0) -> list[dict]:
        """Collect raw transactions for an address."""
        ...

    async def collect_address_balance(self, address: str) -> dict:
        """Collect raw balance data."""
        ...


class Normalizer(Protocol):
    chain: Chain

    def normalize_block(self, raw: dict) -> Block:
        """Normalize raw block data to domain Block entity."""
        ...

    def normalize_transaction(self, raw: dict, chain: Chain) -> Transaction:
        """Normalize raw transaction data to domain Transaction entity."""
        ...

    def normalize_address(self, raw: dict) -> Address:
        """Normalize raw address data to domain Address entity."""
        ...

    def normalize_token_balance(self, raw: dict) -> TokenBalance:
        """Normalize raw token balance data."""
        ...

    def normalize_contract(self, raw: dict) -> Contract:
        """Normalize raw contract data."""
        ...


class GraphStore(Protocol):
    async def upsert_address(self, address: Address) -> None:
        ...

    async def upsert_transaction(self, tx: Transaction) -> None:
        ...

    async def upsert_block(self, block: Block) -> None:
        ...

    async def upsert_contract(self, contract: Contract) -> None:
        ...

    async def link_transaction_to_address(self, tx_hash: str, address_hash: str, role: str) -> None:
        """Create SENT/RECEIVED edge between tx and address."""
        ...

    async def get_address(self, hash: str, chain: Chain) -> Address | None:
        ...

    async def get_transaction(self, hash: str, chain: Chain) -> Transaction | None:
        ...

    async def get_block(self, number: int, chain: Chain) -> Block | None:
        ...

    async def get_address_transactions(
        self, address: str, chain: Chain, limit: int = 50, offset: int = 0
    ) -> list[Transaction]:
        ...

    async def health_check(self) -> bool:
        ...
