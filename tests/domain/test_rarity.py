"""Shared rarity tiers (cards + relics) and how luck bends drop odds. No pygame."""
from __future__ import annotations

import random
from dataclasses import replace

import pytest

from src.application.card_rewards import pick_reward_cards
from src.application.run_manager import create_run, pick_boss_relics, pick_shop_stock, pick_treasure_relic
from src.domain.card import CardRarity
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma, roll_chroma
from src.domain.rarity import (
    BASE_RARITY_WEIGHT,
    LUCK_CHROMA_STEP,
    RARITY_LABEL,
    Rarity,
    luck_chroma_multiplier,
    rarity_label,
    rarity_odds,
    rarity_weight,
    weighted_sample,
)
from src.domain.relic import RELIC_RARITY, Relic, RelicTag
from src.domain.tuning import TUNING


@pytest.fixture(autouse=True)
def _reset_tuning():
    TUNING.reset()
    yield
    TUNING.reset()


# --- tiers ---------------------------------------------------------------

class TestTiers:
    def test_five_tiers(self):
        assert len(Rarity) == 5

    def test_cards_and_relics_share_the_enum(self):
        assert CardRarity is Rarity

    def test_every_tier_has_label_and_weight(self):
        for r in Rarity:
            assert rarity_label(r) == RARITY_LABEL[r]
            assert BASE_RARITY_WEIGHT[r] > 0

    def test_base_weights_decrease_with_tier(self):
        ws = [BASE_RARITY_WEIGHT[r] for r in sorted(Rarity, key=lambda r: r.value)]
        assert ws == sorted(ws, reverse=True)


# --- luck ----------------------------------------------------------------

class TestLuckWeights:
    def test_zero_luck_is_base(self):
        for r in Rarity:
            assert rarity_weight(r, 0) == BASE_RARITY_WEIGHT[r]

    def test_negative_luck_counts_as_zero(self):
        for r in Rarity:
            assert rarity_weight(r, -10) == BASE_RARITY_WEIGHT[r]

    def test_common_never_changes(self):
        assert rarity_weight(Rarity.COMMON, 1000) == BASE_RARITY_WEIGHT[Rarity.COMMON]

    @pytest.mark.parametrize("luck", [1, 2, 5, 8, 100, 10**6])
    def test_more_luck_more_high_tiers(self, luck):
        low, high = rarity_odds(0), rarity_odds(luck)
        assert high[Rarity.LEGENDARY] > low[Rarity.LEGENDARY]
        assert high[Rarity.COMMON] < low[Rarity.COMMON]

    @pytest.mark.parametrize("luck", [0, 1, 8, 10**6])
    def test_odds_sum_to_one(self, luck):
        assert sum(rarity_odds(luck).values()) == pytest.approx(1.0)

    def test_odds_restricted_to_tiers(self):
        odds = rarity_odds(5, [Rarity.RARE, Rarity.EPIC])
        assert set(odds) == {Rarity.RARE, Rarity.EPIC}
        assert sum(odds.values()) == pytest.approx(1.0)

    def test_chroma_multiplier(self):
        assert luck_chroma_multiplier(0) == 1.0
        assert luck_chroma_multiplier(-3) == 1.0
        assert luck_chroma_multiplier(1) == pytest.approx(1 + LUCK_CHROMA_STEP)
        assert luck_chroma_multiplier(8) == pytest.approx(1 + 8 * LUCK_CHROMA_STEP)


# --- weighted_sample -----------------------------------------------------

def _items():
    return [(f"{r.name}{i}", r) for r in Rarity for i in range(3)]


