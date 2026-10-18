"""The 114 relics approved in ``docs/reliquias.xlsx`` (2026-10-17).

Each relic is exercised through the real use cases (``play_card``, ``end_turn``,
``run_manager``, ``card_rewards``, ``gacha``, ``warlock``, ``deck_choice``) with plain domain
objects. Random effects are pinned with a single living enemy or a seeded rng.
No pygame.
"""
from __future__ import annotations

import random

import pytest

from src.application import relic_triggers
from src.application.card_rewards import pick_pack_cards, pick_reward_cards, reward_count
from src.application.deck_choice import apply_choice, choice_limit, next_choice
from src.application.drawing import draw_cards
from src.application.end_turn import draw_opening_hand, end_player_turn
from src.application.gacha import gacha_price, pull
from src.application.play_card import play_card
from src.application.run_manager import (
    _all_relic_defs, _relic_pool, acquire_relic, apply_combat_victory, create_run, enter_room,
    max_hp, pack_picks, run_luck, shop_offer_price, use_voucher,
)
from src.application.warlock import upgrade_price
from src.domain.card import Card, CardClass, CardEffect, CardRarity, CardType
from src.domain.card_pool import hidden_dagger
from src.domain.character import ALL_CHARACTERS, CharacterId
from src.domain.chroma import Chroma, effect_multiplier
from src.domain.combat import CombatState
from src.domain.elements import Element, apply_element, element_stacks
from src.domain.entities import (
    FROZEN, MARKED, POISON, STRENGTH, VULNERABLE, WEAK, Enemy, Intent, IntentType, Player,
    StatusEffect, status_stacks,
)
from src.domain.gacha import PullKind
from src.domain.keywords import Keyword
from src.domain.map_node import RoomType
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.rarity import Rarity
from src.domain.relic import RELIC_RARITY, Relic, RelicTag
from src.infrastructure.sprite_loader import RELIC_SPRITE_PATHS

G = Chroma.GOLDEN
NEW_TAGS = list(RelicTag)[42:]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enemy(hp: int = 100, block: int = 0, eid: str = "e", intent: int = 5, hits: int = 1,
           boss: bool = False, elite: bool = False) -> Enemy:
    return Enemy(id=eid, name="E", max_hp=hp, current_hp=hp, block=block,
                 intent=Intent(IntentType.ATTACK, intent, hits=hits), is_boss=boss, is_elite=elite)


def _card(cid="c", ctype=CardType.ATTACK, cost=0, dmg=0, blk=0, draw=0, **kw) -> Card:
    return Card(id=cid, name=cid, card_type=ctype, cost=cost,
                base_effect=CardEffect(cid, damage=BigValue(dmg), block=BigValue(blk), draw=draw, **kw))


def _atk(dmg=10, cost=0, cid="a") -> Card:
    return _card(cid, CardType.ATTACK, cost, dmg=dmg)


def _skill(blk=5, cost=0, cid="s") -> Card:
    return _card(cid, CardType.SKILL, cost, blk=blk)


def _filler(n: int) -> list[Card]:
    return [_card(f"f{i}", CardType.SKILL, 0) for i in range(n)]


def _relic(tag: RelicTag, chroma=None) -> Relic:
    return Relic("r", "Reliquia", "d", tag=tag, chroma=chroma)


def _state(hand=(), *, enemies=None, relics=(), hp=100, max_hp=100, mana=5, draw=()) -> CombatState:
    state = CombatState(
        player=Player(name="P", max_hp=max_hp, current_hp=hp),
        enemies=enemies if enemies is not None else [_enemy()],
        hand=Hand(cards=list(hand)), draw_pile=DrawPile(cards=list(draw)),
        discard_pile=DiscardPile(cards=[]), mana=Mana(current=mana, maximum=mana),
        relics=[_relic(t) if isinstance(t, RelicTag) else t for t in relics],
    )
    state.turn_start_alive = len(state.living_enemies())
    return state


def _play(state: CombatState, card: Card, target: int | None = 0):
    state.hand.cards.append(card)
    return play_card(state, state.hand.count - 1, target)


def _run(hero: CharacterId = CharacterId.WARRIOR, relics=(), gold=0, seed=3):
    run = create_run(next(c for c in ALL_CHARACTERS if c.id is hero), seed)
    run.gold = gold
    for t in relics:
        acquire_relic(run, _relic(t) if isinstance(t, RelicTag) else t)
    return run


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

