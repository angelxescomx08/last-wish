"""Tests for domain entities: Player, Enemy, Intent, StatusEffect."""
from __future__ import annotations

import pytest

from src.domain.entities import Enemy, Intent, IntentType, Player, StatusEffect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enemy(hp: int = 50, max_hp: int = 50, block: int = 0) -> Enemy:
    return Enemy(
        id="e1", name="Enemigo",
        max_hp=max_hp, current_hp=hp, block=block,
        intent=Intent(IntentType.ATTACK, 10),
    )


def _player(hp: int = 80, max_hp: int = 80, block: int = 0) -> Player:
    return Player(name="Viajero", max_hp=max_hp, current_hp=hp, block=block)


# ---------------------------------------------------------------------------
# StatusEffect
# ---------------------------------------------------------------------------

class TestStatusEffect:
    def test_buff_creation(self):
        fx = StatusEffect("Fuerza", stacks=2, is_buff=True)
        assert fx.name == "Fuerza"
        assert fx.stacks == 2
        assert fx.is_buff is True

    def test_debuff_creation(self):
        fx = StatusEffect("Veneno", stacks=5, is_buff=False)
        assert not fx.is_buff
        assert fx.stacks == 5

    def test_zero_stacks(self):
        fx = StatusEffect("Ritual", stacks=0, is_buff=True)
        assert fx.stacks == 0

    def test_large_stacks(self):
        fx = StatusEffect("Fuerza", stacks=10**6, is_buff=True)
        assert fx.stacks == 10**6


# ---------------------------------------------------------------------------
# Intent
# ---------------------------------------------------------------------------

class TestIntent:
    def test_attack_intent(self):
        intent = Intent(IntentType.ATTACK, 12)
        assert intent.intent_type == IntentType.ATTACK
        assert intent.value == 12

    def test_block_intent(self):
        intent = Intent(IntentType.BLOCK, 8)
        assert intent.intent_type == IntentType.BLOCK
        assert intent.value == 8

    def test_buff_intent_zero_value(self):
        intent = Intent(IntentType.BUFF, 0)
        assert intent.value == 0

    def test_debuff_intent(self):
        intent = Intent(IntentType.DEBUFF, 0)
        assert intent.intent_type == IntentType.DEBUFF

    def test_unknown_intent(self):
        intent = Intent(IntentType.UNKNOWN)
        assert intent.intent_type == IntentType.UNKNOWN
        assert intent.value == 0

    def test_large_attack_value(self):
        intent = Intent(IntentType.ATTACK, 10**9)
        assert intent.value == 10**9


# ---------------------------------------------------------------------------
# Enemy.is_alive
# ---------------------------------------------------------------------------

class TestEnemyIsAlive:
    def test_alive_when_positive_hp(self):
        assert _enemy(hp=1).is_alive

    def test_alive_at_full_hp(self):
        assert _enemy(hp=50, max_hp=50).is_alive

    def test_dead_at_zero_hp(self):
        assert not _enemy(hp=0).is_alive

    def test_alive_with_one_hp(self):
        assert _enemy(hp=1, max_hp=100).is_alive

    def test_dead_with_large_max_hp(self):
        assert not _enemy(hp=0, max_hp=10**9).is_alive


# ---------------------------------------------------------------------------
# Enemy.hp_ratio
# ---------------------------------------------------------------------------

class TestEnemyHpRatio:
    def test_full_hp(self):
        assert _enemy(hp=50, max_hp=50).hp_ratio == 1.0

    def test_half_hp(self):
        assert _enemy(hp=25, max_hp=50).hp_ratio == pytest.approx(0.5)

    def test_zero_hp(self):
        assert _enemy(hp=0, max_hp=50).hp_ratio == 0.0

    def test_one_hp(self):
        ratio = _enemy(hp=1, max_hp=100).hp_ratio
        assert ratio == pytest.approx(0.01)

    def test_zero_max_hp_safe(self):
        # max_hp=0 should not raise ZeroDivisionError
        e = Enemy(id="x", name="X", max_hp=0, current_hp=0,
                  intent=Intent(IntentType.UNKNOWN))
        assert e.hp_ratio == 0.0

    def test_ratio_between_zero_and_one(self):
        ratio = _enemy(hp=30, max_hp=50).hp_ratio
        assert 0.0 <= ratio <= 1.0

    def test_large_hp_ratio(self):
        e = Enemy(id="x", name="X", max_hp=10**9, current_hp=5 * 10**8,
                  intent=Intent(IntentType.UNKNOWN))
        assert e.hp_ratio == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Enemy — fields and defaults
# ---------------------------------------------------------------------------

class TestEnemyFields:
    def test_default_block_zero(self):
        e = Enemy(id="e", name="E", max_hp=50, current_hp=50,
                  intent=Intent(IntentType.UNKNOWN))
        assert e.block == 0

    def test_default_status_effects_empty(self):
        e = Enemy(id="e", name="E", max_hp=50, current_hp=50,
                  intent=Intent(IntentType.UNKNOWN))
        assert e.status_effects == []

    def test_default_intent_unknown(self):
        e = Enemy(id="e", name="E", max_hp=50, current_hp=50)
        assert e.intent.intent_type == IntentType.UNKNOWN

    def test_status_effects_stored(self):
        fx = [StatusEffect("Vulnerable", 2, is_buff=False)]
        e = _enemy()
        e.status_effects = fx
        assert len(e.status_effects) == 1

    def test_block_stored(self):
        assert _enemy(block=8).block == 8


# ---------------------------------------------------------------------------
# Player.hp_ratio
# ---------------------------------------------------------------------------

class TestPlayerHpRatio:
    def test_full_hp(self):
        assert _player(hp=80, max_hp=80).hp_ratio == 1.0

    def test_half_hp(self):
        assert _player(hp=40, max_hp=80).hp_ratio == pytest.approx(0.5)

    def test_zero_hp(self):
        assert _player(hp=0, max_hp=80).hp_ratio == 0.0

    def test_one_hp(self):
        assert _player(hp=1, max_hp=100).hp_ratio == pytest.approx(0.01)

    def test_zero_max_hp_safe(self):
        p = Player(name="X", max_hp=0, current_hp=0)
        assert p.hp_ratio == 0.0


# ---------------------------------------------------------------------------
# Player — fields and defaults
# ---------------------------------------------------------------------------

class TestPlayerFields:
    def test_default_block_zero(self):
        assert _player().block == 0

    def test_default_status_effects_empty(self):
        assert _player().status_effects == []

    def test_name_stored(self):
        assert _player().name == "Viajero"

    def test_block_stored(self):
        assert _player(block=5).block == 5

    def test_status_effects_stored(self):
        fx = [StatusEffect("Fuerza", 3, is_buff=True)]
        p = _player()
        p.status_effects = fx
        assert p.status_effects[0].name == "Fuerza"
