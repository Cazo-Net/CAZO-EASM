from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..value_objects.chain import Chain


@dataclass
class Block:
    number: int
    chain: Chain
    hash: str
    parent_hash: str | None = None
    timestamp: datetime | None = None
    tx_count: int = 0
    size: int | None = None
    gas_limit: int | None = None
    gas_used: int | None = None
    miner: str | None = None
    difficulty: int | None = None
    total_difficulty: int | None = None
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.chain.value}:{self.number}"

    def copy_with(self, **kwargs) -> Block:
        return Block(**{**self.__dict__, **kwargs})
