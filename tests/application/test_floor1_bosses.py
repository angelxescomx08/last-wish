"""Floor-1 bosses: pattern AI, new statuses, status cards and the extended enemy turn.

Scope: ``application/enemy_ai.py``, ``domain/status_cards.py``, the boss parts of
``end_turn`` (multi-hit, extras, Veneno on the hero, Enredado, timed debuffs),
``play_card`` (Injugable, Agotar, Frágil), ``drawing`` (Moho) and
``run_manager.generate_boss``. Stress: 300 enemy turns per boss, 10^9 stacks.
"""
from __future__ import annotations

import random

import pytest

from src.application import enemy_ai
from src.application.end_turn import _execute_intent, end_player_turn
from src.application.play_card import play_card
from src.application.run_manager import create_run, floor_boss_ai, generate_boss
from src.domain.card import Card, CardEffect, CardType
from src.domain.character import ALL_CHARACTERS
from src.domain.combat import CombatState
from src.domain.entities import (BLADES, ENTANGLED, FRAIL, POISON, STRENGTH, VULNERABLE, WEAK,
                                 Enemy, Intent, IntentType, Player, add_status, enemy_hit_damage,
                                 frail, status_stacks, vulnerable)
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic, RelicTag
from src.domain.status_cards import MOLD_ID, SPORE_ID, SPORE_POISON, mold, spore
from src.domain.tuning import TUNING


def _plain(cid: str = "c", block: int = 0, damage: int = 0) -> Card:
    return Card(id=cid, name=cid, card_type=CardType.SKILL if block else CardType.ATTACK, cost=0,
                base_effect=CardEffect(name=cid, block=BigValue(block), damage=BigValue(damage)))


def _state(enemy: Enemy, *, hp: int = 100, hand=None, draw=None, relics=None,
           mana: int = 3) -> CombatState:
    return CombatState(
        player=Player(name="Héroe", max_hp=hp, current_hp=hp),
        enemies=[enemy], hand=Hand(cards=list(hand or [])),
        draw_pile=DrawPile(cards=list(draw if draw is not None else [_plain(f"d{i}") for i in range(30)])),
        discard_pile=DiscardPile(cards=[]), mana=Mana(current=mana, maximum=mana),
        relics=list(relics or []))


def _boss(ai: str) -> Enemy:
    return enemy_ai.create_boss(ai, 1)


def _enemy(intent: Intent, hp: int = 50) -> Enemy:
    return Enemy(id="e", name="Dummy", max_hp=hp, current_hp=hp, intent=intent)


# ---------------------------------------------------------------------------
# Status math
# ---------------------------------------------------------------------------

