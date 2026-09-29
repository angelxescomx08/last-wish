"""Keyword COMBO: extra layer when another card was played earlier this turn. No pygame."""
from __future__ import annotations

from src.application.end_turn import end_player_turn
from src.application.play_card import play_card, requires_target
from src.domain.card import Card, CardClass, CardEffect, CardType
from src.domain.card_pool import card_factories_for_classes
from src.domain.chroma import Chroma
from src.domain.entities import StatusEffect
from src.domain.keywords import KEYWORD_DEFS, Keyword, combo_text, keyword_def
from src.domain.numbers import BigValue
from tests.application.test_play_card import _make_state


def _combo_card(dmg=6, combo_dmg=5, **combo_kw):
    return Card(id="tajo", name="Tajo", card_type=CardType.ATTACK, cost=1,
                base_effect=CardEffect(name="Tajo", damage=BigValue(dmg),
                                       combo=CardEffect(name="Combo", damage=BigValue(combo_dmg), **combo_kw)))


def _plain(dmg=1, cost=0):
    return Card(id="p", name="P", card_type=CardType.ATTACK, cost=cost,
                base_effect=CardEffect(name="P", damage=BigValue(dmg)))


def _pool_card(card_id):
    return next(f for f in card_factories_for_classes(set(CardClass)) if f.card_id == card_id)()


class TestKeywordDomain:
    def test_definitions(self):
        assert set(KEYWORD_DEFS) == set(Keyword)
        assert keyword_def(Keyword.COMBO).name == "Combo"
        assert "otra carta" in keyword_def(Keyword.COMBO).rule

    def test_card_keywords(self):
        assert _combo_card().keywords() == frozenset({Keyword.COMBO})
        assert _plain().keywords() == frozenset()

    def test_totals_with_and_without_combo(self):
        c = _combo_card()
        assert (c.total_damage(), c.total_damage(combo=True)) == (6, 11)

    def test_combo_text(self):
        assert combo_text(_combo_card()) == "+5 de daño"
        assert combo_text(_combo_card(combo_dmg=0, draw=1, mana_gain=1)) == "roba 1, +1 de maná"

    def test_golden_casts_combo_twice(self):
        c = _combo_card()
        c.chroma = Chroma.GOLDEN
        assert c.total_damage(combo=True) == 11 and combo_text(c) == "+5 de daño"
        state = _make_state([_plain(), c], enemy_hp=50)
        play_card(state, 0, 0)
        result = play_card(state, 0, 0)
        assert result.combo and result.casts == 2
        assert state.enemies[0].current_hp == 50 - 1 - 22


class TestComboInCombat:
    def test_first_card_of_turn_has_no_combo(self):
        state = _make_state([_combo_card()], enemy_hp=50)
        result = play_card(state, 0, 0)
        assert result.success and not result.combo
        assert state.enemies[0].current_hp == 44
        assert state.cards_played_this_turn == 1

    def test_second_card_triggers_combo(self):
        state = _make_state([_plain(), _combo_card()], enemy_hp=50)
        play_card(state, 0, 0)
        result = play_card(state, 0, 0)
        assert result.combo and "Combo" in result.message
        assert state.enemies[0].current_hp == 50 - 1 - 11

    def test_combo_resets_next_turn(self):
        state = _make_state([_plain()], enemy_hp=500, draw_cards=[_combo_card() for _ in range(10)])
        play_card(state, 0, 0)
        assert state.combo_active
        end_player_turn(state)
        assert state.cards_played_this_turn == 0 and not state.combo_active

    def test_failed_play_does_not_count(self):
        state = _make_state([_plain(cost=9)])
        assert not play_card(state, 0, 0).success
        assert state.cards_played_this_turn == 0

    def test_combo_draw_and_mana(self):
        card = Card(id="c", name="C", card_type=CardType.SKILL, cost=1,
                    base_effect=CardEffect(name="C", block=BigValue(6),
                                           combo=CardEffect(name="Combo", draw=1, mana_gain=1)))
        state = _make_state([_plain(), card], draw_cards=[_plain() for _ in range(5)], mana_current=2, mana_max=5)
        play_card(state, 0, 0)
        play_card(state, 0)
        assert state.hand.count == 1
        assert state.mana.current == 2 - 0 - 1 + 1

    def test_combo_on_play_runs(self):
        def poison(state):
            state.enemies[0].status_effects.append(StatusEffect("Veneno", 3, is_buff=False))
        card = Card(id="v", name="V", card_type=CardType.SKILL, cost=1,
                    base_effect=CardEffect(name="V", needs_target=True, on_play=poison,
                                           combo=CardEffect(name="Combo", on_play=poison)))
        state = _make_state([_plain(), card])
        play_card(state, 0, 0)
        play_card(state, 0, 0)
        assert sum(s.stacks for s in state.enemies[0].status_effects) == 6

    def test_combo_only_damage_needs_target(self):
        card = Card(id="x", name="X", card_type=CardType.SKILL, cost=0,
                    base_effect=CardEffect(name="X", combo=CardEffect(name="Combo", damage=BigValue(3))))
        assert requires_target(card)


class TestRogueCards:
    def test_combo_cards_belong_to_the_rogue(self):
        combo = [f() for f in card_factories_for_classes(set(CardClass)) if f().combo_effects()]
        assert len(combo) == 8
        assert {c.card_class for c in combo} == {CardClass.ROGUE}

    def test_every_rogue_combo_card_is_stronger_with_combo(self):
        for f in card_factories_for_classes({CardClass.ROGUE}):
            c = f()
            if not c.combo_effects():
                continue
            with_c = (c.total_damage(True), c.total_block(True), c.total_draw(True), c.total_mana_gain(True))
            without = (c.total_damage(), c.total_block(), c.total_draw(), c.total_mana_gain())
            assert with_c != without or any(fx.on_play for fx in c.combo_effects()), c.name

    def test_real_tajo_combo(self):
        state = _make_state([_plain(), _pool_card("a_tajo")], enemy_hp=50)
        play_card(state, 0, 0)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 50 - 1 - 11

    def test_stress_many_turns(self):
        state = _make_state([], enemy_hp=10 ** 9, draw_cards=[_combo_card() if i % 2 else _plain()
                                                              for i in range(40)], mana_current=99, mana_max=99)
        end_player_turn(state)
        for _ in range(300):
            while state.hand.count:
                assert play_card(state, 0, 0).success
            end_player_turn(state)
            state.enemies[0].current_hp = 10 ** 9
            state.player.current_hp = 100
        assert state.turn == 302
