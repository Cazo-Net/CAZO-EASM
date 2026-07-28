from __future__ import annotations

import asyncio
import json
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
from app.config import settings

logger = logging.getLogger(__name__)


class EthLikeConnector(ChainConnector):
    chain_id: str

    def __init__(
        self,
        *,
        chain: Chain,
        chain_id: int,
        api_base_url: str,
        native_symbol: str = "ETH",
        native_decimals: int = 18,
        api_key: str = "",
    ) -> None:
        self.chain = chain
        self.chain_id = chain.value
        self._chain_id_int = chain_id
        self._api_base = api_base_url
        self._native_symbol = native_symbol
        self._native_decimals = native_decimals
        self._api_key = api_key or getattr(settings, "ETHERSCAN_API_KEY", "")
        self._last_request = 0.0

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.25:
            await asyncio.sleep(0.25 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        await self._throttle()
        params.setdefault("chainid", str(self._chain_id_int))
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

    async def validate_address(self, address: str) -> bool:
        if not address.startswith("0x") or len(address) != 42:
            return False
        try:
            int(address, 16)
            return True
        except ValueError:
            return False

    async def get_wallet(self, address: str) -> Address:
        balance_resp = await self._get({
            "module": "account", "action": "balance",
            "address": address, "tag": "latest",
        })
        balance_wei = int(balance_resp.get("result", "0"))
        balance = Amount(balance_wei, AmountUnit.WEI)

        tx_resp = await self._get({
            "module": "account", "action": "txlist",
            "address": address,
            "startblock": "0", "endblock": "99999999",
            "page": "1", "offset": "5", "sort": "desc",
        })
        txs = tx_resp.get("result", []) if isinstance(tx_resp.get("result"), list) else []

        code_resp = await self._get({
            "module": "proxy", "action": "eth_getCode",
            "address": address, "tag": "latest",
        })
        code = code_resp.get("result", "0x")
        is_contract = bool(code and code != "0x")

        first_seen = None
        last_active = None
        if txs:
            timestamps = [int(t.get("timeStamp", 0)) for t in txs if t.get("timeStamp")]
            if timestamps:
                first_seen = datetime.fromtimestamp(min(timestamps), tz=timezone.utc)
                last_active = datetime.fromtimestamp(max(timestamps), tz=timezone.utc)

        return Address(
            hash=address,
            chain=self.chain,
            wallet_type=WalletType.CONTRACT if is_contract else WalletType.EOA,
            first_seen_block=first_seen,
            last_active_at=last_active,
            tx_count=len(txs),
            balance=balance,
            is_contract=is_contract,
        )

    async def get_transaction(self, tx_hash: str) -> Transaction:
        tx_resp = await self._get({
            "module": "proxy", "action": "eth_getTransactionByHash", "txhash": tx_hash,
        })
        receipt_resp = await self._get({
            "module": "proxy", "action": "eth_getTransactionReceipt", "txhash": tx_hash,
        })
        tx = tx_resp.get("result", {})
        receipt = receipt_resp.get("result", {})

        if not tx or not receipt:
            return Transaction(hash=tx_hash, chain=self.chain, status=TransactionStatus.PENDING)

        status = TransactionStatus.SUCCESS if receipt.get("status") == "0x1" else TransactionStatus.FAILED
        value_wei = int(tx.get("value", "0x0"), 16)
        gas_used = int(receipt.get("gasUsed", "0x0"), 16)
        gas_price_val = int(tx.get("gasPrice", "0x0"), 16)

        logs = [{
            "address": log.get("address", ""),
            "topics": log.get("topics", []),
            "data": log.get("data", ""),
            "block_number": int(log.get("blockNumber", "0x0"), 16),
        } for log in receipt.get("logs", [])]

        return Transaction(
            hash=tx_hash,
            chain=self.chain,
            status=status,
            block_number=int(receipt.get("blockNumber", "0x0"), 16),
            timestamp=datetime.fromtimestamp(
                int(tx.get("timeStamp", "0x0"), 16) if tx.get("timeStamp") else 0, tz=timezone.utc,
            ),
            from_address=tx.get("from", ""),
            to_address=tx.get("to", ""),
            value=Amount(value_wei, AmountUnit.WEI),
            fee=Amount(gas_used * gas_price_val, AmountUnit.WEI),
            gas_price=gas_price_val, gas_used=gas_used,
            nonce=int(tx.get("nonce", "0x0"), 16),
            input_data=tx.get("input", "0x"),
            logs=logs,
        )

    async def get_contract(self, address: str) -> Contract | None:
        code_resp = await self._get({
            "module": "proxy", "action": "eth_getCode", "address": address, "tag": "latest",
        })
        code = code_resp.get("result", "0x")
        if not code or code == "0x":
            return None

        abi_resp = await self._get({
            "module": "contract", "action": "getabi", "address": address,
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
            except (json.JSONDecodeError, TypeError):
                pass

        creator_resp = await self._get({
            "module": "contract", "action": "getcontractcreation", "contractaddresses": address,
        })
        creator_data = creator_resp.get("result", [])
        creator = creator_data[0].get("contractCreator", "") if isinstance(creator_data, list) and creator_data else None
        creation_tx = creator_data[0].get("txHash", "") if isinstance(creator_data, list) and creator_data else None

        return Contract(
            address=address, chain=self.chain,
            creator=creator, creation_tx=creation_tx,
            verified=abi is not None, abi=abi,
            contract_type=contract_type, name=name, symbol=symbol,
        )

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        resp = await self._get({
            "module": "account", "action": "tokentx",
            "address": address, "page": "1", "offset": "200", "sort": "desc",
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

        balances = []
        for info in seen.values():
            balance = await self._get_token_balance(address, info["contract_address"], info["decimals"])
            balances.append(TokenBalance(
                contract_address=info["contract_address"], chain=self.chain,
                symbol=info["symbol"], name=info["name"],
                balance=balance, decimals=info["decimals"],
            ))
        return balances

    async def _get_token_balance(self, owner: str, contract: str, decimals: int) -> Amount:
        try:
            padded = owner.lower().replace("0x", "").zfill(64)
            data = f"0x70a08231{padded}"
            resp = await self._get({
                "module": "proxy", "action": "eth_call",
                "to": contract, "data": data, "tag": "latest",
            })
            result = resp.get("result", "0x0")
            raw = int(result, 16) if result and result != "0x" else 0
            return Amount(raw, AmountUnit.NATIVE)
        except Exception as e:
            logger.debug("balanceOf failed for %s on %s: %s", owner, contract, e)
            return Amount.zero()

    async def get_current_block(self) -> int:
        resp = await self._get({"module": "proxy", "action": "eth_blockNumber"})
        return int(resp.get("result", "0x0"), 16)

    async def get_block(self, number: int) -> Block:
        resp = await self._get({
            "module": "proxy", "action": "eth_getBlockByNumber",
            "tag": hex(number), "boolean": "false",
        })
        data = resp.get("result", {})
        return Block(
            number=number, chain=self.chain,
            hash=data.get("hash", ""),
            parent_hash=data.get("parentHash"),
            timestamp=datetime.fromtimestamp(int(data.get("timestamp", "0x0"), 16), tz=timezone.utc)
            if data.get("timestamp") else None,
            tx_count=len(data.get("transactions", [])),
            gas_limit=int(data.get("gasLimit", "0x0"), 16),
            gas_used=int(data.get("gasUsed", "0x0"), 16),
            miner=data.get("miner", ""),
        )

    async def stream_new_activity(self, address: str) -> AsyncIterator[Transaction]:
        last_nonce: int | None = None
        while True:
            tx_resp = await self._get({
                "module": "account", "action": "txlist",
                "address": address,
                "startblock": "0", "endblock": "99999999",
                "page": "1", "offset": "5", "sort": "desc",
            })
            txs = tx_resp.get("result", [])
            if isinstance(txs, list) and txs:
                latest_nonce = int(txs[0].get("nonce", "0"))
                if last_nonce is not None and latest_nonce > last_nonce:
                    for tx_data in txs:
                        if int(tx_data.get("nonce", "0")) > last_nonce:
                            yield Transaction(
                                hash=tx_data.get("hash", ""),
                                chain=self.chain,
                                block_number=int(tx_data.get("blockNumber", 0)),
                                timestamp=datetime.fromtimestamp(int(tx_data.get("timeStamp", 0)), tz=timezone.utc),
                                from_address=tx_data.get("from", ""),
                                to_address=tx_data.get("to", ""),
                                value=Amount(int(tx_data.get("value", "0")), AmountUnit.WEI),
                                status=TransactionStatus.SUCCESS
                                if tx_data.get("isError") == "0" else TransactionStatus.FAILED,
                                nonce=int(tx_data.get("nonce", "0")),
                            )
                last_nonce = latest_nonce
            await asyncio.sleep(15)


# ── EVM Chain Factories ────────────────────────────────────────────────────

def ethereum_connector(api_key: str = "") -> EthLikeConnector:
    return EthLikeConnector(
        chain=Chain.ETHEREUM, chain_id=1,
        api_base_url="https://api.etherscan.io/v2/api",
        api_key=api_key,
    )


def bnb_connector(api_key: str = "") -> EthLikeConnector:
    return EthLikeConnector(
        chain=Chain.BNB, chain_id=56,
        api_base_url="https://api.bscscan.com/api",
        native_symbol="BNB", api_key=api_key,
    )


def polygon_connector(api_key: str = "") -> EthLikeConnector:
    return EthLikeConnector(
        chain=Chain.POLYGON, chain_id=137,
        api_base_url="https://api.polygonscan.com/api",
        native_symbol="MATIC", api_key=api_key,
    )


def arbitrum_connector(api_key: str = "") -> EthLikeConnector:
    return EthLikeConnector(
        chain=Chain.ARBITRUM, chain_id=42161,
        api_base_url="https://api.arbiscan.io/api",
        native_symbol="ETH", api_key=api_key,
    )


def optimism_connector(api_key: str = "") -> EthLikeConnector:
    return EthLikeConnector(
        chain=Chain.OPTIMISM, chain_id=10,
        api_base_url="https://api-optimistic.etherscan.io/api",
        native_symbol="ETH", api_key=api_key,
    )


def base_connector(api_key: str = "") -> EthLikeConnector:
    return EthLikeConnector(
        chain=Chain.BASE, chain_id=8453,
        api_base_url="https://api.basescan.org/api",
        native_symbol="ETH", api_key=api_key,
    )


def avalanche_connector(api_key: str = "") -> EthLikeConnector:
    return EthLikeConnector(
        chain=Chain.AVALANCHE, chain_id=43114,
        api_base_url="https://api.snowtrace.io/api",
        native_symbol="AVAX", api_key=api_key,
    )
