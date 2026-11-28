"""Ethereum provider using Etherscan public API.

Delegates to EthEtherscanBaseProvider for real data.
No mock mode — every call hits the real public API.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
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

ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"

# Fallback IP for DNS resolution issues
_ETHERSCAN_IPS = ["23.92.68.154", "217.79.240.58", "217.79.243.34"]


class EthereumProvider(ChainProvider):
    chain = Chain.ETHEREUM

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or settings.ETHERSCAN_API_KEY
        self._last_request = 0.0
        self._use_ip_fallback = False

    @property
    def _has_key(self) -> bool:
        return bool(self.api_key)

    def is_available(self) -> bool:
        return self._has_key

    def _not_configured(self) -> DataSourceUnavailable:
        return DataSourceUnavailable(
            self.chain,
            "not_configured",
            f"Live {self.chain.value} data needs an Etherscan API key. "
            "Set ETHERSCAN_API_KEY on the backend (one Etherscan V2 key covers Ethereum and most EVM chains).",
            setting="ETHERSCAN_API_KEY",
        )

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.25:
            await asyncio.sleep(0.25 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        await self._throttle()
        params.setdefault("chainid", "1")
        if self.api_key:
            params["apikey"] = self.api_key

        urls_to_try = [
            (ETHERSCAN_BASE, {}),
            (f"https://{_ETHERSCAN_IPS[0]}/v2/api", {"Host": "api.etherscan.io"}),
            (f"https://{_ETHERSCAN_IPS[1]}/v2/api", {"Host": "api.etherscan.io"}),
        ]

        last_error = None
        for url, extra_headers in urls_to_try:
            try:
                verify = not bool(extra_headers)
                async with httpx.AsyncClient(timeout=30, verify=verify) as client:
                    resp = await client.get(url, params=params, headers=extra_headers)
                    resp.raise_for_status()
                    if extra_headers:
                        self._use_ip_fallback = True
                    return resp.json()
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue
        raise last_error or httpx.ConnectError("All Etherscan endpoints failed")

    # ── Wallet ───────────────────────────────────────────────────────────

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        if not self._has_key:
            raise self._not_configured()

        balance_resp = await self._get({
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
        })
        balance_wei = int(balance_resp.get("result", "0"))
        balance_eth = str(balance_wei / 10**18)

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

        wallet_type = WalletType.EOA
        code_resp = await self._get({
            "module": "proxy",
            "action": "eth_getCode",
            "address": address,
            "tag": "latest",
        })
        code = code_resp.get("result", "0x")
        if code and code != "0x":
            wallet_type = WalletType.CONTRACT

        # Newest transaction gives "last active"; the oldest one (a second,
        # ascending query) gives "first seen". Both are real on-chain times.
        first_seen = None
        last_active = None
        if txs and txs[0].get("timeStamp"):
            last_active = datetime.fromtimestamp(int(txs[0]["timeStamp"]), tz=timezone.utc)
            oldest_resp = await self._get({
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": "0",
                "endblock": "99999999",
                "page": "1",
                "offset": "1",
                "sort": "asc",
            })
            oldest = oldest_resp.get("result")
            if isinstance(oldest, list) and oldest and oldest[0].get("timeStamp"):
                first_seen = datetime.fromtimestamp(int(oldest[0]["timeStamp"]), tz=timezone.utc)

        return WalletSummary(
            address=address,
            chain=Chain.ETHEREUM,
            wallet_type=wallet_type,
            balance=balance_eth,
            first_seen=first_seen,
            last_active=last_active,
        )

    # ── Transactions ─────────────────────────────────────────────────────

    async def get_transactions(
        self, address: str, page: int = 1, page_size: int = 20
    ) -> list[TransactionSummary]:
        if not self._has_key:
            raise self._not_configured()

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
        summaries = []
        for tx in results:
            status = TransactionStatus.SUCCESS if tx.get("isError") == "0" else TransactionStatus.FAILED
            value_wei = int(tx.get("value", "0"))
            summaries.append(TransactionSummary(
                hash=tx.get("hash", ""),
                chain=Chain.ETHEREUM,
                status=status,
                block_number=int(tx.get("blockNumber", 0)),
                timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc),
                from_address=tx.get("from", ""),
                to_address=tx.get("to", ""),
                value=str(value_wei / 10**18),
                fee=str(int(tx.get("gasUsed", 0)) * int(tx.get("gasPrice", 0)) / 10**18),
                method=tx.get("functionName", "").split("(")[0] if tx.get("functionName") else None,
            ))
        return summaries

    async def get_internal_transactions(self, address: str, tx_hash: str | None = None) -> list[dict[str, Any]]:
        """Fetch internal transactions for an address or a specific tx."""
        if not self._has_key:
            raise self._not_configured()

        params: dict[str, Any] = {
            "module": "account",
            "action": "txlistinternal",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "100",
            "sort": "desc",
        }
        if tx_hash:
            params["txhash"] = tx_hash
            del params["address"]
        resp = await self._get(params)
        results = resp.get("result", [])
        return results if isinstance(results, list) else []

    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        if not self._has_key:
            raise self._not_configured()

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

        logs = []
        for log in receipt.get("logs", []):
            logs.append({
                "address": log.get("address", ""),
                "topics": log.get("topics", []),
                "data": log.get("data", ""),
                "block_number": int(log.get("blockNumber", "0x0"), 16),
            })

        internal_txs = await self.get_internal_transactions("", tx_hash=tx_hash)

        return TransactionDetail(
            hash=tx_hash,
            chain=Chain.ETHEREUM,
            status=status,
            block_number=int(receipt.get("blockNumber", "0x0"), 16),
            timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", "0x0"), 16) if tx.get("timeStamp") else 0, tz=timezone.utc),
            from_address=tx.get("from", ""),
            to_address=tx.get("to", ""),
            value=str(value_wei / 10**18),
            fee=str(gas_used * gas_price / 10**18),
            gas_price=str(gas_price),
            gas_used=gas_used,
            nonce=int(tx.get("nonce", "0x0"), 16),
            input_data=tx.get("input", "0x"),
            logs=logs,
        )

    # ── Tokens ───────────────────────────────────────────────────────────

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        if not self._has_key:
            raise self._not_configured()

        resp = await self._get({
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": "1",
            "offset": "200",
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
                "last_block": int(tx.get("blockNumber", "0")),
            }

        balances = []
        for token_info in seen.values():
            balance = await self._get_token_balance(address, token_info["contract_address"], token_info["decimals"])
            balances.append(TokenBalance(
                contract_address=token_info["contract_address"],
                symbol=token_info["symbol"],
                name=token_info["name"],
                balance=balance,
                decimals=token_info["decimals"],
            ))
        return balances

    async def _get_token_balance(self, owner: str, contract: str, decimals: int) -> str:
        """Call balanceOf(address) on an ERC-20 contract via eth_call."""
        try:
            # balanceOf(address) selector = 0x70a08231
            padded_owner = owner.lower().replace("0x", "").zfill(64)
            data = f"0x70a08231{padded_owner}"
            resp = await self._get({
                "module": "proxy",
                "action": "eth_call",
                "to": contract,
                "data": data,
                "tag": "latest",
            })
            result = resp.get("result", "0x0")
            raw = int(result, 16) if result and result != "0x" else 0
            return str(raw / 10**decimals)
        except Exception as e:
            logger.debug("balanceOf failed for %s on %s: %s", owner, contract, e)
            return "0"

    # ── Contract ─────────────────────────────────────────────────────────

    async def get_contract_detail(self, address: str) -> ContractDetail | None:
        if not self._has_key:
            raise self._not_configured()

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
                import json
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
                logger.debug("ABI parse error for %s", address)

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
            chain=Chain.ETHEREUM,
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
        if not self._has_key:
            raise self._not_configured()

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
                    category="contract", label="Verified contract", weight=1.0, contribution=10,
                    evidence=[Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=95)],
                ))
            else:
                score += 30
                factors.append(RiskFactor(
                    category="contract", label="Unverified contract", weight=2.0, contribution=30,
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
                category="activity", label="Very high transaction count", weight=1.5, contribution=10,
            ))

        balance_resp = await self._get({
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
        })
        balance_wei = int(balance_resp.get("result", "0"))
        if balance_wei > 100 * 10**18:
            score += 5

        if total_count == 0:
            score += 10
            factors.append(RiskFactor(
                category="activity", label="No transactions found", weight=1.0, contribution=10,
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
            chain=Chain.ETHEREUM,
            score=score,
            band=band,
            factors=factors,
        )

    # ── Graph ────────────────────────────────────────────────────────────

    async def get_graph_data(
        self, address: str, depth: int = 2, limit: int = 50
    ) -> GraphData:
        if not self._has_key:
            raise self._not_configured()

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

        nodes[address] = GraphNode(
            id=address, chain=Chain.ETHEREUM, label="center"
        )

        for tx in txs:
            from_addr = tx.get("from", "")
            to_addr = tx.get("to", "")
            value_eth = int(tx.get("value", "0")) / 10**18
            total_volume += value_eth

            for addr in (from_addr, to_addr):
                if addr and addr not in nodes:
                    nodes[addr] = GraphNode(id=addr, chain=Chain.ETHEREUM)

            if from_addr and to_addr:
                edges.append(GraphEdge(
                    source=from_addr, target=to_addr,
                    value=str(value_eth),
                    tx_count=1,
                    timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0)), tz=timezone.utc),
                ))

        return GraphData(
            nodes=list(nodes.values()),
            edges=edges,
            total_volume=str(total_volume),
        )
