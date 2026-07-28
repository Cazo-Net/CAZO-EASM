from __future__ import annotations

from app.blockchain.adapters.collectors.eth_like import (
    ethereum_collector, bnb_collector, polygon_collector,
    arbitrum_collector, optimism_collector, base_collector, avalanche_collector,
)
from app.blockchain.adapters.collectors.bitcoin import BitcoinCollector
from app.blockchain.adapters.collectors.solana import SolanaCollector
from app.blockchain.adapters.collectors.tron import TronCollector
from app.blockchain.adapters.connectors.eth_like import (
    ethereum_connector, bnb_connector, polygon_connector,
    arbitrum_connector, optimism_connector, base_connector, avalanche_connector,
)
from app.blockchain.adapters.connectors.bitcoin import BitcoinConnector
from app.blockchain.adapters.connectors.solana import SolanaConnector
from app.blockchain.adapters.connectors.tron import TronConnector
from app.blockchain.adapters.normalizers.ethereum import EthereumNormalizer
from app.blockchain.adapters.normalizers.bitcoin import BitcoinNormalizer
from app.blockchain.adapters.normalizers.solana import SolanaNormalizer
from app.blockchain.adapters.normalizers.tron import TronNormalizer
from app.blockchain.domain.contracts.chain_connector import ChainConnector, Collector, Normalizer, GraphStore
from app.blockchain.domain.value_objects.chain import Chain
from app.blockchain.infrastructure.graph.address_store import (
    Neo4jAddressStore,
    Neo4jTransactionStore,
    Neo4jBlockStore,
)


class ConnectorRegistry:
    _connectors: dict[Chain, ChainConnector] = {}
    _collectors: dict[Chain, Collector] = {}
    _normalizers: dict[Chain, Normalizer] = {}
    _address_stores: dict[Chain, Neo4jAddressStore] = {}
    _tx_stores: dict[Chain, Neo4jTransactionStore] = {}
    _block_stores: dict[Chain, Neo4jBlockStore] = {}

    @classmethod
    def register(
        cls,
        chain: Chain,
        connector: ChainConnector | None = None,
        collector: Collector | None = None,
        normalizer: Normalizer | None = None,
    ) -> None:
        if connector:
            cls._connectors[chain] = connector
        if collector:
            cls._collectors[chain] = collector
        if normalizer:
            cls._normalizers[chain] = normalizer
        cls._address_stores[chain] = Neo4jAddressStore()
        cls._tx_stores[chain] = Neo4jTransactionStore()
        cls._block_stores[chain] = Neo4jBlockStore()

    @classmethod
    def get_connector(cls, chain: Chain) -> ChainConnector:
        if chain not in cls._connectors:
            raise ValueError(f"No connector registered for {chain}")
        return cls._connectors[chain]

    @classmethod
    def get_collector(cls, chain: Chain) -> Collector:
        if chain not in cls._collectors:
            raise ValueError(f"No collector registered for {chain}")
        return cls._collectors[chain]

    @classmethod
    def get_normalizer(cls, chain: Chain) -> Normalizer:
        if chain not in cls._normalizers:
            raise ValueError(f"No normalizer registered for {chain}")
        return cls._normalizers[chain]

    @classmethod
    def get_address_store(cls, chain: Chain) -> Neo4jAddressStore:
        if chain not in cls._address_stores:
            cls._address_stores[chain] = Neo4jAddressStore()
        return cls._address_stores[chain]

    @classmethod
    def get_tx_store(cls, chain: Chain) -> Neo4jTransactionStore:
        if chain not in cls._tx_stores:
            cls._tx_stores[chain] = Neo4jTransactionStore()
        return cls._tx_stores[chain]

    @classmethod
    def get_block_store(cls, chain: Chain) -> Neo4jBlockStore:
        if chain not in cls._block_stores:
            cls._block_stores[chain] = Neo4jBlockStore()
        return cls._block_stores[chain]

    @classmethod
    def available_chains(cls) -> list[Chain]:
        return list(cls._connectors.keys())

    @classmethod
    def has_connector(cls, chain: Chain) -> bool:
        return chain in cls._connectors

    @classmethod
    def has_collector(cls, chain: Chain) -> bool:
        return chain in cls._collectors

    @classmethod
    def has_normalizer(cls, chain: Chain) -> bool:
        return chain in cls._normalizers


def register_defaults() -> None:
    from app.config import settings

    api_key = getattr(settings, "ETHERSCAN_API_KEY", "")

    # EVM chains (Etherscan-compatible)
    evm_chains = [
        (Chain.ETHEREUM, ethereum_connector, ethereum_collector, EthereumNormalizer),
        (Chain.BNB, bnb_connector, bnb_collector, EthereumNormalizer),
        (Chain.POLYGON, polygon_connector, polygon_collector, EthereumNormalizer),
        (Chain.ARBITRUM, arbitrum_connector, arbitrum_collector, EthereumNormalizer),
        (Chain.OPTIMISM, optimism_connector, optimism_collector, EthereumNormalizer),
        (Chain.BASE, base_connector, base_collector, EthereumNormalizer),
        (Chain.AVALANCHE, avalanche_connector, avalanche_collector, EthereumNormalizer),
    ]
    for chain, ctor, col, norm in evm_chains:
        ConnectorRegistry.register(
            chain,
            connector=ctor(api_key=api_key),
            collector=col(api_key=api_key),
            normalizer=norm(),
        )

    # Non-EVM chains
    ConnectorRegistry.register(
        Chain.BITCOIN,
        connector=BitcoinConnector(),
        collector=BitcoinCollector(),
        normalizer=BitcoinNormalizer(),
    )
    ConnectorRegistry.register(
        Chain.SOLANA,
        connector=SolanaConnector(),
        collector=SolanaCollector(),
        normalizer=SolanaNormalizer(),
    )
    ConnectorRegistry.register(
        Chain.TRON,
        connector=TronConnector(api_key=getattr(settings, "TRONGRID_API_KEY", "")),
        collector=TronCollector(api_key=getattr(settings, "TRONGRID_API_KEY", "")),
        normalizer=TronNormalizer(),
    )