class TestWeightedSample:
    def test_distinct_and_count(self):
        out = weighted_sample(_items(), 5, random.Random(1), rarity_of=lambda x: x[1])
        assert len(out) == 5 and len(set(out)) == 5

    @pytest.mark.parametrize("count", [0, 1, 15, 16, 100])
    def test_count_capped_by_pool(self, count):
        out = weighted_sample(_items(), count, random.Random(2), rarity_of=lambda x: x[1])
        assert len(out) == min(count, 15)

    def test_empty_pool(self):
        assert weighted_sample([], 3, random.Random(0), rarity_of=lambda x: x) == []

    def test_deterministic(self):
        a = weighted_sample(_items(), 4, random.Random(9), rarity_of=lambda x: x[1], luck=5)
        b = weighted_sample(_items(), 4, random.Random(9), rarity_of=lambda x: x[1], luck=5)
        assert a == b

    def test_single_tier_pool(self):
        items = [("a", Rarity.EPIC), ("b", Rarity.EPIC)]
        out = weighted_sample(items, 2, random.Random(0), rarity_of=lambda x: x[1], luck=100)
        assert sorted(out) == items

    def test_luck_raises_high_tier_frequency(self):
        def legendary_rate(luck):
            rng = random.Random(123)
            hits = sum(weighted_sample(_items(), 1, rng, rarity_of=lambda x: x[1], luck=luck)[0][1]
                       is Rarity.LEGENDARY for _ in range(4000))
            return hits / 4000
        assert legendary_rate(20) > legendary_rate(0) * 2


# --- chroma ----------------------------------------------------------------

class TestLuckyChroma:
    def _rate(self, luck, kind="card"):
        rng = random.Random(7)
        return sum(roll_chroma(rng, kind=kind, luck=luck) is Chroma.GOLDEN for _ in range(20000)) / 20000

    @pytest.mark.parametrize("kind", ["card", "relic"])
    def test_luck_raises_golden_rate(self, kind):
        assert self._rate(10, kind) > self._rate(0, kind) * 1.5

    def test_zero_luck_matches_base_chance(self):
        assert self._rate(0) == pytest.approx(0.05, abs=0.01)

    def test_huge_luck_caps_at_always(self):
        assert self._rate(10**6) == 1.0

    def test_zero_chance_stays_zero_with_luck(self):
        TUNING.chroma_chances["golden:card"] = 0.0
        assert self._rate(10**6) == 0.0


# --- relics ------------------------------------------------------------------

class TestRelicRarity:
    def test_every_tag_has_a_tier(self):
        assert set(RELIC_RARITY) == set(RelicTag)

    def test_relics_cover_all_five_tiers(self):
        assert set(RELIC_RARITY.values()) == set(Rarity)

    def test_rarity_from_tag(self):
        assert Relic("x", "X", "d", tag=RelicTag.SPECTRAL_SHIELD).rarity is Rarity.LEGENDARY

    def test_untagged_is_common(self):
        assert Relic("x", "X", "d").rarity is Rarity.COMMON

    def test_explicit_rarity_wins(self):
        assert Relic("x", "X", "d", tag=RelicTag.GOLD_RING, rarity=Rarity.EPIC).rarity is Rarity.EPIC


def _run_with_luck(luck: int, seed: int):
    base = ALL_CHARACTERS[0]
    char = replace(base, stats=replace(base.stats, luck=luck))
    return create_run(char, seed)


class TestLuckInRuns:
    def test_offered_relics_have_tiers(self):
        run = _run_with_luck(0, 1)
        for relic in pick_boss_relics(run, 3):
            assert relic.rarity is RELIC_RARITY[relic.tag]

    def test_shop_still_three_distinct_relics(self):
        _, relics = pick_shop_stock(_run_with_luck(8, 3))
        assert len({r.tag for r in relics}) == 3

    def test_luck_gives_rarer_treasure_relics(self):
        def avg_tier(luck):
            tiers = [pick_treasure_relic(_run_with_luck(luck, s), "tr").rarity.value for s in range(400)]
            return sum(tiers) / len(tiers)
        assert avg_tier(30) > avg_tier(0)

    def test_luck_gives_more_golden_cards(self):
        def golden(luck):
            return sum(c.chroma is Chroma.GOLDEN
                       for s in range(400) for c in pick_reward_cards(_run_with_luck(luck, s), "r"))
        assert golden(30) > golden(0)

    def test_luck_gives_more_golden_relics(self):
        def golden(luck):
            return sum(r.chroma is Chroma.GOLDEN
                       for s in range(400) for r in pick_boss_relics(_run_with_luck(luck, s), 3))
        assert golden(30) > golden(0)
