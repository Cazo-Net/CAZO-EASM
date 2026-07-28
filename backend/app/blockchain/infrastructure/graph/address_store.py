from __future__ import annotations

import logging

from ...domain.entities.address import Address
from ...domain.entities.transaction import Transaction
from ...domain.entities.token import TokenBalance, Contract
from ...domain.entities.block import Block
from ...domain.value_objects.chain import Chain
from .neo4j_driver import driver

logger = logging.getLogger(__name__)


class Neo4jAddressStore:
    async def upsert(self, address: Address) -> None:
        if not driver.is_connected:
            return
        await driver.run_write(
            """
            MERGE (a:Address {hash: $hash})
            SET a.chain = $chain,
                a.wallet_type = $wallet_type,
                a.first_seen_block = $first_seen_block,
                a.first_seen_at = $first_seen_at,
                a.last_active_at = $last_active_at,
                a.tx_count = $tx_count,
                a.balance = $balance,
                a.token_count = $token_count,
                a.nft_count = $nft_count,
                a.is_contract = $is_contract,
                a.entity_name = $entity_name,
                a.labels = $labels,
                a.updated_at = timestamp()
            """,
            hash=address.normalized_hash(),
            chain=address.chain.value,
            wallet_type=address.wallet_type.value,
            first_seen_block=address.first_seen_block,
            first_seen_at=address.first_seen_at.isoformat() if address.first_seen_at else None,
            last_active_at=address.last_active_at.isoformat() if address.last_active_at else None,
            tx_count=address.tx_count,
            balance=str(address.balance.value) if address.balance else "0",
            token_count=address.token_count,
            nft_count=address.nft_count,
            is_contract=address.is_contract,
            entity_name=address.entity_name,
            labels=address.labels,
        )

    async def get(self, hash: str, chain: Chain) -> Address | None:
        if not driver.is_connected:
            return None
        results = await driver.run(
            "MATCH (a:Address {hash: $hash}) RETURN a",
            hash=hash.lower() if hash.startswith("0x") else hash,
        )
        if not results:
            return None
        data = results[0].get("a", {})
        return Address(
            hash=data.get("hash", hash),
            chain=Chain(data.get("chain", chain.value)),
            wallet_type=data.get("wallet_type", "unknown"),
            first_seen_block=data.get("first_seen_block"),
            first_seen_at=data.get("first_seen_at"),
            last_active_at=data.get("last_active_at"),
            tx_count=data.get("tx_count", 0),
            balance=data.get("balance", "0"),
            token_count=data.get("token_count", 0),
            nft_count=data.get("nft_count", 0),
            is_contract=data.get("is_contract", False),
            entity_name=data.get("entity_name"),
            labels=data.get("labels", []),
        )

    async def link_transaction(self, tx_hash: str, address_hash: str, role: str) -> None:
        if not driver.is_connected:
            return
        rel_type = "SENT" if role == "from" else "RECEIVED"
        await driver.run_write(
            f"""
            MATCH (a:Address {{hash: $address_hash}})
            MATCH (t:Transaction {{hash: $tx_hash}})
            MERGE (a)-[:{rel_type}]->(t)
            """,
            address_hash=address_hash,
            tx_hash=tx_hash,
        )


