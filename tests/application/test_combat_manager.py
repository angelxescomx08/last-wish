"""Tests for create_sample_combat() — structural integrity and relic effect application."""
from __future__ import annotations

import pytest

from src.application.combat_manager import create_sample_combat
from src.application import relic_effects
from src.domain.relic import RelicTag


# ---------------------------------------------------------------------------
# create_sample_combat() — structure
# ---------------------------------------------------------------------------

class TestCreateSampleCombatStructure:
    def test_returns_valid_state(self):
        state = create_sample_combat()
        assert state is not None

    def test_has_three_enemies(self):
        assert len(create_sample_combat().enemies) == 3

    def test_all_enemies_alive(self):
        for enemy in create_sample_combat().enemies:
            assert enemy.is_alive

    def test_player_alive(self):
        state = create_sample_combat()
        assert state.player.current_hp > 0

    def test_player_name(self):
        assert create_sample_combat().player.name == "Viajero"

    def test_has_four_relics(self):
        assert len(create_sample_combat().relics) == 4

    def test_turn_starts_at_one(self):
        assert create_sample_combat().turn == 1

    def test_no_active_powers_initially(self):
        assert create_sample_combat().active_powers == []

    def test_selected_and_targeted_none(self):
        state = create_sample_combat()
        assert state.selected_card_index is None
        assert state.targeted_enemy_index is None


# ---------------------------------------------------------------------------
# Relic tags in sample combat
# ---------------------------------------------------------------------------

class TestSampleCombatRelicTags:
    def test_combat_amulet_present(self):
        relics = create_sample_combat().relics
        assert any(r.tag == RelicTag.COMBAT_AMULET for r in relics)

    def test_broken_totem_present(self):
        relics = create_sample_combat().relics
        assert any(r.tag == RelicTag.BROKEN_TOTEM for r in relics)

    def test_fire_orb_present(self):
        relics = create_sample_combat().relics
        assert any(r.tag == RelicTag.FIRE_ORB for r in relics)

    def test_spectral_shield_present(self):
        relics = create_sample_combat().relics
        assert any(r.tag == RelicTag.SPECTRAL_SHIELD for r in relics)

    def test_all_relics_active_at_start(self):
        for relic in create_sample_combat().relics:
            assert relic.is_active


# ---------------------------------------------------------------------------
# Relic effects applied by draw_opening_hand
# ---------------------------------------------------------------------------

class TestSampleCombatRelicEffects:
    def test_mana_max_is_four(self):
        # COMBAT_AMULET adds 1 → 3+1=4
        assert create_sample_combat().mana.maximum == 4

    def test_mana_current_is_four(self):
        assert create_sample_combat().mana.current == 4

    def test_hand_has_six_cards(self):
        # Base 5 + 1 from BROKEN_TOTEM = 6
        assert create_sample_combat().hand.count == 6

    def test_fire_orb_bonus_is_two(self):
        state = create_sample_combat()
        assert relic_effects.extra_attack_damage(state.relics) == 2

    def test_draw_bonus_is_one(self):
        state = create_sample_combat()
        assert relic_effects.extra_draw_per_turn(state.relics) == 1


# ---------------------------------------------------------------------------
# Card pool integrity
# ---------------------------------------------------------------------------

class TestSampleCombatCardPool:
    def test_total_cards_is_eighteen(self):
        # 8 interesting + 10 Golpe = 18 cards total in draw+hand
        state = create_sample_combat()
        total = state.hand.count + state.draw_pile.count + state.discard_pile.count
        assert total == 21  # 18 draw + 3 discard kept separate

    def test_hand_cards_have_valid_cost(self):
        for card in create_sample_combat().hand.cards:
            assert card.cost >= 0

    def test_draw_pile_not_empty_after_opening_hand(self):
        # 18 total in deck; drew 6 → 12 left in draw pile
        state = create_sample_combat()
        assert state.draw_pile.count == 12

    def test_discard_has_three_cards(self):
        # Discard pile starts with 3 Defender cards
        assert create_sample_combat().discard_pile.count == 3

    def test_all_hand_cards_have_positive_or_zero_values(self):
        for card in create_sample_combat().hand.cards:
            assert card.total_damage() >= 0
            assert card.total_block() >= 0

    def test_reproducible_total_across_runs(self):
        # Shuffling changes order but never card count
        totals = set()
        for _ in range(5):
            state = create_sample_combat()
            totals.add(state.hand.count + state.draw_pile.count + state.discard_pile.count)
        assert totals == {21}
