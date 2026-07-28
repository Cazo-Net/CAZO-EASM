from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from .models import VASP, VASPStatus

logger = logging.getLogger(__name__)


class VASPRegistry:
    _vasps: dict[str, VASP] = {}
    _address_map: dict[str, str] = {}

    @classmethod
    def register(cls, vasp: VASP) -> None:
        cls._vasps[vasp.id] = vasp
        for addr in vasp.addresses:
            cls._address_map[addr.lower()] = vasp.id
        logger.info("Registered VASP: %s (%d addresses)", vasp.name, len(vasp.addresses))

    @classmethod
    def get(cls, vasp_id: str) -> VASP | None:
        return cls._vasps.get(vasp_id)

    @classmethod
    def find_by_address(cls, address: str) -> VASP | None:
        vasp_id = cls._address_map.get(address.lower())
        return cls._vasps.get(vasp_id) if vasp_id else None

    @classmethod
    def find_by_chain(cls, chain: str) -> list[VASP]:
        return [v for v in cls._vasps.values() if chain in v.chains]

    @classmethod
    def list(cls, status: str | None = None, jurisdiction: str | None = None) -> list[dict]:
        results = list(cls._vasps.values())
        if status:
            results = [v for v in results if v.status.value == status]
        if jurisdiction:
            results = [v for v in results if v.jurisdiction.lower() == jurisdiction.lower()]
        return [v.to_dict() for v in sorted(results, key=lambda v: v.name)]

    @classmethod
    def update_status(cls, vasp_id: str, status: VASPStatus) -> bool:
        vasp = cls._vasps.get(vasp_id)
        if vasp:
            vasp.status = status
            return True
        return False

    @classmethod
    def known_addresses(cls) -> list[str]:
        return list(cls._address_map.keys())

    @classmethod
    def is_vasp_address(cls, address: str) -> bool:
        return address.lower() in cls._address_map


def register_default_vasps() -> None:
    defaults = [
        VASP(
            id="binance", name="Binance", legal_name="Binance Holdings Limited",
            jurisdiction="Cayman Islands", registration_number="BN2024",
            website="https://binance.com", api_endpoint="https://api.binance.com/sapi/v1/travel-rule",
            addresses=[
                "0x28c6c06298d514db089934071355e5743bf21d60",
                "0x21a31ee1afc51d94c2efccaa2092ad1028285549",
                "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
            ],
            chains=["ethereum", "bnb", "polygon"],
            status=VASPStatus.ACTIVE, verified_at=datetime(2024, 1, 15),
        ),
        VASP(
            id="coinbase", name="Coinbase", legal_name="Coinbase, Inc.",
            jurisdiction="United States", registration_number="CB2023",
            website="https://coinbase.com", api_endpoint="https://api.coinbase.com/v2/travel-rule",
            addresses=[
                "0x71660c4005ba85c37ccec55d0c4493e66fe775d3",
                "0x503828976d22510aad0201ac7ec88293211d23da",
            ],
            chains=["ethereum", "bitcoin", "base"],
            status=VASPStatus.ACTIVE, verified_at=datetime(2024, 3, 1),
        ),
        VASP(
            id="kraken", name="Kraken", legal_name="Kraken Digital Asset Exchange",
            jurisdiction="United States", registration_number="KR2022",
            website="https://kraken.com",
            addresses=[
                "0x2910543af39aba0cd09dbb2d50200b3e800a63d2",
                "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",
            ],
            chains=["ethereum", "bitcoin"],
            status=VASPStatus.ACTIVE, verified_at=datetime(2024, 6, 1),
        ),
        VASP(
            id="bybit", name="Bybit", legal_name="Bybit Fintech Limited",
            jurisdiction="British Virgin Islands", registration_number="BB2024",
            website="https://bybit.com",
            addresses=[
                "0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4",
            ],
            chains=["ethereum", "arbitrum"],
            status=VASPStatus.ACTIVE,
        ),
        VASP(
            id="okx", name="OKX", legal_name="OKX Technologies Limited",
            jurisdiction="Seychelles", registration_number="OK2023",
            website="https://okx.com",
            addresses=[
                "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2",
            ],
            chains=["ethereum", "polygon"],
            status=VASPStatus.ACTIVE,
        ),
    ]
    for vasp in defaults:
        VASPRegistry.register(vasp)
    logger.info("Registered %d default VASPs", len(defaults))


registry = VASPRegistry()
