"""Bitcoin provider using Blockstream.info public API."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas.blockchain import (
    Chain,
    ContractDetail,
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

BLOCKSTREAM_BASE = "https://blockstream.info/api"


class BitcoinProvider(ChainProvider):
    chain = Chain.BITCOIN

    def __init__(self) -> None:
        self._last_request = 0.0

    def is_available(self) -> bool:
        return True

    async def _throttle(self) -> None:
        """Rate-limit requests to ~3 per second."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < 0.33:
            await asyncio.sleep(0.33 - elapsed)
        self._last_request = asyncio.get_event_loop().time()

    async def _get(self, path: str) -> Any:
        await self._throttle()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(f"{BLOCKSTREAM_BASE}{path}")
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                continue
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                last_error = exc
                break
        logger.warning("Blockstream unavailable: %s", last_error)
        raise DataSourceUnavailable(
            Chain.BITCOIN, "upstream_error",
            "Blockstream did not answer, so no live Bitcoin data is shown. Try again shortly.",
        ) from last_error

    async def _get_first_tx_time(self, address: str) -> datetime | None:
        """Fetch the earliest transaction time for an address."""
        try:
            txs = await self._get(f"/address/{address}/txs")
            if not isinstance(txs, list) or not txs:
                return None
            timestamps = []
            for tx in txs:
                bt = tx.get("status", {}).get("block_time")
                if bt:
                    timestamps.append(bt)
            if timestamps:
                return datetime.fromtimestamp(min(timestamps), tz=timezone.utc)
        except Exception:
            pass
        return None

    # ── Wallet ───────────────────────────────────────────────────────────

    async def get_wallet_summary(self, address: str) -> WalletSummary:
        try:
            addr_info = await self._get(f"/address/{address}")
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 400:
                raise ValueError("That is not a valid Bitcoin address.") from exc
            raise DataSourceUnavailable(
                Chain.BITCOIN, "upstream_error",
                "Blockstream returned an error, so no live Bitcoin data is shown. Try again shortly.",
            ) from exc

        stats = addr_info.get("chain_stats", {})
        mempool = addr_info.get("mempool_stats", {})
        funded = stats.get("funded_txo_sum", 0)
        spent = stats.get("spent_txo_sum", 0)
        balance_sat = funded - spent
        tx_count = stats.get("tx_count", 0)

        wallet_type = WalletType.UNKNOWN
        if stats.get("p2pkh", 0) + stats.get("p2sh", 0) + stats.get("bech32", 0) + stats.get("p2tr", 0) > 0:
            wallet_type = WalletType.EOA

        first_seen = None
        last_active = None

        try:
            txs = await self._get(f"/address/{address}/txs")
            if isinstance(txs, list) and txs:
                confirmed_txs = [tx for tx in txs if tx.get("status", {}).get("confirmed")]
                if confirmed_txs:
                    timestamps = [tx["status"]["block_time"] for tx in confirmed_txs if tx.get("status", {}).get("block_time")]
                    if timestamps:
                        last_active = datetime.fromtimestamp(max(timestamps), tz=timezone.utc)
                        # The endpoint returns only the newest transactions, so
                        # the oldest one here is the real first one only when
                        # it covers the whole history.
                        if len(confirmed_txs) >= tx_count:
                            first_seen = datetime.fromtimestamp(min(timestamps), tz=timezone.utc)
        except Exception:
            pass

        return WalletSummary(
            address=address,
            chain=Chain.BITCOIN,
            wallet_type=wallet_type,
            balance=str(balance_sat / 10**8),
            tx_count=tx_count,
            first_seen=first_seen,
            last_active=last_active,
            inbound_volume=str(funded / 10**8),
            outbound_volume=str(spent / 10**8),
            net_flow=str((funded - spent) / 10**8),
        )

    # ── Transactions ─────────────────────────────────────────────────────

    async def get_transactions(
        self, address: str, page: int = 1, page_size: int = 20
    ) -> list[TransactionSummary]:
        try:
            txs = await self._get(f"/address/{address}/txs")
        except httpx.HTTPStatusError:
            return []
        if not isinstance(txs, list):
            return []

        start = (page - 1) * page_size
        page_txs = txs[start : start + page_size]

        summaries = []
        for tx in page_txs:
            status = TransactionStatus.SUCCESS if tx.get("status", {}).get("confirmed", False) else TransactionStatus.PENDING
            block_height = tx.get("status", {}).get("block_height")

            value_out = sum(
                vout.get("value", 0)
                for vout in tx.get("vout", [])
            )

            fee = tx.get("fee", 0)

            from_addrs = []
            for vin in tx.get("vin", []):
                prevout = vin.get("prevout", {})
                addr = prevout.get("scriptpubkey_address", "")
                if addr:
                    from_addrs.append(addr)

            to_addrs = []
            for vout in tx.get("vout", []):
                addr = vout.get("scriptpubkey_address", "")
                if addr:
                    to_addrs.append(addr)

            summaries.append(TransactionSummary(
                hash=tx.get("txid", ""),
                chain=Chain.BITCOIN,
                status=status,
                block_number=block_height,
                timestamp=datetime.fromtimestamp(tx.get("status", {}).get("block_time", 0), tz=timezone.utc) if tx.get("status", {}).get("block_time") else None,
                from_address=", ".join(set(from_addrs)),
                to_address=", ".join(set(to_addrs)),
                value=str(value_out / 10**8),
                fee=str(fee / 10**8),
            ))
        return summaries

    async def get_transaction(self, tx_hash: str) -> TransactionDetail:
        tx = await self._get(f"/tx/{tx_hash}")

        status = TransactionStatus.SUCCESS if tx.get("status", {}).get("confirmed", False) else TransactionStatus.PENDING
        block_height = tx.get("status", {}).get("block_height")
        fee = tx.get("fee", 0)

        from_addrs = []
        for vin in tx.get("vin", []):
            prevout = vin.get("prevout", {})
            addr = prevout.get("scriptpubkey_address", "")
            if addr:
                from_addrs.append(addr)

        to_addrs = []
        total_out = 0
        for vout in tx.get("vout", []):
            addr = vout.get("scriptpubkey_address", "")
            if addr:
                to_addrs.append(addr)
            total_out += vout.get("value", 0)

        return TransactionDetail(
            hash=tx_hash,
            chain=Chain.BITCOIN,
            status=status,
            block_number=block_height,
            timestamp=datetime.fromtimestamp(tx.get("status", {}).get("block_time", 0), tz=timezone.utc) if tx.get("status", {}).get("block_time") else None,
            from_address=", ".join(set(from_addrs)),
            to_address=", ".join(set(to_addrs)),
            value=str(total_out / 10**8),
            fee=str(fee / 10**8),
            input_data="",
            nonce=None,
        )

    # ── Tokens ───────────────────────────────────────────────────────────

    async def get_token_balances(self, address: str) -> list[TokenBalance]:
        return []

    # ── Contract ─────────────────────────────────────────────────────────

    async def get_contract_detail(self, address: str) -> ContractDetail | None:
        return None

    # ── Risk ─────────────────────────────────────────────────────────────

    async def get_risk_score(self, address: str) -> RiskScore:
        score = 10
        factors: list[RiskFactor] = []

        try:
            addr_info = await self._get(f"/address/{address}")
        except httpx.HTTPStatusError:
            return RiskScore(address=address, chain=Chain.BITCOIN, score=score, band=RiskBand.UNKNOWN, factors=factors)

        stats = addr_info.get("chain_stats", {})
        tx_count = stats.get("tx_count", 0)
        balance_sat = stats.get("funded_txo_sum", 0) - stats.get("spent_txo_sum", 0)
        balance_btc = balance_sat / 10**8

        if tx_count == 0:
            score += 10
            factors.append(RiskFactor(
                category="activity", label="No transactions found", weight=1.0, contribution=10,
            ))

        if tx_count > 10000:
            score += 10
            factors.append(RiskFactor(
                category="activity", label="Very high transaction count", weight=1.5, contribution=10,
            ))

        if balance_btc > 100:
            score += 5
            factors.append(RiskFactor(
                category="balance", label="High balance (>100 BTC)", weight=1.0, contribution=5,
            ))

        if balance_btc > 1000:
            score += 10
            factors.append(RiskFactor(
                category="balance", label="Very high balance (>1000 BTC)", weight=2.0, contribution=10,
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
            chain=Chain.BITCOIN,
            score=score,
            band=band,
            factors=factors,
        )

    # ── Graph ────────────────────────────────────────────────────────────

    async def get_graph_data(
        self, address: str, depth: int = 2, limit: int = 50
    ) -> GraphData:
        try:
            txs = await self._get(f"/address/{address}/txs")
        except httpx.HTTPStatusError:
            return GraphData()

        if not isinstance(txs, list):
            return GraphData()

        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []
        total_volume = 0.0

        nodes[address] = GraphNode(id=address, chain=Chain.BITCOIN, label="center")

        for tx in txs[:limit]:
            for vin in tx.get("vin", []):
                prevout = vin.get("prevout", {})
                from_addr = prevout.get("scriptpubkey_address", "")
                if from_addr:
                    if from_addr not in nodes:
                        nodes[from_addr] = GraphNode(id=from_addr, chain=Chain.BITCOIN)

            for vout in tx.get("vout", []):
                to_addr = vout.get("scriptpubkey_address", "")
                if to_addr:
                    if to_addr not in nodes:
                        nodes[to_addr] = GraphNode(id=to_addr, chain=Chain.BITCOIN)
                    total_volume += vout.get("value", 0) / 10**8

            from_set = {
                vin.get("prevout", {}).get("scriptpubkey_address", "")
                for vin in tx.get("vin", [])
                if vin.get("prevout", {}).get("scriptpubkey_address")
            }
            to_set = {
                vout.get("scriptpubkey_address", "")
                for vout in tx.get("vout", [])
                if vout.get("scriptpubkey_address")
            }

            tx_value = sum(v.get("value", 0) for v in tx.get("vout", [])) / 10**8
            for f in from_set:
                for t in to_set:
                    edges.append(GraphEdge(
                        source=f, target=t,
                        value=str(tx_value),
                        tx_count=1,
                    ))

        return GraphData(
            nodes=list(nodes.values()),
            edges=edges,
            total_volume=str(total_volume),
        )
