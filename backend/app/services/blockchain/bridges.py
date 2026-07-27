"""Cross-chain bridge tracking.

Identifies bridge contracts, traces hop paths, and correlates
deposits/withdrawals across chains.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas.blockchain import (
    BridgeHop,
    BridgeType,
    Chain,
    EntityCategory,
    Evidence,
    EvidenceType,
)
from app.services.blockchain.labels.curated import lookup_address

logger = logging.getLogger(__name__)

ETHERSCAN_BASE = "https://api.etherscan.io/api"
BLOCKSTREAM_BASE = "https://blockstream.info/api"


# ── Known Bridge Contracts ──────────────────────────────────────────────────

KNOWN_BRIDGES: list[dict[str, Any]] = [
    # Ethereum → L2 bridges
    {
        "source_chain": Chain.ETHEREUM,
        "dest_chain": Chain.ARBITRUM,
        "contract_address": "0x4Dbd4fc535Ac27206064B68FfCf827b0A60BAB3f",
        "bridge_type": BridgeType.LOCK_AND_MINT,
        "name": "Arbitrum Delayed Inbox",
    },
    {
        "source_chain": Chain.ETHEREUM,
        "dest_chain": Chain.OPTIMISM,
        "contract_address": "0x25ace71c97B33Cc4729CF772ae268934F7ab5fA1",
        "bridge_type": BridgeType.LOCK_AND_MINT,
        "name": "Optimism L1StandardBridge",
    },
    {
        "source_chain": Chain.ETHEREUM,
        "dest_chain": Chain.BASE,
        "contract_address": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
        "bridge_type": BridgeType.LOCK_AND_MINT,
        "name": "Base L1StandardBridge",
    },
    {
        "source_chain": Chain.ETHEREUM,
        "dest_chain": Chain.POLYGON,
        "contract_address": "0xA0c68C638235ee32657E8f720a23ceC1bFc5c282",
        "bridge_type": BridgeType.LOCK_AND_MINT,
        "name": "Polygon PoS Bridge (MaticToken)",
    },
    {
        "source_chain": Chain.ETHEREUM,
        "dest_chain": Chain.AVALANCHE,
        "contract_address": "0x8EB8a3b98659Cce2904028Ae3dff84dc57AE0919",
        "bridge_type": BridgeType.LOCK_AND_MINT,
        "name": "Avalanche Bridge",
    },
    # L2 → Ethereum bridges (withdrawal)
    {
        "source_chain": Chain.ARBITRUM,
        "dest_chain": Chain.ETHEREUM,
        "contract_address": "0x4Dbd4fc535Ac27206064B68FfCf827b0A60BAB3f",
        "bridge_type": BridgeType.BURN_AND_MINT,
        "name": "Arbitrum Delayed Inbox (withdrawal)",
    },
    {
        "source_chain": Chain.OPTIMISM,
        "dest_chain": Chain.ETHEREUM,
        "contract_address": "0x25ace71c97B33Cc4729CF772ae268934F7ab5fA1",
        "bridge_type": BridgeType.BURN_AND_MINT,
        "name": "Optimism L1StandardBridge (withdrawal)",
    },
    # Stablecoin bridges
    {
        "source_chain": Chain.ETHEREUM,
        "dest_chain": Chain.ARBITRUM,
        "contract_address": "0x3c44cdddb6a900fa2b586dd2520140948586c615",
        "bridge_type": BridgeType.LOCK_AND_MINT,
        "name": "USDC Bridge (Circle)",
    },
]


def get_known_bridges(
    source_chain: Chain | None = None,
    dest_chain: Chain | None = None,
) -> list[dict[str, Any]]:
    """Return known bridge contracts, optionally filtered by chain pair."""
    results = KNOWN_BRIDGES
    if source_chain:
        results = [b for b in results if b["source_chain"] == source_chain]
    if dest_chain:
        results = [b for b in results if b["dest_chain"] == dest_chain]
    return results


def is_bridge_address(address: str) -> bool:
    """Check if an address is a known bridge contract."""
    addr_lower = address.lower()
    return any(b["contract_address"].lower() == addr_lower for b in KNOWN_BRIDGES)


def get_bridge_info(address: str) -> dict[str, Any] | None:
    """Get bridge details for a known bridge address."""
    addr_lower = address.lower()
    for b in KNOWN_BRIDGES:
        if b["contract_address"].lower() == addr_lower:
            return {
                "source_chain": b["source_chain"],
                "dest_chain": b["dest_chain"],
                "bridge_type": b["bridge_type"],
                "name": b["name"],
            }
    return None


# ── Bridge Detection ─────────────────────────────────────────────────────────

async def detect_bridge_interactions(
    address: str, chain: Chain, limit: int = 50
) -> list[dict[str, Any]]:
    """Find transactions from an address that interact with known bridges."""
    interactions: list[dict[str, Any]] = []

    if chain == Chain.ETHEREUM:
        try:
            from app.config import settings
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(ETHERSCAN_BASE, params={
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": "0",
                    "endblock": "99999999",
                    "page": "1",
                    "offset": str(limit),
                    "sort": "desc",
                    "apikey": settings.ETHERSCAN_API_KEY,
                })
                resp.raise_for_status()
                data = resp.json()
                txs = data.get("result", []) if isinstance(data.get("result"), list) else []
        except Exception as e:
            logger.debug("Failed to fetch ETH txs for bridge detection: %s", e)
            return []

        for tx in txs:
            to_addr = tx.get("to", "").lower()
            for bridge in KNOWN_BRIDGES:
                if bridge["source_chain"] == Chain.ETHEREUM and bridge["contract_address"].lower() == to_addr:
                    interactions.append({
                        "tx_hash": tx.get("hash", ""),
                        "bridge_name": bridge["name"],
                        "dest_chain": bridge["dest_chain"],
                        "bridge_type": bridge["bridge_type"],
                        "value": str(int(tx.get("value", "0")) / 10**18),
                        "timestamp": datetime.fromtimestamp(
                            int(tx.get("timeStamp", 0)), tz=timezone.utc
                        ),
                    })
                    break

    return interactions


# ── Bridge Hop Tracing ───────────────────────────────────────────────────────

async def trace_bridge_hops(
    address: str, source_chain: Chain, depth: int = 3
) -> list[BridgeHop]:
    """Trace the flow of funds through bridge hops.

    Attempts to follow funds from the source chain through bridges
    to destination chains.
    """
    hops: list[BridgeHop] = []

    if depth <= 0:
        return hops

    # Get bridge interactions from this address
    interactions = await detect_bridge_interactions(address, source_chain)

    for ix in interactions[:5]:  # Limit to 5 hops
        hop = BridgeHop(
            source_chain=source_chain,
            source_tx=ix["tx_hash"],
            bridge_contract=ix.get("bridge_name", ""),
            dest_chain=ix["dest_chain"],
            amount=ix["value"],
            confidence=0.8,
            timestamp=ix.get("timestamp"),
            evidence=[
                Evidence(
                    source="etherscan",
                    type=EvidenceType.NETWORK_ANALYSIS,
                    confidence=85,
                    reason=f"Transaction to known bridge: {ix.get('bridge_name', 'unknown')}",
                )
            ],
        )
        hops.append(hop)

        # Try to trace further (recursive, but limited by depth)
        if depth > 1:
            # In production, you'd look for corresponding withdrawal on dest chain
            # For now, we just record the hop
            pass

    return hops


# ── Aggregate Bridge Stats ──────────────────────────────────────────────────

async def get_bridge_volume(
    address: str, source_chain: Chain
) -> dict[str, Any]:
    """Get aggregate bridge volume for an address."""
    interactions = await detect_bridge_interactions(address, source_chain, limit=200)

    volume_by_dest: dict[str, float] = {}
    tx_count = 0

    for ix in interactions:
        dest = ix["dest_chain"].value
        value = float(ix.get("value", "0"))
        volume_by_dest[dest] = volume_by_dest.get(dest, 0.0) + value
        tx_count += 1

    return {
        "address": address,
        "source_chain": source_chain.value,
        "total_bridge_txs": tx_count,
        "volume_by_dest_chain": volume_by_dest,
        "unique_dest_chains": list(volume_by_dest.keys()),
    }
