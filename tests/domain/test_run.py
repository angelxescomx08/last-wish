"""Tests for the Run dataclass.

Covers default field values, add_card(), add_relic(), and apply_combat_result()
including the clamp-to-1 boundary.  No pygame dependency.
"""
from __future__ import annotations

from src.domain.card import Card, CardEffect, CardType
from src.domain.character import ALL_CHARACTERS, CharacterId
from src.domain.numbers import BigValue
from src.domain.relic import Relic, RelicTag
from src.domain.run import Run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _warrior() -> object:
    return next(c for c in ALL_CHARACTERS if c.id == CharacterId.WARRIOR)


def _make_run(**kwargs) -> Run:
    return Run(character=_warrior(), seed=42, **kwargs)


def _card(id: str = "test_card") -> Card:
    return Card(
        id=id,
        name="Golpe",
        card_type=CardType.ATTACK,
        cost=1,
        base_effect=CardEffect(name="Golpe", damage=BigValue(6)),
    )


def _relic(tag: RelicTag = RelicTag.FIRE_ORB) -> Relic:
    return Relic(id="r_test", name="Reliquía", description="Desc", tag=tag)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

class TestRunDefaults:
    def test_floor_default_one(self):
        run = _make_run()
        assert run.floor == 1

    def test_gold_default_zero(self):
        run = _make_run()
        assert run.gold == 0

    def test_deck_default_empty(self):
        run = _make_run()
        assert run.deck == []

    def test_relics_default_empty(self):
        run = _make_run()
        assert run.relics == []

    def test_current_room_id_default_none(self):
        run = _make_run()
        assert run.current_room_id is None

    def test_character_stored(self):
        run = _make_run()
        assert run.character.id == CharacterId.WARRIOR

    def test_seed_stored(self):
        run = _make_run()
        assert run.seed == 42


# ---------------------------------------------------------------------------
# add_card()
# ---------------------------------------------------------------------------

class TestAddCard:
    def test_add_card_appends_to_deck(self):
        run = _make_run()
        card = _card()
        run.add_card(card)
        assert card in run.deck

    def test_deck_length_increases(self):
        run = _make_run()
        run.add_card(_card("c1"))
        run.add_card(_card("c2"))
        assert len(run.deck) == 2

    def test_add_card_preserves_order(self):
        run = _make_run()
        c1 = _card("c1")
        c2 = _card("c2")
        run.add_card(c1)
        run.add_card(c2)
        assert run.deck[0] is c1
        assert run.deck[1] is c2


# ---------------------------------------------------------------------------
# add_relic()
# ---------------------------------------------------------------------------

class TestAddRelic:
    def test_add_relic_appends(self):
        run = _make_run()
        relic = _relic()
        run.add_relic(relic)
        assert relic in run.relics

    def test_relic_count_increases(self):
        run = _make_run()
        run.add_relic(_relic(RelicTag.FIRE_ORB))
        run.add_relic(_relic(RelicTag.BROKEN_TOTEM))
        assert len(run.relics) == 2

    def test_add_relic_preserves_tag(self):
        run = _make_run()
        r = _relic(RelicTag.SPECTRAL_SHIELD)
        run.add_relic(r)
        assert run.relics[0].tag == RelicTag.SPECTRAL_SHIELD


# ---------------------------------------------------------------------------
# apply_combat_result()
# ---------------------------------------------------------------------------

class TestApplyCombatResult:
    def test_sets_current_hp(self):
        run = _make_run(player_max_hp=100, player_current_hp=100)
        run.apply_combat_result(60)
        assert run.player_current_hp == 60

    def test_clamps_zero_to_one(self):
        run = _make_run(player_max_hp=100, player_current_hp=100)
        run.apply_combat_result(0)
        assert run.player_current_hp == 1

    def test_clamps_negative_to_one(self):
        run = _make_run(player_max_hp=100, player_current_hp=100)
        run.apply_combat_result(-50)
        assert run.player_current_hp == 1

    def test_hp_one_stays_one(self):
        run = _make_run(player_max_hp=100, player_current_hp=50)
        run.apply_combat_result(1)
        assert run.player_current_hp == 1

    def test_full_hp_preserved(self):
        run = _make_run(player_max_hp=100, player_current_hp=50)
        run.apply_combat_result(100)
        assert run.player_current_hp == 100

    def test_does_not_affect_gold(self):
        run = _make_run(gold=75, player_max_hp=100, player_current_hp=100)
        run.apply_combat_result(50)
        assert run.gold == 75
