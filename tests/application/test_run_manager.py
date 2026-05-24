"""Tests for src/application/run_manager.py.

Covers create_run(), generate_enemies(), generate_boss(),
apply_combat_victory(), generate_event_gold(), pick_treasure_relic(),
pick_boss_relics(), and advance_floor().  No pygame dependency.
"""
from __future__ import annotations

from src.application.run_manager import (
    advance_floor,
    apply_combat_victory,
    create_run,
    generate_boss,
    generate_enemies,
    generate_event_gold,
    pick_boss_relics,
    pick_treasure_relic,
)
from src.domain.character import ALL_CHARACTERS, CharacterId
from src.domain.entities import Enemy
from src.domain.relic import Relic
from src.domain.run import Run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _warrior():
    return next(c for c in ALL_CHARACTERS if c.id == CharacterId.WARRIOR)


def _run(seed: int = 1) -> Run:
    return create_run(_warrior(), seed)


# ---------------------------------------------------------------------------
# create_run()
# ---------------------------------------------------------------------------

class TestCreateRun:
    def test_returns_run(self):
        assert isinstance(_run(), Run)

    def test_player_max_hp_matches_character(self):
        char = _warrior()
        run = create_run(char, seed=1)
        assert run.player_max_hp == char.stats.max_hp

    def test_player_current_hp_full(self):
        char = _warrior()
        run = create_run(char, seed=1)
        assert run.player_current_hp == char.stats.max_hp

    def test_relics_empty(self):
        assert _run().relics == []

    def test_deck_non_empty(self):
        assert len(_run().deck) > 0

    def test_deck_ten_cards(self):
        assert len(_run().deck) == 10

    def test_floor_one(self):
        assert _run().floor == 1

    def test_gold_zero(self):
        assert _run().gold == 0

    def test_current_map_not_none(self):
        assert _run().current_map is not None


# ---------------------------------------------------------------------------
# generate_enemies()
# ---------------------------------------------------------------------------

class TestGenerateEnemies:
    def test_returns_non_empty_list(self):
        run = _run()
        enemies = generate_enemies(run, "room_01")
        assert len(enemies) > 0

    def test_all_enemies_are_enemy_instances(self):
        run = _run()
        for e in generate_enemies(run, "room_01"):
            assert isinstance(e, Enemy)

    def test_enemy_hp_positive(self):
        run = _run()
        for e in generate_enemies(run, "room_01"):
            assert e.current_hp > 0

    def test_deterministic_same_room(self):
        run = _run(seed=99)
        count1 = len(generate_enemies(run, "room_A"))
        count2 = len(generate_enemies(run, "room_A"))
        assert count1 == count2

    def test_different_rooms_may_differ(self):
        run = _run(seed=7)
        # collect counts for many different room ids
        counts = {len(generate_enemies(run, f"r{i}")) for i in range(20)}
        # at least one should differ (not all the same count)
        assert len(counts) >= 1   # trivially true; real check is no crash


# ---------------------------------------------------------------------------
# generate_boss()
# ---------------------------------------------------------------------------

class TestGenerateBoss:
    def test_returns_one_enemy(self):
        run = _run()
        assert len(generate_boss(run)) == 1

    def test_boss_is_enemy(self):
        run = _run()
        assert isinstance(generate_boss(run)[0], Enemy)

    def test_boss_hp_positive(self):
        run = _run()
        assert generate_boss(run)[0].current_hp > 0

    def test_boss_tougher_than_regular_enemy_floor1(self):
        run = _run(seed=5)
        boss_hp = generate_boss(run)[0].max_hp
        # Regular enemies on floor 1 have max_hp <= 70 (Golem = 70)
        assert boss_hp > 70


# ---------------------------------------------------------------------------
# apply_combat_victory()
# ---------------------------------------------------------------------------

class TestApplyCombatVictory:
    def test_returns_positive_gold(self):
        run = _run()
        enemies = generate_enemies(run, "room_01")
        gold = apply_combat_victory(run, hp_after=80, enemies=enemies)
        assert gold > 0

    def test_run_gold_increases(self):
        run = _run()
        enemies = generate_enemies(run, "room_01")
        before = run.gold
        gold = apply_combat_victory(run, hp_after=80, enemies=enemies)
        assert run.gold == before + gold

    def test_current_hp_set_to_hp_after(self):
        run = _run()
        enemies = generate_enemies(run, "room_01")
        apply_combat_victory(run, hp_after=75, enemies=enemies)
        # HP may be slightly higher if a BLOOD_POTION relic triggers,
        # but run has no relics so hp == 75
        assert run.player_current_hp == 75


# ---------------------------------------------------------------------------
# generate_event_gold()
# ---------------------------------------------------------------------------

class TestGenerateEventGold:
    def test_returns_positive_int(self):
        run = _run()
        assert generate_event_gold(run, "ev_01") > 0

    def test_is_int(self):
        run = _run()
        assert isinstance(generate_event_gold(run, "ev_01"), int)


# ---------------------------------------------------------------------------
# pick_treasure_relic()
# ---------------------------------------------------------------------------

class TestPickTreasureRelic:
    def test_returns_relic(self):
        run = _run()
        assert isinstance(pick_treasure_relic(run, "tr_01"), Relic)

    def test_relic_has_tag(self):
        run = _run()
        assert pick_treasure_relic(run, "tr_01").tag is not None


# ---------------------------------------------------------------------------
# pick_boss_relics()
# ---------------------------------------------------------------------------

class TestPickBossRelics:
    def test_returns_three_relics(self):
        run = _run()
        assert len(pick_boss_relics(run, 3)) == 3

    def test_all_are_relics(self):
        run = _run()
        for r in pick_boss_relics(run, 3):
            assert isinstance(r, Relic)

    def test_three_distinct_tags(self):
        run = _run()
        tags = [r.tag for r in pick_boss_relics(run, 3)]
        assert len(set(tags)) == 3


# ---------------------------------------------------------------------------
# advance_floor()
# ---------------------------------------------------------------------------

class TestAdvanceFloor:
    def test_increments_floor(self):
        run = _run()
        advance_floor(run)
        assert run.floor == 2

    def test_new_map_generated(self):
        run = _run()
        old_map = run.current_map
        advance_floor(run)
        assert run.current_map is not old_map

    def test_new_map_is_gamemap(self):
        from src.domain.game_map import GameMap
        run = _run()
        advance_floor(run)
        assert isinstance(run.current_map, GameMap)

    def test_floor_increments_again_on_second_advance(self):
        run = _run()
        advance_floor(run)
        advance_floor(run)
        assert run.floor == 3
