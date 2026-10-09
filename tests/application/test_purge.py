"""Altar de Purga: remove one card of your choice for gold. No pygame.

Covers ``application/purge`` (price 75 rising 25 per card removed this run, Máscara del
Ladrón discount, minimum deck, not enough gold, invalid indices, the chosen card is the one
removed, counter and gold bookkeeping, 10^9 gold / many removals) and the map (exactly one
altar per floor in a middle row, every other special room still there).
"""
from __future__ import annotations

import pytest

from src.application.map_generator import generate_map
from src.application.purge import (MIN_DECK, PURGE_BASE, PURGE_STEP, can_purge, purge_block_reason,
                                   purge_card, purge_price)
from src.application.run_manager import create_run
from src.domain.character import ALL_CHARACTERS
from src.domain.map_node import RoomType
from src.domain.relic import Relic, RelicTag


def _run(gold: int = 500):
    run = create_run(ALL_CHARACTERS[0], 3)
    run.gold = gold
    return run


class TestPrice:
    def test_base(self):
        assert purge_price(_run()) == PURGE_BASE == 75

    def test_rises_per_removal(self):
        run = _run()
        run.cards_removed = 3
        assert purge_price(run) == PURGE_BASE + 3 * PURGE_STEP

    def test_negative_counter_is_base(self):
        run = _run()
        run.cards_removed = -4
        assert purge_price(run) == PURGE_BASE

    def test_thief_mask_discount(self):
        run = _run()
        run.relics.append(Relic("m", "Máscara del Ladrón", "", tag=RelicTag.THIEF_MASK))
        assert purge_price(run) < PURGE_BASE


class TestRemove:
    def test_removes_the_chosen_card(self):
        run = _run()
        target = run.deck[4]
        assert purge_card(run, 4) is target and all(c is not target for c in run.deck)

    def test_pays_and_counts(self):
        run = _run(100)
        n = len(run.deck)
        purge_card(run, 0)
        assert (run.gold, run.cards_removed, len(run.deck)) == (25, 1, n - 1)

    def test_next_one_costs_more(self):
        run = _run()
        purge_card(run, 0)
        assert purge_price(run) == PURGE_BASE + PURGE_STEP

    def test_exact_gold(self):
        run = _run(PURGE_BASE)
        assert purge_card(run, 0) is not None and run.gold == 0

    def test_one_gold_short(self):
        run = _run(PURGE_BASE - 1)
        n = len(run.deck)
        assert purge_card(run, 0) is None and len(run.deck) == n and run.gold == PURGE_BASE - 1
        assert purge_block_reason(run) == "No tienes suficiente oro"

    @pytest.mark.parametrize("index", [-1, 999])
    def test_invalid_index(self, index):
        run = _run()
        assert purge_card(run, index) is None and run.cards_removed == 0 and run.gold == 500

    def test_minimum_deck(self):
        run = _run(10 ** 9)
        run.deck = run.deck[:MIN_DECK]
        assert not can_purge(run) and purge_card(run, 0) is None
        assert MIN_DECK == 1 and "última carta" in purge_block_reason(run)

    def test_min_plus_one(self):
        run = _run()
        run.deck = run.deck[:MIN_DECK + 1]
        assert purge_card(run, 0) is not None and len(run.deck) == MIN_DECK

    def test_stress_many_removals(self):
        run = _run(10 ** 9)
        run.deck = run.deck * 30
        removed = 0
        while purge_card(run, 0) is not None:
            removed += 1
        assert len(run.deck) == MIN_DECK and run.cards_removed == removed
        assert purge_price(run) == PURGE_BASE + PURGE_STEP * removed


class TestMap:
    @pytest.mark.parametrize("floor", range(1, 11))
    def test_exactly_one_altar_per_floor(self, floor):
        for seed in range(40):
            gm = generate_map(seed, floor)
            altars = [n for n in gm.nodes.values() if n.room_type is RoomType.PURGE]
            assert len(altars) == 1 and 0 < altars[0].row < gm.rows - 1

    def test_other_special_rooms_still_there(self):
        for seed in range(30):
            types = {n.room_type for n in generate_map(seed, 1).nodes.values()}
            assert {RoomType.TREASURE, RoomType.SHOP, RoomType.BOSS, RoomType.WARLOCK, RoomType.GACHA,
                    RoomType.PURGE, RoomType.COMBAT} <= types

    def test_deterministic(self):
        a = [n.id for n in generate_map(9, 2).nodes.values() if n.room_type is RoomType.PURGE]
        b = [n.id for n in generate_map(9, 2).nodes.values() if n.room_type is RoomType.PURGE]
        assert a == b
