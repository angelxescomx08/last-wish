"""Keyword VOID ("Vacío"): extra layer when the card spends your last mana. No pygame."""
from __future__ import annotations

import pytest

from src.application.play_card import TargetKind, play_card, requires_target, target_kind
from src.domain.card import Card, CardEffect, CardType
from src.domain.card_pool import _add_void
from src.domain.chroma import Chroma
from src.domain.keywords import Keyword, keyword_def, void_text, void_triggers
from src.domain.numbers import BigValue
from tests.application.test_play_card import _make_state


def _void_card(cost=1, dmg=4, void_dmg=6, cid="chispa", **kw):
    return Card(id=cid, name="Chispa", card_type=CardType.ATTACK, cost=cost,
                base_effect=CardEffect(name="Chispa", damage=BigValue(dmg),
                                       void=CardEffect(name="Vacío", damage=BigValue(void_dmg), **kw)))


def _plain(cost=1):
    return Card(id="p", name="P", card_type=CardType.ATTACK, cost=cost,
                base_effect=CardEffect(name="P", damage=BigValue(1)))


class TestDomain:
    def test_definition(self):
        d = keyword_def(Keyword.VOID)
        assert d.name == "Vacío" and "0 de maná" in d.rule

    def test_card_keywords(self):
        assert _void_card().keywords() == frozenset({Keyword.VOID})

    def test_totals(self):
        c = _void_card()
        assert (c.total_damage(), c.total_damage(void=True)) == (4, 10)
        assert c.total_damage(combo=True, singular=True) == 4

    def test_text_and_helper(self):
        assert void_text(_void_card()) == "+6 de daño"
        c = _add_void(_plain(), blk=3, draw=1)
        assert c.total_block(void=True) == 3 and c.total_draw(void=True) == 1

    @pytest.mark.parametrize("cost, mana, expected", [
        (1, 1, True), (3, 3, True), (10**6, 10**6, True),
        (1, 2, False), (2, 3, False),
        (0, 0, False),   # a free card never "spends" the last mana
        (0, 1, False),
    ])
    def test_void_triggers(self, cost, mana, expected):
        assert void_triggers(cost, mana) is expected


class TestReady:
    def test_ready_when_cost_equals_mana(self):
        state = _make_state([], mana_current=2)
        assert state.void_ready(_void_card(cost=2))
        assert not state.void_ready(_void_card(cost=1))

    def test_plain_card_never_ready(self):
        state = _make_state([], mana_current=1)
        assert not state.void_ready(_plain(cost=1))


class TestPlay:
    def test_last_mana_triggers(self):
        state = _make_state([_void_card(cost=1)], mana_current=1)
        result = play_card(state, 0, 0)
        assert result.success and result.void
        assert state.enemies[0].current_hp == 50 - 10
        assert state.mana.current == 0
        assert "Vacío" in result.message

    def test_mana_left_does_not_trigger(self):
        state = _make_state([_void_card(cost=1)], mana_current=3)
        result = play_card(state, 0, 0)
        assert not result.void
        assert state.enemies[0].current_hp == 50 - 4

    def test_second_card_that_empties_mana(self):
        state = _make_state([_plain(cost=2), _void_card(cost=1)], mana_current=3)
        assert not play_card(state, 0, 0).void            # 3 → 1
        assert play_card(state, 0, 0).void                # 1 → 0
        assert state.enemies[0].current_hp == 50 - 1 - 10

    def test_free_card_at_zero_mana_does_not_trigger(self):
        state = _make_state([_void_card(cost=0)], mana_current=0)
        assert not play_card(state, 0, 0).void

    def test_mana_gain_in_void_layer(self):
        c = Card(id="r", name="R", card_type=CardType.SKILL, cost=2,
                 base_effect=CardEffect(name="R", void=CardEffect(name="Vacío", mana_gain=1)))
        state = _make_state([c], mana_current=2)
        assert play_card(state, 0).void
        assert state.mana.current == 1

    def test_golden_resolves_layer_each_cast(self):
        c = _void_card(cost=1)
        c.chroma = Chroma.GOLDEN
        state = _make_state([c], mana_current=1, enemy_hp=100)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 100 - 10 * 2

    def test_void_damage_only_card_needs_target(self):
        c = Card(id="v", name="V", card_type=CardType.ATTACK, cost=1,
                 base_effect=CardEffect(name="V", void=CardEffect(name="Vacío", damage=BigValue(5))))
        assert requires_target(c) and target_kind(c) is TargetKind.ENEMY

    def test_combo_and_void_together(self):
        c = _void_card(cost=1)
        c.base_effect.combo = CardEffect(name="Combo", damage=BigValue(2))
        state = _make_state([_plain(cost=1), c], mana_current=2)
        play_card(state, 0, 0)
        result = play_card(state, 0, 0)
        assert result.combo and result.void
        assert state.enemies[0].current_hp == 50 - 1 - (4 + 2 + 6)