class TestStatusMath:
    def test_vulnerable_x1_5(self):
        assert vulnerable(10, _st(VULNERABLE, 1)) == 15

    def test_vulnerable_rounds_down(self):
        assert vulnerable(5, _st(VULNERABLE, 1)) == 7

    def test_vulnerable_absent(self):
        assert vulnerable(10, []) == 10

    def test_frail_x0_75(self):
        assert frail(8, _st(FRAIL, 2)) == 6

    def test_frail_zero(self):
        assert frail(0, _st(FRAIL, 1)) == 0

    def test_huge_values(self):
        assert vulnerable(10 ** 18, _st(VULNERABLE, 10 ** 9)) == 15 * 10 ** 17

    def test_hit_damage_strength_weak_vulnerable(self):
        e = _enemy(Intent(IntentType.ATTACK, 8))
        add_status(e.status_effects, STRENGTH, 4, is_buff=True)
        add_status(e.status_effects, WEAK, 1, is_buff=False)
        p = Player("P", 50, 50)
        add_status(p.status_effects, VULNERABLE, 1, is_buff=False)
        assert enemy_hit_damage(e, p) == (12 * 3 // 4) * 3 // 2


def _st(name: str, stacks: int):
    out = []
    add_status(out, name, stacks, is_buff=False)
    return out


# ---------------------------------------------------------------------------
# Multi-hit and extras
# ---------------------------------------------------------------------------

class TestEnemyTurn:
    def test_multi_hit_total(self):
        s = _state(_enemy(Intent(IntentType.ATTACK, 4, hits=3, move="X")))
        _execute_intent(s, s.enemies[0])
        assert s.player.current_hp == 88

    def test_block_absorbs_each_hit(self):
        s = _state(_enemy(Intent(IntentType.ATTACK, 4, hits=3, move="X")))
        s.player.block = 6
        log = _execute_intent(s, s.enemies[0])
        assert log.hits == [0, 2, 4]

    def test_one_hit_still_works(self):
        s = _state(_enemy(Intent(IntentType.ATTACK, 11)))
        _execute_intent(s, s.enemies[0])
        assert s.player.current_hp == 89

    def test_counter_damage_per_blocked_hit(self):
        s = _state(_enemy(Intent(IntentType.ATTACK, 2, hits=4, move="X")))
        s.player.block, s.counter_damage = 100, 3
        _execute_intent(s, s.enemies[0])
        assert s.enemies[0].current_hp == 50 - 12

    def test_multi_hit_stops_when_hero_dies(self):
        s = _state(_enemy(Intent(IntentType.ATTACK, 10, hits=5, move="X")), hp=15)
        log = _execute_intent(s, s.enemies[0])
        assert len(log.hits) == 2 and s.player.current_hp == 0

    def test_invincible_takes_no_damage(self):
        TUNING.invincible = True
        s = _state(_enemy(Intent(IntentType.ATTACK, 10, hits=5, move="X")))
        _execute_intent(s, s.enemies[0])
        assert s.player.current_hp == 100

    def test_debuffs_applied(self):
        s = _state(_enemy(Intent(IntentType.DEBUFF, move="X", debuffs=((FRAIL, 2), (WEAK, 1)))))
        _execute_intent(s, s.enemies[0])
        assert (status_stacks(s.player.status_effects, FRAIL),
                status_stacks(s.player.status_effects, WEAK)) == (2, 1)

    def test_named_debuff_does_not_add_generic_weak(self):
        s = _state(_enemy(Intent(IntentType.DEBUFF, move="X", debuffs=((FRAIL, 2),))))
        _execute_intent(s, s.enemies[0])
        assert status_stacks(s.player.status_effects, WEAK) == 0

    def test_legacy_debuff_still_weakens(self):
        s = _state(_enemy(Intent(IntentType.DEBUFF)))
        _execute_intent(s, s.enemies[0])
        assert status_stacks(s.player.status_effects, WEAK) == 2

    def test_panacea_blocks_boss_debuffs(self):
        s = _state(_enemy(Intent(IntentType.DEBUFF, move="X", debuffs=((VULNERABLE, 2),))),
                   relics=[Relic("panacea", "Panacea", "", tag=RelicTag.PANACEA)])
        _execute_intent(s, s.enemies[0])
        assert s.player.status_effects == []

    def test_buffs_on_self(self):
        s = _state(_enemy(Intent(IntentType.BUFF, move="X", buffs=((STRENGTH, 2),), block=6)))
        _execute_intent(s, s.enemies[0])
        assert (status_stacks(s.enemies[0].status_effects, STRENGTH), s.enemies[0].block) == (2, 6)

    def test_cards_to_draw_pile(self):
        s = _state(_enemy(Intent(IntentType.ATTACK, 1, move="X", cards=((SPORE_ID, 2, "draw"),))))
        _execute_intent(s, s.enemies[0])
        assert sum(c.id == SPORE_ID for c in s.draw_pile.cards) == 2

    def test_cards_to_hand_overflow_to_discard(self):
        s = _state(_enemy(Intent(IntentType.DEBUFF, move="X", cards=((SPORE_ID, 3, "hand"),))),
                   hand=[_plain(f"h{i}") for i in range(s_max() - 1)])
        _execute_intent(s, s.enemies[0])
        assert (sum(c.id == SPORE_ID for c in s.hand.cards),
                sum(c.id == SPORE_ID for c in s.discard_pile.cards)) == (1, 2)

    def test_log_records_cards(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 5, move="X", cards=((MOLD_ID, 2, "discard"),))))
        log = _execute_intent(s, s.enemies[0])
        assert log.cards == [(MOLD_ID, 2, "discard")]


def s_max() -> int:
    return Hand(cards=[]).max_size


# ---------------------------------------------------------------------------
# Hero statuses over turns
# ---------------------------------------------------------------------------

