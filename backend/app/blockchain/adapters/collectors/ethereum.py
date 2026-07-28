from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.blockchain.domain.contracts.chain_connector import Collector
from app.blockchain.domain.value_objects.chain import Chain
from app.config import settings

logger = logging.getLogger(__name__)

ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"
_ETHERSCAN_IPS = ["23.92.68.154", "217.79.240.58", "217.79.243.34"]


class EthereumCollector(Collector):
    chain = Chain.ETHEREUM

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key or settings.ETHERSCAN_API_KEY
        self._last_request = 0.0

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.25:
            await asyncio.sleep(0.25 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        await self._throttle()
        params.setdefault("chainid", "1")
        if self._api_key:
            params["apikey"] = self._api_key

        urls_to_try = [
            (ETHERSCAN_BASE, {}),
            (f"https://{_ETHERSCAN_IPS[0]}/v2/api", {"Host": "api.etherscan.io"}),
            (f"https://{_ETHERSCAN_IPS[1]}/v2/api", {"Host": "api.etherscan.io"}),
        ]

        last_error: Exception | None = None
        for url, extra_headers in urls_to_try:
            try:
                verify = not bool(extra_headers)
                async with httpx.AsyncClient(timeout=30, verify=verify) as client:
                    resp = await client.get(url, params=params, headers=extra_headers)
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue
        raise last_error or httpx.ConnectError("All Etherscan endpoints failed")

    async def collect_block(self, block_number: int) -> dict:
        resp = await self._get({
            "module": "proxy",
            "action": "eth_getBlockByNumber",
            "tag": hex(block_number),
            "boolean": "true",
        })
        return resp.get("result", {})

    async def collect_address_txs(self, address: str, start_block: int = 0) -> list[dict]:
        resp = await self._get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": str(start_block),
            "endblock": "99999999",
            "page": "1",
            "offset": "100",
            "sort": "desc",
        })
        results = resp.get("result", [])
        return results if isinstance(results, list) else []

    async def collect_address_balance(self, address: str) -> dict:
        resp = await self._get({
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
        })
        return {"address": address, "balance": resp.get("result", "0")}
