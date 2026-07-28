from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..value_objects.amount import Amount
from ..value_objects.chain import Chain


class ContractType(str, Enum):
    ERC20 = "erc20"
    ERC721 = "erc721"
    ERC1155 = "erc1155"
    PROXY = "proxy"
    UNKNOWN = "unknown"


@dataclass
class Contract:
    address: str
    chain: Chain
    creator: str | None = None
    creation_tx: str | None = None
    creation_date: datetime | None = None
    verified: bool = False
    contract_type: ContractType = ContractType.UNKNOWN
    name: str = ""
    symbol: str = ""
    total_supply: Amount | None = None
    decimals: int | None = None
    abi: list[dict] | None = None
    compiler_version: str | None = None
    implementation: str | None = None
    is_proxy: bool = False
    tags: dict[str, str] = field(default_factory=dict)

    def copy_with(self, **kwargs) -> Contract:
        return Contract(**{**self.__dict__, **kwargs})


@dataclass
class TokenBalance:
    contract_address: str
    chain: Chain
    symbol: str = ""
    name: str = ""
    balance: Amount | None = None
    decimals: int = 18
    usd_value: float | None = None