class TestHeroStatuses:
    def test_poison_ticks_at_turn_start(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)))
        add_status(s.player.status_effects, POISON, 3, is_buff=False)
        end_player_turn(s)
        assert (s.player.current_hp, status_stacks(s.player.status_effects, POISON)) == (97, 2)

    def test_poison_ignores_block(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)))
        s.retain_block = True
        s.player.block = 50
        add_status(s.player.status_effects, POISON, 4, is_buff=False)
        end_player_turn(s)
        assert s.player.current_hp == 96

    def test_poison_10e9_kills_but_not_negative(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)))
        add_status(s.player.status_effects, POISON, 10 ** 9, is_buff=False)
        end_player_turn(s)
        assert s.player.current_hp == 0

    def test_entangled_draws_less_once(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)))
        add_status(s.player.status_effects, ENTANGLED, 2, is_buff=False)
        end_player_turn(s)
        first = s.hand.count
        end_player_turn(s)
        assert (first, s.hand.count) == (3, 5)

    def test_entangled_huge_draws_nothing(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)))
        add_status(s.player.status_effects, ENTANGLED, 10 ** 9, is_buff=False)
        end_player_turn(s)
        assert s.hand.count == 0

    def test_vulnerable_and_frail_tick_at_end_of_turn(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)))
        add_status(s.player.status_effects, VULNERABLE, 2, is_buff=False)
        add_status(s.player.status_effects, FRAIL, 1, is_buff=False)
        end_player_turn(s)
        assert ({se.name: se.stacks for se in s.player.status_effects}) == {VULNERABLE: 1}

    def test_frail_reduces_card_block(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)), hand=[_plain("b", block=8)])
        add_status(s.player.status_effects, FRAIL, 1, is_buff=False)
        play_card(s, 0)
        assert s.player.block == 6

    def test_vulnerable_increases_hit(self):
        s = _state(_enemy(Intent(IntentType.ATTACK, 10)))
        add_status(s.player.status_effects, VULNERABLE, 1, is_buff=False)
        _execute_intent(s, s.enemies[0])
        assert s.player.current_hp == 85


# ---------------------------------------------------------------------------
# Status cards
# ---------------------------------------------------------------------------

class TestStatusCards:
    def test_spore_costs_one_and_exhausts(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)), hand=[spore()])
        play_card(s, 0)
        assert (s.mana.current, s.discard_pile.count, len(s.exhausted)) == (2, 0, 1)

    def test_spore_in_hand_poisons(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)), hand=[spore(), spore()])
        end_player_turn(s)
        assert status_stacks(s.player.status_effects, POISON) == 2 * SPORE_POISON - 1

    def test_spore_discarded_when_kept(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)), hand=[spore()])
        end_player_turn(s)
        assert any(c.id == SPORE_ID for c in s.discard_pile.cards + s.hand.cards + s.draw_pile.cards)

    def test_mold_unplayable(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)), hand=[mold()])
        assert not play_card(s, 0).success

    def test_mold_drains_mana_on_draw(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)), draw=[_plain(f"d{i}") for i in range(10)] + [mold()])
        end_player_turn(s)
        assert s.mana.current == 2

    def test_mold_drain_never_negative(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)), draw=[mold() for _ in range(5)], mana=1)
        end_player_turn(s)
        assert s.mana.current == 0

    def test_mold_fades_at_end_of_turn(self):
        s = _state(_enemy(Intent(IntentType.BLOCK, 0)), hand=[mold()], draw=[])
        end_player_turn(s)
        assert all(c.id != MOLD_ID for c in s.discard_pile.cards + s.hand.cards + s.draw_pile.cards)

    def test_status_cards_not_upgradable(self):
        from src.domain.card_upgrade import can_upgrade
        assert not can_upgrade(spore()) and not can_upgrade(mold())

    def test_status_cards_never_reach_run_deck(self):
        from src.application.combat_factory import create_combat_from_run
        run = create_run(ALL_CHARACTERS[0], seed=3)
        before = len(run.deck)
        state = create_combat_from_run(run, [_boss(enemy_ai.MYCELID)])
        state.add_status_cards(SPORE_ID, 5, "draw")
        assert len(run.deck) == before


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

