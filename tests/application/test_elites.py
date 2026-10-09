"""Elites (``application/elites.py``): one mini-boss room per floor.

Covers the five elites (HP between the regular enemies and the bosses, floor scaling,
``is_elite``), each pattern's cycle and move ids, the one-shot move at half HP, the
Minotauro's growing Embestida, the Bruja's Moho and brew, seeded rolls and Pruebas
overrides, intents resolved by the real turn pipeline (100 turns per elite), the map
(exactly one ÉLITE room per floor, never in the first two rows nor on the boss's
doorstep, almost always avoidable, other rooms unchanged), the relic drop and the card
reward's small luck bonus (odds better but not too much, golden chances unchanged).
"""
from __future__ import annotations

import random

import pytest

from src.application import elites as E
from src.application import enemy_ai, enemy_roster
from src.application.card_rewards import pick_reward_cards
from src.application.combat_factory import create_combat_from_run
from src.application.end_turn import end_player_turn
from src.application.map_generator import generate_map
from src.application.run_manager import (create_run, generate_elite, generate_enemies,
                                         pick_elite_relic, run_luck)
from src.domain.character import ALL_CHARACTERS
from src.domain.entities import STRENGTH, IntentType, status_stacks
from src.domain.map_node import RoomType
from src.domain.rarity import Rarity, rarity_odds
from src.domain.status_cards import MOLD_ID
from src.domain.tuning import TUNING


def _run(seed: int = 3):
    return create_run(ALL_CHARACTERS[0], seed)


def _moves(ai: str, n: int = 12) -> list[str]:
    e = E.create_elite(ai)
    ids = [e.intent.move_id]
    for _ in range(n):
        ids.append(E.next_intent(e, None).move_id)
    return ids


class TestDefinitions:
    def test_five_elites(self):
        assert len(E.ELITES) == 5 and set(E.ELITE_ORDER) == set(E.ELITES)

    @pytest.mark.parametrize("ai", E.ELITE_ORDER)
    def test_between_regulars_and_bosses(self, ai):
        hp = E.ELITES[ai].hp
        assert max(d.hp for d in enemy_roster.ENEMIES.values()) < hp < min(
            d.hp for d in enemy_ai.BOSSES.values())

    def test_names_unique_and_not_regular(self):
        names = [d.name for d in E.ELITES.values()]
        assert len(set(names)) == 5 and not set(names) & {d.name for d in enemy_roster.ENEMIES.values()}

    @pytest.mark.parametrize("ai", E.ELITE_ORDER)
    def test_created(self, ai):
        e = E.create_elite(ai, 1, "x")
        assert e.is_elite and not e.is_boss and e.ai == ai and e.current_hp == e.max_hp == E.ELITES[ai].hp
        assert e.intent.intent_type is not IntentType.UNKNOWN and e.intent.move

    @pytest.mark.parametrize("floor", [1, 2, 5, 12])
    def test_floor_scaling(self, floor):
        e = E.create_elite(E.MINOTAUR, floor)
        assert e.max_hp == int(100 * (1 + 0.15 * (floor - 1))) and e.floor == floor

    def test_has_pattern_through_enemy_ai(self):
        e = E.create_elite(E.GARGOYLE)
        assert enemy_ai.has_pattern(e) and enemy_ai.next_intent(e, None).move_id

    def test_labels(self):
        assert E.elite_label(0) == "Al azar" and E.elite_label(1) == "El Verdugo"
        assert E.elite_label(99) == "Al azar"