class TestCatalogue:
    def test_114_new_tags(self):
        assert len(NEW_TAGS) == 114

    def test_every_tag_has_a_definition_rarity_and_icon(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        for tag in NEW_TAGS:
            assert tag in defs and tag in RELIC_RARITY
            assert defs[tag].name in RELIC_SPRITE_PATHS

    def test_names_unique(self):
        names = [r.name for r in _all_relic_defs()]
        assert len(names) == len(set(names))

    def test_class_relics(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        assert defs[RelicTag.SPIKED_GAUNTLET].relic_class is CardClass.WARRIOR
        assert defs[RelicTag.TINDER].relic_class is CardClass.MAGE
        assert defs[RelicTag.TWIN_DAGGERS].relic_class is CardClass.ROGUE
        assert defs[RelicTag.DIAMOND_CARDS].relic_class is CardClass.NEUTRAL

    def test_review_comments_applied(self):
        defs = {r.tag: r for r in _all_relic_defs()}
        assert defs[RelicTag.ANTIDOTE].description == "Eres inmune al Veneno."
        assert "reliquia es gratis" in defs[RelicTag.VOUCHER].description
        assert "Una vez por turno" in defs[RelicTag.MANA_VIAL].description
        assert RELIC_RARITY[RelicTag.ANTIQUARY_SEAL] is Rarity.LEGENDARY


# ---------------------------------------------------------------------------
# Card costs
# ---------------------------------------------------------------------------

class TestCosts:
    def test_unique_piece_first_card_only_with_singular_deck(self):
        state = _state(relics=[RelicTag.UNIQUE_PIECE])
        state.singular_deck = True
        assert state.card_cost(_atk(cost=2)) == 1
        state.cards_played_this_turn = 1
        assert state.card_cost(_atk(cost=2)) == 2

    def test_unique_piece_needs_singular(self):
        state = _state(relics=[RelicTag.UNIQUE_PIECE])
        assert state.card_cost(_atk(cost=2)) == 2

    def test_old_scroll_first_skill_of_combat(self):
        state = _state(relics=[RelicTag.OLD_SCROLL])
        assert state.card_cost(_skill(cost=2)) == 0
        _play(state, _skill(cost=2), None)
        assert state.mana.current == 5 and state.card_cost(_skill(cost=2)) == 2

    def test_prism_golden_minimum_one(self):
        state = _state(relics=[RelicTag.PRISM])
        golden = _atk(cost=3)
        golden.chroma = G
        one = _atk(cost=1)
        one.chroma = G
        assert state.card_cost(golden) == 2 and state.card_cost(one) == 1
        assert state.card_cost(_atk(cost=3)) == 3

    def test_stolen_watch_after_six_cards(self):
        state = _state(relics=[RelicTag.STOLEN_WATCH], mana=10)
        for _ in range(6):
            _play(state, _skill(cost=1), None)
        assert state.card_cost(_atk(cost=3)) == 0

    def test_thief_king_crown_poisoned_death(self):
        enemy = _enemy(hp=5)
        enemy.status_effects.append(StatusEffect(POISON, 3, False))
        state = _state(enemies=[enemy, _enemy(eid="b")], relics=[RelicTag.THIEF_KING_CROWN])
        _play(state, _atk(10))
        assert state.card_cost(_atk(cost=2)) == 1


# ---------------------------------------------------------------------------
# Damage and block bonuses
# ---------------------------------------------------------------------------

class TestDamageBonuses:
    def test_whetstone_first_attack_of_combat(self):
        state = _state(relics=[RelicTag.WHETSTONE])
        _play(state, _atk(10))
        _play(state, _atk(10))
        assert state.enemies[0].current_hp == 100 - 16 - 10

    def test_war_horn_turn_three(self):
        state = _state(relics=[RelicTag.WAR_HORN])
        state.turn = 3
        _play(state, _atk(10))
        assert state.enemies[0].current_hp == 86

    def test_pendulum_even_attack_odd_block(self):
        state = _state(relics=[RelicTag.PENDULUM])
        _play(state, _skill(5), None)
        assert state.player.block == 7
        state.turn = 2
        _play(state, _atk(10))
        assert state.enemies[0].current_hp == 88

    def test_breach_spear_against_block(self):
        state = _state(enemies=[_enemy(block=5)], relics=[RelicTag.BREACH_SPEAR])
        _play(state, _atk(10))
        assert state.enemies[0].current_hp == 100 - 8

    def test_berserker_helm_under_half(self):
        state = _state(hp=40, relics=[RelicTag.BERSERKER_HELM])
        _play(state, _atk(10))
        assert state.enemies[0].current_hp == 87

    def test_molten_iron_first_attack_adds_block_capped(self):
        state = _state(relics=[RelicTag.MOLTEN_IRON])
        state.player.block = 40
        _play(state, _atk(10))
        _play(state, _atk(10))
        assert state.enemies[0].current_hp == 100 - 25 - 10

    def test_notched_axe_first_fury_attack(self):
        from tests.application.test_warrior import _card as wcard
        state = _state(relics=[RelicTag.NOTCHED_AXE])
        state.lose_hp(1)
        _play(state, wcard("wr_tajo_brutal"))
        _play(state, wcard("wr_tajo_brutal"))
        assert state.enemies[0].current_hp == 100 - 17 - 13

    def test_brazier_without_block(self):
        state = _state(draw=_filler(10), enemies=[_enemy(intent=0)], relics=[RelicTag.BRAZIER])
        end_player_turn(state)
        _play(state, _atk(10))
        assert state.enemies[0].current_hp == 87

    def test_touchstone_upgraded_cards(self):
        state = _state(relics=[RelicTag.TOUCHSTONE])
        card = _atk(10)
        card.upgrade_level = 1
        _play(state, card)
        assert state.enemies[0].current_hp == 88

    def test_harlequin_third_combo(self):
        state = _state(relics=[RelicTag.HARLEQUIN_MASK])
        combo = lambda: _card("k", CardType.ATTACK, 0, dmg=5, combo=CardEffect("Combo"))  # noqa: E731
        _play(state, _skill(0), None)
        for _ in range(3):
            _play(state, combo())
        assert state.enemies[0].current_hp == 100 - 5 - 5 - 10

    def test_oil_lamp_first_turn_block(self):
        state = _state(relics=[RelicTag.OIL_LAMP])
        _play(state, _skill(5), None)
        assert state.player.block == 8

    def test_dented_plate_per_missing_hp(self):
        state = _state(hp=70, relics=[RelicTag.DENTED_PLATE])
        _play(state, _skill(5), None)
        assert state.player.block == 8

    def test_wristguard_endure_cards(self):
        from tests.application.test_warrior import _card as wcard
        state = _state(relics=[RelicTag.WRISTGUARD])
        _play(state, wcard("wr_muro_acero"), None)
        assert state.player.block == 16

    def test_stairway_rising_costs(self):
        state = _state(relics=[RelicTag.STAIRWAY], mana=10)
        for cost in (0, 1, 2):
            _play(state, _skill(0, cost=cost), None)
        assert state.player.attack_bonus == 1 and state.player.dexterity == 1

    def test_stairway_broken_chain(self):
        state = _state(relics=[RelicTag.STAIRWAY], mana=10)
        for cost in (0, 2, 3):
            _play(state, _skill(0, cost=cost), None)
        assert state.player.attack_bonus == 0

    def test_archmage_cloak_area(self):
        from src.domain.card_pool import _on_all_hit
        state = _state(relics=[RelicTag.ARCHMAGE_CLOAK])
        state.player.attack_bonus = 8
        _on_all_hit(6)(state)
        assert state.enemies[0].current_hp == 86


# ---------------------------------------------------------------------------
# Combat start and turns
# ---------------------------------------------------------------------------

class TestCombatStart:
    def _open(self, relics, enemies=None, hp=100, draw=None):
        state = _state(enemies=enemies, relics=relics, hp=hp,
                       draw=draw if draw is not None else _filler(10))
        draw_opening_hand(state)
        return state

    def test_votive_candle_weakens_strongest(self):
        state = self._open([RelicTag.VOTIVE_CANDLE], [_enemy(50, eid="a"), _enemy(90, eid="b")])
        assert status_stacks(state.enemies[1].status_effects, WEAK) == 1
        assert status_stacks(state.enemies[0].status_effects, WEAK) == 0

    def test_shackle_vulnerable_everyone(self):
        state = self._open([RelicTag.SHACKLE], [_enemy(eid="a"), _enemy(eid="b")])
        assert all(status_stacks(e.status_effects, VULNERABLE) == 1 for e in state.enemies)

    def test_frost_amulet_skips_bosses(self):
        state = self._open([RelicTag.FROST_AMULET], [_enemy(boss=True)])
        assert status_stacks(state.enemies[0].status_effects, FROZEN) == 0
        state = self._open([RelicTag.FROST_AMULET], [_enemy()])
        assert status_stacks(state.enemies[0].status_effects, FROZEN) == 1

    def test_willow_wand_water(self):
        state = self._open([RelicTag.WILLOW_WAND])
        assert element_stacks(state.enemies[0], Element.WATER) == 2

    def test_folding_knife_marks_weakest(self):
        state = self._open([RelicTag.FOLDING_KNIFE], [_enemy(80, eid="a"), _enemy(30, eid="b")])
        assert status_stacks(state.enemies[1].status_effects, MARKED) == 2

    def test_phoenix_feather_under_half(self):
        assert self._open([RelicTag.PHOENIX_FEATHER], hp=40).player.current_hp == 48
        assert self._open([RelicTag.PHOENIX_FEATHER], hp=60).player.current_hp == 60

    def test_blood_skin_full_hp(self):
        state = self._open([RelicTag.BLOOD_SKIN])
        assert state.player.current_hp == 95 and state.hero_strength == 2

    def test_racing_heart_doubles_on_boss(self):
        state = self._open([RelicTag.SCAR, RelicTag.RACING_HEART], [_enemy(boss=True)])
        assert state.hero_strength == 2
        state = self._open([RelicTag.SCAR, RelicTag.RACING_HEART])
        assert state.hero_strength == 1

    def test_cursed_contract(self):
        state = self._open([RelicTag.CURSED_CONTRACT])
        cards = state.hand.cards + state.draw_pile.cards
        assert state.mana.maximum == 6 and any(c.id == "status_herida" for c in cards)

    def test_d20_makes_one_golden(self):
        state = self._open([RelicTag.D20])
        assert sum(c.chroma is G for c in state.hand.cards) == 1

    def test_singular_locket_dagger_in_hand(self):
        state = _state(relics=[RelicTag.SINGULAR_LOCKET], draw=_filler(5))
        state.singular_deck = True
        draw_opening_hand(state)
        assert any(c.id == "t_daga_oculta" and not c.play_on_draw for c in state.hand.cards)

    def test_marble_bag(self):
        state = self._open([RelicTag.MARBLE_BAG])
        assert state.player.block == 3 and state.discards_this_turn == 1

    def test_marked_cards_innate_drawn_first(self):
        deck = _filler(20)
        deck[0].innate = True
        state = self._open([], draw=deck)
        assert deck[0] in state.hand.cards


class TestTurns:
    def test_sandbag_and_chess_piece(self):
        state = _state(relics=[RelicTag.SANDBAG], draw=_filler(10), enemies=[_enemy(intent=0)])
        for _ in range(3):
            _play(state, _skill(0), None)
        end_player_turn(state)
        state2 = _state(relics=[RelicTag.CHESS_PIECE, RelicTag.ANCHOR], draw=_filler(10),
                        enemies=[_enemy(intent=0)])
        for _ in range(2):
            _play(state2, _skill(0), None)
        end_player_turn(state2)
        assert state2.player.block == 5

    def test_balance_bracelet(self):
        state = _state(relics=[RelicTag.BALANCE_BRACELET, RelicTag.ANCHOR], draw=_filler(10),
                       enemies=[_enemy(intent=0)])
        _play(state, _atk(1))
        _play(state, _skill(0), None)
        end_player_turn(state)
        assert state.player.block == 5

    def test_empty_bowl_unspent_mana(self):
        state = _state(relics=[RelicTag.EMPTY_BOWL, RelicTag.ANCHOR], draw=_filler(10),
                       enemies=[_enemy(intent=0)], mana=3)
        end_player_turn(state)
        assert state.player.block == 9

    def test_arcane_battery_keeps_one(self):
        state = _state(relics=[RelicTag.ARCANE_BATTERY], draw=_filler(10), enemies=[_enemy(intent=0)], mana=3)
        end_player_turn(state)
        assert state.mana.current == 4

    def test_ragged_cape(self):
        state = _state(relics=[RelicTag.RAGGED_CAPE], draw=_filler(10), enemies=[_enemy(intent=5)])
        end_player_turn(state)
        assert state.player.current_hp == 98

    def test_field_bandage(self):
        state = _state(hp=80, relics=[RelicTag.FIELD_BANDAGE], draw=_filler(10), enemies=[_enemy(intent=0)])
        state.lose_hp(3)
        end_player_turn(state)
        assert state.player.current_hp == 79

    def test_hourglass_every_fourth_turn(self):
        state = _state(relics=[RelicTag.HOURGLASS], draw=_filler(60), enemies=[_enemy(intent=0)])
        hands = []
        for _ in range(4):
            end_player_turn(state)
            hands.append(state.hand.count)
        assert hands == [5, 5, 6, 5]           # turns 2, 3, 4 (+1), 5

    def test_anchor_first_turn_only(self):
        state = _state(relics=[RelicTag.ANCHOR], draw=_filler(20), enemies=[_enemy(intent=0)])
        state.player.block = 7
        end_player_turn(state)
        assert state.player.block == 7
        end_player_turn(state)
        assert state.player.block == 0

    def test_worn_roundel_keeps_half(self):
        state = _state(relics=[RelicTag.WORN_ROUNDEL], draw=_filler(10), enemies=[_enemy(intent=0)])
        state.player.block = 9
        end_player_turn(state)
        assert state.player.block == 4

    def test_legion_banner(self):
        state = _state(relics=[RelicTag.LEGION_BANNER, RelicTag.WORN_ROUNDEL], draw=_filler(10),
                       enemies=[_enemy(intent=1)])
        state.player.block = 40
        end_player_turn(state)
        assert state.hero_strength == 1

    def test_mana_vial_once_per_turn(self):
        state = _state(relics=[RelicTag.MANA_VIAL], mana=4)
        for _ in range(4):
            _play(state, _skill(0, cost=1), None)
        assert state.mana.current == 1
        _play(state, _skill(0, cost=1), None)
        assert state.mana.current == 0


# ---------------------------------------------------------------------------
# Hits, debuffs, deaths, HP
# ---------------------------------------------------------------------------

class TestDefence:
    def test_thorn_crown(self):
        state = _state(relics=[RelicTag.THORN_CROWN], draw=_filler(10), enemies=[_enemy(intent=5, hits=3)])
        end_player_turn(state)
        assert state.enemies[0].current_hp == 94

    def test_white_flag_first_hit(self):
        state = _state(relics=[RelicTag.WHITE_FLAG], draw=_filler(10), enemies=[_enemy(intent=5, hits=2)])
        end_player_turn(state)
        assert state.player.current_hp == 100 - 1 - 5

    def test_capuche_first_turn_half(self):
        state = _state(relics=[RelicTag.CAPUCHE], draw=_filler(10), enemies=[_enemy(intent=10)])
        end_player_turn(state)
        assert state.player.current_hp == 95

    def test_last_breath(self):
        state = _state(hp=30, relics=[RelicTag.LAST_BREATH], draw=_filler(10), enemies=[_enemy(intent=10)])
        state.retain_block = True
        end_player_turn(state)
        assert state.player.current_hp == 20 and state.player.block == 15

    def test_antidote(self):
        state = _state(relics=[RelicTag.ANTIDOTE])
        assert state.poison_hero(5) == 0 and status_stacks(state.player.status_effects, POISON) == 0
        assert relic_triggers.blocks_debuff(state, POISON)

    def test_monk_wraps_first_debuff_only(self):
        state = _state(relics=[RelicTag.MONK_WRAPS])
        assert relic_triggers.blocks_debuff(state, WEAK)
        assert not relic_triggers.blocks_debuff(state, WEAK)

    def test_broken_chain_ethereal(self):
        state = _state(relics=[RelicTag.BROKEN_CHAIN])
        state.add_status_cards("status_espora", 1, "hand")
        assert state.hand.cards[-1].ethereal

    def test_stone_heart_no_heal(self):
        state = _state(hp=50, relics=[RelicTag.STONE_HEART])
        assert state.heal_hero(20) == 0 and state.player.current_hp == 50

    def test_dandelion_and_fang_necklace_on_kill(self):
        state = _state(hp=50, enemies=[_enemy(hp=5), _enemy(eid="b")],
                       relics=[RelicTag.DANDELION, RelicTag.FANG_NECKLACE])
        _play(state, _atk(10))
        assert state.player.current_hp == 53 and state.hero_strength == 1

    def test_death_counts_once(self):
        state = _state(hp=50, enemies=[_enemy(hp=5), _enemy(eid="b")], relics=[RelicTag.DANDELION])
        _play(state, _atk(10))
        _play(state, _atk(1), 1)
        assert state.player.current_hp == 53

    def test_spiked_gauntlet_and_martyr_shield(self):
        state = _state(relics=[RelicTag.SPIKED_GAUNTLET, RelicTag.MARTYR_SHIELD])
        state.lose_hp(3)
        assert state.enemies[0].current_hp == 98 and state.player.block == 6

    def test_crimson_chalice_overflow_hits(self):
        state = _state(hp=98, relics=[RelicTag.CRIMSON_CHALICE])
        state.heal_hero(5)
        assert state.enemies[0].current_hp == 97 and state.player.block == 3

    def test_blood_gem_draws_once(self):
        state = _state(hp=50, relics=[RelicTag.BLOOD_GEM])
        state.heal_hero(10)
        state.heal_hero(12)
        assert state.pending_draws == 1

    def test_blood_rune_enemy_hit_turns_fury_on(self):
        from tests.application.test_warrior import _card as wcard
        state = _state(relics=[RelicTag.BLOOD_RUNE], draw=_filler(10), enemies=[_enemy(intent=5)])
        end_player_turn(state)
        assert state.fury_ready(wcard("wr_tajo_brutal"))


# ---------------------------------------------------------------------------
# Counters of keywords
# ---------------------------------------------------------------------------

class TestKeywordRelics:
    def test_war_drum_every_third_endure(self):
        from tests.application.test_warrior import _card as wcard
        state = _state(relics=[RelicTag.WAR_DRUM], mana=20)
        state.player.block = 1
        for _ in range(3):
            _play(state, wcard("wr_embate_firme"))
        assert state.hero_strength == 1

    def _void(self, cost=1):
        return _card("v", CardType.SKILL, cost, void=CardEffect("Vacío"))

    def test_water_clock_first_void(self):
        state = _state(relics=[RelicTag.WATER_CLOCK], mana=1)
        _play(state, self._void(), None)
        assert state.player.block == 4

    def test_blank_grimoire_every_third_void(self):
        state = _state(relics=[RelicTag.BLANK_GRIMOIRE], mana=1, draw=_filler(5))
        for _ in range(3):
            state.mana.current = 1
            _play(state, self._void(), None)
        assert state.hand.count == 1

    def test_lesser_fount_expensive_void(self):
        state = _state(relics=[RelicTag.LESSER_FOUNT], mana=3)
        _play(state, self._void(cost=3), None)
        assert state.mana.current == 1

    def test_poisoned_scarf_first_combo(self):
        state = _state(relics=[RelicTag.POISONED_SCARF])
        _play(state, _skill(0), None)
        _play(state, _card("k", CardType.ATTACK, 0, dmg=1, combo=CardEffect("Combo")))
        assert status_stacks(state.enemies[0].status_effects, POISON) == 2

    def test_mist_flask(self):
        state = _state(relics=[RelicTag.MIST_FLASK], hand=_filler(2))
        state.discard_random()
        _play(state, _card("d", CardType.SKILL, 0, spoil=CardEffect("Despojo")), None)
        assert status_stacks(state.enemies[0].status_effects, WEAK) == 1


# ---------------------------------------------------------------------------
# Mage elements
# ---------------------------------------------------------------------------

class TestMage:
    def _fire_card(self, cost=1, stacks=2):
        return _card("fire", CardType.ATTACK, cost, dmg=1, element=Element.FIRE, element_stacks=stacks,
                     needs_target=True)

    def test_tinder_and_pointy_hat(self):
        state = _state(relics=[RelicTag.TINDER, RelicTag.POINTY_HAT])
        _play(state, self._fire_card(cost=0))
        assert element_stacks(state.enemies[0], Element.FIRE) == 4

    def test_element_relic_only_its_element(self):
        state = _state(relics=[RelicTag.SEASHELL])
        _play(state, self._fire_card())
        assert element_stacks(state.enemies[0], Element.FIRE) == 2

    def test_cauldron_steam_weakens(self):
        state = _state(relics=[RelicTag.CAULDRON])
        apply_element(state, state.enemies[0], Element.FIRE, 1)
        apply_element(state, state.enemies[0], Element.WATER, 1)
        assert status_stacks(state.enemies[0].status_effects, WEAK) == 1

    def test_volcano_ember_magma(self):
        state = _state(relics=[RelicTag.VOLCANO_EMBER])
        apply_element(state, state.enemies[0], Element.FIRE, 1)
        apply_element(state, state.enemies[0], Element.EARTH, 1)
        assert state.enemies[0].current_hp < 100

    def test_lava_stone_wildfire(self):
        state = _state(enemies=[_enemy(eid="a"), _enemy(eid="b")], relics=[RelicTag.LAVA_STONE])
        apply_element(state, state.enemies[0], Element.FIRE, 1)
        apply_element(state, state.enemies[0], Element.AIR, 1)
        assert element_stacks(state.enemies[1], Element.FIRE) == 3

    def test_witch_broom_sandstorm(self):
        state = _state(relics=[RelicTag.WITCH_BROOM])
        apply_element(state, state.enemies[0], Element.EARTH, 1)
        apply_element(state, state.enemies[0], Element.AIR, 1)
        assert status_stacks(state.enemies[0].status_effects, WEAK) == 2

    def test_storm_orb_each_reaction(self):
        state = _state(relics=[RelicTag.STORM_ORB])
        apply_element(state, state.enemies[0], Element.WATER, 1)
        apply_element(state, state.enemies[0], Element.EARTH, 1)          # Barro: no damage itself
        assert state.enemies[0].current_hp == 97

    def test_frost_crystal_two_turns_normal_one_boss(self):
        state = _state(relics=[RelicTag.FROST_CRYSTAL], enemies=[_enemy(eid="a"), _enemy(eid="b", boss=True)])
        for e in state.enemies:
            apply_element(state, e, Element.WATER, 1)
            apply_element(state, e, Element.AIR, 1)
        assert [status_stacks(e.status_effects, FROZEN) for e in state.enemies] == [2, 1]

    def test_frozen_twice_loses_two_turns(self):
        state = _state(draw=_filler(20), enemies=[_enemy(intent=10)])
        state.enemies[0].status_effects.append(StatusEffect(FROZEN, 2, False))
        end_player_turn(state)
        assert state.enemy_log == [] and status_stacks(state.enemies[0].status_effects, FROZEN) == 1
        end_player_turn(state)
        assert state.enemy_log == [] and status_stacks(state.enemies[0].status_effects, FROZEN) == 0

    def test_prismatic_lens_first_reaction_twice(self):
        state = _state(relics=[RelicTag.PRISMATIC_LENS])
        apply_element(state, state.enemies[0], Element.FIRE, 2)
        apply_element(state, state.enemies[0], Element.WATER, 1)          # Vapor 6 ×2
        assert state.enemies[0].current_hp == 88 and state.lens_used

    def test_ring_of_four(self):
        state = _state(relics=[RelicTag.RING_OF_FOUR], enemies=[_enemy(eid=str(i)) for i in range(4)], mana=10)
        for i, el in enumerate(Element):
            _play(state, _card(f"e{i}", CardType.ATTACK, 0, dmg=1, element=el, element_stacks=1,
                               needs_target=True), i)
        assert state.mana.maximum == 11


# ---------------------------------------------------------------------------
# Rogue
# ---------------------------------------------------------------------------

class TestRogue:
    def test_pocket_sharpener_first_dagger(self):
        state = _state(relics=[RelicTag.POCKET_SHARPENER], draw=[hidden_dagger(), hidden_dagger()])
        draw_cards(state, 2)
        assert state.enemies[0].current_hp == 100 - 8 - 4

    def test_twin_daggers(self):
        state = _state(relics=[RelicTag.TWIN_DAGGERS], enemies=[_enemy(eid="a"), _enemy(eid="b")],
                       draw=[hidden_dagger()])
        random.seed(1)
        draw_cards(state, 1)
        assert sorted(e.current_hp for e in state.enemies) == [96, 98]

    def test_fox_tail(self):
        enemy = _enemy()
        enemy.status_effects.append(StatusEffect(POISON, 7, False))
        state = _state(relics=[RelicTag.FOX_TAIL], enemies=[enemy], draw=[hidden_dagger()])
        draw_cards(state, 1)
        assert enemy.current_hp == 94

    def test_scorpion_venom_on_marked(self):
        enemy = _enemy()
        enemy.status_effects.append(StatusEffect(MARKED, 1, False))
        state = _state(relics=[RelicTag.SCORPION_VENOM], enemies=[enemy])
        assert state.poison_enemy(enemy, 3) == 6

    def test_black_silk_marked_lasts_a_turn_more(self):
        state = _state(relics=[RelicTag.BLACK_SILK], draw=_filler(20), enemies=[_enemy(intent=0)])
        state.enemies[0].status_effects.append(StatusEffect(MARKED, 2, False))
        end_player_turn(state)
        assert status_stacks(state.enemies[0].status_effects, MARKED) == 2
        end_player_turn(state)
        assert status_stacks(state.enemies[0].status_effects, MARKED) == 0

    def test_bone_die_more_rolls(self):
        from src.domain.card_pool import _luck_rolls
        assert _luck_rolls(_state(relics=[RelicTag.BONE_DIE])) == 2
        assert _luck_rolls(_state()) == 1

    def test_thief_glove_capped(self):
        state = _state(relics=[RelicTag.THIEF_GLOVE], hand=_filler(15))
        for _ in range(15):
            state.discard_random()
        assert state.gold_earned == 10


# ---------------------------------------------------------------------------
# Draw pile
# ---------------------------------------------------------------------------

class TestDrawPile:
    def test_tidy_pile_and_magic_deck(self):
        state = _state(relics=[RelicTag.TIDY_PILE, RelicTag.MAGIC_DECK], draw=_filler(1))
        state.discard_pile.cards = _filler(5)
        draw_cards(state, 2)
        assert state.player.block == 4 and state.hand.count == 3
        state.discard_pile.cards = list(state.hand.cards)
        state.hand.cards.clear()
        state.draw_pile.cards.clear()
        draw_cards(state, 1)
        assert state.hand.count == 1 and state.player.block == 8

    def test_spyglass(self):
        draw = _filler(5)
        state = _state(relics=[RelicTag.SPYGLASS], draw=draw)
        assert relic_triggers.spyglass_cards(state) == ["f4", "f3", "f2"]
        assert relic_triggers.spyglass_cards(_state(draw=draw)) == []


# ---------------------------------------------------------------------------
# Run: rooms, victories, shop, gacha, Brujo, rewards
# ---------------------------------------------------------------------------

class TestRun:
    def test_leaky_purse_every_room(self):
        run = _run(relics=[RelicTag.LEAKY_PURSE])
        assert enter_room(run, RoomType.COMBAT) == 5 and run.gold == 5

    def test_piggy_bank(self):
        run = _run(relics=[RelicTag.PIGGY_BANK], gold=200)
        assert enter_room(run, RoomType.SHOP) == 15
        run.gold = 50
        assert enter_room(run, RoomType.SHOP) == 5

    def test_treasure_gold(self):
        run = _run(relics=[RelicTag.MINER_PICK, RelicTag.LOCKPICK])
        assert enter_room(run, RoomType.TREASURE) == 45

    def test_victory_relics(self):
        run = _run(relics=[RelicTag.CANTEEN, RelicTag.HUNTING_TROPHY, RelicTag.GRINNING_SKULL])
        plain = _run()
        enemies = [_enemy(hp=80)]
        base = apply_combat_victory(plain, 50, enemies, hp_lost=0, turns=2, elite=True)
        gold = apply_combat_victory(run, 50, enemies, hp_lost=0, turns=2, elite=True)
        assert gold - base == 15 + 20 + 30

    def test_canteen_needs_no_damage(self):
        run, plain = _run(relics=[RelicTag.CANTEEN]), _run()
        assert (apply_combat_victory(run, 50, [_enemy()], hp_lost=3)
                == apply_combat_victory(plain, 50, [_enemy()], hp_lost=3))

    def test_veteran_medal_max_hp(self):
        run = _run(relics=[RelicTag.VETERAN_MEDAL])
        before = run.player_max_hp
        apply_combat_victory(run, run.player_current_hp, [_enemy()], elite=True)
        assert run.player_max_hp == before + 3 and max_hp(run) == before + 3

    def test_laurel_leaf_full_heal_on_boss(self):
        run = _run(relics=[RelicTag.LAUREL_LEAF])
        apply_combat_victory(run, 10, [_enemy()], boss=True)
        assert run.player_current_hp == run.player_max_hp

    def test_rascal_boots_luck(self):
        run = _run(CharacterId.ROGUE, relics=[RelicTag.RASCAL_BOOTS])
        luck = run_luck(run)
        apply_combat_victory(run, 50, [_enemy()], hp_lost=0)
        assert run_luck(run) == luck + 2

    def test_max_hp_relics(self):
        base = _run().player_max_hp
        assert _run(relics=[RelicTag.WILD_FRUIT]).player_max_hp == base + 7
        assert _run(relics=[RelicTag.STONE_HEART]).player_max_hp == base + 30

    def test_rabbit_foot_luck(self):
        assert run_luck(_run(relics=[RelicTag.RABBIT_FOOT])) == run_luck(_run()) + 15

    def test_member_card_first_purchase(self):
        run = _run(relics=[RelicTag.MEMBER_CARD])
        assert shop_offer_price(run, 150, relic=True, purchases=0) == 75
        assert shop_offer_price(run, 150, relic=True, purchases=1) == 150

    def test_voucher_free_relic_once(self):
        run = _run(relics=[RelicTag.VOUCHER])
        assert shop_offer_price(run, 150, relic=True, purchases=0) == 0
        assert shop_offer_price(run, 75, relic=False, purchases=0) == 75
        assert use_voucher(run)
        assert shop_offer_price(run, 150, relic=True, purchases=1) == 150

    def test_smith_hammer_half(self):
        card = _atk()
        card.rarity = CardRarity.RARE
        assert upgrade_price(card, [_relic(RelicTag.SMITH_HAMMER)]) == 50
        assert upgrade_price(card) == 100

    def test_two_faced_coin_once_per_floor(self):
        run = _run(relics=[RelicTag.TWO_FACED_COIN], gold=10_000)
        assert gacha_price(run, PullKind.NORMAL) == 0
        assert gacha_price(run, PullKind.STELLAR) > 0
        result = pull(run, PullKind.NORMAL)
        assert result.success and run.gold == 10_000 and gacha_price(run, PullKind.NORMAL) > 0
        run.floor += 1
        assert gacha_price(run, PullKind.NORMAL) == 0

    def test_appraiser_lens_extra_card(self):
        run = _run(relics=[RelicTag.APPRAISER_LENS])
        assert reward_count(run) == 4
        assert len([c for c in pick_reward_cards(run, "x") if not c.lucky_drop]) == 4

    def test_collector_seal_no_low_cards(self):
        run = _run(relics=[RelicTag.COLLECTOR_SEAL])
        for room in range(20):
            cards = pick_reward_cards(run, f"r{room}")
            assert all(c.rarity.value >= Rarity.RARE.value for c in cards)

    def test_collector_seal_packs_never_short(self):
        run = _run(relics=[RelicTag.COLLECTOR_SEAL])
        from src.domain.card_pool import PackTheme
        for theme in PackTheme:
            cards = [c for c in pick_pack_cards(run, theme) if not c.lucky_drop]
            assert len(cards) == 5

    def test_antiquary_seal_relic_pool(self):
        run = _run(relics=[RelicTag.ANTIQUARY_SEAL])
        assert all(r.rarity.value >= Rarity.RARE.value for r in _relic_pool(run))

    def test_pack_reroll_differs(self):
        from src.domain.card_pool import PackTheme
        run = _run()
        first = [c.id for c in pick_pack_cards(run, PackTheme.ACERO)]
        again = [c.id for c in pick_pack_cards(run, PackTheme.ACERO, reroll=1)]
        assert first != again and len(again) >= 5

    def test_bottomless_bag(self):
        run = _run(relics=[RelicTag.BOTTOMLESS_BAG])
        assert pack_picks(run, G) == 3 and pack_picks(run, None) == 1
        assert pack_picks(_run(), G) == 2


# ---------------------------------------------------------------------------
# Pickup effects and deck choices
# ---------------------------------------------------------------------------

class TestPickup:
    def test_diamond_cards(self):
        run = _run()
        run.deck[0].chroma = G
        acquire_relic(run, _relic(RelicTag.DIAMOND_CARDS))
        assert run.deck[0].chroma is Chroma.DIAMOND and run.deck[0].casts() == 3
        card = _atk()
        card.chroma = G
        run.add_card(card)
        assert card.chroma is Chroma.DIAMOND

    def test_diamond_never_drops(self):
        from src.domain.chroma import roll_chroma
        rng = random.Random(1)
        assert all(roll_chroma(rng, luck=10_000) is not Chroma.DIAMOND for _ in range(500))
        assert effect_multiplier(Chroma.DIAMOND) == 3

    def test_portable_anvil(self):
        run = _run()
        acquire_relic(run, _relic(RelicTag.PORTABLE_ANVIL))
        assert sum(c.is_upgraded for c in run.deck) == 1

    def test_iron_file(self):
        run = _run()
        n = len(run.deck)
        acquire_relic(run, _relic(RelicTag.IRON_FILE))
        assert len(run.deck) == n - 1

    def test_tailor_scissors_choice(self):
        run = _run()
        acquire_relic(run, _relic(RelicTag.TAILOR_SCISSORS))
        assert run.pending_choices == [("remove", 3)]
        kind, count = next_choice(run)
        n = len(run.deck)
        assert count == 3 and apply_choice(run, kind, [0, 1, 2]) == 3 and len(run.deck) == n - 3
        assert run.pending_choices == []

    def test_remove_never_empties_the_deck(self):
        run = _run()
        run.deck = run.deck[:2]
        assert choice_limit(run, "remove", 3) == 1
        apply_choice(run, "remove", [0, 1])
        assert len(run.deck) == 1

    def test_marked_cards_choice(self):
        run = _run()
        acquire_relic(run, _relic(RelicTag.MARKED_CARDS))
        kind, count = next_choice(run)
        apply_choice(run, kind, [4])
        assert kind == "innate" and run.deck[4].innate

    def test_apply_choice_ignores_bad_indices(self):
        run = _run()
        n = len(run.deck)
        assert apply_choice(run, "remove", [-1, 99, 0, 0]) == 1 and len(run.deck) == n - 1


# ---------------------------------------------------------------------------
# Stress
# ---------------------------------------------------------------------------

class TestStress:
    def test_every_new_relic_survives_a_long_fight(self):
        """All 114 relics at once (golden): 60 turns of random plays never crash."""
        from src.domain.card_pool import card_factories_for_classes
        rng = random.Random(7)
        relics = [_relic(t, G) for t in NEW_TAGS]
        pool = card_factories_for_classes(set(CardClass))
        deck = [rng.choice(pool)() for _ in range(25)]
        state = _state(relics=relics, enemies=[_enemy(10 ** 6, eid=str(i), intent=3) for i in range(3)],
                       draw=deck, mana=3)
        draw_opening_hand(state)
        for _ in range(60):
            for _ in range(4):
                if state.hand.count:
                    i = rng.randrange(state.hand.count)
                    play_card(state, i, rng.randrange(len(state.enemies)) if state.enemies else None)
            end_player_turn(state)
        assert state.turn == 61