class TestPatterns:
    def test_three_floor1_bosses(self):
        assert len(enemy_ai.FLOOR1_BOSSES) == 3

    def test_bosses_flagged(self):
        assert all(_boss(ai).is_boss for ai in enemy_ai.FLOOR1_BOSSES)

    def test_first_intents(self):
        assert [_boss(ai).intent.move_id for ai in enemy_ai.FLOOR1_BOSSES] == ["spores", "web", "blade_dance"]

    def test_mycelid_cycle(self):
        b = _boss(enemy_ai.MYCELID)
        ids = [b.intent.move_id] + [enemy_ai.next_intent(b, None).move_id for _ in range(5)]
        assert ids == ["spores", "roots", "mold", "spores", "roots", "mold"]

    def test_mycelid_identity_is_cards(self):
        b = _boss(enemy_ai.MYCELID)
        intents = [b.intent] + [enemy_ai.next_intent(b, None) for _ in range(2)]
        assert sum(n for it in intents for _, n, _ in it.cards) == 4

    def test_weaver_cycle(self):
        b = _boss(enemy_ai.WEAVER)
        ids = [b.intent.move_id] + [enemy_ai.next_intent(b, None).move_id for _ in range(3)]
        assert ids == ["web", "fang", "cocoon", "feast"]

    def test_feast_bites_per_debuff(self):
        b = _boss(enemy_ai.WEAVER)
        b.ai_step = 3
        p = Player("P", 50, 50)
        for name in (WEAK, FRAIL, VULNERABLE):
            add_status(p.status_effects, name, 1, is_buff=False)
        assert enemy_ai.next_intent(b, p).hits == 4

    def test_feast_without_debuffs_one_bite(self):
        b = _boss(enemy_ai.WEAVER)
        b.ai_step = 3
        assert enemy_ai.next_intent(b, Player("P", 5, 5)).hits == 1

    def test_knight_starts_with_two_blades(self):
        assert status_stacks(_boss(enemy_ai.HOLLOW_KNIGHT).status_effects, BLADES) == 2

    def test_knight_dance_hits_per_blade(self):
        b = _boss(enemy_ai.HOLLOW_KNIGHT)
        assert b.intent.hits == 2

    def test_knight_blades_capped(self):
        b = _boss(enemy_ai.HOLLOW_KNIGHT)
        s = _state(b, hp=10 ** 9)
        TUNING.invincible = True
        for _ in range(60):
            end_player_turn(s)
        assert status_stacks(b.status_effects, BLADES) == enemy_ai.KNIGHT_MAX_BLADES

    def test_enrage_once(self):
        b = _boss(enemy_ai.WEAVER)
        b.current_hp = b.max_hp // 2
        first = enemy_ai.next_intent(b, None).move_id
        second = enemy_ai.next_intent(b, None).move_id
        assert (first, second != "brood") == ("brood", True)

    def test_enrage_not_above_half(self):
        b = _boss(enemy_ai.HOLLOW_KNIGHT)
        b.current_hp = b.max_hp // 2 + 1
        assert enemy_ai.next_intent(b, None).move_id != "fury"

    def test_unknown_ai(self):
        assert enemy_ai.next_intent(Enemy("x", "X", 1, 1, ai="nope"), None).intent_type == IntentType.UNKNOWN

    def test_floor_scaling(self):
        assert enemy_ai.create_boss(enemy_ai.HOLLOW_KNIGHT, 3).max_hp > _boss(enemy_ai.HOLLOW_KNIGHT).max_hp

    @pytest.mark.parametrize("ai", enemy_ai.FLOOR1_BOSSES)
    def test_300_turns_stress(self, ai):
        random.seed(7)
        b = _boss(ai)
        s = _state(b, hp=10 ** 6, draw=[_plain(f"d{i}") for i in range(40)])
        for _ in range(300):
            end_player_turn(s)
        assert s.player.is_alive and b.is_alive and b.intent.move


# ---------------------------------------------------------------------------
# Run integration
# ---------------------------------------------------------------------------

class TestRunBoss:
    def test_floor1_boss_is_a_pattern_boss(self):
        run = create_run(ALL_CHARACTERS[0], seed=1)
        assert generate_boss(run)[0].ai in enemy_ai.FLOOR1_BOSSES

    def test_seed_deterministic(self):
        a = create_run(ALL_CHARACTERS[0], seed=42)
        b = create_run(ALL_CHARACTERS[1], seed=42)
        assert floor_boss_ai(a) == floor_boss_ai(b)

    def test_all_three_appear_over_seeds(self):
        seen = {floor_boss_ai(create_run(ALL_CHARACTERS[0], seed=s)) for s in range(60)}
        assert seen == set(enemy_ai.FLOOR1_BOSSES)

    def test_forced_boss(self):
        TUNING.forced_boss = 3
        run = create_run(ALL_CHARACTERS[0], seed=1)
        assert generate_boss(run)[0].ai == enemy_ai.HOLLOW_KNIGHT

    def test_floor2_keeps_crypt_lord(self):
        run = create_run(ALL_CHARACTERS[0], seed=1)
        run.floor = 2
        assert generate_boss(run)[0].ai == ""

    def test_boss_rooms_toggle(self):
        from src.application.run_manager import generate_enemies
        TUNING.boss_rooms = True
        run = create_run(ALL_CHARACTERS[0], seed=1)
        assert generate_enemies(run, "r")[0].is_boss
