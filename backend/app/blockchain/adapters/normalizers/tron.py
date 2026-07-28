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


class TronNormalizer(Normalizer):
    chain = Chain.TRON

    def normalize_block(self, raw: dict) -> Block:
        header = raw.get("block_header", {}).get("raw_data", {})
        return Block(
            number=header.get("number", 0),
            chain=Chain.TRON,
            hash=raw.get("blockID", ""),
            parent_hash=header.get("parentHash"),
            timestamp=datetime.fromtimestamp(header.get("timestamp", 0) / 1000, tz=timezone.utc)
            if header.get("timestamp") else None,
            tx_count=len(raw.get("transactions", [])),
        )

    def normalize_transaction(self, raw: dict, chain: Chain | None = None) -> Transaction:
        raw_data = raw.get("raw_data", {})
        contract = raw_data.get("contract", [{}])[0]
        value = contract.get("value", {})

        ret = raw.get("ret", [{}])
        status = TransactionStatus.SUCCESS
        if ret and ret[0].get("contractRet") != "SUCCESS":
            status = TransactionStatus.FAILED

        return Transaction(
            hash=raw.get("txID", ""),
            chain=Chain.TRON,
            status=status,
            timestamp=datetime.fromtimestamp(raw_data.get("timestamp", 0) / 1000, tz=timezone.utc)
            if raw_data.get("timestamp") else None,
            from_address=value.get("owner_address", ""),
            to_address=value.get("to_address", ""),
            value=Amount(int(value.get("amount", 0)), AmountUnit.SUN),
            block_number=raw.get("block_number"),
        )

    def normalize_address(self, raw: dict) -> Address:
        return Address(
            hash=raw.get("address", ""),
            chain=Chain.TRON,
            wallet_type=WalletType.EOA,
            balance=Amount(int(raw.get("balance", "0")), AmountUnit.SUN),
            tx_count=raw.get("tx_count", 0),
        )

    def normalize_token_balance(self, raw: dict) -> TokenBalance:
        return TokenBalance(
            contract_address=raw.get("tokenId", ""),
            chain=Chain.TRON,
            symbol=raw.get("tokenAbbr", ""),
            name=raw.get("tokenName", ""),
            decimals=6,
        )

    def normalize_contract(self, raw: dict) -> Contract:
        return Contract(
            address=raw.get("address", ""),
            chain=Chain.TRON,
            name=raw.get("name", ""),
        )