class Neo4jTransactionStore:
    async def upsert(self, tx: Transaction) -> None:
        if not driver.is_connected:
            return
        await driver.run_write(
            """
            MERGE (t:Transaction {hash: $hash, chain: $chain})
            SET t.block_number = $block_number,
                t.timestamp = $timestamp,
                t.from_address = $from_address,
                t.to_address = $to_address,
                t.value = $value,
                t.fee = $fee,
                t.status = $status,
                t.gas_price = $gas_price,
                t.gas_used = $gas_used,
                t.nonce = $nonce,
                t.method = $method,
                t.is_contract_creation = $is_contract_creation,
                t.error = $error,
                t.updated_at = timestamp()
            """,
            hash=tx.hash,
            chain=tx.chain.value,
            block_number=tx.block_number,
            timestamp=tx.timestamp.isoformat() if tx.timestamp else None,
            from_address=tx.from_address,
            to_address=tx.to_address,
            value=str(tx.value) if tx.value else "0",
            fee=str(tx.fee) if tx.fee else None,
            status=tx.status.value,
            gas_price=tx.gas_price,
            gas_used=tx.gas_used,
            nonce=tx.nonce,
            method=tx.method,
            is_contract_creation=tx.is_contract_creation,
            error=tx.error,
        )

    async def get(self, hash: str, chain: Chain) -> Transaction | None:
        if not driver.is_connected:
            return None
        results = await driver.run(
            "MATCH (t:Transaction {hash: $hash, chain: $chain}) RETURN t",
            hash=hash, chain=chain.value,
        )
        if not results:
            return None
        data = results[0].get("t", {})
        return Transaction(
            hash=data.get("hash", hash),
            chain=Chain(data.get("chain", chain.value)),
            block_number=data.get("block_number"),
            timestamp=data.get("timestamp"),
            from_address=data.get("from_address"),
            to_address=data.get("to_address"),
            value=data.get("value"),
            fee=data.get("fee"),
            status=data.get("status", "pending"),
            gas_price=data.get("gas_price"),
            gas_used=data.get("gas_used"),
            nonce=data.get("nonce"),
            method=data.get("method"),
        )

    async def get_for_address(
        self, address: str, chain: Chain, limit: int = 50, offset: int = 0
    ) -> list[Transaction]:
        if not driver.is_connected:
            return []
        results = await driver.run(
            """
            MATCH (t:Transaction {chain: $chain})
            WHERE t.from_address = $address OR t.to_address = $address
            RETURN t
            ORDER BY t.timestamp DESC
            SKIP $offset LIMIT $limit
            """,
            chain=chain.value, address=address, offset=offset, limit=limit,
        )
        return [
            Transaction(
                hash=r["t"].get("hash", ""),
                chain=chain,
                block_number=r["t"].get("block_number"),
                timestamp=r["t"].get("timestamp"),
                from_address=r["t"].get("from_address"),
                to_address=r["t"].get("to_address"),
                value=r["t"].get("value"),
                fee=r["t"].get("fee"),
                status=r["t"].get("status", "pending"),
            )
            for r in results
        ]


class Neo4jBlockStore:
    async def upsert(self, block: Block) -> None:
        if not driver.is_connected:
            return
        await driver.run_write(
            """
            MERGE (b:Block {chain: $chain, number: $number})
            SET b.hash = $hash,
                b.parent_hash = $parent_hash,
                b.timestamp = $timestamp,
                b.tx_count = $tx_count,
                b.size = $size,
                b.gas_limit = $gas_limit,
                b.gas_used = $gas_used,
                b.miner = $miner,
                b.updated_at = timestamp()
            """,
            chain=block.chain.value,
            number=block.number,
            hash=block.hash,
            parent_hash=block.parent_hash,
            timestamp=block.timestamp.isoformat() if block.timestamp else None,
            tx_count=block.tx_count,
            size=block.size,
            gas_limit=block.gas_limit,
            gas_used=block.gas_used,
            miner=block.miner,
        )

    async def get(self, number: int, chain: Chain) -> Block | None:
        if not driver.is_connected:
            return None
        results = await driver.run(
            "MATCH (b:Block {chain: $chain, number: $number}) RETURN b",
            chain=chain.value, number=number,
        )
        if not results:
            return None
        data = results[0].get("b", {})
        return Block(
            number=data.get("number", number),
            chain=chain,
            hash=data.get("hash", ""),
            parent_hash=data.get("parent_hash"),
            timestamp=data.get("timestamp"),
            tx_count=data.get("tx_count", 0),
            size=data.get("size"),
            gas_limit=data.get("gas_limit"),
            gas_used=data.get("gas_used"),
            miner=data.get("miner"),
        )
