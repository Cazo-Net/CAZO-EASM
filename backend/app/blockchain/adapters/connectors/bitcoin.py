from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from app.blockchain.domain.contracts.chain_connector import ChainConnector
from app.blockchain.domain.entities.address import Address, WalletType
from app.blockchain.domain.entities.transaction import Transaction, TransactionStatus
from app.blockchain.domain.entities.token import TokenBalance, Contract, ContractType
from app.blockchain.domain.entities.block import Block
from app.blockchain.domain.value_objects.chain import Chain
from app.blockchain.domain.value_objects.amount import Amount, AmountUnit

logger = logging.getLogger(__name__)

BLOCKSTREAM_BASE = "https://blockstream.info/api"


class BitcoinConnector(ChainConnector):
    chain_id = "bitcoin"

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

    async def validate_address(self, address: str) -> bool:
        if not address or len(address) < 25 or len(address) > 62:
            return False
        prefixes = ("1", "3", "bc1", "bc1q", "bc1p")
        return address.startswith(prefixes)

    async def get_wallet(self, address: str) -> Address:
        try:
            addr_info = await self._get(f"/address/{address}")
        except httpx.HTTPStatusError:
            return Address(hash=address, chain=Chain.BITCOIN, wallet_type=WalletType.UNKNOWN)

        stats = addr_info.get("chain_stats", {})
        funded = stats.get("funded_txo_sum", 0)
        spent = stats.get("spent_txo_sum", 0)
        balance_sat = funded - spent
        tx_count = stats.get("tx_count", 0)

        first_seen = None
        last_active = None
        try:
            txs = await self._get(f"/address/{address}/txs")
            if isinstance(txs, list) and txs:
                confirmed = [tx for tx in txs if tx.get("status", {}).get("confirmed")]
                if confirmed:
                    timestamps = [tx["status"]["block_time"] for tx in confirmed if tx.get("status", {}).get("block_time")]
                    if timestamps:
                        first_seen = datetime.fromtimestamp(min(timestamps), tz=timezone.utc)
                        last_active = datetime.fromtimestamp(max(timestamps), tz=timezone.utc)
        except Exception:
            pass

        return Address(
            hash=address,
            chain=Chain.BITCOIN,
            wallet_type=WalletType.EOA,
            first_seen_block=first_seen,
            last_active_at=last_active,
            tx_count=tx_count,
            balance=Amount(balance_sat, AmountUnit.SATOSHI),
        )

    async def get_transaction(self, tx_hash: str) -> Transaction:
        tx = await self._get(f"/tx/{tx_hash}")
        status = TransactionStatus.SUCCESS if tx.get("status", {}).get("confirmed") else TransactionStatus.PENDING
        block_height = tx.get("status", {}).get("block_height")
        fee = tx.get("fee", 0)

        from_addrs = []
        for vin in tx.get("vin", []):
            prevout = vin.get("prevout", {})
            addr = prevout.get("scriptpubkey_address", "")
            if addr:
                from_addrs.append(addr)

        to_addrs = []
        total_out = 0
        for vout in tx.get("vout", []):
            addr = vout.get("scriptpubkey_address", "")
            if addr:
                to_addrs.append(addr)
            total_out += vout.get("value", 0)

        return Transaction(
            hash=tx_hash,
            chain=Chain.BITCOIN,
            status=status,
            block_number=block_height,
            timestamp=datetime.fromtimestamp(tx.get("status", {}).get("block_time", 0), tz=timezone.utc)
            if tx.get("status", {}).get("block_time") else None,
            from_address=", ".join(sorted(set(from_addrs))),
            to_address=", ".join(sorted(set(to_addrs))),
            value=Amount(total_out, AmountUnit.SATOSHI),
            fee=Amount(fee, AmountUnit.SATOSHI),
        )

    async def get_contract(self, address: str) -> Contract | None:
        return None

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        return []

    async def get_current_block(self) -> int:
        height = await self._get("/blocks/tip/height")
        return int(height)

    async def get_block(self, number: int) -> Block:
        block_hash = await self._get(f"/block-height/{number}")
        data = await self._get(f"/block/{block_hash}")
        return Block(
            number=number,
            chain=Chain.BITCOIN,
            hash=data.get("id", ""),
            parent_hash=data.get("previousblockhash"),
            timestamp=datetime.fromtimestamp(data.get("timestamp", 0), tz=timezone.utc),
            tx_count=len(data.get("tx", [])),
            size=data.get("size"),
            difficulty=data.get("difficulty"),
        )

    async def stream_new_activity(self, address: str) -> AsyncIterator[Transaction]:
        last_txid: str | None = None
        while True:
            try:
                txs = await self._get(f"/address/{address}/txs")
                if isinstance(txs, list) and txs:
                    latest = txs[0].get("txid", "")
                    if last_txid is not None and latest != last_txid:
                        for tx_data in txs[:5]:
                            yield await self.get_transaction(tx_data.get("txid", ""))
                    last_txid = latest
            except Exception as e:
                logger.debug("BTC stream poll error: %s", e)
            await asyncio.sleep(30)
