"""Relics: Amuleto de Vitalidad, Trébol de Siete Hojas and the Rogue combo relics. No pygame."""
from __future__ import annotations

import random

import pytest

from src.application import relic_effects
from src.application.card_rewards import pick_reward_cards
from src.application.combat_factory import create_combat_from_run
from src.application.play_card import play_card
from src.application.run_manager import (
    _all_relic_defs,
    create_run,
    pick_boss_relics,
    pick_shop_stock,
    pick_treasure_relic,
    run_luck,
)
from src.domain.card import Card, CardClass, CardEffect, CardType
from src.domain.character import ALL_CHARACTERS, CharacterId
from src.domain.chroma import Chroma
from src.domain.entities import Enemy, Intent, IntentType
from src.domain.numbers import BigValue
from src.domain.rarity import Rarity
from src.domain.relic import Relic, RelicTag
from tests.application.test_play_card import _make_state

G = Chroma.GOLDEN


def _char(cid: CharacterId):
    return next(c for c in ALL_CHARACTERS if c.id is cid)


def _relic(tag, chroma=None, active=True):
    return Relic("r", "Reliquia", "d", tag=tag, chroma=chroma, is_active=active)


def _combo_card(dmg=0, blk=0) -> Card:
    return Card(id="cc", name="Combo", card_type=CardType.SKILL, cost=0,
                base_effect=CardEffect(name="Combo", damage=BigValue(dmg), block=BigValue(blk),
                                       combo=CardEffect(name="extra", block=BigValue(1))))


def _plain_card() -> Card:
    return Card(id="pc", name="Normal", card_type=CardType.SKILL, cost=0,
                base_effect=CardEffect(name="Normal", block=BigValue(2)))


def _enemy(hp=30, block=0, eid="e"):
    return Enemy(id=eid, name="E", max_hp=hp, current_hp=hp, block=block,
                 intent=Intent(IntentType.ATTACK, 1))


# --- definitions ---------------------------------------------------------------

