from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if self.amount < Decimal("0"):
            raise ValueError("Amount cannot be negative")


@dataclass(frozen=True)
class Dimensions:
    weight: Decimal | None = None
    weight_unit: str | None = None
    length: Decimal | None = None
    width: Decimal | None = None
    height: Decimal | None = None
    dimension_unit: str | None = None


@dataclass(frozen=True)
class OptionSignature:
    signature: str

    @classmethod
    def generate(cls, option_value_ids: list[UUID]) -> OptionSignature:
        """Generate canonical sorted option signature from value IDs.

        Sorts string representation of UUIDs deterministically.
        """
        sorted_ids = sorted([str(vid) for vid in option_value_ids])
        return cls(signature=":".join(sorted_ids))

    @classmethod
    def from_pairs(cls, option_value_pairs: list[tuple[UUID, UUID]]) -> OptionSignature:
        """Generate signature from sorted (option_id, option_value_id) pairs."""
        sorted_pairs = sorted(option_value_pairs, key=lambda p: (str(p[0]), str(p[1])))
        formatted = [f"{op}:{val}" for op, val in sorted_pairs]
        return cls(signature="|".join(formatted))
