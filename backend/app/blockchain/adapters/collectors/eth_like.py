from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.blockchain.domain.contracts.chain_connector import Collector
from app.blockchain.domain.value_objects.chain import Chain
from app.config import settings

logger = logging.getLogger(__name__)


class EthLikeCollector(Collector):
    def __init__(
        self,
        chain: Chain,
        api_base_url: str,
        chain_id: int,
        api_key: str = "",
    ) -> None:
        self.chain = chain
        self._api_base = api_base_url
        self._chain_id = chain_id
        self._api_key = api_key or getattr(settings, "ETHERSCAN_API_KEY", "")
        self._last_request = 0.0

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.25:
            await asyncio.sleep(0.25 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        await self._throttle()
        params.setdefault("chainid", str(self._chain_id))
        if self._api_key:
            params["apikey"] = self._api_key

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(self._api_base, params=params)
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
        resp = await self._get({
            "module": "proxy", "action": "eth_getBlockByNumber",
            "tag": hex(block_number), "boolean": "true",
        })
        return resp.get("result", {})

    async def collect_address_txs(self, address: str, start_block: int = 0) -> list[dict]:
        resp = await self._get({
            "module": "account", "action": "txlist",
            "address": address,
            "startblock": str(start_block), "endblock": "99999999",
            "page": "1", "offset": "100", "sort": "desc",
        })
        results = resp.get("result", [])
        return results if isinstance(results, list) else []

    async def collect_address_balance(self, address: str) -> dict:
        resp = await self._get({
            "module": "account", "action": "balance",
            "address": address, "tag": "latest",
        })
        return {"address": address, "balance": resp.get("result", "0")}


# ── EVM Chain Collector Factories ──────────────────────────────────────────

def ethereum_collector(api_key: str = "") -> EthLikeCollector:
    return EthLikeCollector(Chain.ETHEREUM, "https://api.etherscan.io/v2/api", 1, api_key)


def bnb_collector(api_key: str = "") -> EthLikeCollector:
    return EthLikeCollector(Chain.BNB, "https://api.bscscan.com/api", 56, api_key)


def polygon_collector(api_key: str = "") -> EthLikeCollector:
    return EthLikeCollector(Chain.POLYGON, "https://api.polygonscan.com/api", 137, api_key)


def arbitrum_collector(api_key: str = "") -> EthLikeCollector:
    return EthLikeCollector(Chain.ARBITRUM, "https://api.arbiscan.io/api", 42161, api_key)


def optimism_collector(api_key: str = "") -> EthLikeCollector:
    return EthLikeCollector(Chain.OPTIMISM, "https://api-optimistic.etherscan.io/api", 10, api_key)


def base_collector(api_key: str = "") -> EthLikeCollector:
    return EthLikeCollector(Chain.BASE, "https://api.basescan.org/api", 8453, api_key)


def avalanche_collector(api_key: str = "") -> EthLikeCollector:
    return EthLikeCollector(Chain.AVALANCHE, "https://api.snowtrace.io/api", 43114, api_key)