class TestDefinitions:
    def test_new_relics_exist_with_tiers(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        assert defs[RelicTag.VITALITY_AMULET].rarity is Rarity.COMMON
        assert defs[RelicTag.SEVEN_LEAF_CLOVER].rarity is Rarity.LEGENDARY
        assert defs[RelicTag.EVASION_BROOCH].rarity is Rarity.UNCOMMON
        assert defs[RelicTag.THROWING_KNIFE].rarity is Rarity.UNCOMMON

    def test_classes(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        assert defs[RelicTag.VITALITY_AMULET].relic_class is CardClass.NEUTRAL
        assert defs[RelicTag.SEVEN_LEAF_CLOVER].relic_class is CardClass.NEUTRAL
        assert defs[RelicTag.EVASION_BROOCH].relic_class is CardClass.ROGUE
        assert defs[RelicTag.THROWING_KNIFE].relic_class is CardClass.ROGUE

    def test_every_tag_has_one_definition(self):
        tags = [r.tag for r in _all_relic_defs()]
        assert sorted(t.value for t in tags) == sorted(t.value for t in RelicTag)

    def test_default_relic_class_is_neutral(self):
        assert Relic("x", "X", "d").relic_class is CardClass.NEUTRAL


# --- class filter in offers ------------------------------------------------------

ROGUE_TAGS = {RelicTag.EVASION_BROOCH, RelicTag.THROWING_KNIFE}


class TestClassFilter:
    @pytest.mark.parametrize("cid", [CharacterId.WARRIOR, CharacterId.MAGE])
    def test_other_heroes_never_see_rogue_relics(self, cid):
        seen = set()
        for seed in range(150):
            run = create_run(_char(cid), seed)
            run.current_room_id = "shop"
            seen |= {r.tag for r in pick_boss_relics(run, 3)}
            seen.add(pick_treasure_relic(run, "t").tag)
            seen |= {r.tag for r in pick_shop_stock(run)[1]}
        assert not seen & ROGUE_TAGS

    def test_rogue_can_find_rogue_relics(self):
        seen = set()
        for seed in range(150):
            run = create_run(_char(CharacterId.ROGUE), seed)
            seen |= {r.tag for r in pick_boss_relics(run, 3)}
        assert ROGUE_TAGS <= seen

    def test_owning_everything_still_offers_only_allowed(self):
        run = create_run(_char(CharacterId.WARRIOR), 1)
        run.relics = [r for r in _all_relic_defs() if r.relic_class is CardClass.NEUTRAL]
        offered = pick_boss_relics(run, 3)
        assert len(offered) == 3
        assert all(r.relic_class is CardClass.NEUTRAL for r in offered)


# --- Amuleto de Vitalidad ------------------------------------------------------

class TestVitality:
    def test_plus_ten(self):
        assert relic_effects.max_hp_bonus([_relic(RelicTag.VITALITY_AMULET)]) == 10

    def test_golden_twenty(self):
        assert relic_effects.max_hp_bonus([_relic(RelicTag.VITALITY_AMULET, G)]) == 20

    def test_stacks_with_iron_heart(self):
        relics = [_relic(RelicTag.VITALITY_AMULET), _relic(RelicTag.IRON_HEART)]
        assert relic_effects.max_hp_bonus(relics) == 25

    def test_applies_to_combat(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        run.relics.append(_relic(RelicTag.VITALITY_AMULET))
        state = create_combat_from_run(run, [_enemy()])
        assert state.player.max_hp == ALL_CHARACTERS[0].stats.max_hp + 10


# --- Trébol de Siete Hojas -------------------------------------------------------

class TestClover:
    def test_luck_bonus(self):
        assert relic_effects.luck_bonus([]) == 0
        assert relic_effects.luck_bonus([_relic(RelicTag.SEVEN_LEAF_CLOVER)]) == 100
        assert relic_effects.luck_bonus([_relic(RelicTag.SEVEN_LEAF_CLOVER, G)]) == 200

    def test_inactive_gives_nothing(self):
        assert relic_effects.luck_bonus([_relic(RelicTag.SEVEN_LEAF_CLOVER, active=False)]) == 0

    def test_run_luck_and_player_luck(self):
        c = ALL_CHARACTERS[0]
        run = create_run(c, 1)
        run.relics.append(_relic(RelicTag.SEVEN_LEAF_CLOVER))
        assert run_luck(run) == c.stats.luck + 100
        assert create_combat_from_run(run, [_enemy()]).player.luck == c.stats.luck + 100

    def test_many_more_golden_cards(self):
        def golden(with_clover):
            total = 0
            for seed in range(200):
                run = create_run(ALL_CHARACTERS[0], seed)
                if with_clover:
                    run.relics.append(_relic(RelicTag.SEVEN_LEAF_CLOVER))
                total += sum(c.chroma is G for c in pick_reward_cards(run, "r"))
            return total
        assert golden(True) > golden(False) * 3


# --- Rogue combo relics ----------------------------------------------------------

class TestEvasionBrooch:
    def test_combo_card_gives_one_block(self):
        state = _make_state([_combo_card()], relics=[_relic(RelicTag.EVASION_BROOCH)])
        relic_effects.on_card_played(state, _combo_card(), True)
        assert state.player.block == 1

    def test_plain_card_gives_nothing(self):
        state = _make_state([], relics=[_relic(RelicTag.EVASION_BROOCH)])
        relic_effects.on_card_played(state, _plain_card(), True)
        assert state.player.block == 0

    def test_golden_gives_two(self):
        state = _make_state([], relics=[_relic(RelicTag.EVASION_BROOCH, G)])
        relic_effects.on_card_played(state, _combo_card(), True)
        assert state.player.block == 2

    def test_combo_not_resolved_gives_nothing(self):
        state = _make_state([], relics=[_relic(RelicTag.EVASION_BROOCH)])
        relic_effects.on_card_played(state, _combo_card(), False)
        assert state.player.block == 0

    def test_first_card_of_turn_does_not_trigger(self):
        # Combo card played first: its Combo layer does not resolve, so no relic.
        state = _make_state([_combo_card()], relics=[_relic(RelicTag.EVASION_BROOCH)])
        assert not play_card(state, 0).combo
        assert state.player.block == 0

    def test_second_card_triggers(self):
        # Plain card first (+2 block), then the combo card: its Combo (+1) and the brooch (+1).
        state = _make_state([_plain_card(), _combo_card()], relics=[_relic(RelicTag.EVASION_BROOCH)])
        play_card(state, 0)
        assert play_card(state, 0).combo
        assert state.player.block == 2 + 1 + 1

    def test_once_per_play_with_golden_card(self):
        card = _combo_card()
        card.chroma = G                       # cast twice: Combo +1 each cast, brooch once
        state = _make_state([_plain_card(), card], relics=[_relic(RelicTag.EVASION_BROOCH)])
        play_card(state, 0)
        assert play_card(state, 0).combo
        assert state.player.block == 2 + 1 * 2 + 1

    def test_without_relic_nothing(self):
        state = _make_state([_combo_card()])
        play_card(state, 0)
        assert state.player.block == 0


class TestThrowingKnife:
    def test_hits_one_enemy_for_one(self):
        state = _make_state([], relics=[_relic(RelicTag.THROWING_KNIFE)])
        state.enemies = [_enemy(30, eid="a"), _enemy(30, eid="b")]
        relic_effects.on_card_played(state, _combo_card(), True, random.Random(1))
        assert sorted(e.current_hp for e in state.enemies) == [29, 30]

    def test_block_absorbs(self):
        state = _make_state([], relics=[_relic(RelicTag.THROWING_KNIFE)])
        state.enemies = [_enemy(30, block=1)]
        relic_effects.on_card_played(state, _combo_card(), True)
        assert (state.enemies[0].current_hp, state.enemies[0].block) == (30, 0)

    def test_only_living_enemies(self):
        state = _make_state([], relics=[_relic(RelicTag.THROWING_KNIFE)])
        dead = _enemy(30, eid="dead")
        dead.current_hp = 0
        state.enemies = [dead, _enemy(30, eid="alive")]
        for s in range(20):
            relic_effects.on_card_played(state, _combo_card(), True, random.Random(s))
        assert dead.current_hp == 0 and state.enemies[1].current_hp == 10

    def test_no_enemies_alive_is_safe(self):
        state = _make_state([], relics=[_relic(RelicTag.THROWING_KNIFE)])
        state.enemies[0].current_hp = 0
        relic_effects.on_card_played(state, _combo_card(), True)
        assert state.enemies[0].current_hp == 0

    def test_golden_deals_two(self):
        state = _make_state([], relics=[_relic(RelicTag.THROWING_KNIFE, G)])
        relic_effects.on_card_played(state, _combo_card(), True)
        assert state.enemies[0].current_hp == 48

    def test_plain_card_nothing(self):
        state = _make_state([], relics=[_relic(RelicTag.THROWING_KNIFE)])
        relic_effects.on_card_played(state, _plain_card(), True)
        assert state.enemies[0].current_hp == 50

    def test_combo_not_resolved_nothing(self):
        state = _make_state([], relics=[_relic(RelicTag.THROWING_KNIFE)])
        relic_effects.on_card_played(state, _combo_card(), False)
        assert state.enemies[0].current_hp == 50

    def test_through_play_card_is_in_last_cast_hits(self):
        state = _make_state([_plain_card(), _combo_card()], relics=[_relic(RelicTag.THROWING_KNIFE)])
        first = play_card(state, 0)
        assert state.enemies[0].current_hp == 50 and first.cast_hits[-1] == [0]
        result = play_card(state, 0)
        assert result.combo
        assert state.enemies[0].current_hp == 49
        assert result.cast_hits[-1] == [1]
        assert result.cast_enemy_hp[-1] == [49]


# --- Ankh --------------------------------------------------------------------------

from src.application.end_turn import end_player_turn  # noqa: E402


def _dying_state(relics):
    state = _make_state([], relics=relics, player_hp=0)
    return state


class TestAnkh:
    def test_definition(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        ankh = defs[RelicTag.ANKH]
        assert ankh.rarity is Rarity.LEGENDARY and ankh.relic_class is CardClass.NEUTRAL

    def test_revives_at_full_hp(self):
        state = _dying_state([_relic(RelicTag.ANKH)])
        assert relic_effects.try_ankh(state)
        assert state.player.current_hp == state.player.max_hp == 100

    def test_single_use(self):
        ankh = _relic(RelicTag.ANKH)
        state = _dying_state([ankh])
        relic_effects.try_ankh(state)
        assert not ankh.is_active
        state.player.current_hp = 0
        assert not relic_effects.try_ankh(state)
        assert state.player.current_hp == 0

    def test_golden_two_uses(self):
        ankh = _relic(RelicTag.ANKH, G)
        state = _dying_state([ankh])
        assert relic_effects.try_ankh(state) and ankh.is_active
        state.player.current_hp = 0
        assert relic_effects.try_ankh(state) and not ankh.is_active

    def test_alive_does_nothing(self):
        ankh = _relic(RelicTag.ANKH)
        state = _make_state([], relics=[ankh], player_hp=1)
        assert not relic_effects.try_ankh(state)
        assert ankh.is_active and state.player.current_hp == 1

    def test_inactive_does_nothing(self):
        state = _dying_state([_relic(RelicTag.ANKH, active=False)])
        assert not relic_effects.try_revive(state)

    def test_shield_is_spent_before_ankh(self):
        shield, ankh = _relic(RelicTag.SPECTRAL_SHIELD), _relic(RelicTag.ANKH)
        state = _dying_state([ankh, shield])
        assert relic_effects.try_revive(state)
        assert state.player.current_hp == 1
        assert not shield.is_active and ankh.is_active
        state.player.current_hp = 0
        assert relic_effects.try_revive(state)
        assert state.player.current_hp == 100 and not ankh.is_active

    def test_enemy_attack_triggers_ankh(self):
        state = _make_state([], relics=[_relic(RelicTag.ANKH)], player_hp=3)
        state.enemies[0].intent = Intent(IntentType.ATTACK, 50)
        end_player_turn(state)
        assert state.player.current_hp == 100


# --- Espejo Singular --------------------------------------------------------------

from src.application.run_manager import acquire_relic  # noqa: E402
from src.domain.keywords import deck_is_singular  # noqa: E402


def _c(cid, chroma=None):
    return Card(id=cid, name=cid, card_type=CardType.SKILL, cost=0,
                base_effect=CardEffect(name=cid), chroma=chroma)


class TestRemoveDuplicates:
    def test_empty(self):
        assert relic_effects.remove_duplicate_cards([]) == []

    def test_keeps_first_seen_order(self):
        deck = [_c("a"), _c("b"), _c("a"), _c("c"), _c("b")]
        assert [c.id for c in relic_effects.remove_duplicate_cards(deck)] == ["a", "b", "c"]

    def test_no_repeats_unchanged(self):
        deck = [_c("a"), _c("b")]
        assert relic_effects.remove_duplicate_cards(deck) == deck

    def test_golden_copy_is_kept(self):
        plain, gold = _c("a"), _c("a", G)
        out = relic_effects.remove_duplicate_cards([plain, _c("b"), gold])
        assert out[0] is gold and [c.id for c in out] == ["a", "b"]

    def test_large(self):
        deck = [_c(f"c{i % 100}") for i in range(10_000)]
        assert len(relic_effects.remove_duplicate_cards(deck)) == 100


class TestSingularMirror:
    def test_definition(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        mirror = defs[RelicTag.SINGULAR_MIRROR]
        assert mirror.rarity is Rarity.LEGENDARY and mirror.relic_class is CardClass.NEUTRAL

    @pytest.mark.parametrize("character", ALL_CHARACTERS, ids=lambda c: c.id.value)
    def test_pickup_cleans_starter_deck(self, character):
        run = create_run(character, 1)
        ids = {c.id for c in run.deck}
        acquire_relic(run, _relic(RelicTag.SINGULAR_MIRROR))
        assert deck_is_singular(run.deck)
        assert {c.id for c in run.deck} == ids
        assert len(run.deck) == len(ids)

    def test_next_combat_is_singular(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        acquire_relic(run, _relic(RelicTag.SINGULAR_MIRROR))
        assert create_combat_from_run(run, [_enemy()]).singular_deck

    def test_only_once(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        acquire_relic(run, _relic(RelicTag.SINGULAR_MIRROR))
        run.add_card(_c(run.deck[0].id))           # a new copy found later stays
        assert not deck_is_singular(run.deck)

    def test_other_relics_do_not_touch_deck(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        before = len(run.deck)
        acquire_relic(run, _relic(RelicTag.GOLD_RING))
        assert len(run.deck) == before


class TestAcquireRelic:
    def test_adds_relic(self):
        run = create_run(ALL_CHARACTERS[0], 1)
        relic = _relic(RelicTag.FIRE_ORB)
        acquire_relic(run, relic)
        assert run.relics == [relic]

    def test_recomputes_max_hp(self):
        c = ALL_CHARACTERS[0]
        run = create_run(c, 1)
        acquire_relic(run, _relic(RelicTag.VITALITY_AMULET))
        acquire_relic(run, _relic(RelicTag.IRON_HEART))
        assert run.player_max_hp == c.stats.max_hp + 25


# --- Panacea and Fuente Eterna ---------------------------------------------------

from src.domain.entities import WEAK, StatusEffect  # noqa: E402


def _state_with_enemy_intent(relics, intent_type, value=0):
    state = _make_state([], relics=relics, draw_cards=[_c(f"d{i}") for i in range(10)])
    state.enemies[0].intent = Intent(intent_type, value)
    return state


class TestPanacea:
    def test_definition(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        assert defs[RelicTag.PANACEA].rarity is Rarity.LEGENDARY
        assert defs[RelicTag.PANACEA].relic_class is CardClass.NEUTRAL

    def test_enemy_debuff_weakens_hero_for_two_turns(self):
        state = _state_with_enemy_intent([], IntentType.DEBUFF)
        end_player_turn(state)
        assert [se.stacks for se in state.player.status_effects if se.name == WEAK] == [2]

    def test_panacea_blocks_it(self):
        state = _state_with_enemy_intent([_relic(RelicTag.PANACEA)], IntentType.DEBUFF)
        end_player_turn(state)
        assert not state.player.status_effects

    def test_weak_hero_deals_less(self):
        state = _make_state([_combo_card()], player_attack_bonus=0)
        state.player.status_effects.append(StatusEffect(WEAK, 1, False))
        state.hand.cards = [Card(id="a", name="A", card_type=CardType.ATTACK, cost=0,
                                 base_effect=CardEffect(name="A", damage=BigValue(20)))]
        play_card(state, 0, 0)
        assert state.enemies[0].current_hp == 50 - 15


class TestEternalFount:
    def test_definition(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        assert defs[RelicTag.ETERNAL_FOUNT].rarity is Rarity.LEGENDARY

    def test_max_mana_grows_each_turn(self):
        state = _state_with_enemy_intent([_relic(RelicTag.ETERNAL_FOUNT)], IntentType.BLOCK)
        start = state.mana.maximum
        end_player_turn(state)
        end_player_turn(state)
        assert state.mana.maximum == start + 2 and state.mana.current == start + 2

    def test_golden_two_per_turn(self):
        state = _state_with_enemy_intent([_relic(RelicTag.ETERNAL_FOUNT, G)], IntentType.BLOCK)
        start = state.mana.maximum
        end_player_turn(state)
        assert state.mana.maximum == start + 2
