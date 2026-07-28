"""Reusable base class for all Etherscan-compatible chains.

Polygon, BSC, Arbitrum, Optimism, Base, and Avalanche all expose an
Etherscan-compatible API with the same request/response format but
different base URLs and chain IDs.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas.blockchain import (
    Chain,
    ContractDetail,
    ContractType,
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
from app.services.blockchain.providers.base import ChainProvider

logger = logging.getLogger(__name__)


class EthEtherscanBaseProvider(ChainProvider):
    """Base provider for chains that expose an Etherscan-compatible API.

    Subclasses must set ``chain`` and call ``super().__init__`` with the
    chain-specific configuration.  No mock mode — every call hits the real
    public API.
    """

    chain: Chain

    def __init__(
        self,
        *,
        api_base_url: str,
        chain_id: int,
        native_symbol: str,
        native_decimals: int = 18,
        api_key: str = "",
    ) -> None:
        self._api_base = api_base_url
        self._chain_id = chain_id
        self._native_symbol = native_symbol
        self._native_decimals = native_decimals
        self._api_key = api_key
        self._last_request = 0.0

    def is_available(self) -> bool:
        return True

    # ── Internal helpers ─────────────────────────────────────────────────

    async def _throttle(self) -> None:
        """Rate-limit requests to ~4 per second (Etherscan free tier)."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.25:
            await asyncio.sleep(0.25 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a GET request against the Etherscan-compatible API.

        Automatically injects ``chainid`` and ``apikey`` (if set).
        Retries once on transient errors.
        """
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
        raise last_error  # type: ignore[misc]

    def _wei_to_native(self, wei: int) -> str:
        """Convert a wei integer to the chain's native currency string."""
        return str(wei / 10 ** self._native_decimals)

    # ── Wallet ───────────────────────────────────────────────────────────

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        balance_resp = await self._get({
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
        })
        balance_wei = int(balance_resp.get("result", "0"))
        balance_native = self._wei_to_native(balance_wei)

        tx_resp = await self._get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "10",
            "sort": "desc",
        })
        txs = tx_resp.get("result", []) if isinstance(tx_resp.get("result"), list) else []

        code_resp = await self._get({
            "module": "proxy",
            "action": "eth_getCode",
            "address": address,
            "tag": "latest",
        })
        code = code_resp.get("result", "0x")
        wallet_type = WalletType.CONTRACT if code and code != "0x" else WalletType.EOA

        first_seen = None
        last_active = None
        if txs:
            timestamps = [int(t.get("timeStamp", 0)) for t in txs if t.get("timeStamp")]
            if timestamps:
                first_seen = datetime.fromtimestamp(min(timestamps), tz=timezone.utc)
                last_active = datetime.fromtimestamp(max(timestamps), tz=timezone.utc)

        return WalletSummary(
            address=address,
            chain=self.chain,
            wallet_type=wallet_type,
            balance=balance_native,
            tx_count=len(txs),
            first_seen=first_seen,
            last_active=last_active,
        )

    # ── Transactions ─────────────────────────────────────────────────────

    async def get_transactions(
        self, address: str, page: int = 1, page_size: int = 20
    ) -> list[TransactionSummary]:
        resp = await self._get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": str(page),
            "offset": str(page_size),
            "sort": "desc",
        })
        results = resp.get("result", [])
        if not isinstance(results, list):
            return []

        summaries: list[TransactionSummary] = []
        for tx in results:
            status = TransactionStatus.SUCCESS if tx.get("isError") == "0" else TransactionStatus.FAILED
            value_wei = int(tx.get("value", "0"))
            summaries.append(TransactionSummary(
                hash=tx.get("hash", ""),
                chain=self.chain,
                status=status,
                block_number=int(tx.get("blockNumber", 0)),
                timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc),
                from_address=tx.get("from", ""),
                to_address=tx.get("to", ""),
                value=self._wei_to_native(value_wei),
                fee=str(
                    int(tx.get("gasUsed", 0)) * int(tx.get("gasPrice", 0))
                    / 10 ** self._native_decimals
                ),
                method=tx.get("functionName", "").split("(")[0] if tx.get("functionName") else None,
            ))
        return summaries

    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        tx_resp = await self._get({
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash,
        })
        receipt_resp = await self._get({
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
        })
        tx = tx_resp.get("result", {})
        receipt = receipt_resp.get("result", {})

        status = TransactionStatus.SUCCESS if receipt.get("status") == "0x1" else TransactionStatus.FAILED
        value_wei = int(tx.get("value", "0x0"), 16)
        gas_used = int(receipt.get("gasUsed", "0x0"), 16)
        gas_price = int(tx.get("gasPrice", "0x0"), 16)

        logs: list[dict[str, Any]] = []
        for log in receipt.get("logs", []):
            logs.append({
                "address": log.get("address", ""),
                "topics": log.get("topics", []),
                "data": log.get("data", ""),
                "block_number": int(log.get("blockNumber", "0x0"), 16),
            })

        timestamp_raw = tx.get("timeStamp")
        if timestamp_raw is not None:
            ts_val = int(timestamp_raw, 16) if isinstance(timestamp_raw, str) and timestamp_raw.startswith("0x") else int(timestamp_raw)
        else:
            ts_val = 0

        return TransactionDetail(
            hash=tx_hash,
            chain=self.chain,
            status=status,
            block_number=int(receipt.get("blockNumber", "0x0"), 16),
            timestamp=datetime.fromtimestamp(ts_val, tz=timezone.utc),
            from_address=tx.get("from", ""),
            to_address=tx.get("to", ""),
            value=self._wei_to_native(value_wei),
            fee=str(gas_used * gas_price / 10 ** self._native_decimals),
            gas_price=str(gas_price),
            gas_used=gas_used,
            nonce=int(tx.get("nonce", "0x0"), 16),
            input_data=tx.get("input", "0x"),
            logs=logs,
        )

    # ── Tokens ───────────────────────────────────────────────────────────

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        resp = await self._get({
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": "1",
            "offset": "100",
            "sort": "desc",
        })
        results = resp.get("result", [])
        if not isinstance(results, list):
            return []

        seen: dict[str, dict[str, Any]] = {}
        for tx in results:
            key = tx.get("contractAddress", "")
            if not key or key in seen:
                continue
            seen[key] = {
                "contract_address": key,
                "symbol": tx.get("tokenSymbol", ""),
                "name": tx.get("tokenName", ""),
                "decimals": int(tx.get("tokenDecimal", "18")),
            }

        return [
            TokenBalance(
                contract_address=v["contract_address"],
                symbol=v["symbol"],
                name=v["name"],
                balance="0",
                decimals=v["decimals"],
            )
            for v in seen.values()
        ]

    # ── Contract ─────────────────────────────────────────────────────────

    async def get_contract_detail(self, address: str) -> ContractDetail | None:
        code_resp = await self._get({
            "module": "proxy",
            "action": "eth_getCode",
            "address": address,
            "tag": "latest",
        })
        code = code_resp.get("result", "0x")
        if not code or code == "0x":
            return None

        abi_resp = await self._get({
            "module": "contract",
            "action": "getabi",
            "address": address,
        })
        abi_str = abi_resp.get("result", "")
        abi = None
        contract_type = ContractType.UNKNOWN
        name = ""
        symbol = ""

        if abi_str and abi_str != "Contract source code not verified":
            try:
                abi = json.loads(abi_str)
                methods = {item.get("name", "") for item in abi if item.get("type") == "function"}

                if {"totalSupply", "balanceOf", "transfer"}.issubset(methods):
                    contract_type = ContractType.ERC20
                elif "tokenOfOwnerByIndex" in methods:
                    contract_type = ContractType.ERC721

                for item in abi:
                    if item.get("type") == "function":
                        if item.get("name") == "name" and len(item.get("inputs", [])) == 0:
                            name = item.get("name", "")
                        if item.get("name") == "symbol" and len(item.get("inputs", [])) == 0:
                            symbol = item.get("name", "")
            except (json.JSONDecodeError, TypeError):
                pass

        creator_resp = await self._get({
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": address,
        })
        creator_data = creator_resp.get("result", [])
        creator = creator_data[0].get("contractCreator", "") if isinstance(creator_data, list) and creator_data else None
        creation_tx = creator_data[0].get("txHash", "") if isinstance(creator_data, list) and creator_data else None

        return ContractDetail(
            address=address,
            chain=self.chain,
            creator=creator,
            creation_tx=creation_tx,
            verified=abi is not None,
            abi=abi,
            contract_type=contract_type,
            name=name,
            symbol=symbol,
        )

    # ── Risk ─────────────────────────────────────────────────────────────

    async def get_risk_score(self, address: str) -> RiskScore:
        score = 10
        factors: list[RiskFactor] = []

        contract_resp = await self._get({
            "module": "proxy",
            "action": "eth_getCode",
            "address": address,
            "tag": "latest",
        })
        code = contract_resp.get("result", "0x")
        is_contract = bool(code and code != "0x")

        if is_contract:
            abi_resp = await self._get({
                "module": "contract",
                "action": "getabi",
                "address": address,
            })
            verified = abi_resp.get("result", "") != "Contract source code not verified"
            if verified:
                score += 10
                factors.append(RiskFactor(
                    category="contract",
                    label="Verified contract",
                    weight=1.0,
                    contribution=10,
                    evidence=[Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=95)],
                ))
            else:
                score += 30
                factors.append(RiskFactor(
                    category="contract",
                    label="Unverified contract",
                    weight=2.0,
                    contribution=30,
                    evidence=[Evidence(source="etherscan", type=EvidenceType.OSINT, confidence=80, reason="Contract source code not verified")],
                ))

        tx_resp = await self._get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "1",
            "sort": "desc",
        })
        txs = tx_resp.get("result", [])
        total_count = len(txs) if isinstance(txs, list) else 0

        if total_count > 10000:
            score += 10
            factors.append(RiskFactor(
                category="activity",
                label="Very high transaction count",
                weight=1.5,
                contribution=10,
            ))

        balance_resp = await self._get({
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
        })
        balance_wei = int(balance_resp.get("result", "0"))
        if balance_wei > 100 * 10 ** self._native_decimals:
            score += 5

        if total_count == 0:
            score += 10
            factors.append(RiskFactor(
                category="activity",
                label="No transactions found",
                weight=1.0,
                contribution=10,
            ))

        score = min(score, 100)
        band = (
            RiskBand.CRITICAL if score >= 80 else
            RiskBand.HIGH if score >= 60 else
            RiskBand.MEDIUM if score >= 40 else
            RiskBand.LOW if score >= 20 else
            RiskBand.INFO
        )

        return RiskScore(
            address=address,
            chain=self.chain,
            score=score,
            band=band,
            factors=factors,
        )

    # ── Graph ────────────────────────────────────────────────────────────

    async def get_graph_data(
        self, address: str, depth: int = 2, limit: int = 50
    ) -> GraphData:
        tx_resp = await self._get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": str(limit),
            "sort": "desc",
        })
        txs = tx_resp.get("result", [])
        if not isinstance(txs, list):
            return GraphData()

        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []
        total_volume = 0.0

        nodes[address] = GraphNode(id=address, chain=self.chain, label="center")

        for tx in txs:
            from_addr = tx.get("from", "")
            to_addr = tx.get("to", "")
            value_native = int(tx.get("value", "0")) / 10 ** self._native_decimals
            total_volume += value_native

            for addr in (from_addr, to_addr):
                if addr and addr not in nodes:
                    nodes[addr] = GraphNode(id=addr, chain=self.chain)

            if from_addr and to_addr:
                edges.append(GraphEdge(
                    source=from_addr,
                    target=to_addr,
                    value=str(value_native),
                    tx_count=1,
                    timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc),
                ))

        return GraphData(
            nodes=list(nodes.values()),
            edges=edges,
            total_volume=str(total_volume),
        )
