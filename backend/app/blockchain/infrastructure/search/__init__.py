from .opensearch_client import OpenSearchClient, client
from .index_definitions import ensure_indices, ADDRESS_INDEX, TRANSACTION_INDEX, BLOCK_INDEX, CONTRACT_INDEX
from .address_indexer import AddressIndexer
from .transaction_indexer import TransactionIndexer
from .search_service import SearchService, search_service

__all__ = [
    "OpenSearchClient",
    "client",
    "ensure_indices",
    "ADDRESS_INDEX",
    "TRANSACTION_INDEX",
    "BLOCK_INDEX",
    "CONTRACT_INDEX",
    "AddressIndexer",
    "TransactionIndexer",
    "SearchService",
    "search_service",
]
