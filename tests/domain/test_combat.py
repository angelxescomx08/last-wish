"""Tests for CombatState — structure, defaults, and field integrity."""
from __future__ import annotations

import pytest

from src.domain.card import Card, CardEffect, CardType
from src.domain.combat import CombatState
from src.domain.entities import Enemy, Intent, IntentType, Player
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic, RelicTag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player() -> Player:
    return Player(name="Viajero", max_hp=80, current_hp=80)


def _enemy() -> Enemy:
    return Enemy(
        id="e1", name="Cultista", max_hp=50, current_hp=50,
        intent=Intent(IntentType.ATTACK, 10),
    )


def _card() -> Card:
    return Card(
        id="g", name="Golpe", card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect("Golpe", damage=BigValue(6)),
    )


def _minimal_state(**overrides) -> CombatState:
    defaults = dict(
        player=_player(),
        enemies=[_enemy()],
        hand=Hand(),
        draw_pile=DrawPile(),
        discard_pile=DiscardPile(),
        mana=Mana(current=3, maximum=3),
    )
    defaults.update(overrides)
    return CombatState(**defaults)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

class TestCombatStateDefaults:
    def test_turn_default_one(self):
        assert _minimal_state().turn == 1

    def test_relics_default_empty(self):
        assert _minimal_state().relics == []

    def test_active_powers_default_empty(self):
        assert _minimal_state().active_powers == []

    def test_selected_card_index_default_none(self):
        assert _minimal_state().selected_card_index is None

    def test_targeted_enemy_index_default_none(self):
        assert _minimal_state().targeted_enemy_index is None


# ---------------------------------------------------------------------------
# Field storage
# ---------------------------------------------------------------------------

class TestCombatStateFields:
    def test_player_stored(self):
        p = _player()
        state = _minimal_state(player=p)
        assert state.player is p

    def test_enemies_stored(self):
        enemies = [_enemy(), _enemy()]
        state = _minimal_state(enemies=enemies)
        assert len(state.enemies) == 2

    def test_hand_stored(self):
        hand = Hand(cards=[_card()])
        state = _minimal_state(hand=hand)
        assert state.hand.count == 1

    def test_draw_pile_stored(self):
        dp = DrawPile(cards=[_card(), _card()])
        state = _minimal_state(draw_pile=dp)
        assert state.draw_pile.count == 2

    def test_discard_pile_stored(self):
        disc = DiscardPile(cards=[_card()])
        state = _minimal_state(discard_pile=disc)
        assert state.discard_pile.count == 1

    def test_mana_stored(self):
        mana = Mana(current=2, maximum=4)
        state = _minimal_state(mana=mana)
        assert state.mana.current == 2
        assert state.mana.maximum == 4

    def test_relics_stored(self):
        relics = [
            Relic("r1", "Orbe", "", tag=RelicTag.FIRE_ORB),
            Relic("r2", "Escudo", "", tag=RelicTag.SPECTRAL_SHIELD),
        ]
        state = _minimal_state(relics=relics)
        assert len(state.relics) == 2

    def test_turn_custom(self):
        assert _minimal_state(turn=5).turn == 5

    def test_active_powers_stored(self):
        powers = [_card()]
        state = _minimal_state(active_powers=powers)
        assert len(state.active_powers) == 1


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

class TestCombatStateMutation:
    def test_turn_increments(self):
        state = _minimal_state()
        state.turn += 1
        assert state.turn == 2

    def test_selected_card_index_set(self):
        state = _minimal_state()
        state.selected_card_index = 2
        assert state.selected_card_index == 2

    def test_targeted_enemy_index_set(self):
        state = _minimal_state()
        state.targeted_enemy_index = 0
        assert state.targeted_enemy_index == 0

    def test_enemies_list_mutable(self):
        state = _minimal_state()
        initial = len(state.enemies)
        state.enemies.append(_enemy())
        assert len(state.enemies) == initial + 1

    def test_active_powers_grows(self):
        state = _minimal_state()
        state.active_powers.append(_card())
        assert len(state.active_powers) == 1

    def test_relics_list_mutable(self):
        state = _minimal_state()
        state.relics.append(Relic("r", "R", "", tag=RelicTag.FIRE_ORB))
        assert len(state.relics) == 1


# ---------------------------------------------------------------------------
# No coupling with pygame
# ---------------------------------------------------------------------------

class TestNoPygameDependency:
    def test_import_does_not_require_pygame(self):
        # If this test runs without error, the module is pygame-free
        import src.domain.combat  # noqa: F401
        assert True
