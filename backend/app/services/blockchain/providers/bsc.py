"""BNB Smart Chain provider — Etherscan-compatible API."""
from __future__ import annotations

from app.schemas.blockchain import Chain
from app.services.blockchain.providers.eth_base import EthEtherscanBaseProvider


class BSCProvider(EthEtherscanBaseProvider):
    """BNB Smart Chain provider using bscscan.com API."""

    chain = Chain.BNB

    def __init__(self, api_key: str = "") -> None:
        super().__init__(
            api_base_url="https://api.bscscan.com/api",
            chain_id=56,
            native_symbol="BNB",
            native_decimals=18,
            api_key=api_key,
        )
