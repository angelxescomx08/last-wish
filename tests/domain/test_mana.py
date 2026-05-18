"""Tests for Mana: can_afford, spend, gain, refill — including boundary values."""
from __future__ import annotations

import pytest

from src.domain.mana import Mana


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mana(current: int = 3, maximum: int = 3) -> Mana:
    return Mana(current=current, maximum=maximum)


# ---------------------------------------------------------------------------
# can_afford()
# ---------------------------------------------------------------------------

class TestCanAfford:
    def test_exact_cost(self):
        assert _mana(3, 3).can_afford(3)

    def test_more_than_cost(self):
        assert _mana(5, 5).can_afford(3)

    def test_zero_cost_always_affordable(self):
        assert _mana(0, 0).can_afford(0)
        assert _mana(3, 3).can_afford(0)

    def test_one_mana_affords_one(self):
        assert _mana(1, 3).can_afford(1)

    def test_cannot_afford_when_empty(self):
        assert not _mana(0, 3).can_afford(1)

    def test_cannot_afford_higher_than_current(self):
        assert not _mana(2, 5).can_afford(3)

    def test_large_cost_unaffordable(self):
        assert not _mana(3, 3).can_afford(10**9)

    def test_large_mana_affords_large_cost(self):
        m = Mana(current=10**9, maximum=10**9)
        assert m.can_afford(10**9)
        assert not m.can_afford(10**9 + 1)


# ---------------------------------------------------------------------------
# spend()
# ---------------------------------------------------------------------------

class TestSpend:
    def test_spend_exact(self):
        m = _mana(3, 3)
        m.spend(3)
        assert m.current == 0

    def test_spend_partial(self):
        m = _mana(3, 3)
        m.spend(1)
        assert m.current == 2

    def test_spend_zero(self):
        m = _mana(3, 3)
        m.spend(0)
        assert m.current == 3

    def test_spend_does_not_go_negative(self):
        m = _mana(2, 5)
        m.spend(10)
        assert m.current == 0

    def test_spend_maximum_unchanged(self):
        m = _mana(3, 3)
        m.spend(3)
        assert m.maximum == 3

    def test_spend_sequential(self):
        m = _mana(5, 5)
        m.spend(2)
        m.spend(2)
        assert m.current == 1

    def test_spend_from_zero_stays_zero(self):
        m = _mana(0, 5)
        m.spend(5)
        assert m.current == 0

    def test_spend_large_amount(self):
        m = Mana(current=10**9, maximum=10**9)
        m.spend(10**9)
        assert m.current == 0


# ---------------------------------------------------------------------------
# gain()
# ---------------------------------------------------------------------------

class TestGain:
    def test_gain_partial(self):
        m = _mana(1, 3)
        m.gain(1)
        assert m.current == 2

    def test_gain_to_exact_maximum(self):
        m = _mana(1, 3)
        m.gain(2)
        assert m.current == 3

    def test_gain_capped_at_maximum(self):
        m = _mana(1, 3)
        m.gain(100)
        assert m.current == 3

    def test_gain_zero(self):
        m = _mana(2, 3)
        m.gain(0)
        assert m.current == 2

    def test_gain_when_full_stays_full(self):
        m = _mana(3, 3)
        m.gain(10)
        assert m.current == 3

    def test_gain_maximum_unchanged(self):
        m = _mana(0, 5)
        m.gain(3)
        assert m.maximum == 5

    def test_gain_large(self):
        m = Mana(current=0, maximum=10**9)
        m.gain(10**9)
        assert m.current == 10**9

    def test_gain_beyond_large_maximum_capped(self):
        m = Mana(current=0, maximum=10**9)
        m.gain(10**9 + 999)
        assert m.current == 10**9


# ---------------------------------------------------------------------------
# refill()
# ---------------------------------------------------------------------------

class TestRefill:
    def test_refill_empty(self):
        m = _mana(0, 3)
        m.refill()
        assert m.current == 3

    def test_refill_partial(self):
        m = _mana(1, 5)
        m.refill()
        assert m.current == 5

    def test_refill_already_full(self):
        m = _mana(3, 3)
        m.refill()
        assert m.current == 3

    def test_refill_maximum_unchanged(self):
        m = _mana(0, 7)
        m.refill()
        assert m.maximum == 7

    def test_refill_after_spend(self):
        m = _mana(3, 3)
        m.spend(3)
        m.refill()
        assert m.current == 3

    def test_refill_large_maximum(self):
        m = Mana(current=0, maximum=10**9)
        m.refill()
        assert m.current == 10**9

    def test_refill_after_maximum_increase(self):
        m = _mana(3, 3)
        m.maximum += 1
        m.refill()
        assert m.current == 4
        assert m.maximum == 4
