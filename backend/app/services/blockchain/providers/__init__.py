"""Blockchain provider package."""
from app.services.blockchain.providers.base import ChainProvider, ProviderRegistry, registry
from app.services.blockchain.providers.ethereum import EthereumProvider
from app.services.blockchain.providers.bitcoin import BitcoinProvider
from app.services.blockchain.providers.solana import SolanaProvider
from app.services.blockchain.providers.polygon import PolygonProvider
from app.services.blockchain.providers.bsc import BSCProvider
from app.services.blockchain.providers.arbitrum import ArbitrumProvider
from app.services.blockchain.providers.optimism import OptimismProvider
from app.services.blockchain.providers.base_chain import BaseProvider
from app.services.blockchain.providers.avalanche import AvalancheProvider
from app.services.blockchain.providers.tron import TronProvider

# Auto-register providers on import
registry.register(EthereumProvider())
registry.register(BitcoinProvider())
registry.register(SolanaProvider())
registry.register(PolygonProvider())
registry.register(BSCProvider())
registry.register(ArbitrumProvider())
registry.register(OptimismProvider())
registry.register(BaseProvider())
registry.register(AvalancheProvider())
registry.register(TronProvider())

__all__ = [
    "ChainProvider",
    "ProviderRegistry",
    "registry",
    "EthereumProvider",
    "BitcoinProvider",
    "SolanaProvider",
    "PolygonProvider",
    "BSCProvider",
    "ArbitrumProvider",
    "OptimismProvider",
    "BaseProvider",
    "AvalancheProvider",
    "TronProvider",
]
