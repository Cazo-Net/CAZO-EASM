from __future__ import annotations

import logging

from app.blockchain.domain.contracts.chain_connector import ChainConnector, Collector, Normalizer
from app.blockchain.domain.entities.address import Address
from app.blockchain.domain.entities.transaction import Transaction
from app.blockchain.domain.entities.token import Contract
from app.blockchain.domain.value_objects.chain import Chain
from app.blockchain.infrastructure.graph.address_store import (
    Neo4jAddressStore,
    Neo4jTransactionStore,
    Neo4jBlockStore,
)
from app.blockchain.infrastructure.search.address_indexer import AddressIndexer
from app.blockchain.infrastructure.search.transaction_indexer import TransactionIndexer
from .connector_registry import ConnectorRegistry
from .compliance import travel_rule_service

logger = logging.getLogger(__name__)


class AddressSyncService:
    def __init__(self, chain: Chain) -> None:
        if not ConnectorRegistry.has_connector(chain):
            raise ValueError(f"No connector registered for {chain}")
        self.chain = chain
        self.connector: ChainConnector = ConnectorRegistry.get_connector(chain)
        self.collector: Collector = ConnectorRegistry.get_collector(chain)
        self.normalizer: Normalizer = ConnectorRegistry.get_normalizer(chain)
        self.address_store: Neo4jAddressStore = ConnectorRegistry.get_address_store(chain)
        self.tx_store: Neo4jTransactionStore = ConnectorRegistry.get_tx_store(chain)
        self.block_store: Neo4jBlockStore = ConnectorRegistry.get_block_store(chain)
        self.address_indexer = AddressIndexer()
        self.tx_indexer = TransactionIndexer()

    async def sync_address(self, address: str) -> Address:
        wallet = await self.connector.get_wallet(address)

        raw_txs = await self.collector.collect_address_txs(address)
        txs = [self.normalizer.normalize_transaction(tx) for tx in raw_txs]
        await self.sync_transactions(txs)

        token_balances = await self.connector.get_token_balances(address)

        contract: Contract | None = None
        if wallet.is_contract:
            contract = await self.connector.get_contract(address)

        wallet.token_count = len(token_balances)
        await self.address_store.upsert(wallet)

        for tx in txs:
            tx.chain = self.chain
            if tx.from_address:
                await self.address_store.link_transaction(tx.hash, tx.from_address, "from")
            if tx.to_address:
                await self.address_store.link_transaction(tx.hash, tx.to_address, "to")

        if txs:
            self.tx_indexer.bulk_index(txs)
        self.address_indexer.index(wallet)

        for tx in txs:
            try:
                travel_rule_service.create_travel_rule_case(tx)
            except Exception as e:
                logger.debug("Travel rule detection skipped: %s", e)

        logger.info("Synced address %s on %s: %d txs, %d tokens",
                     address, self.chain.value, len(txs), len(token_balances))
        return wallet

    async def sync_transactions(self, txs: list[Transaction]) -> None:
        for tx in txs:
            tx.chain = self.chain
            await self.tx_store.upsert(tx)
        if txs:
            self.tx_indexer.bulk_index(txs)

    async def sync_token_balances(self, address: str, balances: list[TokenBalance]) -> None:
        for tb in balances:
            if tb.contract_address:
                contract = await self.connector.get_contract(tb.contract_address)
                if contract:
                    pass

    async def sync_contract(self, address: str) -> Contract | None:
        contract = await self.connector.get_contract(address)
        if contract:
            pass
        return contract
