from __future__ import annotations

import logging

from app.blockchain.domain.entities.block import Block
from app.blockchain.domain.entities.transaction import Transaction
from app.blockchain.domain.value_objects.chain import Chain
from app.blockchain.domain.contracts.chain_connector import Collector, Normalizer
from app.blockchain.infrastructure.graph.address_store import (
    Neo4jBlockStore,
    Neo4jTransactionStore,
    Neo4jAddressStore,
)
from app.blockchain.infrastructure.search.transaction_indexer import TransactionIndexer
from .connector_registry import ConnectorRegistry

logger = logging.getLogger(__name__)


class BlockSyncService:
    def __init__(self, chain: Chain) -> None:
        if not ConnectorRegistry.has_collector(chain):
            raise ValueError(f"No collector registered for {chain}")
        self.chain = chain
        self.collector: Collector = ConnectorRegistry.get_collector(chain)
        self.normalizer: Normalizer = ConnectorRegistry.get_normalizer(chain)
        self.block_store: Neo4jBlockStore = ConnectorRegistry.get_block_store(chain)
        self.tx_store: Neo4jTransactionStore = ConnectorRegistry.get_tx_store(chain)
        self.address_store: Neo4jAddressStore = ConnectorRegistry.get_address_store(chain)
        self.tx_indexer = TransactionIndexer()

    async def sync_block(self, block_number: int) -> Block:
        raw_block = await self.collector.collect_block(block_number)
        block = self.normalizer.normalize_block(raw_block)
        await self.block_store.upsert(block)

        raw_txs = raw_block.get("transactions", [])
        txs: list[Transaction] = []
        for raw_tx in raw_txs:
            tx = self.normalizer.normalize_transaction(raw_tx)
            tx.chain = self.chain
            await self.tx_store.upsert(tx)
            if tx.from_address:
                await self.address_store.link_transaction(tx.hash, tx.from_address, "from")
            if tx.to_address:
                await self.address_store.link_transaction(tx.hash, tx.to_address, "to")
            txs.append(tx)

        if txs:
            self.tx_indexer.bulk_index(txs)

        logger.info("Synced block %d on %s: %d txs",
                     block_number, self.chain.value, len(raw_txs))
        return block
