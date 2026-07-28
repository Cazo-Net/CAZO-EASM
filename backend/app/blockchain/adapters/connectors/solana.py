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

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
SOLSCAN_API = "https://api.solscan.io"


class SolanaConnector(ChainConnector):
    chain_id = "solana"

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

    async def _solscan_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await self._throttle()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{SOLSCAN_API}{path}", params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success") is False:
                raise RuntimeError(f"Solscan error: {data.get('message', 'Unknown')}")
            return data.get("data", {})

    async def validate_address(self, address: str) -> bool:
        return len(address) == 44 and all(c in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz" for c in address)

    async def get_wallet(self, address: str) -> Address:
        balance_result = await self._rpc("getBalance", [address])
        lamports = balance_result.get("value", 0)

        sig_result = await self._rpc("getSignaturesForAddress", [address, {"limit": 1}])
        sigs = sig_result.get("value", [])
        tx_count = len(sigs) if isinstance(sigs, list) else 0

        try:
            account_info = await self._rpc("getAccountInfo", [address, {"encoding": "jsonParsed"}])
            owner = account_info.get("value", {}).get("owner", "")
            is_contract = owner != "11111111111111111111111111111111"
        except Exception:
            is_contract = False

        try:
            token_result = await self._rpc("getTokenAccountsByOwner", [
                address, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ])
            token_count = len(token_result.get("value", []))
        except Exception:
            token_count = 0

        first_seen = None
        last_active = None
        if isinstance(sigs, list) and sigs:
            first = sigs[-1]
            last = sigs[0]
            if first.get("blockTime"):
                first_seen = datetime.fromtimestamp(first["blockTime"], tz=timezone.utc)
            if last.get("blockTime"):
                last_active = datetime.fromtimestamp(last["blockTime"], tz=timezone.utc)

        return Address(
            hash=address,
            chain=Chain.SOLANA,
            wallet_type=WalletType.CONTRACT if is_contract else WalletType.EOA,
            first_seen_block=first_seen,
            last_active_at=last_active,
            tx_count=tx_count,
            balance=Amount(lamports, AmountUnit.LAMPORTS),
            token_count=token_count,
            is_contract=is_contract,
        )

    async def get_transaction(self, tx_hash: str) -> Transaction:
        result = await self._rpc("getTransaction", [tx_hash, {"encoding": "jsonParsed"}])
        if not result:
            return Transaction(hash=tx_hash, chain=Chain.SOLANA, status=TransactionStatus.PENDING)

        meta = result.get("meta", {})
        status = TransactionStatus.SUCCESS if meta.get("err") is None else TransactionStatus.FAILED
        block_time = result.get("blockTime")
        timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc) if block_time else None
        fee_lamports = meta.get("fee", 0)

        message = result.get("transaction", {}).get("message", {})
        account_keys = message.get("accountKeys", [])
        from_addr = account_keys[0] if account_keys else ""
        to_addr = account_keys[1] if len(account_keys) > 1 else ""

        pre = meta.get("preBalances", [])
        post = meta.get("postBalances", [])
        value = 0
        if pre and post and len(pre) > 1:
            value = post[1] - pre[1]

        logs = [{"message": msg} for msg in meta.get("logMessages", [])]

        return Transaction(
            hash=tx_hash,
            chain=Chain.SOLANA,
            status=status,
            block_number=result.get("slot"),
            timestamp=timestamp,
            from_address=from_addr,
            to_address=to_addr,
            value=Amount(value, AmountUnit.LAMPORTS),
            fee=Amount(fee_lamports, AmountUnit.LAMPORTS),
            gas_used=meta.get("computeUnitsConsumed"),
            logs=logs,
        )

    async def get_contract(self, address: str) -> Contract | None:
        try:
            info = await self._rpc("getAccountInfo", [address, {"encoding": "jsonParsed"}])
            value = info.get("value")
            if not value or not value.get("executable"):
                return None
            return Contract(
                address=address,
                chain=Chain.SOLANA,
                verified=False,
                name=value.get("owner", ""),
            )
        except Exception:
            return None

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        result = await self._rpc("getTokenAccountsByOwner", [
            address, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"},
        ])
        balances = []
        for account in result.get("value", []):
            info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            token_amount = info.get("tokenAmount", {})
            balances.append(TokenBalance(
                contract_address=info.get("mint", ""),
                chain=Chain.SOLANA,
                balance=Amount(int(token_amount.get("amount", "0")), AmountUnit.LAMPORTS),
                decimals=token_amount.get("decimals", 0),
            ))
        return balances

    async def get_current_block(self) -> int:
        result = await self._rpc("getSlot")
        return int(result)

    async def get_block(self, number: int) -> Block:
        result = await self._rpc("getBlock", [number, {"encoding": "jsonParsed"}])
        return Block(
            number=number,
            chain=Chain.SOLANA,
            hash=result.get("blockhash", ""),
            parent_hash=result.get("previousBlockhash"),
            timestamp=datetime.fromtimestamp(result.get("blockTime", 0), tz=timezone.utc)
            if result.get("blockTime") else None,
            tx_count=len(result.get("transactions", [])),
        )

    async def stream_new_activity(self, address: str) -> AsyncIterator[Transaction]:
        last_sig: str | None = None
        while True:
            try:
                sig_result = await self._rpc("getSignaturesForAddress", [address, {"limit": 5}])
                sigs = sig_result.get("value", [])
                if isinstance(sigs, list) and sigs:
                    latest = sigs[0].get("signature", "")
                    if last_sig is not None and latest != last_sig:
                        for sig_data in sigs:
                            sig = sig_data.get("signature", "")
                            if sig != last_sig:
                                yield await self.get_transaction(sig)
                    last_sig = latest
            except Exception as e:
                logger.debug("Solana stream poll error: %s", e)
            await asyncio.sleep(15)
