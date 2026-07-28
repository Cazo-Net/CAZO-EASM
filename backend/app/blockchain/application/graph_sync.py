from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.blockchain.domain.value_objects.chain import Chain
from app.blockchain.domain.contracts.chain_connector import ChainConnector
from app.blockchain.infrastructure.graph.neo4j_driver import driver
from app.blockchain.infrastructure.search.opensearch_client import client as os_client
from .connector_registry import ConnectorRegistry
from .address_sync import AddressSyncService
from .block_sync import BlockSyncService
from .alerts import alert_service
from .compliance import travel_rule_service

logger = logging.getLogger(__name__)


class GraphSync:
    def __init__(self) -> None:
        self._chains: dict[Chain, AddressSyncService] = {}
        self._block_syncs: dict[Chain, BlockSyncService] = {}

    def register_chain(self, chain: Chain) -> None:
        if chain not in self._chains:
            self._chains[chain] = AddressSyncService(chain)
            self._block_syncs[chain] = BlockSyncService(chain)
            logger.info("GraphSync registered chain: %s", chain.value)

    async def sync_address(self, chain: Chain, address: str) -> dict[str, Any]:
        if chain not in self._chains:
            self.register_chain(chain)
        service = self._chains[chain]
        wallet = await service.sync_address(address)
        try:
            await alert_service.process_address(wallet)
        except Exception as e:
            logger.debug("Alert processing skipped for address %s: %s", address, e)
        return {
            "chain": chain.value,
            "address": address,
            "tx_count": wallet.tx_count,
            "token_count": wallet.token_count,
            "is_contract": wallet.is_contract,
        }

    async def sync_block(self, chain: Chain, block_number: int) -> dict[str, Any]:
        if chain not in self._block_syncs:
            self.register_chain(chain)
        service = self._block_syncs[chain]
        block = await service.sync_block(block_number)
        return {
            "chain": chain.value,
            "block_number": block.number,
            "tx_count": block.tx_count,
            "hash": block.hash,
        }

    async def stream_address(
        self, chain: Chain, address: str, interval_seconds: int = 15,
    ) -> None:
        if chain not in self._chains:
            self.register_chain(chain)
        connector: ChainConnector = ConnectorRegistry.get_connector(chain)
        logger.info("Streaming address %s on %s every %ds",
                     address, chain.value, interval_seconds)
        async for tx in connector.stream_new_activity(address):
            try:
                service = self._chains[chain]
                await service.sync_transactions([tx])
                if tx.from_address:
                    store = ConnectorRegistry.get_address_store(chain)
                    await store.link_transaction(tx.hash, tx.from_address, "from")
                if tx.to_address:
                    store = ConnectorRegistry.get_address_store(chain)
                    await store.link_transaction(tx.hash, tx.to_address, "to")
                try:
                    await alert_service.process_transaction(tx)
                except Exception as ae:
                    logger.debug("Alert processing skipped for tx %s: %s", tx.hash, ae)
                logger.info("Streamed new tx %s for %s", tx.hash, address)
            except Exception as e:
                logger.error("Stream sync error for %s: %s", address, e)

    async def health(self) -> dict[str, Any]:
        neo4j_ok = driver.is_connected
        if neo4j_ok:
            try:
                neo4j_ok = await driver.run("RETURN 1 AS ok")
                neo4j_ok = bool(neo4j_ok)
            except Exception:
                neo4j_ok = False
        return {
            "neo4j_connected": neo4j_ok,
            "opensearch_connected": os_client.is_connected,
            "opensearch_health": os_client.health(),
            "chains_registered": [c.value for c in self._chains.keys()],
        }


graph_sync = GraphSync()
