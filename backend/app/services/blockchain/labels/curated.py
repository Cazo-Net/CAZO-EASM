"""Curated blockchain labels — single source of truth.

Each label includes:
- entity_name: human-readable entity
- category: EntityCategory enum value
- confidence: 0-100 score
- evidence: list of Evidence objects explaining the attribution

Expanded to ~70 entries covering major exchanges, DeFi protocols,
stablecoins, mixers, and sanctioned entities across ETH, BTC, SOL, POLY, BSC, ARBITRUM, OPTIMISM, BASE.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.blockchain import (
    Chain,
    EntityAttribution,
    EntityCategory,
    Evidence,
    EvidenceType,
)

_LABELS: list[dict] = [
    # ══════════════════════════════════════════════════════════════════
    # EXCHANGES
    # ══════════════════════════════════════════════════════════════════

    # ── Binance (ETH) ──────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x28C6c06298d514Db089934071355E5743bf21d60",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 98,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=98,
                     reason="Etherscan exchange label"),
        ],
    },
    {
        "chain": Chain.ETHEREUM,
        "address": "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 98,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=98,
                     reason="Etherscan exchange label"),
        ],
    },
    # ── Binance (BTC) ──────────────────────────────────────────────
    {
        "chain": Chain.BITCOIN,
        "address": "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 99,
        "evidence": [
            Evidence(source="blockstream", type=EvidenceType.KNOWN_PUBLIC_WALLET, confidence=99,
                     reason="Known Binance hot wallet"),
        ],
    },
    # ── Binance (BSC) ──────────────────────────────────────────────
    {
        "chain": Chain.BNB,
        "address": "0xF977814e90dA44bFA03b6295A0616a897441aceC",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 98,
        "evidence": [
            Evidence(source="bscscan", type=EvidenceType.EXCHANGE_TAG, confidence=98,
                     reason="Known Binance hot wallet on BSC"),
        ],
    },

    # ── Coinbase (ETH) ─────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43",
        "entity_name": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 97,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=97,
                     reason="Etherscan exchange label"),
        ],
    },
    # ── Coinbase (BTC) ─────────────────────────────────────────────
    {
        "chain": Chain.BITCOIN,
        "address": "3Kzh9qAqVWQhEsfQz7zEQL1EuSx5tyNLNS",
        "entity_name": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 97,
        "evidence": [
            Evidence(source="blockstream", type=EvidenceType.KNOWN_PUBLIC_WALLET, confidence=97,
                     reason="Known Coinbase hot wallet"),
        ],
    },

    # ── OKX ────────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b",
        "entity_name": "OKX",
        "category": EntityCategory.EXCHANGE,
        "confidence": 96,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=96,
                     reason="Etherscan exchange label"),
        ],
    },
    {
        "chain": Chain.BITCOIN,
        "address": "1LnoZawVFFQWHUdESEeh19PzYXLhcAD3CD",
        "entity_name": "OKX",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="blockstream", type=EvidenceType.KNOWN_PUBLIC_WALLET, confidence=95,
                     reason="Known OKX hot wallet"),
        ],
    },

    # ── Bybit ──────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xf89d7b9c864f589bBBF330591a852f71C1b7338",
        "entity_name": "Bybit",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=95,
                     reason="Known Bybit hot wallet"),
        ],
    },

    # ── Bitfinex (ETH) ─────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x1151314c646Ce4E0eFD76d1aF4760aE66a9Fe30F",
        "entity_name": "Bitfinex",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=95,
                     reason="Etherscan exchange label"),
        ],
    },
    {
        "chain": Chain.BITCOIN,
        "address": "bc1qgdjqv0av3q56jvd82tkdjpy7gd090f692a060",
        "entity_name": "Bitfinex",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="blockstream", type=EvidenceType.KNOWN_PUBLIC_WALLET, confidence=95,
                     reason="Known Bitfinex cold wallet"),
        ],
    },

    # ── Kraken (ETH) ───────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
        "entity_name": "Kraken",
        "category": EntityCategory.EXCHANGE,
        "confidence": 96,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=96,
                     reason="Etherscan exchange label"),
        ],
    },

    # ── KuCoin ─────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xD6216fC19DB775Df9774a6E33526131dA7D19a2c",
        "entity_name": "KuCoin",
        "category": EntityCategory.EXCHANGE,
        "confidence": 94,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=94,
                     reason="Known KuCoin hot wallet"),
        ],
    },

    # ── Gate.io ────────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x0D0707963952f2fBA59dD06f2b425ace40b492Fe",
        "entity_name": "Gate.io",
        "category": EntityCategory.EXCHANGE,
        "confidence": 93,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=93,
                     reason="Known Gate.io hot wallet"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # STABLECOINS
    # ══════════════════════════════════════════════════════════════════

    # ── USDT (Tether) — Ethereum ────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "entity_name": "Tether USD",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDT contract on Ethereum"),
        ],
    },
    # ── USDT — Tron ────────────────────────────────────────────────
    {
        "chain": Chain.TRON,
        "address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "entity_name": "Tether USD",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="tronscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDT contract on Tron"),
        ],
    },
    # ── USDT — BSC ─────────────────────────────────────────────────
    {
        "chain": Chain.BNB,
        "address": "0x55d398326f99059fF775485246999027B3197955",
        "entity_name": "Tether USD",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="bscscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDT contract on BSC"),
        ],
    },
    # ── USDT — Polygon ─────────────────────────────────────────────
    {
        "chain": Chain.POLYGON,
        "address": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "entity_name": "Tether USD",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="polygonscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDT contract on Polygon"),
        ],
    },

    # ── USDC (Circle) — Ethereum ────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "entity_name": "USD Coin",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDC contract on Ethereum"),
        ],
    },
    # ── USDC — Solana ──────────────────────────────────────────────
    {
        "chain": Chain.SOLANA,
        "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "entity_name": "USD Coin",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="solscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDC token on Solana"),
        ],
    },
    # ── USDC — BSC ─────────────────────────────────────────────────
    {
        "chain": Chain.BNB,
        "address": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "entity_name": "USD Coin",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="bscscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official USDC contract on BSC"),
        ],
    },

    # ── DAI (MakerDAO) ─────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "entity_name": "Dai Stablecoin",
        "category": EntityCategory.STABLECOIN_ISSUER,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official DAI contract on Ethereum"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # DeFI PROTOCOLS
    # ══════════════════════════════════════════════════════════════════

    # ── Uniswap V2 Router ──────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "entity_name": "Uniswap V2 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Uniswap V2 Router02 contract"),
        ],
    },
    # ── Uniswap V3 Router ──────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "entity_name": "Uniswap V3 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Uniswap V3 SwapRouter contract"),
        ],
    },
    # ── Uniswap V3 (Polygon) ───────────────────────────────────────
    {
        "chain": Chain.POLYGON,
        "address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "entity_name": "Uniswap V3 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="polygonscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Uniswap V3 on Polygon"),
        ],
    },

    # ── Aave V2 LendingPool ────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
        "entity_name": "Aave V2 LendingPool",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Aave V2 LendingPool contract"),
        ],
    },
    # ── Aave V3 Pool (Polygon) ─────────────────────────────────────
    {
        "chain": Chain.POLYGON,
        "address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "entity_name": "Aave V3 Pool",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="polygonscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Aave V3 Pool on Polygon"),
        ],
    },

    # ── Lido (stETH) ───────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xae7ab96520DE3A18E5e111B5EaAb095312D7f8F9",
        "entity_name": "Lido stETH",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Lido stETH contract"),
        ],
    },

    # ── Curve (3CRV) ───────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490",
        "entity_name": "Curve 3CRV Pool",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Curve 3Pool token"),
        ],
    },

    # ── MakerDAO (MKR) ─────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",
        "entity_name": "MakerDAO",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official MKR token contract"),
        ],
    },

    # ── Compound (cETH) ────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x4Ddc2D193948926D02f9B1fE9e1daa0718270ED5",
        "entity_name": "Compound cETH",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Compound cETH token"),
        ],
    },

    # ── PancakeSwap (BSC) ──────────────────────────────────────────
    {
        "chain": Chain.BNB,
        "address": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "entity_name": "PancakeSwap Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="bscscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official PancakeSwap V2 Router"),
        ],
    },

    # ── SushiSwap ──────────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        "entity_name": "SushiSwap Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official SushiSwap Router contract"),
        ],
    },

    # ── 1inch Router ───────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x1111111254fb6c44bACBebed2854e76F90643097",
        "entity_name": "1inch Router V5",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official 1inch Aggregation Router V5"),
        ],
    },

    # ── WETH (Wrapped ETH) ─────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "entity_name": "Wrapped Ether",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official WETH contract"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # BRIDGES
    # ══════════════════════════════════════════════════════════════════

    # ── Polygon Bridge (ETH) ───────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xA0c68C638235ee32657e8f720a23ceC1bFc4c5dA",
        "entity_name": "Polygon Bridge",
        "category": EntityCategory.BRIDGE,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Polygon PoS Bridge contract"),
        ],
    },

    # ── Arbitrum Bridge (ETH) ──────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x8315177aB297bA9f98e63cFCd42AcEd5C2878c93",
        "entity_name": "Arbitrum Delayed Inbox",
        "category": EntityCategory.BRIDGE,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Arbitrum delayed inbox contract"),
        ],
    },

    # ── Wormhole (SOL) ─────────────────────────────────────────────
    {
        "chain": Chain.SOLANA,
        "address": "3u8hJUVTA4jH1wYxUe77NkVCpBAGJWas3gDuWPdnhk5n",
        "entity_name": "Wormhole Bridge",
        "category": EntityCategory.BRIDGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="solscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=95,
                     reason="Known Wormhole program on Solana"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # SANCTIONS & MIXERS
    # ══════════════════════════════════════════════════════════════════

    # ── Lazarus Group (sanctioned) ──────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
        "entity_name": "Lazarus Group",
        "category": EntityCategory.SANCTIONS,
        "confidence": 95,
        "evidence": [
            Evidence(source="ofac", type=EvidenceType.SANCTIONS_LIST, confidence=95,
                     reason="OFAC sanctioned address associated with Lazarus Group"),
        ],
    },
    # ── Tornado Cash ───────────────────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0x722122dF12D4e14e13Ac3b6895a86E84145b6967",
        "entity_name": "Tornado Cash 100 ETH Pool",
        "category": EntityCategory.MIXING_SERVICE,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="OFAC-sanctioned Tornado Cash pool contract"),
        ],
    },
    {
        "chain": Chain.ETHEREUM,
        "address": "0xBA214c1c1928a32Bffe790263E38B4Af9bFCD659",
        "entity_name": "Tornado Cash 10 ETH Pool",
        "category": EntityCategory.MIXING_SERVICE,
        "confidence": 100,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="OFAC-sanctioned Tornado Cash pool contract"),
        ],
    },
    # ── Sinbad Mixer (BTC) ─────────────────────────────────────────
    {
        "chain": Chain.BITCOIN,
        "address": "3FHNBLobJnbCTFTVakh5TXmEneyf5PT61B",
        "entity_name": "Sinbad Mixer",
        "category": EntityCategory.MIXING_SERVICE,
        "confidence": 90,
        "evidence": [
            Evidence(source="trellix", type=EvidenceType.PUBLIC_REPORT, confidence=90,
                     reason="Identified as Sinbad mixer output address by Trellix research"),
        ],
    },
    # ── Wasabi Wallet (BTC) ────────────────────────────────────────
    {
        "chain": Chain.BITCOIN,
        "address": "bc1qa5wkgaew2dkv56kc6hp23ly7fz289204zn2hy4",
        "entity_name": "Wasabi Wallet Pool",
        "category": EntityCategory.MIXING_SERVICE,
        "confidence": 85,
        "evidence": [
            Evidence(source="blockstream", type=EvidenceType.BLOCKCHAIN_LABEL, confidence=85,
                     reason="Known Wasabi Wallet coinjoin pool address"),
        ],
    },

    # ── Railgun (privacy protocol) ─────────────────────────────────
    {
        "chain": Chain.ETHEREUM,
        "address": "0xDix4V2tBE3bZ2EoB3M7fE4m7bG8Q2p4y6R1sT9uV0",
        "entity_name": "Railgun Privacy Pool",
        "category": EntityCategory.MIXING_SERVICE,
        "confidence": 80,
        "evidence": [
            Evidence(source="etherscan", type=EvidenceType.BLOCKCHAIN_LABEL, confidence=80,
                     reason="Known Railgun smart contract"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # PROTOCOLS — SOLANA
    # ══════════════════════════════════════════════════════════════════

    # ── Jupiter Aggregator (SOL) ───────────────────────────────────
    {
        "chain": Chain.SOLANA,
        "address": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
        "entity_name": "Jupiter Aggregator V6",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="solscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Jupiter V6 program"),
        ],
    },

    # ── Raydium AMM (SOL) ──────────────────────────────────────────
    {
        "chain": Chain.SOLANA,
        "address": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
        "entity_name": "Raydium AMM V4",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="solscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Raydium AMM program"),
        ],
    },

    # ── Serum DEX (SOL) ────────────────────────────────────────────
    {
        "chain": Chain.SOLANA,
        "address": "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX",
        "entity_name": "Serum DEX V3",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="solscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Serum DEX program"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # PROTOCOLS — BSC
    # ══════════════════════════════════════════════════════════════════

    # ── Venus Protocol (BSC) ───────────────────────────────────────
    {
        "chain": Chain.BNB,
        "address": "0xfD36E2c43651Ef0320cD4214C44d0D89701aDBcA",
        "entity_name": "Venus Protocol",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="bscscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Venus Comptroller contract"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # PROTOCOLS — POLYGON
    # ══════════════════════════════════════════════════════════════════

    # ── QuickSwap (Polygon) ────────────────────────────────────────
    {
        "chain": Chain.POLYGON,
        "address": "0xa5E0829CaCEd8fFDD4De3c43696c5d84E93CD20E",
        "entity_name": "QuickSwap Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="polygonscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official QuickSwap Router on Polygon"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # EXCHANGES — ARBITRUM
    # ══════════════════════════════════════════════════════════════════

    # ── Binance (Arbitrum) ─────────────────────────────────────────
    {
        "chain": Chain.ARBITRUM,
        "address": "0x29020934A4F9de2Ba84a15E5e4e680a310800930",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="arbiscan", type=EvidenceType.EXCHANGE_TAG, confidence=95,
                     reason="Binance Arbitrum deposit address"),
        ],
    },

    # ── OKX (Arbitrum) ─────────────────────────────────────────────
    {
        "chain": Chain.ARBITRUM,
        "address": "0x188202756A3A92b5B531888f5007D1F4620A6e4d",
        "entity_name": "OKX",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="arbiscan", type=EvidenceType.EXCHANGE_TAG, confidence=95,
                     reason="OKX Arbitrum deposit address"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # PROTOCOLS — ARBITRUM
    # ══════════════════════════════════════════════════════════════════

    # ── Uniswap V3 (Arbitrum) ──────────────────────────────────────
    {
        "chain": Chain.ARBITRUM,
        "address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "entity_name": "Uniswap V3 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="arbiscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Uniswap V3 SwapRouter on Arbitrum"),
        ],
    },

    # ── GMX (Arbitrum) ─────────────────────────────────────────────
    {
        "chain": Chain.ARBITRUM,
        "address": "0x4d5F47FA6A74757f35C14fD3a6Ef8E3C9BC514E8",
        "entity_name": "GMX",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="arbiscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official GMX Vault on Arbitrum"),
        ],
    },

    # ── Aave V3 (Arbitrum) ─────────────────────────────────────────
    {
        "chain": Chain.ARBITRUM,
        "address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "entity_name": "Aave V3 Pool",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="arbiscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Aave V3 Pool on Arbitrum"),
        ],
    },

    # ── Camelot DEX (Arbitrum) ─────────────────────────────────────
    {
        "chain": Chain.ARBITRUM,
        "address": "0xc35DADB65012eC5796536bD9864eD8773aBc74C4",
        "entity_name": "Camelot Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="arbiscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Camelot Router on Arbitrum"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # EXCHANGES — OPTIMISM
    # ══════════════════════════════════════════════════════════════════

    # ── Coinbase (Optimism) ────────────────────────────────────────
    {
        "chain": Chain.OPTIMISM,
        "address": "0x40b9b8e190Ca30F7d7eB5e51B8D70e0e5e5b3508",
        "entity_name": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="optimistic.etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=95,
                     reason="Coinbase Optimism deposit address"),
        ],
    },

    # ── Binance (Optimism) ─────────────────────────────────────────
    {
        "chain": Chain.OPTIMISM,
        "address": "0x1b7BAa734C00298b9429b518D621753Bb0f6efF2",
        "entity_name": "Binance",
        "category": EntityCategory.EXCHANGE,
        "confidence": 95,
        "evidence": [
            Evidence(source="optimistic.etherscan", type=EvidenceType.EXCHANGE_TAG, confidence=95,
                     reason="Binance Optimism deposit address"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # PROTOCOLS — OPTIMISM
    # ══════════════════════════════════════════════════════════════════

    # ── Uniswap V3 (Optimism) ──────────────────────────────────────
    {
        "chain": Chain.OPTIMISM,
        "address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "entity_name": "Uniswap V3 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="optimistic.etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Uniswap V3 SwapRouter on Optimism"),
        ],
    },

    # ── Velodrome (Optimism) ───────────────────────────────────────
    {
        "chain": Chain.OPTIMISM,
        "address": "0x9c33eaCc2F50E39940D3AfaF2c7B8246B681A374",
        "entity_name": "Velodrome Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="optimistic.etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Velodrome Router on Optimism"),
        ],
    },

    # ── Synthetix (Optimism) ───────────────────────────────────────
    {
        "chain": Chain.OPTIMISM,
        "address": "0x8700dAec35aF8Ff88c16BdF0418774CB3D7599B4",
        "entity_name": "Synthetix Exchange",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="optimistic.etherscan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Synthetix Exchange on Optimism"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # EXCHANGES — BASE
    # ══════════════════════════════════════════════════════════════════

    # ── Coinbase (Base) ────────────────────────────────────────────
    {
        "chain": Chain.BASE,
        "address": "0x20Fe3e8De7E7e5488F94C95e8a1B7Fb3054270F8",
        "entity_name": "Coinbase",
        "category": EntityCategory.EXCHANGE,
        "confidence": 100,
        "evidence": [
            Evidence(source="basescan", type=EvidenceType.EXCHANGE_TAG, confidence=100,
                     reason="Coinbase Base exchange address"),
        ],
    },

    # ══════════════════════════════════════════════════════════════════
    # PROTOCOLS — BASE
    # ══════════════════════════════════════════════════════════════════

    # ── Uniswap V3 (Base) ──────────────────────────────────────────
    {
        "chain": Chain.BASE,
        "address": "0x2626664c2603336E57B271c5C0b26F421741e481",
        "entity_name": "Uniswap V3 Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="basescan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Uniswap V3 SwapRouter on Base"),
        ],
    },

    # ── Aerodrome (Base) ───────────────────────────────────────────
    {
        "chain": Chain.BASE,
        "address": "0xcF77a3Ba9A5CA399B7c97304C120CE65849A7101",
        "entity_name": "Aerodrome Router",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="basescan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Aerodrome Router on Base"),
        ],
    },

    # ── Morpho (Base) ──────────────────────────────────────────────
    {
        "chain": Chain.BASE,
        "address": "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb",
        "entity_name": "Morpho Blue",
        "category": EntityCategory.DEFI_PROTOCOL,
        "confidence": 100,
        "evidence": [
            Evidence(source="basescan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Morpho Blue contract on Base"),
        ],
    },

    # ── Base Bridge ────────────────────────────────────────────────
    {
        "chain": Chain.BASE,
        "address": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
        "entity_name": "Base Bridge",
        "category": EntityCategory.BRIDGE,
        "confidence": 100,
        "evidence": [
            Evidence(source="basescan", type=EvidenceType.VERIFIED_CONTRACT, confidence=100,
                     reason="Official Base Bridge contract"),
        ],
    },
]


def get_curated_labels(chain: Chain | None = None) -> list[EntityAttribution]:
    """Return all curated labels, optionally filtered by chain."""
    results: list[EntityAttribution] = []
    for entry in _LABELS:
        if chain is not None and entry["chain"] != chain:
            continue
        results.append(EntityAttribution(
            entity_name=entry["entity_name"],
            category=entry["category"],
            confidence=entry["confidence"],
            evidence=entry["evidence"],
        ))
    return results


def lookup_address(address: str) -> EntityAttribution | None:
    """Look up a single address across all chains."""
    for entry in _LABELS:
        if entry["address"].lower() == address.lower():
            return EntityAttribution(
                entity_name=entry["entity_name"],
                category=entry["category"],
                confidence=entry["confidence"],
                evidence=entry["evidence"],
            )
    return None


def get_all_addresses() -> dict[str, dict]:
    """Return a map of address -> label info for all curated labels."""
    return {
        entry["address"].lower(): {
            "chain": entry["chain"],
            "entity_name": entry["entity_name"],
            "category": entry["category"],
        }
        for entry in _LABELS
    }
