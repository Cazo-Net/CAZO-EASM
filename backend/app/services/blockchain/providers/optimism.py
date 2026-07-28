"""Optimism provider — Etherscan-compatible API."""
from __future__ import annotations

from app.schemas.blockchain import Chain
from app.services.blockchain.providers.eth_base import EthEtherscanBaseProvider


class OptimismProvider(EthEtherscanBaseProvider):
    """Optimism L2 provider using optimistic.etherscan.io API."""

    chain = Chain.OPTIMISM

    def __init__(self, api_key: str = "") -> None:
        super().__init__(
            api_base_url="https://api-optimistic.etherscan.io/api",
            chain_id=10,
            native_symbol="ETH",
            native_decimals=18,
            api_key=api_key,
        )
