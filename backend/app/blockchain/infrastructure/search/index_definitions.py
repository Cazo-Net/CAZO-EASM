from __future__ import annotations

from typing import Any

ADDRESS_INDEX = "blockchain_addresses"
TRANSACTION_INDEX = "blockchain_transactions"
BLOCK_INDEX = "blockchain_blocks"
CONTRACT_INDEX = "blockchain_contracts"

INDICES: dict[str, dict[str, Any]] = {
    ADDRESS_INDEX: {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "hash_analyzer": {"type": "custom", "tokenizer": "keyword", "filter": ["lowercase"]},
                    "partial_address": {"type": "custom", "tokenizer": "ngram_tokenizer", "filter": ["lowercase"]},
                },
                "tokenizer": {
                    "ngram_tokenizer": {"type": "ngram", "min_gram": 3, "max_gram": 20, "token_chars": ["letter", "digit"]},
                },
            },
        },
        "mappings": {
            "properties": {
                "hash": {"type": "keyword"},
                "hash_partial": {"type": "text", "analyzer": "partial_address", "search_analyzer": "keyword"},
                "chain": {"type": "keyword"},
                "wallet_type": {"type": "keyword"},
                "balance": {"type": "keyword"},
                "tx_count": {"type": "integer"},
                "token_count": {"type": "integer"},
                "is_contract": {"type": "boolean"},
                "entity_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "labels": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "first_seen_at": {"type": "date"},
                "last_active_at": {"type": "date"},
                "updated_at": {"type": "date"},
            },
        },
    },
    TRANSACTION_INDEX: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "hash": {"type": "keyword"},
                "chain": {"type": "keyword"},
                "block_number": {"type": "integer"},
                "timestamp": {"type": "date"},
                "from_address": {"type": "keyword"},
                "to_address": {"type": "keyword"},
                "value": {"type": "keyword"},
                "fee": {"type": "keyword"},
                "status": {"type": "keyword"},
                "method": {"type": "keyword"},
                "error": {"type": "text"},
                "is_contract_creation": {"type": "boolean"},
            },
        },
    },
    BLOCK_INDEX: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "number": {"type": "integer"},
                "chain": {"type": "keyword"},
                "hash": {"type": "keyword"},
                "parent_hash": {"type": "keyword"},
                "timestamp": {"type": "date"},
                "tx_count": {"type": "integer"},
                "size": {"type": "integer"},
                "miner": {"type": "keyword"},
            },
        },
    },
    CONTRACT_INDEX: {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "address": {"type": "keyword"},
                "chain": {"type": "keyword"},
                "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "symbol": {"type": "keyword"},
                "contract_type": {"type": "keyword"},
                "verified": {"type": "boolean"},
                "creator": {"type": "keyword"},
                "creation_tx": {"type": "keyword"},
                "decimals": {"type": "integer"},
            },
        },
    },
}


def ensure_indices() -> list[str]:
    from .opensearch_client import client as os_client

    created: list[str] = []
    for name, body in INDICES.items():
        if os_client.create_index(name, body):
            created.append(name)
    return created
