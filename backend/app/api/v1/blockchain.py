"""Blockchain Intelligence API routes (integrated into main EASM backend).

Self-contained version with inline domain models and provider logic.
No external module dependencies.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Domain Models (inline) ──────────────────────────────────────────────────

class Chain(str, Enum):
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    BNB = "bnb"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    AVALANCHE = "avalanche"
    TRON = "tron"
    SOLANA = "solana"


class WalletType(str, Enum):
    EOA = "eoa"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


class ContractType(str, Enum):
    ERC20 = "erc20"
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    PROXY = "proxy"
    UNKNOWN = "unknown"


class TransactionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


class RiskBand(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class EntityCategory(str, Enum):
    EXCHANGE = "exchange"
    DEFI_PROTOCOL = "defi_protocol"
    STABLECOIN_ISSUER = "stablecoin_issuer"
    SANCTIONS = "sanctions"
    MIXING_SERVICE = "mixing_service"
    MINING_POOL = "mining_pool"
    UNKNOWN = "unknown"


class WalletSummary(BaseModel):
    address: str
    chain: Chain
    wallet_type: WalletType = WalletType.UNKNOWN
    balance: str = "0"
    tx_count: int = 0
    first_seen: datetime | None = None
    last_active: datetime | None = None


class TransactionSummary(BaseModel):
    hash: str
    chain: Chain
    status: TransactionStatus = TransactionStatus.PENDING
    block_number: int | None = None
    timestamp: datetime | None = None
    from_address: str = ""
    to_address: str = ""
    value: str = "0"
    fee: str | None = None
    method: str | None = None


class TransactionDetail(TransactionSummary):
    gas_price: str | None = None
    gas_used: int | None = None
    nonce: int | None = None
    input_data: str = "0x"
    decoded_method: str | None = None
    logs: list[dict[str, Any]] = Field(default_factory=list)


class ContractDetail(BaseModel):
    address: str
    chain: Chain
    verified: bool = False
    name: str = ""
    symbol: str = ""
    compiler_version: str | None = None
    contract_type: ContractType = ContractType.UNKNOWN


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_next: bool = False


class RiskFactor(BaseModel):
    name: str
    score: int = 0
    weight: float = 1.0


class RiskScore(BaseModel):
    address: str
    chain: Chain
    score: int = 0
    band: RiskBand = RiskBand.UNKNOWN
    factors: list[RiskFactor] = Field(default_factory=list)


class Evidence(BaseModel):
    source: str
    type: str = "unknown"
    confidence: int = 0
    reason: str = ""


class EntityAttribution(BaseModel):
    address: str
    chain: Chain
    entity: str | None = None
    category: EntityCategory = EntityCategory.UNKNOWN
    confidence: int = 0
    evidence: list[Evidence] = Field(default_factory=list)


# ── Curated Labels ──────────────────────────────────────────────────────────

CURATED_LABELS: list[dict[str, Any]] = [
    {
        "address": "0x28C6c06298d514Db089934071355E5743bf21d60",
        "chain": "ethereum",
        "entity": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "reason": "Publicly disclosed Binance hot wallet",
    },
    {
        "address": "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
        "chain": "ethereum",
        "entity": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "reason": "Publicly disclosed Binance cold wallet",
    },
    {
        "address": "0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43",
        "chain": "ethereum",
        "entity": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "reason": "Publicly disclosed Coinbase hot wallet",
    },
    {
        "address": "0x503828976D22510aad0201ac7EC88293211D23Da",
        "chain": "ethereum",
        "entity": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "reason": "Publicly disclosed Coinbase cold wallet",
    },
    {
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "chain": "ethereum",
        "entity": "Tether (USDT)",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "reason": "Official USDT ERC-20 contract",
    },
    {
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "chain": "ethereum",
        "entity": "Circle (USDC)",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "reason": "Official USDC ERC-20 contract",
    },
    {
        "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "chain": "ethereum",
        "entity": "Uniswap V2 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "reason": "Official Uniswap V2 Router contract",
    },
    {
        "address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "chain": "ethereum",
        "entity": "Uniswap V3 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "reason": "Official Uniswap V3 Router contract",
    },
    {
        "address": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
        "chain": "ethereum",
        "entity": "Aave V2 Lending Pool",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "reason": "Official Aave V2 Lending Pool contract",
    },
    {
        "address": "0x8589427373D6D84E98730D7795D8f6f8731FDA16",
        "chain": "ethereum",
        "entity": "Lazarus Group (DPRK)",
        "category": EntityCategory.SANCTIONS,
        "confidence": 100,
        "reason": "OFAC SDN listed DPRK-associated address",
    },
    {
        "address": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
        "chain": "ethereum",
        "entity": "Sinbad.io Mixer",
        "category": EntityCategory.MIXING_SERVICE,
        "confidence": 85,
        "reason": "OFAC SDN listed mixing service",
    },
]


# ── Etherscan Provider ──────────────────────────────────────────────────────

ETHERSCAN_BASE = "https://api.etherscan.io/api"
ETHERSCAN_RATE_LIMIT = 0.25


def _to_checksum_address(address: str) -> str:
    address = address.lower().removeprefix("0x")
    hashed = hashlib.sha3_256(address.encode()).hexdigest()
    checksummed = "0x"
    for i, char in enumerate(address):
        if char in "0123456789":
            checksummed += char
        elif hashed[i] in "89abcdef":
            checksummed += char.upper()
        else:
            checksummed += char
    return checksummed


def _is_valid_eth_address(address: str) -> bool:
    return bool(re.match(r"^0x[0-9a-fA-F]{40}$", address))


def _parse_timestamp(ts: str | None) -> Any:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _decode_method_id(input_data: str | None) -> str | None:
    if not input_data or input_data == "0x" or len(input_data) < 10:
        return None
    method_id = input_data[:10]
    known = {
        "0xa9059cbb": "transfer",
        "0x23b872dd": "transferFrom",
        "0x095ea7b3": "approve",
        "0xddf252ad": "transfer (event)",
        "0x38ed1739": "swapExactTokensForTokens",
        "0x7ff36ab5": "swapExactETHForTokens",
        "0x18cbafe5": "swapExactTokensForETH",
        "0x6a761202": "execTransaction",
    }
    return known.get(method_id, method_id)


class EtherscanProvider:
    """Ethereum chain provider using Etherscan public API."""

    def __init__(self) -> None:
        self._api_key = ""
        self._last_request = 0.0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def _rate_limited_get(self, params: dict[str, Any]) -> dict[str, Any]:
        elapsed = time.time() - self._last_request
        if elapsed < ETHERSCAN_RATE_LIMIT:
            await asyncio.sleep(ETHERSCAN_RATE_LIMIT - elapsed)

        client = await self._get_client()
        if self._api_key:
            params["apikey"] = self._api_key

        resp = await client.get(ETHERSCAN_BASE, params=params)
        self._last_request = time.time()
        resp.raise_for_status()
        return resp.json()

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        if not _is_valid_eth_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")

        address = _to_checksum_address(address)
        balance_data, code_data = await asyncio.gather(
            self._rate_limited_get({
                "module": "account",
                "action": "balance",
                "address": address,
                "tag": "latest",
            }),
            self._rate_limited_get({
                "module": "proxy",
                "action": "eth_getCode",
                "address": address,
                "tag": "latest",
            }),
            return_exceptions=True,
        )

        balance_wei = "0"
        if isinstance(balance_data, dict):
            balance_wei = balance_data.get("result", "0")
        balance_eth = str(round(int(balance_wei) / 1e18, 8))

        is_contract = False
        if isinstance(code_data, dict):
            code = code_data.get("result", "0x")
            is_contract = code != "0x" and len(code) > 2

        # Get first/last tx timestamps
        first_seen = None
        last_active = None
        tx_count = 0

        txlist_data = await self._rate_limited_get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "1",
            "sort": "desc",
        })
        if isinstance(txlist_data, dict) and isinstance(txlist_data.get("result"), list):
            txns = txlist_data["result"]
            if txns:
                last_active = _parse_timestamp(txns[0].get("timeStamp"))
                tx_count = len(txns)

        first_tx_data = await self._rate_limited_get({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "1",
            "sort": "asc",
        })
        if isinstance(first_tx_data, dict) and isinstance(first_tx_data.get("result"), list):
            txns = first_tx_data["result"]
            if txns:
                first_seen = _parse_timestamp(txns[0].get("timeStamp"))

        count_data = await self._rate_limited_get({
            "module": "proxy",
            "action": "eth_getTransactionCount",
            "address": address,
            "tag": "latest",
        })
        if isinstance(count_data, dict):
            nonce = int(count_data.get("result", "0x0"), 16)
            tx_count = max(tx_count, nonce + 1)

        return WalletSummary(
            address=address,
            chain=Chain.ETHEREUM,
            wallet_type=WalletType.CONTRACT if is_contract else WalletType.EOA,
            balance=balance_eth,
            tx_count=tx_count,
            first_seen=first_seen,
            last_active=last_active,
        )

    async def get_transactions(
        self,
        address: str,
        page: int = 1,
        page_size: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        if not _is_valid_eth_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")

        data = await self._rate_limited_get({
            "module": "account",
            "action": "txlist",
            "address": _to_checksum_address(address),
            "startblock": "0",
            "endblock": "99999999",
            "page": str(page),
            "offset": str(page_size),
            "sort": "desc",
        })

        txns = []
        if isinstance(data.get("result"), list):
            for tx in data["result"]:
                value_raw = int(tx.get("value", "0"))
                gas_used = int(tx.get("gasUsed", "0")) if tx.get("gasUsed") else 0
                gas_price = int(tx.get("gasPrice", "0")) if tx.get("gasPrice") else 0
                fee_raw = gas_price * gas_used

                txns.append(TransactionSummary(
                    hash=tx.get("hash", ""),
                    chain=Chain.ETHEREUM,
                    status=TransactionStatus.SUCCESS if tx.get("txreceipt_status") == "1" else TransactionStatus.FAILED,
                    block_number=int(tx.get("blockNumber", "0")) if tx.get("blockNumber") else None,
                    timestamp=_parse_timestamp(tx.get("timeStamp")),
                    from_address=tx.get("from", ""),
                    to_address=tx.get("to", "") or "",
                    value=str(round(value_raw / 1e18, 8)) if value_raw else "0",
                    fee=str(round(fee_raw / 1e18, 10)) if fee_raw else None,
                    method=_decode_method_id(tx.get("input", "0x")),
                ))

        return PaginatedResponse(
            items=txns,
            total=len(txns) + page * page_size,
            page=page,
            page_size=page_size,
            has_next=len(txns) == page_size,
        )

    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        data = await self._rate_limited_get({
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash,
        })
        tx = data.get("result", {})
        if not tx:
            raise ValueError(f"Transaction not found: {tx_hash}")

        receipt_data = await self._rate_limited_get({
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
        })
        receipt = receipt_data.get("result", {})

        value_wei = int(tx.get("value", "0x0"), 16)
        gas_price = int(tx.get("gasPrice", "0x0"), 16) if tx.get("gasPrice") else 0
        gas_used = int(receipt.get("gasUsed", "0x0"), 16) if receipt.get("gasUsed") else 0
        fee_eth = str(round(gas_price * gas_used / 1e18, 10)) if gas_price and gas_used else None

        status = TransactionStatus.SUCCESS
        if receipt:
            status = TransactionStatus.SUCCESS if receipt.get("status") == "0x1" else TransactionStatus.FAILED

        return TransactionDetail(
            hash=tx_hash,
            chain=Chain.ETHEREUM,
            status=status,
            block_number=int(tx.get("blockNumber", "0x0"), 16) if tx.get("blockNumber") else None,
            from_address=tx.get("from", ""),
            to_address=tx.get("to", "") or "",
            value=str(round(value_wei / 1e18, 8)),
            fee=fee_eth,
            gas_price=str(gas_price),
            gas_used=gas_used,
            nonce=int(tx.get("nonce", "0x0"), 16) if tx.get("nonce") else None,
            input_data=tx.get("input", "0x"),
            decoded_method=_decode_method_id(tx.get("input", "0x")),
            logs=[
                {
                    "address": log.get("address", ""),
                    "topics": log.get("topics", []),
                    "data": log.get("data", ""),
                }
                for log in (receipt.get("logs", []) if receipt else [])
            ],
        )

    async def get_contract(self, address: str) -> ContractDetail | None:
        if not _is_valid_eth_address(address):
            return None
        address = _to_checksum_address(address)

        code_data = await self._rate_limited_get({
            "module": "proxy",
            "action": "eth_getCode",
            "address": address,
            "tag": "latest",
        })
        code = code_data.get("result", "0x")
        if code == "0x" or len(code) <= 2:
            return None

        source_data = await self._rate_limited_get({
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        })
        result = source_data.get("result", [{}])
        if isinstance(result, list) and result:
            info = result[0]
            verified = bool(info.get("SourceCode"))
            name = info.get("ContractName", "")
            contract_type = ContractType.UNKNOWN
            if verified:
                abi = info.get("ABI", "")
                if "totalSupply" in abi and "transfer" in abi:
                    contract_type = ContractType.ERC20
                elif "tokenURI" in abi:
                    contract_type = ContractType.ERC721
                elif "balanceOfBatch" in abi:
                    contract_type = ContractType.ERC1155
                elif "implementation" in abi.lower():
                    contract_type = ContractType.PROXY

            return ContractDetail(
                address=address,
                chain=Chain.ETHEREUM,
                verified=verified,
                name=name,
                symbol=name,
                compiler_version=info.get("CompilerVersion"),
                contract_type=contract_type,
            )

        return ContractDetail(address=address, chain=Chain.ETHEREUM, verified=False)

    async def get_token_balances(self, address: str) -> list[dict[str, Any]]:
        if not _is_valid_eth_address(address):
            return []
        data = await self._rate_limited_get({
            "module": "account",
            "action": "tokentx",
            "address": _to_checksum_address(address),
            "page": "1",
            "offset": "50",
            "sort": "desc",
        })
        tokens = []
        seen = set()
        if isinstance(data.get("result"), list):
            for tx in data["result"]:
                contract = tx.get("contractAddress", "")
                if contract and contract not in seen:
                    seen.add(contract)
                    tokens.append({
                        "contract_address": contract,
                        "symbol": tx.get("tokenSymbol", ""),
                        "name": tx.get("tokenName", ""),
                        "decimals": int(tx.get("tokenDecimal", "18")),
                    })
        return tokens

    async def search(self, query: str) -> list[dict[str, Any]]:
        results = []
        if _is_valid_eth_address(query):
            results.append({
                "type": "address",
                "value": query,
                "chain": "ethereum",
                "label": f"Ethereum address {query[:10]}...",
            })
        return results


# ── Attribution Service ─────────────────────────────────────────────────────

async def attribute_address(address: str, chain: Chain) -> EntityAttribution:
    """Attribute an address to a real-world entity."""
    evidence_list: list[Evidence] = []
    entity_name = None
    category = EntityCategory.UNKNOWN

    # Check curated labels
    for label in CURATED_LABELS:
        if label["address"].lower() == address.lower() and label["chain"] == chain.value:
            entity_name = label["entity"]
            category = label["category"]
            evidence_list.append(Evidence(
                source="curated_labels",
                type="exchange_tag" if category == EntityCategory.EXCHANGE else "label_source",
                confidence=label["confidence"],
                reason=label["reason"],
            ))
            break

    return EntityAttribution(
        address=address,
        chain=chain,
        entity=entity_name,
        category=category,
        confidence=max((e.confidence for e in evidence_list), default=0),
        evidence=evidence_list,
    )


# ── Risk Engine ─────────────────────────────────────────────────────────────

async def compute_risk(
    address: str,
    chain: Chain,
    wallet: WalletSummary | None = None,
    attribution: EntityAttribution | None = None,
) -> RiskScore:
    """Compute risk score for an address."""
    factors: list[RiskFactor] = []

    if attribution and attribution.category:
        category_risk = {
            EntityCategory.SANCTIONS: ("Sanctioned entity", 100, 10.0),
            EntityCategory.MIXING_SERVICE: ("Mixing service", 85, 5.0),
            EntityCategory.EXCHANGE: ("Exchange wallet", 30, 1.0),
            EntityCategory.DEFI_PROTOCOL: ("DeFi protocol", 10, 0.5),
            EntityCategory.STABLECOIN_ISSUER: ("Stablecoin issuer", 5, 0.5),
        }
        if attribution.category in category_risk:
            name, score, weight = category_risk[attribution.category]
            factors.append(RiskFactor(name=name, score=score, weight=weight))

    if wallet:
        balance = float(wallet.balance) if wallet.balance else 0
        if balance > 10000:
            factors.append(RiskFactor(name="Large balance", score=40, weight=1.5))
        elif balance > 1000:
            factors.append(RiskFactor(name="Moderate balance", score=20, weight=1.0))

        if wallet.tx_count > 100000:
            factors.append(RiskFactor(name="Very high tx count", score=50, weight=1.2))
        elif wallet.tx_count > 10000:
            factors.append(RiskFactor(name="High tx count", score=30, weight=0.8))

    if not factors:
        return RiskScore(address=address, chain=chain, score=0, band=RiskBand.UNKNOWN, factors=[])

    total_weight = sum(f.weight for f in factors)
    weighted_score = sum(f.score * f.weight for f in factors) if total_weight > 0 else 0
    composite = round(weighted_score / total_weight) if total_weight > 0 else 0

    if composite >= 90:
        band = RiskBand.CRITICAL
    elif composite >= 70:
        band = RiskBand.HIGH
    elif composite >= 50:
        band = RiskBand.MEDIUM
    elif composite >= 30:
        band = RiskBand.LOW
    elif composite > 0:
        band = RiskBand.INFO
    else:
        band = RiskBand.UNKNOWN

    return RiskScore(address=address, chain=chain, score=composite, band=band, factors=factors)


# ── Bitcoin Provider (Blockstream.info) ─────────────────────────────────────

BLOCKSTREAM_API = "https://blockstream.info/api"


class BitcoinProvider:
    """Bitcoin chain provider using Blockstream.info public API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def _get(self, path: str) -> Any:
        client = await self._get_client()
        resp = await client.get(f"{BLOCKSTREAM_API}{path}")
        resp.raise_for_status()
        return resp.json()

    def _is_valid_btc_address(self, address: str) -> bool:
        import re
        return bool(re.match(r"^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,62}$", address))

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        if not self._is_valid_btc_address(address):
            raise ValueError(f"Invalid Bitcoin address: {address}")

        addr_data = await self._get(f"/address/{address}")

        chain_stats = addr_data.get("chain_stats", {})
        mempool_stats = addr_data.get("mempool_stats", {})

        funded_sum = chain_stats.get("funded_txo_sum", 0)
        spent_sum = chain_stats.get("spent_txo_sum", 0)
        balance_sats = funded_sum - spent_sum
        balance_btc = str(round(balance_sats / 1e8, 8))

        tx_count = chain_stats.get("tx_count", 0)
        funded_count = chain_stats.get("funded_txo_count", 0)
        spent_count = chain_stats.get("spent_txo_count", 0)

        # Determine type
        script_type = "unknown"
        if address.startswith("bc1q"):
            script_type = "p2wpkh"
        elif address.startswith("bc1p"):
            script_type = "p2tr"
        elif address.startswith("3"):
            script_type = "p2sh"
        elif address.startswith("1"):
            script_type = "p2pkh"

        # Get first/last seen from transactions
        first_seen = None
        last_active = None

        try:
            txs = await self._get(f"/address/{address}/txs?limit=1")
            if txs and isinstance(txs, list) and len(txs) > 0:
                last_tx = txs[0]
                status = last_tx.get("status", {})
                if status.get("block_time"):
                    from datetime import datetime, timezone
                    last_active = datetime.fromtimestamp(status["block_time"], tz=timezone.utc)
        except Exception:
            pass

        try:
            txs = await self._get(f"/address/{address}/txs?limit=100")
            if txs and isinstance(txs, list) and len(txs) > 0:
                oldest = txs[-1]
                status = oldest.get("status", {})
                if status.get("block_time"):
                    from datetime import datetime, timezone
                    first_seen = datetime.fromtimestamp(status["block_time"], tz=timezone.utc)
        except Exception:
            pass

        return WalletSummary(
            address=address,
            chain=Chain.BITCOIN,
            wallet_type=WalletType.UNKNOWN,
            balance=balance_btc,
            tx_count=tx_count,
            first_seen=first_seen,
            last_active=last_active,
        )

    async def get_transactions(
        self,
        address: str,
        page: int = 1,
        page_size: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        if not self._is_valid_btc_address(address):
            raise ValueError(f"Invalid Bitcoin address: {address}")

        # Blockstream uses cursor-based pagination
        url = f"/address/{address}/txs?limit={page_size}"
        if cursor:
            url += f"&after={cursor}"

        txs = await self._get(url)

        txns = []
        next_cursor = None
        if isinstance(txs, list):
            for tx in txs:
                txid = tx.get("txid", "")
                status = tx.get("status", {})
                block_height = status.get("block_height")
                block_time = status.get("block_time")

                timestamp = None
                if block_time:
                    from datetime import datetime, timezone
                    timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc)

                # Calculate value
                total_output = sum(
                    vout.get("value", 0)
                    for vout in tx.get("vout", [])
                )
                value_btc = str(round(total_output / 1e8, 8))

                # Check if this address is sender or receiver
                is_receiver = any(
                    prevout.get("address") == address
                    for vin in tx.get("vin", [])
                    if (prevout := vin.get("prevout")) and prevout.get("address")
                )

                method = "received" if is_receiver else "sent"

                txns.append(TransactionSummary(
                    hash=txid,
                    chain=Chain.BITCOIN,
                    status=TransactionStatus.SUCCESS if status.get("confirmed") else TransactionStatus.PENDING,
                    block_number=block_height,
                    timestamp=timestamp,
                    from_address=address if not is_receiver else "multiple",
                    to_address=address if is_receiver else "multiple",
                    value=value_btc,
                    fee=None,
                    method=method,
                ))

            if txs and len(txs) > 0:
                next_cursor = txs[-1].get("txid")

        return PaginatedResponse(
            items=txns,
            total=len(txns) + page * page_size,
            page=page,
            page_size=page_size,
            has_next=len(txns) == page_size,
        )

    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        tx = await self._get(f"/tx/{tx_hash}")

        status = tx.get("status", {})
        block_height = status.get("block_height")
        block_time = status.get("block_time")

        timestamp = None
        if block_time:
            from datetime import datetime, timezone
            timestamp = datetime.fromtimestamp(block_time, tz=timezone.utc)

        total_input = sum(
            vin.get("prevout", {}).get("value", 0)
            for vin in tx.get("vin", [])
            if vin.get("prevout")
        )
        total_output = sum(
            vout.get("value", 0) for vout in tx.get("vout", [])
        )
        fee = total_input - total_output if total_input > 0 else 0

        return TransactionDetail(
            hash=tx_hash,
            chain=Chain.BITCOIN,
            status=TransactionStatus.SUCCESS if status.get("confirmed") else TransactionStatus.PENDING,
            block_number=block_height,
            timestamp=timestamp,
            from_address="multiple",
            to_address="multiple",
            value=str(round(total_output / 1e8, 8)),
            fee=str(round(fee / 1e8, 8)) if fee > 0 else None,
            input_data="",
            logs=[],
        )

    async def get_contract(self, address: str) -> ContractDetail | None:
        return None

    async def get_token_balances(self, address: str) -> list[dict[str, Any]]:
        return []

    async def search(self, query: str) -> list[dict[str, Any]]:
        results = []
        if self._is_valid_btc_address(query):
            results.append({
                "type": "address",
                "value": query,
                "chain": "bitcoin",
                "label": f"Bitcoin address {query[:12]}...",
            })
        return results


