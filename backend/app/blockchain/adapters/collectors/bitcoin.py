from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.blockchain.domain.contracts.chain_connector import Collector
from app.blockchain.domain.value_objects.chain import Chain

logger = logging.getLogger(__name__)

BLOCKSTREAM_BASE = "https://blockstream.info/api"


class BitcoinCollector(Collector):
    chain = Chain.BITCOIN

    def __init__(self) -> None:
        self._last_request = 0.0

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.33:
            await asyncio.sleep(0.33 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, path: str) -> Any:
        await self._throttle()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(f"{BLOCKSTREAM_BASE}{path}")
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                continue
            except Exception as exc:
                last_error = exc
                break
        raise last_error

    async def collect_block(self, block_number: int) -> dict:
        block_hash = await self._get(f"/block-height/{block_number}")
        return await self._get(f"/block/{block_hash}")

    async def collect_address_txs(self, address: str, start_block: int = 0) -> list[dict]:
        try:
            txs = await self._get(f"/address/{address}/txs")
            return txs if isinstance(txs, list) else []
        except httpx.HTTPStatusError:
            return []

    async def collect_address_balance(self, address: str) -> dict:
        try:
            info = await self._get(f"/address/{address}")
            stats = info.get("chain_stats", {})
            funded = stats.get("funded_txo_sum", 0)
            spent = stats.get("spent_txo_sum", 0)
            return {"address": address, "balance": str(funded - spent)}
        except httpx.HTTPStatusError:
            return {"address": address, "balance": "0"}
