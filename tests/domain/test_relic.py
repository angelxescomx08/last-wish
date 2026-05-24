"""Tests for Relic dataclass and RelicTag enum — creation, defaults, all tags."""
from __future__ import annotations

import pytest

from src.domain.relic import Relic, RelicTag


# ---------------------------------------------------------------------------
# RelicTag enum
# ---------------------------------------------------------------------------

class TestRelicTag:
    def test_core_tags_exist(self):
        tags = {t for t in RelicTag}
        assert RelicTag.COMBAT_AMULET   in tags
        assert RelicTag.BROKEN_TOTEM    in tags
        assert RelicTag.FIRE_ORB        in tags
        assert RelicTag.SPECTRAL_SHIELD in tags

    def test_new_tags_exist(self):
        tags = {t for t in RelicTag}
        assert RelicTag.ENERGY_STONE in tags
        assert RelicTag.GOLD_RING    in tags
        assert RelicTag.IRON_HEART   in tags
        assert RelicTag.BLOOD_POTION in tags

    def test_eight_tags_total(self):
        assert len(list(RelicTag)) == 8

    def test_tags_are_unique(self):
        values = [t.value for t in RelicTag]
        assert len(values) == len(set(values))

    def test_tags_are_strings(self):
        for tag in RelicTag:
            assert isinstance(tag.value, str)

    def test_combat_amulet_value(self):
        assert RelicTag.COMBAT_AMULET.value == "combat_amulet"

    def test_broken_totem_value(self):
        assert RelicTag.BROKEN_TOTEM.value == "broken_totem"

    def test_fire_orb_value(self):
        assert RelicTag.FIRE_ORB.value == "fire_orb"

    def test_spectral_shield_value(self):
        assert RelicTag.SPECTRAL_SHIELD.value == "spectral_shield"


# ---------------------------------------------------------------------------
# Relic — creation and defaults
# ---------------------------------------------------------------------------

class TestRelicDefaults:
    def test_is_active_default_true(self):
        r = Relic(id="r", name="N", description="D")
        assert r.is_active is True

    def test_tag_default_none(self):
        r = Relic(id="r", name="N", description="D")
        assert r.tag is None

    def test_all_fields_stored(self):
        r = Relic(
            id="r1",
            name="Orbe de Fuego",
            description="Daño extra",
            tag=RelicTag.FIRE_ORB,
            is_active=True,
        )
        assert r.id          == "r1"
        assert r.name        == "Orbe de Fuego"
        assert r.description == "Daño extra"
        assert r.tag         == RelicTag.FIRE_ORB
        assert r.is_active   is True


# ---------------------------------------------------------------------------
# Relic — each tag can be assigned
# ---------------------------------------------------------------------------

class TestRelicTagAssignment:
    def test_combat_amulet(self):
        r = Relic("r", "Amuleto", "", tag=RelicTag.COMBAT_AMULET)
        assert r.tag == RelicTag.COMBAT_AMULET

    def test_broken_totem(self):
        r = Relic("r", "Tótem", "", tag=RelicTag.BROKEN_TOTEM)
        assert r.tag == RelicTag.BROKEN_TOTEM

    def test_fire_orb(self):
        r = Relic("r", "Orbe", "", tag=RelicTag.FIRE_ORB)
        assert r.tag == RelicTag.FIRE_ORB

    def test_spectral_shield(self):
        r = Relic("r", "Escudo", "", tag=RelicTag.SPECTRAL_SHIELD)
        assert r.tag == RelicTag.SPECTRAL_SHIELD

    def test_tag_none_explicit(self):
        r = Relic("r", "Sin Tag", "", tag=None)
        assert r.tag is None


# ---------------------------------------------------------------------------
# Relic — is_active mutation
# ---------------------------------------------------------------------------

class TestRelicIsActive:
    def test_active_by_default(self):
        assert Relic("r", "R", "").is_active is True

    def test_inactive_on_creation(self):
        assert Relic("r", "R", "", is_active=False).is_active is False

    def test_can_deactivate(self):
        r = Relic("r", "R", "", tag=RelicTag.SPECTRAL_SHIELD)
        r.is_active = False
        assert not r.is_active

    def test_can_reactivate(self):
        r = Relic("r", "R", "", is_active=False)
        r.is_active = True
        assert r.is_active

    def test_deactivation_does_not_affect_tag(self):
        r = Relic("r", "R", "", tag=RelicTag.FIRE_ORB)
        r.is_active = False
        assert r.tag == RelicTag.FIRE_ORB
