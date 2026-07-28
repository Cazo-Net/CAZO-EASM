"""Tron provider — TronGrid public API."""
from __future__ import annotations

import logging
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

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        data = await self._get(f"/v1/accounts/{address}")
        account = data.get("data", [{}])[0]
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
        params = {
            "limit": min(page_size, 200),
            "offset": (page - 1) * page_size,
            "order_by": "block_timestamp,desc",
        }
        data = await self._get(f"/v1/accounts/{address}/transactions", params)
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
        data = await self._get(f"/wallet/gettransactionbyid", {"value": tx_hash})
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
        data = await self._get(f"/v1/accounts/{address}/tokens")
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
        data = await self._get(f"/v1/accounts/{address}")
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
