from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..value_objects.address_hash import AddressHash
from ..value_objects.amount import Amount, AmountUnit
from ..value_objects.chain import Chain


class WalletType(str, Enum):
    EOA = "eoa"
    CONTRACT = "contract"
    EXCHANGE_HOT = "exchange_hot_wallet"
    UNKNOWN = "unknown"


@dataclass
class Address:
    hash: str
    chain: Chain
    wallet_type: WalletType = WalletType.UNKNOWN
    first_seen_block: int | None = None
    first_seen_at: datetime | None = None
    last_active_at: datetime | None = None
    tx_count: int = 0
    balance: Amount = field(default_factory=lambda: Amount.zero())
    token_count: int = 0
    nft_count: int = 0
    is_contract: bool = False
    labels: list[str] = field(default_factory=list)
    entity_name: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ = AddressHash(self.hash, self.chain)

    def normalized_hash(self) -> str:
        return AddressHash(self.hash, self.chain).normalized()

    def copy_with(self, **kwargs) -> Address:
        return Address(**{**self.__dict__, **kwargs})
