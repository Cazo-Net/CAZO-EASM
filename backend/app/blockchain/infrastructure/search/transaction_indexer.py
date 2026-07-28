from __future__ import annotations

from datetime import datetime
from typing import Any

from app.blockchain.domain.entities.transaction import Transaction
from .opensearch_client import client as os_client
from .index_definitions import TRANSACTION_INDEX


class TransactionIndexer:
    INDEX = TRANSACTION_INDEX

    def index(self, tx: Transaction) -> bool:
        if not os_client.is_connected:
            return False
        doc = {
            "hash": tx.hash,
            "chain": tx.chain.value,
            "block_number": tx.block_number,
            "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
            "from_address": tx.from_address,
            "to_address": tx.to_address,
            "value": str(tx.value) if tx.value else "0",
            "fee": str(tx.fee) if tx.fee else None,
            "status": tx.status.value,
            "method": tx.method,
            "error": tx.error,
            "is_contract_creation": tx.is_contract_creation,
            "updated_at": datetime.utcnow().isoformat(),
        }
        doc_id = f"{tx.chain.value}:{tx.hash}"
        return os_client.index_doc(self.INDEX, doc_id, doc)

    def bulk_index(self, txs: list[Transaction]) -> int:
        if not os_client.is_connected or not txs:
            return 0
        docs = []
        for tx in txs:
            doc = {
                "_id": f"{tx.chain.value}:{tx.hash}",
                "hash": tx.hash,
                "chain": tx.chain.value,
                "block_number": tx.block_number,
                "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
                "from_address": tx.from_address,
                "to_address": tx.to_address,
                "value": str(tx.value) if tx.value else "0",
                "fee": str(tx.fee) if tx.fee else None,
                "status": tx.status.value,
                "method": tx.method,
                "error": tx.error,
                "is_contract_creation": tx.is_contract_creation,
            }
            docs.append(doc)
        return os_client.bulk_index(self.INDEX, docs)

    def search_by_address(self, address: str, chain: str | None = None, size: int = 50) -> list[dict]:
        must: list[dict] = [
            {"multi_match": {"query": address, "fields": ["from_address", "to_address"]}},
        ]
        if chain:
            must.append({"term": {"chain": chain}})
        body = {
            "query": {"bool": {"must": must}},
            "sort": [{"timestamp": {"order": "desc"}}],
        }
        return os_client.search(self.INDEX, body, size)
