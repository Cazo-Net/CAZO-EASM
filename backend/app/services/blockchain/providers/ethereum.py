"""Ethereum provider using Etherscan public API."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
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
from app.services.blockchain.providers.base import ChainProvider

logger = logging.getLogger(__name__)

ETHERSCAN_BASE = "https://api.etherscan.io/v2/api"

# Fallback IP for DNS resolution issues
_ETHERSCAN_IPS = ["23.92.68.154", "217.79.240.58", "217.79.243.34"]


def _mock_wallet_summary(address: str) -> WalletSummary:
    """Generate deterministic mock data from address hash."""
    h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
    balance_eth = str(round(h % 1000 + random.uniform(0.1, 50.0), 4))
    tx_count = (h % 5000) + 10
    now = datetime.now(tz=timezone.utc)
    first_seen = datetime.fromtimestamp(now.timestamp() - (h % 31536000), tz=timezone.utc)
    last_active = datetime.fromtimestamp(now.timestamp() - (h % 86400), tz=timezone.utc)
    wallet_type = WalletType.CONTRACT if h % 3 == 0 else WalletType.EOA
    return WalletSummary(
        address=address,
        chain=Chain.ETHEREUM,
        wallet_type=wallet_type,
        balance=balance_eth,
        tx_count=tx_count,
        first_seen=first_seen,
        last_active=last_active,
    )


def _mock_transactions(address: str, count: int = 20) -> list[TransactionSummary]:
    """Generate deterministic mock transactions from address hash."""
    h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
    now = datetime.now(tz=timezone.utc)
    txs = []
    for i in range(count):
        tx_h = hashlib.sha256(f"{address}:{i}".encode()).hexdigest()[:64]
        ts = datetime.fromtimestamp(now.timestamp() - (i * 3600 + h % 600), tz=timezone.utc)
        value = round((h >> (i * 3)) % 100 + random.uniform(0.01, 5.0), 4)
        fee = round(random.uniform(0.001, 0.05), 6)
        status = TransactionStatus.SUCCESS if i % 7 != 0 else TransactionStatus.FAILED
        from_addr = address if i % 2 == 0 else "0x" + hashlib.sha256(f"from:{i}".encode()).hexdigest()[:40]
        to_addr = address if i % 2 == 1 else "0x" + hashlib.sha256(f"to:{i}".encode()).hexdigest()[:40]
        methods = ["transfer", "approve", "swap", "mint", "burn", None, None]
        txs.append(TransactionSummary(
            hash="0x" + tx_h,
            chain=Chain.ETHEREUM,
            status=status,
            block_number=20000000 + i,
            timestamp=ts,
            from_address=from_addr,
            to_address=to_addr,
            value=str(value),
            fee=str(fee),
            method=methods[i % len(methods)],
        ))
    return txs


def _mock_token_balances(address: str) -> list[TokenBalance]:
    """Generate deterministic mock token balances."""
    tokens = [
        ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT", "Tether USD", 6),
        ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC", "USD Coin", 6),
        ("0x6B175474E89094C44Da98b954EedeAC495271d0F", "DAI", "Dai Stablecoin", 18),
        ("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", "WBTC", "Wrapped Bitcoin", 8),
        ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "WETH", "Wrapped Ether", 18),
    ]
    h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
    return [
        TokenBalance(
            contract_address=t[0], symbol=t[1], name=t[2],
            balance=str(round((h >> (i * 4)) % 10000 + random.uniform(0.1, 100.0), 2)),
            decimals=t[3],
        )
        for i, t in enumerate(tokens)
    ]


def _mock_graph_data(address: str, limit: int = 50) -> GraphData:
    """Generate deterministic mock graph data."""
    h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
    nodes: dict[str, GraphNode] = {address: GraphNode(id=address, chain=Chain.ETHEREUM, label="center")}
    edges: list[GraphEdge] = []
    now = datetime.now(tz=timezone.utc)
    for i in range(min(limit, 30)):
        peer = "0x" + hashlib.sha256(f"peer:{address}:{i}".encode()).hexdigest()[:40]
        nodes[peer] = GraphNode(id=peer, chain=Chain.ETHEREUM)
        val = round((h >> (i * 3)) % 50 + 0.1, 4)
        ts = datetime.fromtimestamp(now.timestamp() - (i * 1800), tz=timezone.utc)
        edges.append(GraphEdge(source=address, target=peer, value=str(val), tx_count=1, timestamp=ts))
    total_volume = sum(float(e.value) for e in edges)
    return GraphData(nodes=list(nodes.values()), edges=edges, total_volume=str(round(total_volume, 4)))


def _mock_risk_score(address: str) -> RiskScore:
    """Generate deterministic mock risk score."""
    h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
    score = (h % 60) + 10
    factors: list[RiskFactor] = []
    if score > 40:
        factors.append(RiskFactor(category="contract", label="Unverified contract", weight=2.0, contribution=30))
    if h % 2 == 0:
        factors.append(RiskFactor(category="activity", label="Active wallet", weight=1.0, contribution=10))
    band = (
        RiskBand.CRITICAL if score >= 80 else
        RiskBand.HIGH if score >= 60 else
        RiskBand.MEDIUM if score >= 40 else
        RiskBand.LOW if score >= 20 else
        RiskBand.INFO
    )
    return RiskScore(address=address, chain=Chain.ETHEREUM, score=score, band=band, factors=factors)


def _mock_attribution(address: str) -> EntityAttribution:
    """Generate deterministic mock attribution."""
    h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
    categories = [
        (EntityCategory.EXCHANGE, "Unknown Exchange", 60),
        (EntityCategory.PROTOCOL, "DeFi Protocol", 70),
        (EntityCategory.INDIVIDUAL, "Individual Wallet", 50),
        (EntityCategory.MINER, "Mining Pool", 65),
    ]
    cat, name, conf = categories[h % len(categories)]
    return EntityAttribution(
        address=address,
        chain=Chain.ETHEREUM,
        entity_name=name,
        category=cat,
        confidence=conf,
        evidence=[Evidence(source="curated", type=EvidenceType.CURATED_LABEL, confidence=conf)],
    )


class EthereumProvider(ChainProvider):
    chain = Chain.ETHEREUM

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or settings.ETHERSCAN_API_KEY
        self._last_request = 0.0
        self._use_ip_fallback = False
        self._mock_mode = not bool(self.api_key)

    def is_available(self) -> bool:
        return True

    def _needs_key(self) -> bool:
        return self._mock_mode

    async def _throttle(self) -> None:
        if self._mock_mode:
            return
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.25:
            await asyncio.sleep(0.25 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._mock_mode:
            raise RuntimeError("No Etherscan API key configured")
        await self._throttle()
        params.setdefault("chainid", "1")
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
        if self._mock_mode:
            return _mock_wallet_summary(address)

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
        total_tx_resp = await self._get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "1",
            "sort": "desc",
        })

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

        first_seen = None
        last_active = None
        if txs:
            timestamps = [int(t.get("timeStamp", 0)) for t in txs if t.get("timeStamp")]
            if timestamps:
                first_seen = datetime.fromtimestamp(min(timestamps), tz=timezone.utc)
                last_active = datetime.fromtimestamp(max(timestamps), tz=timezone.utc)

        return WalletSummary(
            address=address,
            chain=Chain.ETHEREUM,
            wallet_type=wallet_type,
            balance=balance_eth,
            tx_count=len(txs) if isinstance(txs, list) else 0,
            first_seen=first_seen,
            last_active=last_active,
        )

    # ── Transactions ─────────────────────────────────────────────────────

    async def get_transactions(
        self, address: str, page: int = 1, page_size: int = 20
    ) -> list[TransactionSummary]:
        if self._mock_mode:
            return _mock_transactions(address, page_size)

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

    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        if self._mock_mode:
            h = int(hashlib.sha256(tx_hash.encode()).hexdigest()[:8], 16)
            now = datetime.now(tz=timezone.utc)
            return TransactionDetail(
                hash=tx_hash, chain=Chain.ETHEREUM,
                status=TransactionStatus.SUCCESS if h % 7 != 0 else TransactionStatus.FAILED,
                block_number=20000000 + h % 1000,
                timestamp=now,
                from_address="0x" + hashlib.sha256(f"from:{tx_hash}".encode()).hexdigest()[:40],
                to_address="0x" + hashlib.sha256(f"to:{tx_hash}".encode()).hexdigest()[:40],
                value=str(round(h % 100 + 0.1, 4)),
                fee=str(round(random.uniform(0.001, 0.05), 6)),
                gas_price=str(random.randint(10, 100) * 10**9),
                gas_used=random.randint(21000, 500000),
                nonce=h % 100,
                input_data="0x",
            )

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
        if self._mock_mode:
            return _mock_token_balances(address)

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
        if self._mock_mode:
            h = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
            if h % 2 == 0:
                return None
            return ContractDetail(
                address=address, chain=Chain.ETHEREUM,
                creator="0x" + hashlib.sha256(f"creator:{address}".encode()).hexdigest()[:40],
                creation_tx="0x" + hashlib.sha256(f"ctx:{address}".encode()).hexdigest()[:64],
                verified=h % 3 != 0,
                contract_type=ContractType.ERC20 if h % 4 == 0 else ContractType.UNKNOWN,
            )

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
        if self._mock_mode:
            return _mock_risk_score(address)

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
        if self._mock_mode:
            return _mock_graph_data(address, limit)

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
