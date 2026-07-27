"""Ethereum chain provider — Etherscan public API adapter.

Uses the free Etherscan API (rate-limited to 5 req/s).
No API key required for basic endpoints.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from typing import Any

import httpx

from ..base import ChainProviderInterface, registry
from ...domain.models.base import (
    Chain,
    ContractDetail,
    ContractType,
    PaginatedResponse,
    TransactionDetail,
    TransactionStatus,
    TransactionSummary,
    WalletSummary,
    WalletType,
)

logger = logging.getLogger(__name__)

ETHERSCAN_BASE = "https://api.etherscan.io/api"
ETHERSCAN_RATE_LIMIT = 0.25  # 4 req/s to stay under free tier

# EVM address checksum (EIP-55)
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


class EthereumProvider(ChainProviderInterface):
    chain = Chain.ETHEREUM

    def __init__(self) -> None:
        self._api_key = os.environ.get("ETHERSCAN_API_KEY", "")
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
        data = resp.json()

        if data.get("status") == "0" and data.get("message") != "No transactions found":
            logger.warning("Etherscan error: %s", data.get("result"))
        return data

    async def validate_address(self, address: str) -> bool:
        if not _is_valid_eth_address(address):
            return False
        try:
            data = await self._rate_limited_get({
                "module": "proxy",
                "action": "eth_getCode",
                "address": _to_checksum_address(address),
                "tag": "latest",
            })
            result = data.get("result", "0x")
            # EOAs return "0x", contracts return bytecode
            return True  # Valid EVM address
        except Exception:
            return False

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        if not _is_valid_eth_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")

        address = _to_checksum_address(address)
        balance_data, txlist_data, code_data = await asyncio.gather(
            self._rate_limited_get({
                "module": "account",
                "action": "balance",
                "address": address,
                "tag": "latest",
            }),
            self._rate_limited_get({
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": "0",
                "endblock": "99999999",
                "page": "1",
                "offset": "1",
                "sort": "desc",
            }),
            self._rate_limited_get({
                "module": "proxy",
                "action": "eth_getCode",
                "address": address,
                "tag": "latest",
            }),
            return_exceptions=True,
        )

        # Balance
        balance_wei = "0"
        if isinstance(balance_data, dict):
            balance_wei = balance_data.get("result", "0")
        balance_eth = str(round(int(balance_wei) / 1e18, 8))

        # Wallet type
        is_contract = False
        if isinstance(code_data, dict):
            code = code_data.get("result", "0x")
            is_contract = code != "0x" and len(code) > 2

        # Tx count from latest tx
        tx_count = 0
        first_seen = None
        last_active = None
        if isinstance(txlist_data, dict) and isinstance(txlist_data.get("result"), list):
            txns = txlist_data["result"]
            tx_count = len(txns)
            if txns:
                last_tx = txns[0]
                last_active = _parse_timestamp(last_tx.get("timeStamp"))
                # Get total tx count
                count_data = await self._rate_limited_get({
                    "module": "proxy",
                    "action": "eth_getTransactionCount",
                    "address": address,
                    "tag": "latest",
                })
                if isinstance(count_data, dict):
                    nonce = int(count_data.get("result", "0x0"), 16)
                    tx_count = max(tx_count, nonce + 1)

        # Get first tx
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
                txns.append(TransactionSummary(
                    hash=tx.get("hash", ""),
                    chain=Chain.ETHEREUM,
                    status=TransactionStatus.SUCCESS if tx.get("txreceipt_status") == "1" else TransactionStatus.FAILED,
                    block_number=int(tx.get("blockNumber", "0")),
                    timestamp=_parse_timestamp(tx.get("timeStamp")),
                    from_address=tx.get("from", ""),
                    to_address=tx.get("to", "") or "",
                    value=str(int(tx.get("value", "0")) // 10**18 * 10**18 / 10**18) if tx.get("value") else "0",
                    fee=str(int(tx.get("gasUsed", "0")) * int(tx.get("gasPrice", "0")) // 10**18) if tx.get("gasUsed") and tx.get("gasPrice") else None,
                    method=_decode_method_id(tx.get("input", "0x")),
                ))

        total = int(data.get("result", [{}])[0].get("blockNumber", "0")) if data.get("result") else 0

        return PaginatedResponse(
            items=txns,
            total=total,
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
            status_code = receipt.get("status", "0x1")
            status = TransactionStatus.SUCCESS if status_code == "0x1" else TransactionStatus.FAILED

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
                    "block_number": int(log.get("blockNumber", "0x0"), 16),
                }
                for log in (receipt.get("logs", []) if receipt else [])
            ],
        )

    async def get_contract(self, address: str) -> ContractDetail | None:
        if not _is_valid_eth_address(address):
            return None

        address = _to_checksum_address(address)

        # Check if it's a contract
        code_data = await self._rate_limited_get({
            "module": "proxy",
            "action": "eth_getCode",
            "address": address,
            "tag": "latest",
        })
        code = code_data.get("result", "0x")
        if code == "0x" or len(code) <= 2:
            return None

        # Try to get source code
        source_data = await self._rate_limited_get({
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
        })

        result = source_data.get("result", [{}])
        if isinstance(result, list) and result:
            contract_info = result[0]
            verified = bool(contract_info.get("SourceCode"))
            contract_type = ContractType.UNKNOWN
            name = contract_info.get("ContractName", "")
            symbol = ""

            # Detect type from ABI/function signatures
            if verified:
                abi_str = contract_info.get("ABI", "")
                if "totalSupply" in abi_str and "transfer" in abi_str:
                    contract_type = ContractType.ERC20
                    symbol = name
                elif "tokenURI" in abi_str:
                    contract_type = ContractType.ERC721
                elif "uri" in abi_str and "balanceOfBatch" in abi_str:
                    contract_type = ContractType.ERC1155
                elif "implementation" in abi_str.lower():
                    contract_type = ContractType.PROXY

            return ContractDetail(
                address=address,
                chain=Chain.ETHEREUM,
                verified=verified,
                name=name,
                symbol=symbol,
                compiler_version=contract_info.get("CompilerVersion"),
                contract_type=contract_type,
            )

        return ContractDetail(
            address=address,
            chain=Chain.ETHEREUM,
            verified=False,
            contract_type=ContractType.UNKNOWN,
        )

    async def get_token_balances(self, address: str) -> list[dict[str, Any]]:
        """Get ERC-20 token transfers (proxy for token balances via Etherscan free API)."""
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
        """Search is limited in free Etherscan — return address validation result."""
        results = []
        if _is_valid_eth_address(query):
            results.append({
                "type": "address",
                "value": query,
                "chain": Chain.ETHEREUM,
                "label": f"Ethereum address {query[:10]}...",
            })
        return results


def _parse_timestamp(ts: str | None) -> Any:
    if not ts:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _decode_method_id(input_data: str | None) -> str | None:
    if not input_data or input_data == "0x" or len(input_data) < 10:
        return None
    method_id = input_data[:10]
    known_methods = {
        "0xa9059cbb": "transfer",
        "0x23b872dd": "transferFrom",
        "0x095ea7b3": "approve",
        "0xddf252ad": "transfer (event)",
        "0x38ed1739": "swapExactTokensForTokens",
        "0x7ff36ab5": "swapExactETHForTokens",
        "0x18cbafe5": "swapExactTokensForETH",
        "0x6a761202": "execTransaction",
    }
    return known_methods.get(method_id, method_id)


# Register on import
registry.register(EthereumProvider())
