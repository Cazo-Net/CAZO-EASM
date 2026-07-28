from __future__ import annotations

from datetime import datetime
from typing import Any

from app.blockchain.domain.entities.address import Address
from .opensearch_client import client as os_client
from .index_definitions import ADDRESS_INDEX


class AddressIndexer:
    INDEX = ADDRESS_INDEX

    def index(self, address: Address) -> bool:
        if not os_client.is_connected:
            return False
        doc = {
            "hash": address.hash,
            "hash_partial": address.hash,
            "chain": address.chain.value,
            "wallet_type": address.wallet_type.value,
            "balance": str(address.balance) if address.balance else "0",
            "tx_count": address.tx_count,
            "token_count": address.token_count,
            "is_contract": address.is_contract,
            "entity_name": address.entity_name,
            "labels": address.labels,
            "first_seen_at": address.first_seen_at.isoformat() if address.first_seen_at else None,
            "last_active_at": address.last_active_at.isoformat() if address.last_active_at else None,
            "updated_at": datetime.utcnow().isoformat(),
        }
        doc_id = f"{address.chain.value}:{address.hash}"
        return os_client.index_doc(self.INDEX, doc_id, doc)

    def bulk_index(self, addresses: list[Address]) -> int:
        if not os_client.is_connected or not addresses:
            return 0
        docs = []
        for addr in addresses:
            doc = {
                "_id": f"{addr.chain.value}:{addr.hash}",
                "hash": addr.hash,
                "hash_partial": addr.hash,
                "chain": addr.chain.value,
                "wallet_type": addr.wallet_type.value,
                "balance": str(addr.balance) if addr.balance else "0",
                "tx_count": addr.tx_count,
                "token_count": addr.token_count,
                "is_contract": addr.is_contract,
                "entity_name": addr.entity_name,
                "labels": addr.labels,
                "first_seen_at": addr.first_seen_at.isoformat() if addr.first_seen_at else None,
                "last_active_at": addr.last_active_at.isoformat() if addr.last_active_at else None,
                "updated_at": datetime.utcnow().isoformat(),
            }
            docs.append(doc)
        return os_client.bulk_index(self.INDEX, docs)

    def search(self, query: str, chain: str | None = None, size: int = 20) -> list[dict]:
        must: list[dict] = [
            {"multi_match": {"query": query, "fields": ["hash", "hash_partial", "entity_name", "labels"], "type": "best_fields"}},
        ]
        if chain:
            must.append({"term": {"chain": chain}})
        body = {"query": {"bool": {"must": must}}}
        return os_client.search(self.INDEX, body, size)

    def get_by_hash(self, hash: str, chain: str) -> dict | None:
        doc_id = f"{chain}:{hash}"
        try:
            if not os_client.is_connected:
                return None
            from opensearchpy.exceptions import NotFoundError
            client = os_client._ensure()
            result = client.get(index=self.INDEX, id=doc_id)
            return result.get("_source")
        except NotFoundError:
            return None
        except Exception:
            return None
