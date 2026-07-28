from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from app.blockchain.domain.contracts.chain_connector import ChainConnector
from app.blockchain.domain.entities.address import Address, WalletType
from app.blockchain.domain.entities.transaction import Transaction, TransactionStatus
from app.blockchain.domain.entities.token import TokenBalance, Contract
from app.blockchain.domain.entities.block import Block
from app.blockchain.domain.value_objects.chain import Chain
from app.blockchain.domain.value_objects.amount import Amount, AmountUnit

logger = logging.getLogger(__name__)

_TRONGRID_BASE = "https://api.trongrid.io"


class TronConnector(ChainConnector):
    chain_id = "tron"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["TRON-PRO-API-KEY"] = api_key

    async def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{_TRONGRID_BASE}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params or {}, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, body: dict | None = None) -> dict:
        url = f"{_TRONGRID_BASE}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body or {}, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def validate_address(self, address: str) -> bool:
        return len(address) == 34 and address.startswith("T")

    async def get_wallet(self, address: str) -> Address:
        data = await self._get(f"/v1/accounts/{address}")
        account = data.get("data", [{}])[0]
        balance_sun = account.get("balance", 0)
        tx_count = account.get("create_time", 0)
        tokens = account.get("trc20", [])
        token_count = len(tokens) if tokens else 0

        return Address(
            hash=address,
            chain=Chain.TRON,
            wallet_type=WalletType.CONTRACT if account.get("type") == "Contract" else WalletType.EOA,
            balance=Amount(balance_sun, AmountUnit.SUN),
            tx_count=tx_count,
            token_count=token_count,
        )

    async def get_transaction(self, tx_hash: str) -> Transaction:
        data = await self._post("/wallet/gettransactionbyid", {"value": tx_hash})
        raw = data.get("raw_data", {})
        contract = raw.get("contract", [{}])[0]
        value = contract.get("value", {})

        status = TransactionStatus.SUCCESS
        ret = data.get("ret", [{}])
        if ret and ret[0].get("contractRet") != "SUCCESS":
            status = TransactionStatus.FAILED

        return Transaction(
            hash=tx_hash,
            chain=Chain.TRON,
            status=status,
            timestamp=datetime.fromtimestamp(raw.get("timestamp", 0) / 1000, tz=timezone.utc)
            if raw.get("timestamp") else None,
            from_address=value.get("owner_address", ""),
            to_address=value.get("to_address", ""),
            value=Amount(int(value.get("amount", 0)), AmountUnit.SUN),
            block_number=data.get("block_number"),
        )

    async def get_contract(self, address: str) -> Contract | None:
        data = await self._get(f"/v1/accounts/{address}")
        account = data.get("data", [{}])
        if not account or account[0].get("type") != "Contract":
            return None
        return Contract(
            address=address,
            chain=Chain.TRON,
            name=account[0].get("name", ""),
            verified=False,
        )

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        data = await self._get(f"/v1/accounts/{address}/tokens")
        tokens = data.get("data", [])
        return [
            TokenBalance(
                contract_address=t.get("tokenId", ""),
                chain=Chain.TRON,
                symbol=t.get("tokenAbbr", ""),
                name=t.get("tokenName", ""),
                balance=Amount(int(t.get("balance", "0")), AmountUnit.NATIVE),
                decimals=6,
            )
            for t in tokens
        ]

    async def get_current_block(self) -> int:
        data = await self._post("/wallet/getnowblock")
        return data.get("block_header", {}).get("raw_data", {}).get("number", 0)

    async def get_block(self, number: int) -> Block:
        data = await self._post("/wallet/getblockbynum", {"num": number})
        header = data.get("block_header", {}).get("raw_data", {})
        return Block(
            number=number,
            chain=Chain.TRON,
            hash=data.get("blockID", ""),
            parent_hash=header.get("parentHash"),
            timestamp=datetime.fromtimestamp(header.get("timestamp", 0) / 1000, tz=timezone.utc)
            if header.get("timestamp") else None,
            tx_count=len(data.get("transactions", [])),
        )

    async def stream_new_activity(self, address: str) -> AsyncIterator[Transaction]:
        last_txid: str | None = None
        while True:
            try:
                data = await self._get(f"/v1/accounts/{address}/transactions",
                                       {"limit": 5, "order_by": "block_timestamp,desc"})
                txs = data.get("data", [])
                if txs:
                    latest = txs[0].get("txID", "")
                    if last_txid is not None and latest != last_txid:
                        for tx_data in txs[:5]:
                            yield await self.get_transaction(tx_data.get("txID", ""))
                    last_txid = latest
            except Exception as e:
                logger.debug("TRON stream poll error: %s", e)
            await asyncio.sleep(15)
