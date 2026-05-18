"""Tests for Card domain object: effects, stacking, modifiers, and edge cases."""
from __future__ import annotations

import pytest

from src.domain.card import Card, CardEffect, CardModifier, CardType, ModifierTag
from src.domain.numbers import BigValue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attack(damage: int, *, stacked: list[CardEffect] | None = None) -> Card:
    return Card(
        id="test", name="Test", card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect(name="base", damage=BigValue(damage)),
        stacked_effects=stacked or [],
    )


def _skill(block: int, draw: int = 0) -> Card:
    return Card(
        id="test", name="Test", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect(name="base", block=BigValue(block), draw=draw),
    )


def _power() -> Card:
    return Card(
        id="test", name="Test", card_type=CardType.POWER, cost=0,
        base_effect=CardEffect(name="base"),
    )


# ---------------------------------------------------------------------------
# total_damage()
# ---------------------------------------------------------------------------

class TestTotalDamage:
    def test_zero(self):
        assert _attack(0).total_damage() == 0

    def test_base_only(self):
        assert _attack(6).total_damage() == 6

    def test_single_stacked_flat(self):
        extra = CardEffect("extra", damage=BigValue(4))
        assert _attack(6, stacked=[extra]).total_damage() == 10

    def test_stacked_with_multiplier(self):
        # stacked effect: BigValue(4).add_multiplier(2) → 8
        extra = CardEffect("extra", damage=BigValue(4).add_multiplier(2))
        assert _attack(6, stacked=[extra]).total_damage() == 14

    def test_multiple_stacked(self):
        e1 = CardEffect("e1", damage=BigValue(3))
        e2 = CardEffect("e2", damage=BigValue(2))
        assert _attack(6, stacked=[e1, e2]).total_damage() == 11

    def test_very_large_damage(self):
        extra = CardEffect("e", damage=BigValue(10**9).add_multiplier(10**9))
        # base(6) + stacked(10^18) → 10^18 + 6
        result = _attack(6, stacked=[extra]).total_damage()
        assert result == 10**18 + 6

    def test_skill_has_zero_damage(self):
        assert _skill(5).total_damage() == 0


# ---------------------------------------------------------------------------
# total_block()
# ---------------------------------------------------------------------------

class TestTotalBlock:
    def test_zero(self):
        assert _skill(0).total_block() == 0

    def test_base_only(self):
        assert _skill(5).total_block() == 5

    def test_attack_has_zero_block(self):
        assert _attack(6).total_block() == 0

    def test_stacked_block(self):
        extra = CardEffect("e", block=BigValue(3))
        card = Card(
            id="t", name="T", card_type=CardType.SKILL, cost=1,
            base_effect=CardEffect("b", block=BigValue(5)),
            stacked_effects=[extra],
        )
        assert card.total_block() == 8

    def test_large_block(self):
        extra = CardEffect("e", block=BigValue(10**15))
        card = Card(
            id="t", name="T", card_type=CardType.SKILL, cost=1,
            base_effect=CardEffect("b", block=BigValue(10**15)),
            stacked_effects=[extra],
        )
        assert card.total_block() == 2 * 10**15


# ---------------------------------------------------------------------------
# all_effects()
# ---------------------------------------------------------------------------

class TestAllEffects:
    def test_no_stacked(self):
        card = _attack(6)
        effects = card.all_effects()
        assert len(effects) == 1
        assert effects[0] is card.base_effect

    def test_with_stacked(self):
        e1 = CardEffect("e1", damage=BigValue(2))
        e2 = CardEffect("e2", damage=BigValue(3))
        card = _attack(6, stacked=[e1, e2])
        effects = card.all_effects()
        assert len(effects) == 3
        assert effects[0] is card.base_effect
        assert effects[1] is e1
        assert effects[2] is e2


# ---------------------------------------------------------------------------
# effect_count()
# ---------------------------------------------------------------------------

class TestEffectCount:
    def test_no_stacked(self):
        assert _attack(6).effect_count() == 0

    def test_two_stacked(self):
        e1 = CardEffect("e1", damage=BigValue(1))
        e2 = CardEffect("e2", damage=BigValue(1))
        assert _attack(6, stacked=[e1, e2]).effect_count() == 2


# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------

class TestModifiers:
    def test_has_modifier_false(self):
        assert not _attack(6).has_modifier(ModifierTag.CHROMA)

    def test_has_modifier_true(self):
        card = _attack(6)
        card.modifiers.append(CardModifier(ModifierTag.CHROMA, stacks=1))
        assert card.has_modifier(ModifierTag.CHROMA)

    def test_modifier_stacks_zero_when_absent(self):
        assert _attack(6).modifier_stacks(ModifierTag.ECHO) == 0

    def test_modifier_stacks_returns_count(self):
        card = _attack(6)
        card.modifiers.append(CardModifier(ModifierTag.ECHO, stacks=3))
        assert card.modifier_stacks(ModifierTag.ECHO) == 3

    def test_multiple_different_modifiers(self):
        card = _attack(6)
        card.modifiers.append(CardModifier(ModifierTag.CHROMA, stacks=1))
        card.modifiers.append(CardModifier(ModifierTag.TRANSPARENT, stacks=2))
        assert card.has_modifier(ModifierTag.CHROMA)
        assert card.has_modifier(ModifierTag.TRANSPARENT)
        assert not card.has_modifier(ModifierTag.ETHEREAL)
        assert card.modifier_stacks(ModifierTag.TRANSPARENT) == 2


# ---------------------------------------------------------------------------
# is_broken flag
# ---------------------------------------------------------------------------

class TestIsBroken:
    def test_default_not_broken(self):
        assert not _attack(6).is_broken

    def test_set_broken(self):
        card = _attack(6)
        card.is_broken = True
        assert card.is_broken


# ---------------------------------------------------------------------------
# CardEffect draw field
# ---------------------------------------------------------------------------

class TestCardEffectDraw:
    def test_draw_zero_by_default(self):
        effect = CardEffect("e", damage=BigValue(6))
        assert effect.draw == 0

    def test_draw_positive(self):
        card = _skill(5, draw=2)
        total_draw = sum(fx.draw for fx in card.all_effects())
        assert total_draw == 2
