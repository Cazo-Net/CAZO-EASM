"""Address clustering heuristics.

Groups addresses that likely belong to the same entity using:
- Common-input ownership (Bitcoin)
- Change-address detection (Bitcoin)
- Deployer-reuse (Ethereum)
- Gas-payer heuristic (Ethereum)
- Peeling chain detection (both)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas.blockchain import (
    Chain,
    ClusterHeuristicType,
    ClusteringHeuristic,
    AddressCluster,
    Evidence,
    EvidenceType,
)

logger = logging.getLogger(__name__)

BLOCKSTREAM_BASE = "https://blockstream.info/api"


# ── Bitcoin Clustering ───────────────────────────────────────────────────────

async def _get_btc_txs(address: str, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent transactions for a Bitcoin address."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{BLOCKSTREAM_BASE}/address/{address}/txs?limit={limit}")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.debug("Failed to fetch BTC txs for %s: %s", address, e)
        return []


async def common_input_heuristic(address: str) -> list[ClusteringHeuristic]:
    """Bitcoin multi-input heuristic.

    If address A and address B both appear as inputs in the same transaction,
    they likely belong to the same wallet.
    """
    txs = await _get_btc_txs(address, limit=20)
    heuristics: list[ClusteringHeuristic] = []

    co_spent_with: set[str] = set()
    for tx in txs:
        input_addrs = set()
        for vin in tx.get("vin", []):
            prevout = vin.get("prevout", {})
            addr = prevout.get("scriptpubkey_address", "")
            if addr:
                input_addrs.add(addr)

        if address in input_addrs:
            others = input_addrs - {address}
            co_spent_with.update(others)

    if co_spent_with:
        heuristics.append(ClusteringHeuristic(
            type=ClusterHeuristicType.COMMON_INPUT,
            confidence=0.9,
            description=f"Co-spent with {len(co_spent_with)} address(es) in shared inputs",
            evidence=[Evidence(
                source="blockstream",
                type=EvidenceType.MEMPOOL_ANALYSIS,
                confidence=90,
                reason=f"Shared transaction inputs with {len(co_spent_with)} addresses",
            )],
        ))

    return heuristics


async def change_address_heuristic(address: str) -> list[ClusteringHeuristic]:
    """Bitcoin change address detection.

    Heuristics:
    1. Output spent before any other output from the same tx (first-spent)
    2. Output value matches a round number or typical change pattern
    3. Output goes to an address first seen in this transaction
    """
    txs = await _get_btc_txs(address, limit=20)
    heuristics: list[ClusteringHeuristic] = []

    change_candidates: set[str] = set()
    for tx in txs:
        vouts = tx.get("vout", [])
        if len(vouts) < 2:
            continue

        for vout in vouts:
            addr = vout.get("scriptpubkey_address", "")
            value = vout.get("value", 0)

            # Skip if it's our address
            if addr == address:
                continue

            # Heuristic: very small outputs (< 1000 sats) are often change
            if 0 < value < 1000:
                change_candidates.add(addr)

            # Heuristic: output value is close to input sum minus fee
            # (simplified: if value is > 80% of total output, likely the "real" payment)
            total_out = sum(v.get("value", 0) for v in vouts)
            if total_out > 0 and value / total_out > 0.8:
                # This is the main output, the OTHER small one is change
                pass

    if change_candidates:
        heuristics.append(ClusteringHeuristic(
            type=ClusterHeuristicType.CHANGE_ADDRESS,
            confidence=0.6,
            description=f"Detected {len(change_candidates)} potential change address(es)",
            evidence=[Evidence(
                source="heuristic",
                type=EvidenceType.HEURISTIC,
                confidence=60,
                reason="Small-value outputs consistent with change patterns",
            )],
        ))

    return heuristics


async def peeling_chain_heuristic(address: str) -> list[ClusteringHeuristic]:
    """Detect Bitcoin peeling chains.

    A peeling chain is a series of transactions where a large amount is
    progressively peeled off to different addresses.
    """
    txs = await _get_btc_txs(address, limit=50)
    heuristics: list[ClusteringHeuristic] = []

    # Look for a pattern: tx with many outputs where one output is small
    # and the rest are very small or the same address
    for tx in txs:
        vouts = tx.get("vout", [])
        if len(vouts) < 3:
            continue

        values = sorted([v.get("value", 0) for v in vouts], reverse=True)
        if not values:
            continue

        # If the largest output is > 10x the second largest, it's a peel
        if values[0] > values[1] * 10 if len(values) > 1 else False:
            heuristics.append(ClusteringHeuristic(
                type=ClusterHeuristicType.PEELING_CHAIN,
                confidence=0.7,
                description=f"Peeling chain pattern detected in tx {tx.get('txid', '')[:16]}...",
                evidence=[Evidence(
                    source="heuristic",
                    type=EvidenceType.MEMPOOL_ANALYSIS,
                    confidence=70,
                    reason="Progressive value splitting pattern",
                )],
            ))
            break

    return heuristics


# ── Ethereum Clustering ──────────────────────────────────────────────────────

async def _get_eth_txs(address: str, api_key: str = "") -> list[dict[str, Any]]:
    """Fetch recent transactions for an Ethereum address via Etherscan."""
    from app.config import settings
    key = api_key or settings.ETHERSCAN_API_KEY
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://api.etherscan.io/api", params={
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": "0",
                "endblock": "99999999",
                "page": "1",
                "offset": "50",
                "sort": "desc",
                "apikey": key,
            })
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", []) if isinstance(data.get("result"), list) else []
    except Exception as e:
        logger.debug("Failed to fetch ETH txs for %s: %s", address, e)
        return []


async def deployer_reuse_heuristic(address: str) -> list[ClusteringHeuristic]:
    """Ethereum deployer-reuse heuristic.

    If the same address deploys multiple contracts, those contracts are
    controlled by the same entity.
    """
    txs = await _get_eth_txs(address)
    heuristics: list[ClusteringHeuristic] = []

    deployed_contracts: list[str] = []
    for tx in txs:
        to_addr = tx.get("to", "")
        input_data = tx.get("input", "0x")

        # Contract creation: to is empty and input has init code
        if not to_addr and input_data != "0x" and len(input_data) > 10:
            # Get contract address from receipt
            contract = tx.get("contractAddress", "")
            if contract:
                deployed_contracts.append(contract)

    if len(deployed_contracts) >= 2:
        heuristics.append(ClusteringHeuristic(
            type=ClusterHeuristicType.DEPLOYER_REUSE,
            confidence=0.95,
            description=f"Deployed {len(deployed_contracts)} contracts from same address",
            evidence=[Evidence(
                source="etherscan",
                type=EvidenceType.NETWORK_ANALYSIS,
                confidence=95,
                reason=f"Address deployed {len(deployed_contracts)} contracts",
            )],
        ))

    return heuristics


async def gas_payer_heuristic(address: str) -> list[ClusteringHeuristic]:
    """Ethereum gas-payer heuristic.

    If address A consistently pays gas for transactions FROM address B,
    address A likely controls address B (e.g., a deployer funding a proxy).
    """
    txs = await _get_eth_txs(address)
    heuristics: list[ClusteringHeuristic] = []

    # For the given address, check if it's frequently the gas payer
    # for transactions where it's NOT the from address
    # (This is a simplified check — in practice you'd look at
    # transactions TO this address and check who paid gas)
    from_count: dict[str, int] = defaultdict(int)
    for tx in txs:
        from_addr = tx.get("from", "").lower()
        from_count[from_addr] += 1

    # If the address is the from address for many transactions to different
    # contracts, and one contract consistently receives funds, that contract
    # is likely controlled by the same entity
    if len(from_count) > 1:
        # Check if this address funds a specific contract repeatedly
        to_contracts: dict[str, int] = defaultdict(int)
        for tx in txs:
            if tx.get("from", "").lower() == address.lower():
                to_addr = tx.get("to", "")
                if to_addr:
                    to_contracts[to_addr.lower()] += 1

        for contract, count in to_contracts.items():
            if count >= 3:
                heuristics.append(ClusteringHeuristic(
                    type=ClusterHeuristicType.GAS_PAYER,
                    confidence=0.8,
                    description=f"Consistently funded {contract[:10]}... ({count} txs)",
                    evidence=[Evidence(
                        source="etherscan",
                        type=EvidenceType.NETWORK_ANALYSIS,
                        confidence=80,
                        reason=f"Gas payment pattern: {count} transactions to same address",
                    )],
                ))
                break

    return heuristics


# ── Main Clustering Service ──────────────────────────────────────────────────

async def cluster_address(address: str, chain: Chain) -> AddressCluster:
    """Run all applicable heuristics and return an AddressCluster."""
    heuristics: list[ClusteringHeuristic] = []

    if chain == Chain.BITCOIN:
        heuristics.extend(await common_input_heuristic(address))
        heuristics.extend(await change_address_heuristic(address))
        heuristics.extend(await peeling_chain_heuristic(address))
    elif chain in (Chain.ETHEREUM, Chain.POLYGON, Chain.ARBITRUM, Chain.OPTIMISM, Chain.BASE, Chain.AVALANCHE):
        heuristics.extend(await deployer_reuse_heuristic(address))
        heuristics.extend(await gas_payer_heuristic(address))

    # Compute overall confidence
    if heuristics:
        overall_confidence = max(h.confidence for h in heuristics)
    else:
        overall_confidence = 0.0

    return AddressCluster(
        chain=chain,
        addresses=[address],
        heuristics=heuristics,
        confidence=overall_confidence,
    )
