"""Chromas (golden = x2): domain rules, card play, relics and drops. No pygame."""
from __future__ import annotations

import random

import pytest

from src.application import relic_effects
from src.application.card_rewards import pick_pack_cards, pick_reward_cards
from src.application.play_card import play_card
from src.application.run_manager import create_run, pick_boss_relics, pick_shop_stock, pick_treasure_relic
from src.domain import chroma as chroma_mod
from src.domain.card import Card, CardEffect, CardType
from src.domain.card_pool import PackTheme, card_factories_for_theme
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import (
    CHROMA_DEFS,
    Chroma,
    ChromaDef,
    chroma_def,
    chroma_title,
    effect_multiplier,
    roll_chroma,
)
from src.domain.entities import StatusEffect
from src.domain.numbers import BigValue
from src.domain.relic import Relic, RelicTag
from tests.application.test_play_card import _make_state

G = Chroma.GOLDEN


def _card(dmg=0, blk=0, draw=0, mana=0, on_play=None, chroma=None, ctype=CardType.ATTACK, cost=1):
    return Card(id="c", name="Carta", card_type=ctype, cost=cost, chroma=chroma,
                base_effect=CardEffect(name="Carta", damage=BigValue(dmg), block=BigValue(blk),
                                       draw=draw, mana_gain=mana, on_play=on_play))


def _relic(tag, chroma=None, active=True):
    return Relic("r", "Reliquia", "desc", tag=tag, chroma=chroma, is_active=active)


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------

class TestChromaDomain:
    def test_golden_doubles(self):
        assert effect_multiplier(G) == 2
        assert effect_multiplier(None) == 1

    def test_every_chroma_has_a_definition_and_texts(self):
        for c in Chroma:
            d = chroma_def(c)
            assert d.chroma is c and d.name and d.card_note and d.relic_note and d.short_note

    def test_golden_texts_mention_x2(self):
        d = chroma_def(G)
        assert "x2" in d.card_note and "x2" in d.relic_note and "x2" in d.short_note
        assert "dorada" in d.card_note.lower()

    def test_title(self):
        assert chroma_title("Golpe", G) == "Golpe · Dorada"
        assert chroma_title("Golpe", None) == "Golpe"

    def test_card_defaults_without_chroma(self):
        assert _card(dmg=6).chroma is None
        assert _card(dmg=6).total_damage() == 6

    def test_golden_card_totals_double(self):
        c = _card(dmg=6, blk=5, draw=1, mana=2, chroma=G)
        assert (c.total_damage(), c.total_block(), c.total_draw(), c.total_mana_gain()) == (12, 10, 2, 4)

    def test_golden_doubles_stacked_effects_too(self):
        c = _card(dmg=6, chroma=G)
        c.stacked_effects.append(CardEffect(name="extra", damage=BigValue(4)))
        assert c.total_damage() == 20

    def test_golden_relic_multiplier(self):
        assert _relic(RelicTag.FIRE_ORB, G).effect_multiplier() == 2

    def test_roll_uses_drop_chances(self):
        rng = random.Random(1)
        cards = [roll_chroma(rng) for _ in range(20_000)]
        relics = [roll_chroma(rng, for_relic=True) for _ in range(20_000)]
        assert 0.04 < cards.count(G) / 20_000 < 0.06
        assert 0.07 < relics.count(G) / 20_000 < 0.09
        assert set(cards) == {None, G}

    def test_new_chroma_kinds_plug_in_through_the_registry(self):
        # A future chroma only needs a definition; rolls and multipliers read it.
        fake = ChromaDef(G, "X", "n", "n", "n", effect_multiplier=5, card_drop_chance=1.0)
        saved = dict(CHROMA_DEFS)
        try:
            CHROMA_DEFS[G] = fake
            assert effect_multiplier(G) == 5
            assert roll_chroma(random.Random(0)) is G
        finally:
            CHROMA_DEFS.clear()
            CHROMA_DEFS.update(saved)


# ---------------------------------------------------------------------------
# Playing golden cards
# ---------------------------------------------------------------------------

