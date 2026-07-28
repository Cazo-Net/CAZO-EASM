"""Base (Coinbase L2) provider — Etherscan-compatible API."""
from __future__ import annotations

from app.schemas.blockchain import Chain
from app.services.blockchain.providers.eth_base import EthEtherscanBaseProvider


class BaseProvider(EthEtherscanBaseProvider):
    """Base L2 provider using basescan.org API."""

    chain = Chain.BASE

    def __init__(self, api_key: str = "") -> None:
        super().__init__(
            api_base_url="https://api.basescan.org/api",
            chain_id=8453,
            native_symbol="ETH",
            native_decimals=18,
            api_key=api_key,
        )
