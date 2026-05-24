"""Tests for domain/character.py — CharacterStats, Character, ALL_CHARACTERS.

Stress philosophy: verify that all three characters have non-zero stats,
that stat values are within sensible ranges, and that the list is stable.
"""
from __future__ import annotations

import pytest

from src.domain.character import ALL_CHARACTERS, Character, CharacterId, CharacterStats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stats(damage: int = 5, max_hp: int = 80, luck: int = 4,
           max_mana: int = 3, dexterity: int = 2) -> CharacterStats:
    return CharacterStats(
        damage=damage, max_hp=max_hp, luck=luck,
        max_mana=max_mana, dexterity=dexterity,
    )


# ---------------------------------------------------------------------------
# CharacterStats
# ---------------------------------------------------------------------------

class TestCharacterStats:
    def test_fields_stored(self):
        s = _stats()
        assert s.damage == 5
        assert s.max_hp == 80
        assert s.luck == 4
        assert s.max_mana == 3
        assert s.dexterity == 2

    def test_frozen(self):
        s = _stats()
        with pytest.raises((AttributeError, TypeError)):
            s.damage = 99  # type: ignore[misc]

    def test_zero_stats_allowed(self):
        s = CharacterStats(damage=0, max_hp=1, luck=0, max_mana=1, dexterity=0)
        assert s.damage == 0
        assert s.dexterity == 0

    def test_large_stats(self):
        s = CharacterStats(damage=10**6, max_hp=10**9, luck=10**3, max_mana=100, dexterity=50)
        assert s.max_hp == 10**9


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------

class TestCharacter:
    def test_fields_stored(self):
        c = Character(
            id=CharacterId.WARRIOR,
            name="El Guerrero",
            description="Descripción",
            stats=_stats(),
        )
        assert c.id == CharacterId.WARRIOR
        assert c.name == "El Guerrero"
        assert c.description == "Descripción"

    def test_frozen(self):
        c = Character(
            id=CharacterId.MAGE,
            name="El Mago",
            description="Desc",
            stats=_stats(),
        )
        with pytest.raises((AttributeError, TypeError)):
            c.name = "otro"  # type: ignore[misc]

    def test_stats_accessible(self):
        c = Character(
            id=CharacterId.ROGUE,
            name="El Pícaro",
            description="Desc",
            stats=_stats(damage=6, dexterity=3),
        )
        assert c.stats.damage == 6
        assert c.stats.dexterity == 3


# ---------------------------------------------------------------------------
# ALL_CHARACTERS list
# ---------------------------------------------------------------------------

class TestAllCharacters:
    def test_exactly_three_characters(self):
        assert len(ALL_CHARACTERS) == 3

    def test_all_ids_unique(self):
        ids = [c.id for c in ALL_CHARACTERS]
        assert len(set(ids)) == len(ids)

    def test_all_ids_are_valid_enum(self):
        for c in ALL_CHARACTERS:
            assert isinstance(c.id, CharacterId)

    def test_all_have_positive_hp(self):
        for c in ALL_CHARACTERS:
            assert c.stats.max_hp > 0

    def test_all_have_positive_mana(self):
        for c in ALL_CHARACTERS:
            assert c.stats.max_mana > 0

    def test_warrior_is_tank(self):
        warrior = next(c for c in ALL_CHARACTERS if c.id == CharacterId.WARRIOR)
        mage    = next(c for c in ALL_CHARACTERS if c.id == CharacterId.MAGE)
        assert warrior.stats.max_hp > mage.stats.max_hp
        assert warrior.stats.dexterity > mage.stats.dexterity

    def test_mage_has_most_damage(self):
        damages = [c.stats.damage for c in ALL_CHARACTERS]
        mage = next(c for c in ALL_CHARACTERS if c.id == CharacterId.MAGE)
        assert mage.stats.damage == max(damages)

    def test_rogue_has_most_luck(self):
        lucks = [c.stats.luck for c in ALL_CHARACTERS]
        rogue = next(c for c in ALL_CHARACTERS if c.id == CharacterId.ROGUE)
        assert rogue.stats.luck == max(lucks)

    def test_names_are_spanish(self):
        names = [c.name for c in ALL_CHARACTERS]
        assert any("El " in name for name in names)

    def test_descriptions_non_empty(self):
        for c in ALL_CHARACTERS:
            assert len(c.description) > 0

    def test_all_characters_iteration(self):
        count = sum(1 for _ in ALL_CHARACTERS)
        assert count == 3
