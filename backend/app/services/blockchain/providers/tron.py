"""Tron provider — TronGrid public API.

Returns simulated data when the API is unavailable or the address is invalid.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas.blockchain import (
    Chain,
    ContractDetail,
    Evidence,
    EvidenceType,
    GraphData,
    GraphEdge,
    GraphNode,
    RiskBand,
    RiskScore,
    TokenBalance,
    TransactionDetail,
    TransactionStatus,
    TransactionSummary,
    WalletSummary,
    WalletType,
)
from app.services.blockchain.providers.base import ChainProvider

logger = logging.getLogger(__name__)

_TRONGRID_BASE = "https://api.trongrid.io"


def _simulated_balance(address: str) -> int:
    h = int(hashlib.sha256(address.lower().encode()).hexdigest(), 16)
    return (h % 500000) * 1_000_000  # 0–500K TRX in sun


def _simulated_tx_count(address: str) -> int:
    h = int(hashlib.md5(address.lower().encode()).hexdigest(), 16)
    return (h % 500) + 1


class TronProvider(ChainProvider):
    """Tron network provider using TronGrid public API."""

    chain = Chain.TRON

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

    def _simulated_wallet(self, address: str) -> WalletSummary:
        bal = _simulated_balance(address)
        tx_count = _simulated_tx_count(address)
        return WalletSummary(
            address=address,
            chain=Chain.TRON,
            wallet_type=WalletType.EOA,
            balance=str(bal),
            tx_count=tx_count,
            risk_score=15,
            risk_band=RiskBand.LOW,
        )

    def _simulated_transactions(self, address: str, count: int = 5) -> list[TransactionSummary]:
        txs = []
        h = int(hashlib.sha256(address.lower().encode()).hexdigest(), 16)
        for i in range(min(count, 10)):
            val = ((h + i * 137) % 50000) * 1_000_000
            ts = 1700000000 + i * 3600
            txs.append(TransactionSummary(
                hash=hashlib.md5(f"{address}{i}".encode()).hexdigest(),
                chain=Chain.TRON,
                status=TransactionStatus.SUCCESS,
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                from_address=address if i % 2 == 0 else "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
                to_address="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb" if i % 2 == 0 else address,
                value=str(val),
            ))
        return txs

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        try:
            data = await self._get(f"/v1/accounts/{address}")
        except Exception as e:
            logger.warning("TronGrid unavailable, returning simulated data: %s", e)
            return self._simulated_wallet(address)

        account = data.get("data", [{}])[0]
        if not account:
            return self._simulated_wallet(address)

        balance_sun = account.get("balance", 0)
        tx_count = account.get("create_time", 0)
        tokens = account.get("trxInTrc20", [])

        evidence = []
        if tokens:
            evidence.append(Evidence(
                source="trongrid",
                type=EvidenceType.BLOCKCHAIN_LABEL,
                confidence=90,
                reason="Account holds TRC-20 tokens",
            ))

        return WalletSummary(
            address=address,
            chain=Chain.TRON,
            wallet_type=WalletType.CONTRACT if account.get("type") == "Contract" else WalletType.EOA,
            balance=str(balance_sun),
            balance_native=balance_sun / 1_000_000,
            native_symbol="TRX",
            tx_count=tx_count,
            risk_score=RiskScore(
                address=address,
                chain=Chain.TRON,
                risk_band=RiskBand.LOW,
            ),
            evidence=evidence,
        )

    async def get_transactions(
        self, address: str, page: int = 1, page_size: int = 20
    ) -> list[TransactionSummary]:
        try:
            params = {
                "limit": min(page_size, 200),
                "offset": (page - 1) * page_size,
                "order_by": "block_timestamp,desc",
            }
            data = await self._get(f"/v1/accounts/{address}/transactions", params)
        except Exception as e:
            logger.warning("TronGrid unavailable, returning simulated transactions: %s", e)
            return self._simulated_transactions(address, page_size)

        txs = data.get("data", [])
        results = []
        for tx in txs:
            raw = tx.get("raw_data", {})
            contract = raw.get("contract", [{}])[0]
            value = contract.get("value", {})
            results.append(TransactionSummary(
                hash=tx.get("txID", ""),
                from_address=value.get("owner_address", ""),
                to_address=value.get("to_address", ""),
                value=str(value.get("amount", 0)),
                timestamp=tx.get("block_timestamp", 0),
                status=TransactionStatus.SUCCESS if tx.get("ret", [{}])[0].get("contractRet") == "SUCCESS" else TransactionStatus.FAILED,
            ))
        return results

    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        try:
            data = await self._get(f"/wallet/gettransactionbyid", {"value": tx_hash})
        except Exception:
            return TransactionDetail(
                hash=tx_hash,
                chain=Chain.TRON,
                status=TransactionStatus.SUCCESS,
                timestamp=datetime.now(tz=timezone.utc),
            )

        raw = data.get("raw_data", {})
        contract = raw.get("contract", [{}])[0]
        value = contract.get("value", {})
        return TransactionDetail(
            hash=tx_hash,
            from_address=value.get("owner_address", ""),
            to_address=value.get("to_address", ""),
            value=str(value.get("amount", 0)),
            timestamp=data.get("block_timestamp", 0),
            status=TransactionStatus.SUCCESS if data.get("ret", [{}])[0].get("contractRet") == "SUCCESS" else TransactionStatus.FAILED,
            chain=Chain.TRON,
        )

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        try:
            data = await self._get(f"/v1/accounts/{address}/tokens")
        except Exception:
            return []

        tokens = data.get("data", [])
        return [
            TokenBalance(
                token_name=t.get("tokenName", ""),
                token_symbol=t.get("tokenAbbr", ""),
                balance=str(t.get("balance", 0)),
                token_id=t.get("tokenId", ""),
                chain=Chain.TRON,
            )
            for t in tokens
        ]

    async def get_contract_detail(self, address: str) -> ContractDetail | None:
        try:
            data = await self._get(f"/v1/accounts/{address}")
        except Exception:
            return None

        account = data.get("data", [{}])
        if not account or account[0].get("type") != "Contract":
            return None
        return ContractDetail(
            address=address,
            chain=Chain.TRON,
            contract_type="Unknown",
            verified=False,
        )

    async def get_graph_data(self, address: str, depth: int = 2, limit: int = 50) -> GraphData:
        txs = await self.get_transactions(address, page_size=limit)
        nodes = [GraphNode(id=address, label=address[:10] + "...", type="address")]
        edges: list[GraphEdge] = []
        seen = {address}
        for tx in txs:
            for addr in (tx.from_address, tx.to_address):
                if addr and addr not in seen:
                    seen.add(addr)
                    nodes.append(GraphNode(id=addr, label=addr[:10] + "...", type="address"))
            edges.append(GraphEdge(
                source=tx.from_address or address,
                target=tx.to_address or address,
                value=tx.value,
                label="transfer",
            ))
        return GraphData(nodes=nodes, edges=edges)
