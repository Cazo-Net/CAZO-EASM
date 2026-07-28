"""Polygon (MATIC) provider — Etherscan-compatible API."""
from __future__ import annotations

from app.schemas.blockchain import Chain
from app.services.blockchain.providers.eth_base import EthEtherscanBaseProvider


class PolygonProvider(EthEtherscanBaseProvider):
    """Polygon PoS chain provider using polygonscan.com API."""

    chain = Chain.POLYGON

    def __init__(self, api_key: str = "") -> None:
        super().__init__(
            api_base_url="https://api.polygonscan.com/api",
            chain_id=137,
            native_symbol="MATIC",
            native_decimals=18,
            api_key=api_key,
        )
