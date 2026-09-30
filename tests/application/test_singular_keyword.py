"""Keyword SINGULAR: extra layer when the starting deck has no repeated cards. No pygame."""
from __future__ import annotations

import pytest

from src.application.combat_factory import create_combat_from_run
from src.application.play_card import TargetKind, play_card, requires_target, target_kind
from src.application.run_manager import create_run
from src.domain.card import Card, CardEffect, CardType
from src.domain.card_pool import _add_singular
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma
from src.domain.entities import Enemy, Intent, IntentType
from src.domain.keywords import Keyword, deck_is_singular, keyword_def, singular_text
from src.domain.numbers import BigValue
from tests.application.test_play_card import _make_state


def _singular_card(dmg=6, sing_dmg=10, cid="unica", **kw):
    return Card(id=cid, name="Única", card_type=CardType.ATTACK, cost=1,
                base_effect=CardEffect(name="Única", damage=BigValue(dmg),
                                       singular=CardEffect(name="Singular", damage=BigValue(sing_dmg), **kw)))


def _card(cid, dmg=1):
    return Card(id=cid, name=cid, card_type=CardType.ATTACK, cost=0,
                base_effect=CardEffect(name=cid, damage=BigValue(dmg)))


def _enemy():
    return Enemy(id="e", name="E", max_hp=100, current_hp=100, intent=Intent(IntentType.ATTACK, 1))


class TestDomain:
    def test_definition(self):
        d = keyword_def(Keyword.SINGULAR)
        assert d.name == "Singular" and "repetidas" in d.rule

    def test_card_keywords(self):
        assert _singular_card().keywords() == frozenset({Keyword.SINGULAR})

    def test_both_keywords(self):
        c = _singular_card()
        c.base_effect.combo = CardEffect(name="Combo", block=BigValue(2))
        assert c.keywords() == frozenset({Keyword.COMBO, Keyword.SINGULAR})

    def test_totals(self):
        c = _singular_card()
        assert c.total_damage() == 6
        assert c.total_damage(singular=True) == 16
        assert c.total_damage(combo=True) == 6

    def test_text(self):
        assert singular_text(_singular_card()) == "+10 de daño"
        assert singular_text(_singular_card(sing_dmg=0, draw=2)) == "roba 2"

    def test_helper(self):
        c = _add_singular(_card("x"), blk=4, draw=1)
        assert c.singular_effects()[0].block.resolve() == 4
        assert c.total_draw(singular=True) == 1


class TestDeckIsSingular:
    def test_empty(self):
        assert deck_is_singular([])

    def test_one(self):
        assert deck_is_singular([_card("a")])

    def test_all_different(self):
        assert deck_is_singular([_card(c) for c in "abcdefghij"])

    def test_one_repeat(self):
        assert not deck_is_singular([_card("a"), _card("b"), _card("a")])

    def test_golden_copy_counts_as_repeat(self):
        gold = _card("a")
        gold.chroma = Chroma.GOLDEN
        assert not deck_is_singular([_card("a"), gold])

    def test_large_deck(self):
        assert deck_is_singular([_card(f"c{i}") for i in range(10_000)])
        assert not deck_is_singular([_card(f"c{i}") for i in range(10_000)] + [_card("c0")])


class TestCombat:
    def test_starter_decks_are_not_singular(self):
        for c in ALL_CHARACTERS:
            state = create_combat_from_run(create_run(c, 1), [_enemy()])
            assert state.singular_deck is False

    def test_run_deck_without_repeats_is_singular(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        run.deck = [_card(f"c{i}") for i in range(8)]
        assert create_combat_from_run(run, [_enemy()]).singular_deck is True

    def test_flag_fixed_for_the_combat(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        run.deck = [_card(f"c{i}") for i in range(8)]
        state = create_combat_from_run(run, [_enemy()])
        state.hand.cards.append(_card("c0"))       # a copy appearing mid-combat changes nothing
        assert state.singular_deck is True


class TestPlay:
    def test_resolves_when_singular(self):
        state = _make_state([_singular_card()])
        state.singular_deck = True
        result = play_card(state, 0, 0)
        assert result.success and result.singular
        assert state.enemies[0].current_hp == 50 - 16
        assert "Singular" in result.message

    def test_not_when_deck_has_repeats(self):
        state = _make_state([_singular_card()])
        state.singular_deck = False
        result = play_card(state, 0, 0)
        assert not result.singular
        assert state.enemies[0].current_hp == 50 - 6

    def test_first_card_of_turn_works(self):
        # Unlike Combo, Singular does not need another card played first.
        state = _make_state([_singular_card()])
        state.singular_deck = True
        assert state.cards_played_this_turn == 0
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 34

    def test_plain_card_not_flagged(self):
        state = _make_state([_card("p")])
        state.singular_deck = True
        assert not play_card(state, 0, 0).singular

    def test_golden_card_resolves_layer_each_cast(self):
        c = _singular_card()
        c.chroma = Chroma.GOLDEN
        state = _make_state([c], enemy_hp=100)
        state.singular_deck = True
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 100 - 16 * 2

    def test_singular_layer_block_and_draw(self):
        c = Card(id="s", name="S", card_type=CardType.SKILL, cost=0,
                 base_effect=CardEffect(name="S", singular=CardEffect(name="Singular", block=BigValue(5), draw=1)))
        state = _make_state([c], draw_cards=[_card("d")])
        state.singular_deck = True
        play_card(state, 0)
        assert state.player.block == 5 and state.hand.count == 1

    def test_singular_damage_only_card_needs_target(self):
        c = Card(id="s", name="S", card_type=CardType.ATTACK, cost=0,
                 base_effect=CardEffect(name="S", singular=CardEffect(name="Singular", damage=BigValue(3))))
        assert requires_target(c) and target_kind(c) is TargetKind.ENEMY

    @pytest.mark.parametrize("singular_deck", [True, False])
    def test_singular_ready(self, singular_deck):
        state = _make_state([])
        state.singular_deck = singular_deck
        assert state.singular_ready(_singular_card()) is singular_deck
        assert state.singular_ready(_card("p")) is False