class TestPatterns:
    def test_executioner_cycle(self):
        assert _moves(E.EXECUTIONER, 7) == ["sentence", "chop", "sharpen", "behead"] * 2

    def test_hag_cycle(self):
        assert _moves(E.HAG, 7) == ["hex", "bolt", "cauldron", "voodoo"] * 2

    def test_gargoyle_cycle(self):
        assert _moves(E.GARGOYLE, 5) == ["petrify", "dive", "rend"] * 2

    def test_minotaur_cycle(self):
        assert _moves(E.MINOTAUR, 5) == ["paw", "charge", "stomp"] * 2

    def test_scorpion_cycle(self):
        assert _moves(E.SCORPION, 7) == ["sting", "pinch", "shell", "toxin"] * 2

    def test_multi_hits(self):
        e = E.create_elite(E.GARGOYLE)
        dive = E.next_intent(e, None)
        assert dive.move_id == "dive" and dive.hits == 3

    def test_hag_shuffles_mold(self):
        e = E.create_elite(E.HAG)
        for _ in range(2):
            it = E.next_intent(e, None)
        assert it.move_id == "cauldron" and it.cards == ((MOLD_ID, 2, "draw"),)

    def test_minotaur_charge_grows(self):
        e = E.create_elite(E.MINOTAUR)
        charges = []
        for _ in range(9):
            it = E.next_intent(e, None)
            if it.move_id == "charge":
                charges.append(it.value)
        assert charges[:3] == [15, 20, 25]

    def test_minotaur_charge_scales_by_floor(self):
        e = E.create_elite(E.MINOTAUR, 3)
        it = E.next_intent(e, None)
        assert it.move_id == "charge" and it.value == int(15 * 1.3)

    @pytest.mark.parametrize("ai,key", [(E.EXECUTIONER, "bloodlust"), (E.HAG, "potion"),
                                        (E.GARGOYLE, "awaken"), (E.MINOTAUR, "rage"),
                                        (E.SCORPION, "frenzy")])
    def test_enrage_once_at_half(self, ai, key):
        e = E.create_elite(ai)
        e.current_hp = e.max_hp // 2
        assert E.next_intent(e, None).move_id == key
        assert all(E.next_intent(e, None).move_id != key for _ in range(10))

    def test_no_enrage_above_half(self):
        e = E.create_elite(E.SCORPION)
        e.current_hp = e.max_hp // 2 + 1
        assert all(E.next_intent(e, None).move_id != "frenzy" for _ in range(8))

    def test_every_move_described(self):
        for ai in E.ELITE_ORDER:
            e = E.create_elite(ai)
            e.current_hp = 1
            for _ in range(8):
                it = E.next_intent(e, None)
                assert it.move and it.move_id and it.description

    def test_unknown_ai(self):
        e = E.create_elite(E.HAG)
        e.ai = "nope"
        assert E.next_intent(e, None).intent_type is IntentType.UNKNOWN


class TestTurns:
    @pytest.mark.parametrize("ai", E.ELITE_ORDER)
    def test_100_turns(self, ai):
        TUNING.invincible = True
        run = _run()
        state = create_combat_from_run(run, [E.create_elite(ai, 1, "e")])
        for _ in range(100):
            end_player_turn(state)
        assert state.enemies[0].is_alive and state.player.is_alive

    def test_hag_brew_heals(self):
        run = _run()
        hag = E.create_elite(E.HAG, 1, "e")
        state = create_combat_from_run(run, [hag])
        hag.current_hp = 20
        hag.intent = E.next_intent(hag, None)          # half HP → Brebaje Prohibido
        end_player_turn(state)
        assert hag.current_hp == 35 and status_stacks(hag.status_effects, STRENGTH) == 2

    def test_executioner_sharpen_gives_strength(self):
        TUNING.invincible = True
        run = _run()
        e = E.create_elite(E.EXECUTIONER, 1, "e")
        state = create_combat_from_run(run, [e])
        for _ in range(3):
            end_player_turn(state)
        assert status_stacks(e.status_effects, STRENGTH) == 2


class TestRolls:
    def test_seeded(self):
        a = E.roll_elite(random.Random(5), 1, "r")
        b = E.roll_elite(random.Random(5), 1, "r")
        assert a[0].ai == b[0].ai and len(a) == 1 and a[0].is_elite

    def test_all_appear(self):
        rng = random.Random(1)
        assert {E.roll_elite(rng, 1, "r")[0].ai for _ in range(200)} == set(E.ELITE_ORDER)

    @pytest.mark.parametrize("k", range(1, 6))
    def test_forced(self, k):
        assert E.roll_elite(random.Random(0), 2, "r", forced=k)[0].ai == E.ELITE_ORDER[k - 1]

    def test_generate_elite_stable_per_room(self):
        run = _run(9)
        assert generate_elite(run, "f1_r3_c2")[0].ai == generate_elite(run, "f1_r3_c2")[0].ai

    def test_pruebas_forced_elite(self):
        TUNING.forced_elite = 4
        assert generate_elite(_run(), "x")[0].ai == E.MINOTAUR

    def test_pruebas_elite_rooms(self):
        TUNING.elite_rooms = True
        enemies = generate_enemies(_run(), "f1_r1_c2")
        assert len(enemies) == 1 and enemies[0].is_elite

    def test_boss_rooms_win_over_elite_rooms(self):
        TUNING.elite_rooms = True
        TUNING.boss_rooms = True
        assert generate_enemies(_run(), "x")[0].is_boss

    def test_settings_persist(self, tmp_path):
        from src.infrastructure.dev_settings import load_dev_settings, save_dev_settings
        TUNING.forced_elite, TUNING.elite_rooms = 3, True
        save_dev_settings(tmp_path / "d.json")
        TUNING.reset()
        load_dev_settings(tmp_path / "d.json")
        assert (TUNING.forced_elite, TUNING.elite_rooms) == (3, True)

    def test_settings_clamped(self, tmp_path):
        from src.infrastructure.dev_settings import apply_dict
        apply_dict({"forced_elite": 99, "elite_rooms": 1})
        assert TUNING.forced_elite == 5 and TUNING.elite_rooms is True


