from __future__ import annotations

import re
from dataclasses import dataclass

from .chain import Chain


_EVM_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
_BTC_PATTERN = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^(bc1|bc1p)[a-zA-HJ-NP-Z0-9]{25,80}$")
_SOL_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_TRON_PATTERN = re.compile(r"^T[A-Za-z0-9]{33}$")
_LTC_PATTERN = re.compile(r"^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$|^ltc1[a-z0-9]{25,75}$")


@dataclass(frozen=True)
class AddressHash:
    hash: str
    chain: Chain

    def __post_init__(self) -> None:
        if not self._validate():
            raise ValueError(f"Invalid {self.chain} address: {self.hash}")

    def _validate(self) -> bool:
        if self.chain.is_evm() or self.chain == Chain.TRON:
            return bool(_EVM_PATTERN.match(self.hash))
        if self.chain == Chain.BITCOIN:
            return bool(_BTC_PATTERN.match(self.hash))
        if self.chain == Chain.SOLANA:
            return bool(_SOL_PATTERN.match(self.hash))
        if self.chain == Chain.LITECOIN:
            return bool(_LTC_PATTERN.match(self.hash))
        return False

    def normalized(self) -> str:
        if self.chain.is_evm() and self.hash.startswith("0x"):
            return self.hash.lower()
        return self.hash
