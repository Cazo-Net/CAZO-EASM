from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from app.config import settings

logger = logging.getLogger(__name__)

_neo4j: Any | None = None
try:
    import neo4j as _neo4j
except ImportError:
    _neo4j = None


class Neo4jDriver:
    def __init__(self) -> None:
        self._driver: Any | None = None
        self._uri = settings.NEO4J_URI
        self._user = settings.NEO4J_USER
        self._password = settings.NEO4J_PASSWORD

    async def initialize(self) -> None:
        if self._driver:
            return
        if not _neo4j:
            logger.warning("neo4j package not installed — graph features disabled")
            return
        try:
            self._driver = _neo4j.AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
                max_transaction_retry_time=10,
            )
            await self._driver.verify_connectivity()
            logger.info("Neo4j connected: %s", self._uri)
        except Exception as e:
            logger.warning("Neo4j connection failed (%s). Graph features disabled: %s", self._uri, e)
            self._driver = None

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    @property
    def is_connected(self) -> bool:
        return self._driver is not None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any]:
        if not self._driver:
            raise RuntimeError("Neo4j not connected")
        async with self._driver.session() as session:
            yield session

    async def run(self, query: str, **params) -> list[dict]:
        if not self._driver:
            return []
        async with self._driver.session() as session:
            result = await session.run(query, **params)
            return [record.data() async for record in result]

    async def run_write(self, query: str, **params) -> list[dict]:
        if not self._driver:
            return []
        async with self._driver.session() as session:
            result = await session.execute_write(lambda tx: tx.run(query, **params))
            return [record.data() async for record in result]


driver = Neo4jDriver()
