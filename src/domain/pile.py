from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.card import Card


@dataclass
class DrawPile:
    cards: list[Card] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.cards)


@dataclass
class DiscardPile:
    cards: list[Card] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.cards)


@dataclass
class Hand:
    cards: list[Card] = field(default_factory=list)
    max_size: int = 10

    @property
    def count(self) -> int:
        return len(self.cards)

    @property
    def is_full(self) -> bool:
        return len(self.cards) >= self.max_size
