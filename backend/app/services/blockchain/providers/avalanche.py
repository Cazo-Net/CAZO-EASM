"""Avalanche C-Chain provider — Etherscan-compatible API."""
from __future__ import annotations

from app.schemas.blockchain import Chain
from app.services.blockchain.providers.eth_base import EthEtherscanBaseProvider


class AvalancheProvider(EthEtherscanBaseProvider):
    """Avalanche C-Chain provider using snowtrace.io API."""

    chain = Chain.AVALANCHE

    def __init__(self, api_key: str = "") -> None:
        super().__init__(
            api_base_url="https://api.snowtrace.io/api",
            chain_id=43114,
            native_symbol="AVAX",
            native_decimals=18,
            api_key=api_key,
        )
