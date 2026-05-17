from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

OpKind = Literal["+", "x"]


@dataclass(frozen=True)
class Operation:
    kind: OpKind
    value: int


@dataclass
class BigValue:
    """Arbitrary-precision combat value with a chainable operation log.

    Resolution: chips = base + sum(+ops), result = chips * product(xops).
    Python int has no upper bound — values like 10^1_000 are computed exactly.
    This mirrors Balatro's Chips × Mult model but with zero overflow risk.
    """

    base: int
    ops: list[Operation] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Builders (return new immutable BigValue)
    # ------------------------------------------------------------------

    def add_flat(self, n: int) -> BigValue:
        return BigValue(self.base, self.ops + [Operation("+", n)])

    def add_multiplier(self, n: int) -> BigValue:
        return BigValue(self.base, self.ops + [Operation("x", n)])

    def merge(self, other: BigValue) -> BigValue:
        """Combine two BigValues: flatten both into a single chain."""
        combined_base = self.resolve() + other.base
        return BigValue(combined_base, list(other.ops))

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self) -> int:
        chips: int = self.base
        mult: int = 1
        for op in self.ops:
            if op.kind == "+":
                chips += op.value
            else:
                mult *= op.value
        return chips * mult

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    @staticmethod
    def format_int(value: int) -> str:
        """Format a Python int with suffix — purely integer arithmetic, no floats."""
        if value < 0:
            return f"-{BigValue.format_int(-value)}"
        thresholds: list[tuple[int, str]] = [
            (10**18, "E"),
            (10**15, "Q"),
            (10**12, "T"),
            (10**9,  "B"),
            (10**6,  "M"),
            (10**3,  "K"),
        ]
        for threshold, suffix in thresholds:
            if value >= threshold:
                whole = value // threshold
                frac = (value % threshold) * 10 // threshold
                return f"{whole}.{frac}{suffix}"
        return str(value)

    def display(self) -> str:
        return self.format_int(self.resolve())
