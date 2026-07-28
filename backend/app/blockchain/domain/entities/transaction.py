from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..value_objects.amount import Amount
from ..value_objects.chain import Chain


class TransactionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class Transaction:
    hash: str
    chain: Chain
    block_number: int | None = None
    timestamp: datetime | None = None
    from_address: str | None = None
    to_address: str | None = None
    value: Amount | None = None
    fee: Amount | None = None
    status: TransactionStatus = TransactionStatus.PENDING
    gas_price: int | None = None
    gas_used: int | None = None
    nonce: int | None = None
    input_data: str = "0x"
    method: str | None = None
    is_contract_creation: bool = False
    contract_address: str | None = None
    error: str | None = None
    logs: list[dict] = field(default_factory=list)
    internal_transfers: list[dict] = field(default_factory=list)
    token_transfers: list[dict] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)

    def copy_with(self, **kwargs) -> Transaction:
        return Transaction(**{**self.__dict__, **kwargs})
