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


class BitcoinNormalizer(Normalizer):
    chain = Chain.BITCOIN

    def normalize_block(self, raw: dict) -> Block:
        return Block(
            number=raw.get("height", 0),
            chain=Chain.BITCOIN,
            hash=raw.get("id", ""),
            parent_hash=raw.get("previousblockhash"),
            timestamp=datetime.fromtimestamp(raw.get("timestamp", 0), tz=timezone.utc)
            if raw.get("timestamp") else None,
            tx_count=len(raw.get("tx", [])),
            size=raw.get("size"),
            difficulty=raw.get("difficulty"),
            miner=raw.get("extras", {}).get("miner", ""),
        )

    def normalize_transaction(self, raw: dict, chain: Chain | None = None) -> Transaction:
        status = TransactionStatus.SUCCESS if raw.get("status", {}).get("confirmed") else TransactionStatus.PENDING
        block_height = raw.get("status", {}).get("block_height")
        fee = raw.get("fee", 0)

        from_addrs = []
        for vin in raw.get("vin", []):
            addr = vin.get("prevout", {}).get("scriptpubkey_address", "")
            if addr:
                from_addrs.append(addr)

        to_addrs = []
        total_out = 0
        for vout in raw.get("vout", []):
            addr = vout.get("scriptpubkey_address", "")
            if addr:
                to_addrs.append(addr)
            total_out += vout.get("value", 0)

        return Transaction(
            hash=raw.get("txid", ""),
            chain=Chain.BITCOIN,
            status=status,
            block_number=block_height,
            timestamp=datetime.fromtimestamp(raw.get("status", {}).get("block_time", 0), tz=timezone.utc)
            if raw.get("status", {}).get("block_time") else None,
            from_address=", ".join(sorted(set(from_addrs))),
            to_address=", ".join(sorted(set(to_addrs))),
            value=Amount(total_out, AmountUnit.SATOSHI),
            fee=Amount(fee, AmountUnit.SATOSHI) if fee else None,
        )

    def normalize_address(self, raw: dict) -> Address:
        return Address(
            hash=raw.get("address", ""),
            chain=Chain.BITCOIN,
            wallet_type=WalletType.EOA,
            tx_count=raw.get("tx_count", 0),
        )

    def normalize_token_balance(self, raw: dict) -> TokenBalance:
        return TokenBalance(
            contract_address="", chain=Chain.BITCOIN, symbol="BTC", name="Bitcoin",
            decimals=8,
        )

    def normalize_contract(self, raw: dict) -> Contract:
        return Contract(address="", chain=Chain.BITCOIN)
