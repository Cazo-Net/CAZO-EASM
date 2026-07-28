from __future__ import annotations

import logging
from typing import Any

import httpx

from app.blockchain.domain.contracts.chain_connector import Collector
from app.blockchain.domain.value_objects.chain import Chain

logger = logging.getLogger(__name__)

_TRONGRID_BASE = "https://api.trongrid.io"


class TronCollector(Collector):
    chain = Chain.TRON

    def __init__(self, api_key: str = "") -> None:
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["TRON-PRO-API-KEY"] = api_key

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{_TRONGRID_BASE}{path}", params=params or {}, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, body: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{_TRONGRID_BASE}{path}", json=body or {}, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def collect_block(self, block_number: int) -> dict:
        return await self._post("/wallet/getblockbynum", {"num": block_number})

    async def collect_address_txs(self, address: str, start_block: int = 0) -> list[dict]:
        data = await self._get(f"/v1/accounts/{address}/transactions", {
            "limit": 200, "order_by": "block_timestamp,desc",
        })
        return data.get("data", [])

    async def collect_address_balance(self, address: str) -> dict:
        data = await self._get(f"/v1/accounts/{address}")
        account = data.get("data", [{}])[0]
        return {"address": address, "balance": str(account.get("balance", 0))}
