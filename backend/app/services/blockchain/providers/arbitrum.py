"""Arbitrum One provider — Etherscan-compatible API."""
from __future__ import annotations

from app.schemas.blockchain import Chain
from app.services.blockchain.providers.eth_base import EthEtherscanBaseProvider


class ArbitrumProvider(EthEtherscanBaseProvider):
    """Arbitrum One L2 provider using arbiscan.com API."""

    chain = Chain.ARBITRUM

    def __init__(self, api_key: str = "") -> None:
        super().__init__(
            api_base_url="https://api.arbiscan.com/api",
            chain_id=42161,
            native_symbol="ETH",
            native_decimals=18,
            api_key=api_key,
        )