# ── Provider Registry ───────────────────────────────────────────────────────

_eth_provider = EtherscanProvider()
_btc_provider = BitcoinProvider()


def _get_provider(chain: Chain):
    if chain == Chain.ETHEREUM:
        return _eth_provider
    if chain == Chain.BITCOIN:
        return _btc_provider
    return None


# ── API Routes ──────────────────────────────────────────────────────────────

@router.get("/chains")
async def supported_chains():
    """List supported blockchains."""
    return {"chains": [Chain.ETHEREUM.value, Chain.BITCOIN.value], "primary": "ethereum"}


@router.get("/wallet/{address}")
async def get_wallet(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get wallet summary with attribution and risk score."""
    provider = _get_provider(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        wallet = await provider.get_wallet_summary(address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Wallet lookup failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch wallet data")

    attribution, risk = await asyncio.gather(
        attribute_address(address, chain),
        compute_risk(address, chain, wallet=wallet),
        return_exceptions=True,
    )

    return {
        "wallet": wallet.model_dump(mode="json"),
        "attribution": attribution.model_dump(mode="json") if attribution and not isinstance(attribution, Exception) else None,
        "risk": risk.model_dump(mode="json") if risk and not isinstance(risk, Exception) else None,
    }


@router.get("/wallet/{address}/transactions")
async def get_transactions(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Get paginated transaction history for a wallet."""
    provider = _get_provider(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        return await provider.get_transactions(address, page, page_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")


@router.get("/transaction/{tx_hash}")
async def get_transaction(
    tx_hash: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get full transaction detail by hash."""
    provider = _get_provider(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        tx = await provider.get_transaction(tx_hash)
        return tx.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch transaction")


@router.get("/contract/{address}")
async def get_contract(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get contract details if the address is a contract."""
    provider = _get_provider(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        contract = await provider.get_contract(address)
        if not contract:
            raise HTTPException(status_code=404, detail="Address is not a contract")
        return contract.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Contract fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch contract data")


@router.get("/wallet/{address}/tokens")
async def get_token_balances(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get token balances for a wallet."""
    provider = _get_provider(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        tokens = await provider.get_token_balances(address)
        return {"tokens": tokens}
    except Exception as e:
        logger.error("Token balance fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch token balances")


@router.get("/wallet/{address}/risk")
async def get_risk_score(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get detailed risk assessment for a wallet."""
    provider = _get_provider(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain}")

    try:
        wallet = await provider.get_wallet_summary(address)
    except Exception:
        wallet = None

    try:
        attribution = await attribute_address(address, chain)
    except Exception:
        attribution = None

    try:
        risk = await compute_risk(address, chain, wallet=wallet, attribution=attribution)
        return risk.model_dump(mode="json")
    except Exception as e:
        logger.error("Risk scoring failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to compute risk score")


@router.get("/wallet/{address}/attribution")
async def get_attribution(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get entity attribution for a wallet."""
    try:
        attribution = await attribute_address(address, chain)
        return attribution.model_dump(mode="json")
    except Exception as e:
        logger.error("Attribution failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to attribute wallet")


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    chain: Chain | None = Query(default=None),
):
    """Search for addresses, transactions, or entities."""
    results = []
    query_lower = q.lower()

    # Search curated labels
    for label in CURATED_LABELS:
        if query_lower in label["entity"].lower() or query_lower in label["address"].lower():
            results.append({
                "type": "entity",
                "value": label["address"],
                "chain": label["chain"],
                "entity": label["entity"],
                "category": label["category"].value,
                "confidence": label["confidence"],
            })

    # Search chain providers
    chains_to_search = [chain] if chain else [Chain.ETHEREUM]
    for c in chains_to_search:
        provider = _get_provider(c)
        if provider:
            try:
                chain_results = await provider.search(q)
                results.extend(chain_results)
            except Exception as e:
                logger.debug("Search on %s failed: %s", c, e)

    return {"results": results, "total": len(results)}
