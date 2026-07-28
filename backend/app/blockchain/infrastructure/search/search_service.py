from __future__ import annotations

from typing import Any

from .opensearch_client import client as os_client
from .index_definitions import ADDRESS_INDEX, TRANSACTION_INDEX, BLOCK_INDEX, CONTRACT_INDEX
from .address_indexer import AddressIndexer
from .transaction_indexer import TransactionIndexer


class SearchService:
    def __init__(self) -> None:
        self.addresses = AddressIndexer()
        self.transactions = TransactionIndexer()

    def unified_search(self, query: str, chain: str | None = None, size: int = 20) -> dict[str, list[dict]]:
        if not os_client.is_connected:
            return {"addresses": [], "transactions": [], "contracts": []}

        must: list[dict] = [
            {"multi_match": {"query": query, "fields": ["hash", "hash_partial", "entity_name", "labels", "name", "symbol"], "type": "best_fields"}},
        ]
        if chain:
            must.append({"term": {"chain": chain}})

        body = {"query": {"bool": {"must": must}}}

        results = os_client.multi_search(
            [ADDRESS_INDEX, TRANSACTION_INDEX, CONTRACT_INDEX],
            body, size,
        )

        return {
            "addresses": results.get(ADDRESS_INDEX, []),
            "transactions": results.get(TRANSACTION_INDEX, []),
            "contracts": results.get(CONTRACT_INDEX, []),
        }

    def search_addresses(self, query: str, chain: str | None = None, size: int = 20) -> list[dict]:
        return self.addresses.search(query, chain, size)

    def search_transactions(self, query: str, chain: str | None = None, size: int = 50) -> list[dict]:
        return self.transactions.search_by_address(query, chain, size)

    def health(self) -> dict[str, Any]:
        return os_client.health()


search_service = SearchService()
