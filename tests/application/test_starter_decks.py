"""Starter decks per class: La Pícara has her own 9-card deck. No pygame."""
from __future__ import annotations

from src.application.play_card import play_card
from src.application.run_manager import create_run
from src.domain.card import CardClass, CardRarity, CardType
from src.domain.card_pool import starter_deck
from src.domain.character import ALL_CHARACTERS, CharacterId
from src.domain.keywords import Keyword
from tests.application.test_play_card import _make_state


def _deck(cid):
    return starter_deck(cid)


class TestRogueStarter:
    def test_composition(self):
        deck = _deck(CharacterId.ROGUE)
        assert len(deck) == 9
        attacks = [c for c in deck if c.name == "Puñalada"]
        blocks = [c for c in deck if c.name == "Esquiva"]
        combo = [c for c in deck if Keyword.COMBO in c.keywords()]
        assert len(attacks) == 4 and len(blocks) == 4 and len(combo) == 1

    def test_values(self):
        deck = _deck(CharacterId.ROGUE)
        for c in deck:
            if c.name == "Puñalada":
                assert (c.card_type, c.cost, c.total_damage(), c.total_block()) == (CardType.ATTACK, 1, 6, 0)
            elif c.name == "Esquiva":
                assert (c.card_type, c.cost, c.total_damage(), c.total_block()) == (CardType.SKILL, 1, 0, 6)
        finta = next(c for c in deck if c.name == "Finta")
        assert finta.cost == 1
        assert (finta.total_damage(), finta.total_block()) == (4, 0)
        assert (finta.total_damage(combo=True), finta.total_block(combo=True)) == (4, 4)

    def test_rogue_class_and_common(self):
        deck = _deck(CharacterId.ROGUE)
        assert {c.card_class for c in deck} == {CardClass.ROGUE}
        assert {c.rarity for c in deck} == {CardRarity.COMMON}

    def test_finta_combo_in_combat(self):
        deck = _deck(CharacterId.ROGUE)
        punalada = next(c for c in deck if c.name == "Puñalada")
        finta = next(c for c in deck if c.name == "Finta")
        state = _make_state([punalada, finta], enemy_hp=50)
        play_card(state, 0, 0)
        result = play_card(state, 0, 0)
        assert result.combo
        assert state.enemies[0].current_hp == 50 - 6 - 4
        assert state.player.block == 4

    def test_finta_without_combo_gives_no_block(self):
        finta = next(c for c in _deck(CharacterId.ROGUE) if c.name == "Finta")
        state = _make_state([finta], enemy_hp=50)
        assert not play_card(state, 0, 0).combo
        assert state.player.block == 0 and state.enemies[0].current_hp == 46

    def test_fresh_instances(self):
        a, b = _deck(CharacterId.ROGUE), _deck(CharacterId.ROGUE)
        assert all(x is not y for x, y in zip(a, b))


class TestOtherClasses:
    def test_warrior_mage_and_default_keep_shared_deck(self):
        shared = [c.id for c in starter_deck()]
        assert len(shared) == 10
        assert [c.id for c in _deck(CharacterId.WARRIOR)] == shared
        assert [c.id for c in _deck(CharacterId.MAGE)] == shared

    def test_runs_start_with_their_class_deck(self):
        for ch in ALL_CHARACTERS:
            run = create_run(ch, 3)
            assert len(run.deck) == (9 if ch.id is CharacterId.ROGUE else 10)
