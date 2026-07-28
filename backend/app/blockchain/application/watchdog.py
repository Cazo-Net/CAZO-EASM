from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.blockchain.domain.value_objects.chain import Chain
from app.blockchain.domain.contracts.chain_connector import ChainConnector
from app.blockchain.infrastructure.graph.address_store import Neo4jAddressStore
from .connector_registry import ConnectorRegistry
from .graph_sync import graph_sync

logger = logging.getLogger(__name__)


class WatchdogService:
    def __init__(self, poll_interval: int = 30) -> None:
        self._poll_interval = poll_interval
        self._watched: dict[str, Chain] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def add_watch(self, address: str, chain: Chain) -> None:
        self._watched[address] = chain
        logger.info("Watchdog watching %s on %s", address, chain.value)

    def remove_watch(self, address: str) -> None:
        self._watched.pop(address, None)
        logger.info("Watchdog removed watch: %s", address)

    def list_watches(self) -> list[dict[str, str]]:
        return [
            {"address": addr, "chain": chain.value}
            for addr, chain in self._watched.items()
        ]

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Watchdog started (poll interval: %ds)", self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Watchdog stopped")

    async def _poll_loop(self) -> None:
        while self._running:
            for address, chain in list(self._watched.items()):
                try:
                    connector: ChainConnector = ConnectorRegistry.get_connector(chain)
                    store: Neo4jAddressStore = ConnectorRegistry.get_address_store(chain)

                    wallet = await connector.get_wallet(address)
                    existing = await store.get(address, chain)
                    if existing and wallet.tx_count > existing.tx_count:
                        await graph_sync.sync_address(chain, address)
                        logger.debug("Watchdog synced %s: %d new txs",
                                      address, wallet.tx_count - existing.tx_count)
                except Exception as e:
                    logger.warning("Watchdog poll error for %s: %s", address, e)

            await asyncio.sleep(self._poll_interval)


watchdog = WatchdogService()
