"""Tests for DrawPile, DiscardPile, and Hand — count, is_full, max_size."""
from __future__ import annotations

import pytest

from src.domain.card import Card, CardEffect, CardType
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card(name: str = "Golpe") -> Card:
    return Card(
        id=name, name=name, card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect(name, damage=BigValue(1)),
    )


def _cards(n: int) -> list[Card]:
    return [_card(f"c{i}") for i in range(n)]


# ---------------------------------------------------------------------------
# DrawPile.count
# ---------------------------------------------------------------------------

class TestDrawPileCount:
    def test_empty(self):
        assert DrawPile().count == 0

    def test_one_card(self):
        assert DrawPile(cards=[_card()]).count == 1

    def test_ten_cards(self):
        assert DrawPile(cards=_cards(10)).count == 10

    def test_large_count(self):
        assert DrawPile(cards=_cards(1000)).count == 1000

    def test_count_reflects_mutation(self):
        pile = DrawPile()
        pile.cards.append(_card())
        assert pile.count == 1
        pile.cards.pop()
        assert pile.count == 0

    def test_default_empty(self):
        pile = DrawPile()
        assert pile.cards == []

    def test_count_after_extend(self):
        pile = DrawPile(cards=_cards(5))
        pile.cards.extend(_cards(5))
        assert pile.count == 10


# ---------------------------------------------------------------------------
# DiscardPile.count
# ---------------------------------------------------------------------------

class TestDiscardPileCount:
    def test_empty(self):
        assert DiscardPile().count == 0

    def test_one_card(self):
        assert DiscardPile(cards=[_card()]).count == 1

    def test_ten_cards(self):
        assert DiscardPile(cards=_cards(10)).count == 10

    def test_large_count(self):
        assert DiscardPile(cards=_cards(500)).count == 500

    def test_count_reflects_mutation(self):
        pile = DiscardPile()
        pile.cards.append(_card())
        pile.cards.append(_card())
        assert pile.count == 2
        pile.cards.clear()
        assert pile.count == 0

    def test_default_empty(self):
        pile = DiscardPile()
        assert pile.cards == []


# ---------------------------------------------------------------------------
# Hand.count
# ---------------------------------------------------------------------------

class TestHandCount:
    def test_empty(self):
        assert Hand().count == 0

    def test_one_card(self):
        assert Hand(cards=[_card()]).count == 1

    def test_five_cards(self):
        assert Hand(cards=_cards(5)).count == 5

    def test_at_default_max(self):
        assert Hand(cards=_cards(10)).count == 10

    def test_count_reflects_mutation(self):
        hand = Hand()
        hand.cards.append(_card())
        assert hand.count == 1

    def test_count_after_pop(self):
        hand = Hand(cards=_cards(3))
        hand.cards.pop()
        assert hand.count == 2


# ---------------------------------------------------------------------------
# Hand.is_full
# ---------------------------------------------------------------------------

class TestHandIsFull:
    def test_empty_not_full(self):
        assert not Hand().is_full

    def test_one_below_max_not_full(self):
        assert not Hand(cards=_cards(9)).is_full

    def test_at_max_is_full(self):
        assert Hand(cards=_cards(10)).is_full

    def test_above_max_is_full(self):
        # Unusual but the property must handle it safely
        hand = Hand(cards=_cards(10))
        hand.cards.append(_card())  # force 11 cards
        assert hand.is_full

    def test_custom_max_size_not_full(self):
        hand = Hand(cards=_cards(4), max_size=5)
        assert not hand.is_full

    def test_custom_max_size_full(self):
        hand = Hand(cards=_cards(5), max_size=5)
        assert hand.is_full

    def test_max_size_one(self):
        hand = Hand(max_size=1)
        assert not hand.is_full
        hand.cards.append(_card())
        assert hand.is_full

    def test_max_size_zero_always_full(self):
        hand = Hand(cards=[], max_size=0)
        assert hand.is_full  # 0 >= 0

    def test_large_max_not_full(self):
        hand = Hand(cards=_cards(100), max_size=10**6)
        assert not hand.is_full


# ---------------------------------------------------------------------------
# Hand.max_size
# ---------------------------------------------------------------------------

class TestHandMaxSize:
    def test_default_max_size(self):
        assert Hand().max_size == 10

    def test_custom_max_size(self):
        assert Hand(max_size=7).max_size == 7

    def test_max_size_mutation(self):
        hand = Hand()
        hand.max_size = 5
        assert hand.max_size == 5
