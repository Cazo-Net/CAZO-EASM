"""Solana provider using Solana RPC and Solscan API.

Uses the public Solana JSON-RPC endpoint (no key needed). Raises
DataSourceUnavailable when it does not answer; never invents data.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas.blockchain import (
    Chain,
    ContractDetail,
    ContractType,
    EntityAttribution,
    EntityCategory,
    Evidence,
    EvidenceType,
    GraphData,
    GraphEdge,
    GraphNode,
    RiskBand,
    RiskFactor,
    RiskScore,
    TokenBalance,
    TransactionDetail,
    TransactionStatus,
    TransactionSummary,
    WalletSummary,
    WalletType,
)
from app.services.blockchain.providers.base import ChainProvider, DataSourceUnavailable

logger = logging.getLogger(__name__)

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
SOLSCAN_API = "https://api.solscan.io"


class SolanaProvider(ChainProvider):
    chain = Chain.SOLANA

    def __init__(self) -> None:
        self._last_request = 0.0

    def is_available(self) -> bool:
        return True

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.2:
            await asyncio.sleep(0.2 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _rpc(self, method: str, params: list[Any] | None = None) -> dict[str, Any]:
        await self._throttle()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(SOLANA_RPC, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"Solana RPC error: {data['error']}")
            return data.get("result", {})

    async def _solscan_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await self._throttle()
        url = f"{SOLSCAN_API}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success") is False:
                raise RuntimeError(f"Solscan error: {data.get('message', 'Unknown')}")
            return data.get("data", {})

    # ── Wallet ───────────────────────────────────────────────────────────

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        try:
            balance_result = await self._rpc("getBalance", [address])
            lamports = balance_result.get("value", 0)
            balance_sol = str(lamports / 10**9)

            signatures_result = await self._rpc("getSignaturesForAddress", [address, {"limit": 1}])
            signatures = signatures_result.get("value", [])

            try:
                account_info = await self._rpc("getAccountInfo", [address, {"encoding": "jsonParsed"}])
                owner = account_info.get("value", {}).get("owner", "")
                wallet_type = WalletType.CONTRACT if owner != "11111111111111111111111111111111" else WalletType.EOA
            except Exception as e:
                logger.debug("Failed to get account info for %s: %s", address, e)
                wallet_type = WalletType.EOA

            # Only the newest signature is fetched, so "first seen" stays
            # unknown instead of being guessed.
            first_seen = None
            last_active = None
            if signatures and isinstance(signatures, list):
                last_sig = signatures[0]
                if last_sig and last_sig.get("blockTime"):
                    last_active = datetime.fromtimestamp(last_sig["blockTime"], tz=timezone.utc)

            try:
                token_accounts_result = await self._rpc("getTokenAccountsByOwner", [
                    address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"},
                ])
                token_count = len(token_accounts_result.get("value", []))
            except Exception as e:
                logger.debug("Failed to get token accounts for %s: %s", address, e)
                token_count = 0

            return WalletSummary(
                address=address,
                chain=Chain.SOLANA,
                wallet_type=wallet_type,
                balance=balance_sol,
                first_seen=first_seen,
                last_active=last_active,
                token_count=token_count,
            )
        except Exception as e:
            logger.warning("Solana RPC unavailable: %s", e)
            raise DataSourceUnavailable(self.chain, "upstream_error", "Solana RPC did not answer, so no live data is shown. Try again shortly.") from e

    # ── Transactions ─────────────────────────────────────────────────────

    async def get_transactions(
        self, address: str, page: int = 1, page_size: int = 20
    ) -> list[TransactionSummary]:
        """Recent transaction signatures from the public Solana RPC.

        Uses ``getSignaturesForAddress`` (no key needed). Signatures carry
        the slot, time and success flag; amounts are not part of that call,
        so ``value`` is left empty rather than guessed. Pages past the first
        walk backwards with the ``before`` cursor.
        """
        try:
            before: str | None = None
            batch: list[dict[str, Any]] = []
            for _ in range(max(1, page)):
                opts: dict[str, Any] = {"limit": page_size}
                if before:
                    opts["before"] = before
                batch = await self._rpc("getSignaturesForAddress", [address, opts]) or []
                if not isinstance(batch, list) or not batch:
                    return []
                before = batch[-1].get("signature")
        except Exception as e:
            logger.warning("Solana RPC unavailable: %s", e)
            raise DataSourceUnavailable(self.chain, "upstream_error", "Solana RPC did not answer, so no live data is shown. Try again shortly.") from e

        summaries = []
        for sig in batch:
            summaries.append(TransactionSummary(
                hash=sig.get("signature", ""),
                chain=Chain.SOLANA,
                status=TransactionStatus.FAILED if sig.get("err") else TransactionStatus.SUCCESS,
                block_number=sig.get("slot"),
                timestamp=(datetime.fromtimestamp(sig["blockTime"], tz=timezone.utc) if sig.get("blockTime") else None),
                value="",
            ))
        return summaries

    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        result = await self._rpc("getTransaction", [tx_hash, {"encoding": "jsonParsed"}])
        if not result:
            raise ValueError(f"Transaction not found: {tx_hash}")

        meta = result.get("meta", {})
        status = TransactionStatus.SUCCESS if meta.get("err") is None else TransactionStatus.FAILED
        block_time = result.get("blockTime")
        timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc) if block_time else None

        fee_lamports = meta.get("fee", 0)
        fee_sol = str(fee_lamports / 10**9)

        message = result.get("transaction", {}).get("message", {})
        account_keys = message.get("accountKeys", [])
        from_addr = account_keys[0] if account_keys else ""
        to_addr = account_keys[1] if len(account_keys) > 1 else ""

        pre_balances = meta.get("preBalances", [])
        post_balances = meta.get("postBalances", [])
        value_lamports = 0
        if pre_balances and post_balances and len(pre_balances) > 1:
            value_lamports = post_balances[1] - pre_balances[1]
        value_sol = str(value_lamports / 10**9)

        inner_instructions = meta.get("innerInstructions", [])
        logs = []
        for log_msg in meta.get("logMessages", []):
            logs.append({"message": log_msg})

        return TransactionDetail(
            hash=tx_hash,
            chain=Chain.SOLANA,
            status=status,
            block_number=result.get("slot"),
            timestamp=timestamp,
            from_address=from_addr,
            to_address=to_addr,
            value=value_sol,
            fee=fee_sol,
            gas_price=None,
            gas_used=meta.get("computeUnitsConsumed"),
            nonce=None,
            input_data="",
            logs=logs,
        )

    # ── Tokens ───────────────────────────────────────────────────────────

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        result = await self._rpc("getTokenAccountsByOwner", [
            address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"},
        ])
        accounts = result.get("value", [])

        balances = []
        for account in accounts:
            info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            token_amount = info.get("tokenAmount", {})
            mint = info.get("mint", "")
            amount = token_amount.get("uiAmountString", "0")
            decimals = token_amount.get("decimals", 0)

            balances.append(TokenBalance(
                contract_address=mint,
                symbol="",
                name="",
                balance=amount,
                decimals=decimals,
            ))
        return balances

    # ── Contract ─────────────────────────────────────────────────────────

    async def get_contract_detail(self, address: str) -> ContractDetail | None:
        try:
            account_info = await self._rpc("getAccountInfo", [address, {"encoding": "jsonParsed"}])
        except Exception as e:
            logger.debug("Failed to get account info for contract %s: %s", address, e)
            return None

        value = account_info.get("value")
        if not value:
            return None

        owner = value.get("owner", "")
        executable = value.get("executable", False)
        if not executable:
            return None

        return ContractDetail(
            address=address,
            chain=Chain.SOLANA,
            creator=None,
            creation_tx=None,
            verified=False,
            contract_type=ContractType.UNKNOWN,
            name=owner,
        )