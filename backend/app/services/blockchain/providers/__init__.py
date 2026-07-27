"""Blockchain provider package."""
from app.services.blockchain.providers.base import ChainProvider, ProviderRegistry, registry
from app.services.blockchain.providers.ethereum import EthereumProvider
from app.services.blockchain.providers.bitcoin import BitcoinProvider

# Auto-register providers on import
registry.register(EthereumProvider())
registry.register(BitcoinProvider())

__all__ = [
    "ChainProvider",
    "ProviderRegistry",
    "registry",
    "EthereumProvider",
    "BitcoinProvider",
]
