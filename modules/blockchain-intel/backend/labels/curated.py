"""Label dataset — curated entity labels for attribution.

Seed dataset with known exchange addresses, sanctions, and DeFi protocols.
In production, this would be loaded from a database or external file.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..domain.models.base import EntityCategory, EntityAttribution, Evidence, EvidenceType


# Curated label dataset
LABELS: list[dict[str, Any]] = [
    # Major exchanges (publicly disclosed hot/cold wallets)
    {
        "address": "0x28C6c06298d514Db089934071355E5743bf21d60",
        "chain": "ethereum",
        "entity": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(
                source="Binance public disclosure",
                type=EvidenceType.EXCHANGE_TAG,
                confidence=95,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Publicly disclosed Binance hot wallet",
            )
        ],
    },
    {
        "address": "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
        "chain": "ethereum",
        "entity": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(
                source="Binance public disclosure",
                type=EvidenceType.EXCHANGE_TAG,
                confidence=95,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Publicly disclosed Binance cold wallet",
            )
        ],
    },
    {
        "address": "0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43",
        "chain": "ethereum",
        "entity": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(
                source="Coinbase public disclosure",
                type=EvidenceType.EXCHANGE_TAG,
                confidence=95,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Publicly disclosed Coinbase hot wallet",
            )
        ],
    },
    {
        "address": "0x503828976D22510aad0201ac7EC88293211D23Da",
        "chain": "ethereum",
        "entity": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(
                source="Coinbase public disclosure",
                type=EvidenceType.EXCHANGE_TAG,
                confidence=95,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Publicly disclosed Coinbase cold wallet",
            )
        ],
    },
    {
        "address": "0x1151314c646Ce4E0eFD76d1aF4760aE66a9Fe30F",
        "chain": "ethereum",
        "entity": "Bitfinex",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(
                source="Bitfinex public disclosure",
                type=EvidenceType.EXCHANGE_TAG,
                confidence=95,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Publicly disclosed Bitfinex wallet",
            )
        ],
    },
    {
        "address": "0xDc76CD25977E0a5Ae17155770273aD58648900D3",
        "chain": "ethereum",
        "entity": "Kraken",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(
                source="Kraken public disclosure",
                type=EvidenceType.EXCHANGE_TAG,
                confidence=95,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Publicly disclosed Kraken wallet",
            )
        ],
    },
    # Stablecoin issuers
    {
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "chain": "ethereum",
        "entity": "Tether (USDT)",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(
                source="Etherscan verified contract",
                type=EvidenceType.VERIFIED_CONTRACT,
                confidence=100,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Official USDT ERC-20 contract",
            )
        ],
    },
    {
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "chain": "ethereum",
        "entity": "Circle (USDC)",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(
                source="Etherscan verified contract",
                type=EvidenceType.VERIFIED_CONTRACT,
                confidence=100,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Official USDC ERC-20 contract",
            )
        ],
    },
    # DeFi protocols
    {
        "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "chain": "ethereum",
        "entity": "Uniswap V2 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(
                source="Etherscan verified contract",
                type=EvidenceType.VERIFIED_CONTRACT,
                confidence=100,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Official Uniswap V2 Router contract",
            )
        ],
    },
    {
        "address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "chain": "ethereum",
        "entity": "Uniswap V3 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(
                source="Etherscan verified contract",
                type=EvidenceType.VERIFIED_CONTRACT,
                confidence=100,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Official Uniswap V3 Router contract",
            )
        ],
    },
    {
        "address": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
        "chain": "ethereum",
        "entity": "Aave V2 Lending Pool",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(
                source="Etherscan verified contract",
                type=EvidenceType.VERIFIED_CONTRACT,
                confidence=100,
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                reason="Official Aave V2 Lending Pool contract",
            )
        ],
    },
    # OFAC sanctioned addresses
    {
        "address": "0x8589427373D6D84E98730D7795D8f6f8731FDA16",
        "chain": "ethereum",
        "entity": "Lazarus Group (DPRK)",
        "category": EntityCategory.SANCTIONS,
        "confidence": 100,
        "evidence": [
            Evidence(
                source="OFAC SDN List",
                type=EvidenceType.SANCTIONS_LIST,
                confidence=100,
                timestamp=datetime(2023, 11, 1, tzinfo=timezone.utc),
                reason="Listed on OFAC SDN as DPRK-associated address",
            )
        ],
    },
    {
        "address": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
        "chain": "ethereum",
        "entity": "Sinbad.io Mixer",
        "category": EntityCategory.MIXING_SERVICE,
        "confidence": 85,
        "evidence": [
            Evidence(
                source="OFAC SDN List",
                type=EvidenceType.SANCTIONS_LIST,
                confidence=85,
                timestamp=datetime(2023, 11, 1, tzinfo=timezone.utc),
                reason="Listed as mixing service associated with Lazarus Group",
            )
        ],
    },
    # Known scam addresses (examples)
    {
        "address": "0x00000000219ab540356cBB839Cbe05303d7705Fa",
        "chain": "ethereum",
        "entity": "Ethereum 2.0 Deposit Contract",
        "category": EntityCategory.OTHER,
        "confidence": 100,
        "evidence": [
            Evidence(
                source="Etherscan verified contract",
                type=EvidenceType.VERIFIED_CONTRACT,
                confidence=100,
                timestamp=datetime(2020, 12, 1, tzinfo=timezone.utc),
                reason="Official Eth2 staking deposit contract",
            )
        ],
    },
]


def get_all_labels() -> list[dict[str, Any]]:
    """Return all curated labels."""
    return LABELS


def get_labels_by_chain(chain: str) -> list[dict[str, Any]]:
    """Return labels for a specific chain."""
    return [l for l in LABELS if l.get("chain") == chain]


def get_labels_by_entity(entity: str) -> list[dict[str, Any]]:
    """Return labels for a specific entity."""
    return [l for l in LABELS if l.get("entity", "").lower() == entity.lower()]


def search_labels(query: str) -> list[dict[str, Any]]:
    """Search labels by entity name or address."""
    query_lower = query.lower()
    return [
        l for l in LABELS
        if query_lower in l.get("entity", "").lower()
        or query_lower in l.get("address", "").lower()
    ]
