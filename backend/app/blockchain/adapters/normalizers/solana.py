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


class SolanaNormalizer(Normalizer):
    chain = Chain.SOLANA

    def normalize_block(self, raw: dict) -> Block:
        return Block(
            number=raw.get("blockHeight", raw.get("slot", 0)),
            chain=Chain.SOLANA,
            hash=raw.get("blockhash", ""),
            parent_hash=raw.get("previousBlockhash"),
            timestamp=datetime.fromtimestamp(raw.get("blockTime", 0), tz=timezone.utc)
            if raw.get("blockTime") else None,
            tx_count=len(raw.get("transactions", [])),
        )

    def normalize_transaction(self, raw: dict, chain: Chain | None = None) -> Transaction:
        meta = raw.get("meta", {})
        status = TransactionStatus.SUCCESS if meta.get("err") is None else TransactionStatus.FAILED
        block_time = raw.get("blockTime")
        fee_lamports = meta.get("fee", 0)

        message = raw.get("transaction", {}).get("message", {})
        account_keys = message.get("accountKeys", [])
        from_addr = account_keys[0] if account_keys else ""
        to_addr = account_keys[1] if len(account_keys) > 1 else ""

        pre = meta.get("preBalances", [])
        post = meta.get("postBalances", [])
        value = 0
        if pre and post and len(pre) > 1:
            value = post[1] - pre[1]

        return Transaction(
            hash=raw.get("signature", raw.get("transaction", {}).get("signatures", [""])[0]),
            chain=Chain.SOLANA,
            status=status,
            block_number=raw.get("slot"),
            timestamp=datetime.fromtimestamp(block_time, tz=timezone.utc) if block_time else None,
            from_address=from_addr,
            to_address=to_addr,
            value=Amount(value, AmountUnit.LAMPORTS),
            fee=Amount(fee_lamports, AmountUnit.LAMPORTS) if fee_lamports else None,
            gas_used=meta.get("computeUnitsConsumed"),
            logs=[{"message": msg} for msg in meta.get("logMessages", [])],
        )

    def normalize_address(self, raw: dict) -> Address:
        return Address(
            hash=raw.get("address", ""),
            chain=Chain.SOLANA,
            wallet_type=WalletType.EOA,
            balance=Amount(int(raw.get("balance", "0")), AmountUnit.LAMPORTS),
            tx_count=raw.get("tx_count", 0),
        )

    def normalize_token_balance(self, raw: dict) -> TokenBalance:
        info = raw.get("info", {})
        token_amount = info.get("tokenAmount", {})
        return TokenBalance(
            contract_address=info.get("mint", ""),
            chain=Chain.SOLANA,
            balance=Amount(int(token_amount.get("amount", "0")), AmountUnit.LAMPORTS),
            decimals=token_amount.get("decimals", 0),
        )

    def normalize_contract(self, raw: dict) -> Contract:
        return Contract(
            address=raw.get("address", ""),
            chain=Chain.SOLANA,
            name=raw.get("owner", ""),
        )
