from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class AmountUnit(str, Enum):
    WEI = "wei"
    GWEI = "gwei"
    ETHER = "ether"
    SATOSHI = "satoshi"
    BITCOIN = "bitcoin"
    LAMPORTS = "lamports"
    SOL = "sol"
    SUN = "sun"
    TRX = "trx"
    LITECOIN = "litecoin"
    LITOSHI = "litoshi"
    NATIVE = "native"


_UNIT_DECIMALS: dict[AmountUnit, int] = {
    AmountUnit.WEI: 18,
    AmountUnit.GWEI: 9,
    AmountUnit.ETHER: 0,
    AmountUnit.SATOSHI: 8,
    AmountUnit.BITCOIN: 0,
    AmountUnit.LAMPORTS: 9,
    AmountUnit.SOL: 0,
    AmountUnit.SUN: 6,
    AmountUnit.TRX: 0,
    AmountUnit.LITOSHI: 8,
    AmountUnit.LITECOIN: 0,
    AmountUnit.NATIVE: 0,
}


@dataclass(frozen=True)
class Amount:
    value: Decimal
    unit: AmountUnit

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"Amount cannot be negative: {self.value}")

    @classmethod
    def zero(cls, unit: AmountUnit = AmountUnit.NATIVE) -> Amount:
        return cls(Decimal("0"), unit)

    def to_unit(self, target: AmountUnit) -> Amount:
        if self.unit == target:
            return self
        source_decimals = _UNIT_DECIMALS[self.unit]
        target_decimals = _UNIT_DECIMALS[target]
        diff = source_decimals - target_decimals
        if diff >= 0:
            return Amount(self.value / Decimal(10 ** diff), target)
        return Amount(self.value * Decimal(10 ** abs(diff)), target)

    def to_native(self) -> Amount:
        return self.to_unit(AmountUnit.NATIVE)

    def __add__(self, other: Amount) -> Amount:
        if self.unit != other.unit:
            other = other.to_unit(self.unit)
        return Amount(self.value + other.value, self.unit)

    def __sub__(self, other: Amount) -> Amount:
        if self.unit != other.unit:
            other = other.to_unit(self.unit)
        return Amount(self.value - other.value, self.unit)

    def __mul__(self, factor: int | Decimal) -> Amount:
        return Amount(self.value * Decimal(str(factor)), self.unit)

    def __truediv__(self, divisor: int | Decimal) -> Amount:
        return Amount(self.value / Decimal(str(divisor)), self.unit)

    def __str__(self) -> str:
        return f"{self.value:.{min(8, abs(self.value.as_tuple().exponent or 0))}f} {self.unit.value}"

    def __repr__(self) -> str:
        return f"Amount({self.value}, {self.unit})"

    @property
    def is_zero(self) -> bool:
        return self.value == 0
