"""Tests for application/combat_factory.py — create_combat_for_character().

Verifies that each character produces a CombatState with correct player stats,
full HP for player and all enemies, valid card/relic setup, and that the
character's luck and stats affect the initial state correctly.
"""
from __future__ import annotations

import pytest

from src.application.combat_factory import create_combat_for_character
from src.domain.character import ALL_CHARACTERS, Character, CharacterId, CharacterStats
from src.domain.combat import CombatState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(char_id: CharacterId) -> Character:
    return next(c for c in ALL_CHARACTERS if c.id == char_id)


# ---------------------------------------------------------------------------
# Player stats mirrored from character
# ---------------------------------------------------------------------------

class TestPlayerStats:
    def test_warrior_full_hp(self):
        state = create_combat_for_character(_get(CharacterId.WARRIOR))
        assert state.player.current_hp == state.player.max_hp

    def test_mage_full_hp(self):
        state = create_combat_for_character(_get(CharacterId.MAGE))
        assert state.player.current_hp == state.player.max_hp

    def test_rogue_full_hp(self):
        state = create_combat_for_character(_get(CharacterId.ROGUE))
        assert state.player.current_hp == state.player.max_hp

    def test_player_max_hp_matches_character(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            assert state.player.max_hp == c.stats.max_hp

    def test_player_dexterity_matches_character(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            assert state.player.dexterity == c.stats.dexterity

    def test_player_attack_bonus_matches_character(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            assert state.player.attack_bonus == c.stats.damage

    def test_player_luck_matches_character(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            assert state.player.luck == c.stats.luck

    def test_player_name_matches_character(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            assert state.player.name == c.name


# ---------------------------------------------------------------------------
# Mana setup
# ---------------------------------------------------------------------------

class TestManaSetup:
    def test_mana_starts_at_max(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            # COMBAT_AMULET adds 1 to mana.maximum; current must equal maximum
            assert state.mana.current == state.mana.maximum

    def test_warrior_base_mana(self):
        state = create_combat_for_character(_get(CharacterId.WARRIOR))
        # COMBAT_AMULET adds 1; warrior has max_mana=2 → expected 3
        assert state.mana.maximum == _get(CharacterId.WARRIOR).stats.max_mana + 1

    def test_mage_base_mana(self):
        state = create_combat_for_character(_get(CharacterId.MAGE))
        assert state.mana.maximum == _get(CharacterId.MAGE).stats.max_mana + 1


# ---------------------------------------------------------------------------
# Enemies at full HP
# ---------------------------------------------------------------------------

class TestEnemiesAtFullHp:
    def test_all_enemies_alive(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            for enemy in state.enemies:
                assert enemy.is_alive

    def test_all_enemies_at_full_hp(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            for enemy in state.enemies:
                assert enemy.current_hp == enemy.max_hp

    def test_three_enemies(self):
        state = create_combat_for_character(_get(CharacterId.WARRIOR))
        assert len(state.enemies) == 3


# ---------------------------------------------------------------------------
# Card and relic structure
# ---------------------------------------------------------------------------

class TestCardAndRelicSetup:
    def test_hand_non_empty(self):
        for c in ALL_CHARACTERS:
            state = create_combat_for_character(c)
            assert state.hand.count > 0

    def test_relics_present(self):
        state = create_combat_for_character(_get(CharacterId.MAGE))
        assert len(state.relics) > 0

    def test_turn_starts_at_one(self):
        state = create_combat_for_character(_get(CharacterId.ROGUE))
        assert state.turn == 1

    def test_player_block_starts_at_zero(self):
        state = create_combat_for_character(_get(CharacterId.WARRIOR))
        assert state.player.block == 0

    def test_returns_combat_state(self):
        state = create_combat_for_character(_get(CharacterId.MAGE))
        assert isinstance(state, CombatState)


# ---------------------------------------------------------------------------
# Luck bonus draw
# ---------------------------------------------------------------------------

class TestLuckBonusDraw:
    def test_rogue_draws_more_than_warrior(self):
        warrior_state = create_combat_for_character(_get(CharacterId.WARRIOR))
        rogue_state   = create_combat_for_character(_get(CharacterId.ROGUE))
        warrior_luck  = _get(CharacterId.WARRIOR).stats.luck
        rogue_luck    = _get(CharacterId.ROGUE).stats.luck
        # Rogue has more luck → should draw more cards if luck // 5 differs
        if rogue_luck // 5 > warrior_luck // 5:
            assert rogue_state.hand.count > warrior_state.hand.count
