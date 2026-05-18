"""Tests for relic_effects: all 4 relics, boundary cases, and combinations."""
from __future__ import annotations

import pytest

from src.application import relic_effects
from src.domain.card import Card, CardEffect, CardType
from src.domain.combat import CombatState
from src.domain.entities import Enemy, Intent, IntentType, Player
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic, RelicTag


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _relic(tag: RelicTag, *, active: bool = True) -> Relic:
    return Relic(id="r", name="R", description="", tag=tag, is_active=active)


def _state(
    relics: list[Relic] | None = None,
    player_hp: int = 80,
    player_block: int = 0,
) -> CombatState:
    player = Player(
        name="Test", max_hp=100, current_hp=player_hp, block=player_block,
    )
    enemy = Enemy(
        id="e1", name="E", max_hp=50, current_hp=50, block=0,
        intent=Intent(IntentType.ATTACK, 5),
    )
    return CombatState(
        player=player,
        enemies=[enemy],
        hand=Hand(cards=[]),
        draw_pile=DrawPile(cards=[]),
        discard_pile=DiscardPile(cards=[]),
        mana=Mana(current=3, maximum=3),
        relics=relics or [],
    )


# ---------------------------------------------------------------------------
# extra_draw_per_turn  (Tótem Roto)
# ---------------------------------------------------------------------------

class TestExtraDrawPerTurn:
    def test_no_relics(self):
        assert relic_effects.extra_draw_per_turn([]) == 0

    def test_no_broken_totem(self):
        relics = [_relic(RelicTag.FIRE_ORB)]
        assert relic_effects.extra_draw_per_turn(relics) == 0

    def test_broken_totem_active(self):
        relics = [_relic(RelicTag.BROKEN_TOTEM)]
        assert relic_effects.extra_draw_per_turn(relics) == 1

    def test_broken_totem_inactive(self):
        relics = [_relic(RelicTag.BROKEN_TOTEM, active=False)]
        assert relic_effects.extra_draw_per_turn(relics) == 0

    def test_two_broken_totems(self):
        relics = [_relic(RelicTag.BROKEN_TOTEM), _relic(RelicTag.BROKEN_TOTEM)]
        assert relic_effects.extra_draw_per_turn(relics) == 2

    def test_relic_without_tag(self):
        relics = [Relic(id="x", name="X", description="", tag=None)]
        assert relic_effects.extra_draw_per_turn(relics) == 0


# ---------------------------------------------------------------------------
# extra_attack_damage  (Orbe de Fuego)
# ---------------------------------------------------------------------------

class TestExtraAttackDamage:
    def test_no_relics(self):
        assert relic_effects.extra_attack_damage([]) == 0

    def test_fire_orb_active(self):
        assert relic_effects.extra_attack_damage([_relic(RelicTag.FIRE_ORB)]) == 2

    def test_fire_orb_inactive(self):
        assert relic_effects.extra_attack_damage([_relic(RelicTag.FIRE_ORB, active=False)]) == 0

    def test_two_fire_orbs(self):
        relics = [_relic(RelicTag.FIRE_ORB), _relic(RelicTag.FIRE_ORB)]
        assert relic_effects.extra_attack_damage(relics) == 4

    def test_wrong_tag(self):
        assert relic_effects.extra_attack_damage([_relic(RelicTag.BROKEN_TOTEM)]) == 0


# ---------------------------------------------------------------------------
# bonus_starting_mana  (Amuleto de Combate)
# ---------------------------------------------------------------------------

class TestBonusStartingMana:
    def test_no_relics(self):
        assert relic_effects.bonus_starting_mana([]) == 0

    def test_amulet_active(self):
        assert relic_effects.bonus_starting_mana([_relic(RelicTag.COMBAT_AMULET)]) == 1

    def test_amulet_inactive(self):
        assert relic_effects.bonus_starting_mana([_relic(RelicTag.COMBAT_AMULET, active=False)]) == 0

    def test_two_amulets(self):
        relics = [_relic(RelicTag.COMBAT_AMULET), _relic(RelicTag.COMBAT_AMULET)]
        assert relic_effects.bonus_starting_mana(relics) == 2


# ---------------------------------------------------------------------------
# try_spectral_shield  (Escudo Espectral)
# ---------------------------------------------------------------------------

class TestTrySpectralShield:
    def test_no_trigger_when_hp_positive(self):
        state = _state(relics=[_relic(RelicTag.SPECTRAL_SHIELD)], player_hp=1)
        triggered = relic_effects.try_spectral_shield(state)
        assert not triggered
        assert state.player.current_hp == 1
        assert state.relics[0].is_active

    def test_triggers_at_zero_hp(self):
        state = _state(relics=[_relic(RelicTag.SPECTRAL_SHIELD)], player_hp=0)
        triggered = relic_effects.try_spectral_shield(state)
        assert triggered
        assert state.player.current_hp == 1
        assert not state.relics[0].is_active  # consumed

    def test_no_trigger_when_shield_inactive(self):
        state = _state(relics=[_relic(RelicTag.SPECTRAL_SHIELD, active=False)], player_hp=0)
        triggered = relic_effects.try_spectral_shield(state)
        assert not triggered
        assert state.player.current_hp == 0

    def test_no_trigger_without_relics(self):
        state = _state(relics=[], player_hp=0)
        assert not relic_effects.try_spectral_shield(state)
        assert state.player.current_hp == 0

    def test_shield_consumed_only_once(self):
        state = _state(relics=[_relic(RelicTag.SPECTRAL_SHIELD)], player_hp=0)
        relic_effects.try_spectral_shield(state)
        # HP restored to 1, then set to 0 again manually
        state.player.current_hp = 0
        triggered_again = relic_effects.try_spectral_shield(state)
        assert not triggered_again
        assert state.player.current_hp == 0  # no second save

    def test_wrong_relic_does_not_trigger(self):
        state = _state(relics=[_relic(RelicTag.FIRE_ORB)], player_hp=0)
        assert not relic_effects.try_spectral_shield(state)

    def test_multiple_relics_only_first_shield_consumed(self):
        shield1 = _relic(RelicTag.SPECTRAL_SHIELD)
        shield2 = _relic(RelicTag.SPECTRAL_SHIELD)
        state = _state(relics=[shield1, shield2], player_hp=0)
        relic_effects.try_spectral_shield(state)
        assert not state.relics[0].is_active   # first consumed
        assert state.relics[1].is_active        # second intact
