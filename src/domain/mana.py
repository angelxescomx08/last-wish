from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Mana:
    current: int
    maximum: int

    def can_afford(self, cost: int) -> bool:
        return self.current >= cost

    def spend(self, amount: int) -> None:
        self.current = max(0, self.current - amount)

    def gain(self, amount: int) -> None:
        self.current = min(self.maximum, self.current + amount)

    def refill(self) -> None:
        self.current = self.maximum
