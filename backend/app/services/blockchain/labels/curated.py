"""Curated blockchain labels — single source of truth.

Each label includes:
- entity_name: human-readable entity
- category: EntityCategory enum value
- confidence: 0-100 score
- evidence: list of Evidence objects explaining the attribution
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.blockchain import (
    Chain,
    EntityAttribution,
    EntityCategory,
    Evidence,
    EvidenceType,
)

_LABELS: list[dict] = [
    # ── Binance ──────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x28C6c06298d514Db089934071355E5743bf21d60",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 98,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=98,
                     reason="Etherscan exchange label"),
            Evidence(source="on_chain", type=EvidenceType.BLOCKCHAIN_LABEL, confidence=95,
                     reason="High-volume hot wallet pattern"),
        ],
    },
    {
        "chain": Chain.ETHEREUM,
        "address": "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 98,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=98,
                     reason="Etherscan exchange label"),
        ],
    },
    {
        "chain": Chain.BITCOIN,
        "address": "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 99,
        "evidence": [
            Evidence(source="blockstream", type=EvidenceType.KNOWN_PUBLIC_WALLET, confidence=99,
                     reason="Known Binance hot wallet"),
            Evidence(source="on_chain", type=EvidenceType.BLOCKCHAIN_LABEL, confidence=95,
                     reason="Very high transaction volume"),
        ],
    },
    # ── Coinbase ─────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43",
        "entity_name": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 97,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=97,
                     reason="Etherscan exchange label"),
        ],
    },
    {
        "chain": Chain.BITCOIN,
        "address": "3Kzh9qAqVWQhEsfQz7zEQL1EuSx5tyNLNS",
        "entity_name": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 97,
        "evidence": [
            Evidence(source="blockstream", type=EvidenceType.KNOWN_PUBLIC_WALLET, confidence=97,
                     reason="Known Coinbase hot wallet"),
        ],
    },
    # ── Bitfinex ─────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x1151314c646Ce4E0eFD76d1aF4760aE66a9Fe30F",
        "entity_name": "Bitfinex",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=95,
                     reason="Etherscan exchange label"),
        ],
    },
    # ── Kraken ───────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
        "entity_name": "Kraken",
        "category": EntityCategory.EXCHANGE,
        "confidence": 96,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=96,
                     reason="Etherscan exchange label"),
        ],
    },
    # ── USDT (Tether) ───────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "entity_name": "Tether USD",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDT contract on Ethereum"),
        ],
    },
    # ── USDC (Circle) ────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "entity_name": "USD Coin",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDC contract on Ethereum"),
        ],
    },
    # ── Uniswap V2 ──────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "entity_name": "Uniswap V2 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Uniswap V2 Router02 contract"),
        ],
    },
    # ── Uniswap V3 ──────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "entity_name": "Uniswap V3 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Uniswap V3 SwapRouter contract"),
        ],
    },
    # ── Aave V2 ─────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
        "entity_name": "Aave V2 LendingPool",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Aave V2 LendingPool contract"),
        ],
    },
    # ── Lazarus Group (sanctioned) ───────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
        "entity_name": "Lazarus Group",
        "category": EntityCategory.SANCTIONS,
        "confidence": 95,
        "evidence": [
            Evidence(source="ofac", type=EvidenceType.SANCTIONS_LIST, confidence=95,
                     reason="OFAC sanctioned address associated with Lazarus Group"),
        ],
    },
    # ── Sinbad mixer ────────────────────────────────────────────────
    {
        "chain": Chain.BITCOIN,
        "address": "3FHNBLobJnbCTFTVakh5TXmEneyf5PT61B",
        "entity_name": "Sinbad Mixer",
        "category": EntityCategory.MIXING_SERVICE,
        "confidence": 90,
        "evidence": [
            Evidence(source="trellix", type=EvidenceType.PUBLIC_REPORT, confidence=90,
                     reason="Identified as Sinbad mixer output address by Trellix research"),
            Evidence(source="on_chain", type=EvidenceType.BLOCKCHAIN_LABEL, confidence=85,
                     reason="Known mixing service pattern"),
        ],
    },
]


def get_curated_labels(chain: Chain | None = None) -> list[EntityAttribution]:
    """Return all curated labels, optionally filtered by chain."""
    results: list[EntityAttribution] = []
    for entry in _LABELS:
        if chain is not None and entry["chain"] != chain:
            continue
        results.append(EntityAttribution(
            entity_name=entry["entity_name"],
            category=entry["category"],
            confidence=entry["confidence"],
            evidence=entry["evidence"],
        ))
    return results


def lookup_address(address: str) -> EntityAttribution | None:
    """Look up a single address across all chains."""
    for entry in _LABELS:
        if entry["address"].lower() == address.lower():
            return EntityAttribution(
                entity_name=entry["entity_name"],
                category=entry["category"],
                confidence=entry["confidence"],
                evidence=entry["evidence"],
            )
    return None


def get_all_addresses() -> dict[str, dict]:
    """Return a map of address -> label info for all curated labels."""
    return {
        entry["address"].lower(): {
            "chain": entry["chain"],
            "entity_name": entry["entity_name"],
            "category": entry["category"],
        }
        for entry in _LABELS
    }