def _reachable_without(gm, blocked: str) -> bool:
    start = next(n.id for n in gm.nodes.values() if n.available)
    seen, todo = {start}, [start]
    while todo:
        for nxt in gm.nodes[todo.pop()].connections:
            if nxt != blocked and nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return gm.boss_id in seen


class TestMap:
    @pytest.mark.parametrize("floor", range(1, 11))
    def test_exactly_one_per_floor(self, floor):
        for seed in range(60):
            gm = generate_map(seed, floor)
            assert sum(n.room_type is RoomType.ELITE for n in gm.nodes.values()) == 1

    def test_never_in_first_rows_nor_at_the_boss_door(self):
        for seed in range(150):
            for floor in (1, 2, 4, 7):
                gm = generate_map(seed, floor)
                elite = next(n for n in gm.nodes.values() if n.room_type is RoomType.ELITE)
                assert elite.row >= 2 and gm.boss_id not in elite.connections

    def test_almost_always_avoidable(self):
        maps = [generate_map(seed, floor) for seed in range(200) for floor in (1, 3, 6)]
        forced = sum(not _reachable_without(gm, next(n.id for n in gm.nodes.values()
                                                     if n.room_type is RoomType.ELITE))
                     for gm in maps)
        assert forced / len(maps) < 0.01

    def test_deterministic(self):
        a, b = generate_map(42, 3), generate_map(42, 3)
        assert {k: n.room_type for k, n in a.nodes.items()} == {k: n.room_type for k, n in b.nodes.items()}

    def test_other_rooms_kept(self):
        """The elite only replaces a plain combat room; every other special room stays."""
        for seed in range(80):
            gm = generate_map(seed, 1)
            kinds = [n.room_type for n in gm.nodes.values()]
            for kind in (RoomType.WARLOCK, RoomType.BOSS):
                assert kinds.count(kind) == 1


class TestRewards:
    def test_relic_not_owned(self):
        run = _run()
        relic = pick_elite_relic(run, "f1_r3_c1")
        assert relic.tag not in {r.tag for r in run.relics}

    def test_relic_stable_per_room(self):
        run = _run(11)
        assert pick_elite_relic(run, "a").id == pick_elite_relic(run, "a").id

    def test_bonus_zero_is_the_normal_reward(self):
        run = _run(4)
        assert [c.id for c in pick_reward_cards(run, "r")] == \
               [c.id for c in pick_reward_cards(run, "r", luck_bonus=0)]

    def test_better_but_not_too_much(self):
        """Over many rooms, Rara or better comes up more often, but stays a minority."""
        run = _run(2)
        base = bonus = total = 0
        for k in range(600):
            room = f"room{k}"
            base += sum(c.rarity.value >= Rarity.RARE.value for c in pick_reward_cards(run, room)[:3])
            bonus += sum(c.rarity.value >= Rarity.RARE.value
                         for c in pick_reward_cards(run, room, luck_bonus=E.ELITE_CARD_LUCK)[:3])
            total += 3
        assert bonus > base * 1.2 and bonus / total < 0.5

    def test_odds_moderate(self):
        luck = run_luck(_run())
        rare_up = lambda odds: sum(v for r, v in odds.items() if r.value >= Rarity.RARE.value)   # noqa: E731
        before, after = rare_up(rarity_odds(luck)), rare_up(rarity_odds(luck + E.ELITE_CARD_LUCK))
        assert 0.08 < after - before < 0.2

    def test_golden_chances_unchanged(self):
        run = _run(6)
        normal = [c.chroma for c in pick_reward_cards(run, "z")]
        elite = [c.chroma for c in pick_reward_cards(run, "z", luck_bonus=E.ELITE_CARD_LUCK)]
        assert normal == elite

    def test_negative_bonus_ignored(self):
        run = _run(4)
        assert [c.id for c in pick_reward_cards(run, "r", luck_bonus=-50)] == \
               [c.id for c in pick_reward_cards(run, "r")]
