from __future__ import annotations

from enum import Enum


class Chain(str, Enum):
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    BNB = "bnb"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    AVALANCHE = "avalanche"
    TRON = "tron"
    SOLANA = "solana"
    LITECOIN = "litecoin"

    def display_name(self) -> str:
        return self.value.replace("_", " ").title()

    def is_evm(self) -> bool:
        return self in {
            Chain.ETHEREUM, Chain.BNB, Chain.POLYGON,
            Chain.ARBITRUM, Chain.OPTIMISM, Chain.BASE, Chain.AVALANCHE,
        }
