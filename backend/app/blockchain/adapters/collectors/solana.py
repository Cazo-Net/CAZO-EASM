from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.blockchain.domain.contracts.chain_connector import Collector
from app.blockchain.domain.value_objects.chain import Chain

logger = logging.getLogger(__name__)

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
SOLSCAN_API = "https://api.solscan.io"


class SolanaCollector(Collector):
    chain = Chain.SOLANA

    def __init__(self) -> None:
        self._last_request = 0.0

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.2:
            await asyncio.sleep(0.2 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _rpc(self, method: str, params: list[Any] | None = None) -> dict[str, Any]:
        await self._throttle()
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(SOLANA_RPC, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"Solana RPC error: {data['error']}")
            return data.get("result", {})

    async def collect_block(self, block_number: int) -> dict:
        return await self._rpc("getBlock", [block_number, {"encoding": "jsonParsed"}])

    async def collect_address_txs(self, address: str, start_block: int = 0) -> list[dict]:
        params = {"address": address, "page": "1", "page_size": "100"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{SOLSCAN_API}/v2/account/transactions", params=params)
            resp.raise_for_status()
            data = resp.json()
            txs = data.get("data", [])
            return txs if isinstance(txs, list) else []

    async def collect_address_balance(self, address: str) -> dict:
        result = await self._rpc("getBalance", [address])
        return {"address": address, "balance": str(result.get("value", 0))}
