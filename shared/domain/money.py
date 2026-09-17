from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Self


@dataclass(frozen=True)
class Money:
    """
    Immutable framework-free Money value object.
    Always backed by Python Decimal and a 3-letter ISO-4217 currency code.
    Prevents float rounding errors and currency mismatch arithmetic.
    """
    amount: Decimal
    currency: str

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if not isinstance(self.currency, str) or len(self.currency) != 3:
            raise ValueError(f"Invalid ISO-4217 currency code: {self.currency!r}")
        object.__setattr__(self, "currency", self.currency.upper())

    @classmethod
    def zero(cls, currency: str = "INR") -> Self:
        return cls(amount=Decimal("0.0000"), currency=currency)

    @classmethod
    def from_amount(cls, amount: str | int | float | Decimal, currency: str = "INR") -> Self:
        return cls(amount=Decimal(str(amount)), currency=currency)

    def _assert_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot operate on Money with different currencies: {self.currency} vs {other.currency}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, factor: int | Decimal) -> "Money":
        if isinstance(factor, float):
            raise TypeError("Multiplication of Money by float is strictly forbidden. Use Decimal or int.")
        return Money(amount=self.amount * Decimal(str(factor)), currency=self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount >= other.amount

    def to_display_string(self) -> str:
        """Format as 2-decimal places for customer display: e.g. 1999.00"""
        return f"{self.amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"

    def to_db_decimal(self) -> Decimal:
        """Format to 4-decimal places for PostgreSQL NUMERIC(19,4)"""
        return self.amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