class TestGoldenCardPlay:
    def test_damage_doubles_bonuses_added_once(self):
        state = _make_state([_card(dmg=6, chroma=G)], enemy_hp=50, player_attack_bonus=3)
        assert play_card(state, 0, 0).success
        assert state.enemies[0].current_hp == 50 - (12 + 3)

    def test_block_doubles_dexterity_added_once(self):
        state = _make_state([_card(blk=5, chroma=G, ctype=CardType.SKILL)], player_dexterity=2)
        play_card(state, 0)
        assert state.player.block == 12

    def test_draw_and_mana_double(self):
        fillers = [_card(dmg=1) for _ in range(5)]
        state = _make_state([_card(draw=1, mana=1, chroma=G, ctype=CardType.SKILL, cost=1)],
                            draw_cards=fillers, mana_current=1, mana_max=5)
        play_card(state, 0)
        assert state.hand.count == 2
        assert state.mana.current == 1 - 1 + 2

    def test_on_play_runs_twice(self):
        def poison(state):
            state.enemies[0].status_effects.append(StatusEffect("Veneno", 3, is_buff=False))
        card = _card(on_play=poison, chroma=G, ctype=CardType.SKILL)
        card.base_effect.needs_target = True
        state = _make_state([card])
        play_card(state, 0, 0)
        assert sum(s.stacks for s in state.enemies[0].status_effects) == 6

    def test_cost_is_not_doubled(self):
        state = _make_state([_card(dmg=6, chroma=G, cost=2)], mana_current=3)
        play_card(state, 0, 0)
        assert state.mana.current == 1

    def test_pool_on_play_card_golden(self):
        factory = next(f for f in card_factories_for_theme(PackTheme.ACERO) if f.card_id == "a_golpe_total")
        card = factory()
        card.chroma = G
        state = _make_state([card], enemy_hp=50)
        play_card(state, 0)
        assert state.enemies[0].current_hp == 30        # 10 to all, twice

    def test_chroma_hook_runs_after_play(self):
        calls = []
        saved = dict(CHROMA_DEFS)
        try:
            d = CHROMA_DEFS[G]
            CHROMA_DEFS[G] = ChromaDef(d.chroma, d.name, d.card_note, d.relic_note, d.short_note,
                                       effect_multiplier=2,
                                       on_card_played=lambda st, c: calls.append((c.name, st.hand.count)))
            state = _make_state([_card(dmg=1, chroma=G)])
            play_card(state, 0, 0)
            assert calls == [("Carta", 0)]
        finally:
            CHROMA_DEFS.clear()
            CHROMA_DEFS.update(saved)

    def test_normal_card_unchanged(self):
        state = _make_state([_card(dmg=6)], enemy_hp=50)
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 44


# ---------------------------------------------------------------------------
# Golden relics
# ---------------------------------------------------------------------------

class TestGoldenRelics:
    @pytest.mark.parametrize("tag,fn,base", [
        (RelicTag.FIRE_ORB, relic_effects.extra_attack_damage, 2),
        (RelicTag.BROKEN_TOTEM, relic_effects.extra_draw_per_turn, 1),
        (RelicTag.ENERGY_STONE, relic_effects.extra_draw_per_turn, 1),
        (RelicTag.COMBAT_AMULET, relic_effects.bonus_starting_mana, 1),
        (RelicTag.GOLD_RING, relic_effects.bonus_gold_reward, 15),
        (RelicTag.BLOOD_POTION, relic_effects.post_combat_heal, 8),
        (RelicTag.IRON_HEART, relic_effects.max_hp_bonus, 15),
    ])
    def test_every_numeric_relic_doubles(self, tag, fn, base):
        assert fn([_relic(tag)]) == base
        assert fn([_relic(tag, G)]) == base * 2
        assert fn([_relic(tag, G), _relic(tag)]) == base * 3
        assert fn([_relic(tag, G, active=False)]) == 0

    def test_golden_spectral_shield_saves_twice(self):
        shield = _relic(RelicTag.SPECTRAL_SHIELD, G)
        state = _make_state([], relics=[shield], player_hp=0)
        assert relic_effects.try_spectral_shield(state) and state.player.current_hp == 1
        assert shield.is_active
        state.player.current_hp = 0
        assert relic_effects.try_spectral_shield(state) and state.player.current_hp == 1
        assert not shield.is_active
        state.player.current_hp = 0
        assert not relic_effects.try_spectral_shield(state)

    def test_normal_spectral_shield_saves_once(self):
        shield = _relic(RelicTag.SPECTRAL_SHIELD)
        state = _make_state([], relics=[shield], player_hp=0)
        assert relic_effects.try_spectral_shield(state)
        assert not shield.is_active


# ---------------------------------------------------------------------------
# Drops
# ---------------------------------------------------------------------------

class TestGoldenDrops:
    def _run(self, seed):
        return create_run(ALL_CHARACTERS[seed % 3], seed)

    def test_golden_cards_appear_in_rewards_and_packs(self):
        golden = total = 0
        for seed in range(400):
            run = self._run(seed)
            cards = pick_reward_cards(run, "r") + pick_pack_cards(run, PackTheme.ACERO)
            golden += sum(c.chroma is G for c in cards)
            total += len(cards)
        assert 0.02 < golden / total < 0.09

    def test_chroma_rolls_do_not_change_which_cards_are_offered(self):
        run = self._run(3)
        ids = [c.id for c in pick_pack_cards(run, PackTheme.MAGIA)]
        assert ids == [c.id for c in pick_pack_cards(run, PackTheme.MAGIA)]
        assert [c.chroma for c in pick_pack_cards(run, PackTheme.MAGIA)] == \
               [c.chroma for c in pick_pack_cards(run, PackTheme.MAGIA)]

    def test_golden_relics_appear(self):
        found = 0
        for seed in range(300):
            run = self._run(seed)
            run.current_room_id = "shop"
            relics = pick_boss_relics(run) + pick_shop_stock(run)[1] + [pick_treasure_relic(run, "t")]
            found += sum(r.chroma is G for r in relics)
        assert found > 0

    def test_relic_offers_are_deterministic_including_chroma(self):
        run = self._run(9)
        a = [(r.id, r.chroma) for r in pick_boss_relics(run)]
        assert a == [(r.id, r.chroma) for r in pick_boss_relics(run)]

    def test_stress_huge_seeds(self):
        for seed in range(300):
            run = create_run(ALL_CHARACTERS[seed % 3], seed * 10 ** 15)
            for card in pick_reward_cards(run, f"room{seed}"):
                assert card.chroma in (None, G)
                assert card.total_damage() == (card.total_damage() // card.effect_multiplier()) * card.effect_multiplier()
