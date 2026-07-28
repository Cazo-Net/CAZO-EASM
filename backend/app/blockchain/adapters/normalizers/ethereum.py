from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.blockchain.domain.contracts.chain_connector import Normalizer
from app.blockchain.domain.entities.block import Block
from app.blockchain.domain.entities.transaction import Transaction, TransactionStatus
from app.blockchain.domain.entities.address import Address, WalletType
from app.blockchain.domain.entities.token import TokenBalance, Contract
from app.blockchain.domain.value_objects.chain import Chain
from app.blockchain.domain.value_objects.amount import Amount, AmountUnit


class EthereumNormalizer(Normalizer):
    chain = Chain.ETHEREUM

    def normalize_block(self, raw: dict) -> Block:
        return Block(
            number=int(raw.get("number", "0x0"), 16),
            chain=Chain.ETHEREUM,
            hash=raw.get("hash", ""),
            parent_hash=raw.get("parentHash"),
            timestamp=datetime.fromtimestamp(
                int(raw.get("timestamp", "0x0"), 16), tz=timezone.utc,
            ) if raw.get("timestamp") else None,
            tx_count=len(raw.get("transactions", [])),
            gas_limit=int(raw.get("gasLimit", "0x0"), 16),
            gas_used=int(raw.get("gasUsed", "0x0"), 16),
            miner=raw.get("miner", ""),
            size=int(raw.get("size", "0x0"), 16),
            difficulty=int(raw.get("difficulty", "0x0"), 16),
            total_difficulty=int(raw.get("totalDifficulty", "0x0"), 16),
        )

    def normalize_transaction(self, raw: dict, chain: Chain | None = None) -> Transaction:
        value_wei = int(raw.get("value", "0x0"), 16)
        gas_price_val = int(raw.get("gasPrice", "0x0"), 16) if raw.get("gasPrice") else 0
        return Transaction(
            hash=raw.get("hash", ""),
            chain=chain or Chain.ETHEREUM,
            block_number=int(raw.get("blockNumber", "0x0"), 16) if raw.get("blockNumber") else None,
            timestamp=datetime.fromtimestamp(
                int(raw.get("timeStamp", "0x0"), 16), tz=timezone.utc,
            ) if raw.get("timeStamp") else None,
            from_address=raw.get("from", ""),
            to_address=raw.get("to", ""),
            value=Amount(value_wei, AmountUnit.WEI),
            fee=Amount(gas_price_val, AmountUnit.WEI),
            gas_price=gas_price_val,
            gas_used=int(raw.get("gas", "0x0"), 16) if raw.get("gas") else None,
            nonce=int(raw.get("nonce", "0x0"), 16),
            input_data=raw.get("input", "0x"),
            status=(
                TransactionStatus.SUCCESS
                if raw.get("isError") == "0"
                else TransactionStatus.FAILED if raw.get("isError")
                else TransactionStatus.PENDING
            ),
        )

    def normalize_address(self, raw: dict) -> Address:
        return Address(
            hash=raw.get("address", ""),
            chain=Chain.ETHEREUM,
            wallet_type=WalletType.CONTRACT if raw.get("is_contract") else WalletType.EOA,
            balance=Amount(int(raw.get("balance", "0")), AmountUnit.WEI),
            tx_count=raw.get("tx_count", 0),
        )

    def normalize_token_balance(self, raw: dict) -> TokenBalance:
        return TokenBalance(
            contract_address=raw.get("contractAddress", ""),
            chain=Chain.ETHEREUM,
            symbol=raw.get("symbol", ""),
            name=raw.get("name", ""),
            decimals=raw.get("decimals", 18),
        )

    def normalize_contract(self, raw: dict) -> Contract:
        return Contract(
            address=raw.get("address", ""),
            chain=Chain.ETHEREUM,
            name=raw.get("name", ""),
            symbol=raw.get("symbol", ""),
            verified=raw.get("verified", False),
            decimals=raw.get("decimals"),
        )
