"""Gachapón: domain rules (``domain/gacha.py``) and run use cases (``application/gacha.py``).

Covers prices (base, ×1.5 growth shared by both pulls, rounding, Máscara del
Ladrón, 10^3 pulls), odds (sum to 1, stellar never Común and better on average,
luck lifts high tiers, missing tiers drop out), rolling, paying, the pull
counter, relic acquisition, duplicates once the pool is empty, determinism,
golden chance boost, and a 1 000-pull distribution check.
"""
from __future__ import annotations

import random

import pytest

from src.application.gacha import accept, can_pull, decline, gacha_odds, gacha_price, pull
from src.application.run_manager import create_run
from src.domain.character import ALL_CHARACTERS
from src.domain.gacha import PRICE_GROWTH, PULLS, PullKind, pull_odds, pull_price, roll_pull
from src.domain.rarity import Rarity
from src.domain.relic import Relic, RelicTag
from src.domain.tuning import TUNING


def _run(gold: int = 10_000, hero: int = 0, seed: int = 5):
    run = create_run(ALL_CHARACTERS[hero], seed)
    run.gold = gold
    return run


def _expected_tier(odds) -> float:
    return sum(r.value * p for r, p in odds.items())


class TestPrices:
    def test_normal_base(self):
        assert pull_price(PullKind.NORMAL, 0) == PULLS[PullKind.NORMAL].base_price

    def test_stellar_dearer(self):
        assert pull_price(PullKind.STELLAR, 0) > pull_price(PullKind.NORMAL, 0)

    def test_grows_each_pull(self):
        prices = [pull_price(PullKind.NORMAL, n) for n in range(8)]
        assert all(b > a for a, b in zip(prices, prices[1:]))

    def test_growth_factor(self):
        assert pull_price(PullKind.NORMAL, 1) == round(80 * PRICE_GROWTH / 5) * 5

    def test_multiple_of_five(self):
        assert all(pull_price(k, n) % 5 == 0 for k in PullKind for n in range(30))

    def test_negative_pulls_count_as_zero(self):
        assert pull_price(PullKind.NORMAL, -3) == pull_price(PullKind.NORMAL, 0)

    def test_huge_pull_count(self):
        assert pull_price(PullKind.NORMAL, 1000) > 10 ** 100

    def test_run_price_shared_counter(self):
        run = _run()
        before = gacha_price(run, PullKind.STELLAR)
        pull(run, PullKind.NORMAL)
        assert gacha_price(run, PullKind.STELLAR) > before

    def test_thief_mask_discount(self):
        run = _run()
        full = gacha_price(run, PullKind.NORMAL)
        run.relics.append(Relic("r_mask", "Máscara del Ladrón", "", tag=RelicTag.THIEF_MASK))
        assert gacha_price(run, PullKind.NORMAL) < full


class TestOdds:
    @pytest.mark.parametrize("kind", list(PullKind))
    def test_sum_to_one(self, kind):
        assert sum(pull_odds(kind).values()) == pytest.approx(1.0)

    def test_normal_matches_relic_base(self):
        assert pull_odds(PullKind.NORMAL)[Rarity.LEGENDARY] == pytest.approx(0.02)

    def test_stellar_never_common(self):
        assert pull_odds(PullKind.STELLAR)[Rarity.COMMON] == 0.0

    def test_stellar_better(self):
        assert _expected_tier(pull_odds(PullKind.STELLAR)) > _expected_tier(pull_odds(PullKind.NORMAL)) + 1

    def test_higher_tier_rarer_normal(self):
        odds = pull_odds(PullKind.NORMAL)
        values = [odds[r] for r in Rarity]
        assert values == sorted(values, reverse=True)

    def test_luck_lifts_legendary(self):
        assert pull_odds(PullKind.NORMAL, 50)[Rarity.LEGENDARY] > pull_odds(PullKind.NORMAL, 0)[Rarity.LEGENDARY]

    def test_huge_luck_still_sums_to_one(self):
        assert sum(pull_odds(PullKind.STELLAR, 10 ** 9).values()) == pytest.approx(1.0)

    def test_subset_renormalised(self):
        odds = pull_odds(PullKind.NORMAL, 0, [Rarity.EPIC, Rarity.LEGENDARY])
        assert odds[Rarity.EPIC] == pytest.approx(0.75)

    def test_stellar_only_common_left_still_rolls(self):
        assert pull_odds(PullKind.STELLAR, 0, [Rarity.COMMON]) == {Rarity.COMMON: 1.0}

    def test_run_odds_use_hero_luck(self):
        rogue = _run(hero=2)
        warrior = _run(hero=0)
        assert gacha_odds(rogue, PullKind.NORMAL)[Rarity.LEGENDARY] > \
            gacha_odds(warrior, PullKind.NORMAL)[Rarity.LEGENDARY]


class TestRoll:
    def test_empty_pool(self):
        assert roll_pull([], PullKind.NORMAL, random.Random(1), rarity_of=lambda r: r) is None

    def test_only_present_tiers(self):
        items = [Rarity.RARE, Rarity.RARE]
        assert roll_pull(items, PullKind.STELLAR, random.Random(2), rarity_of=lambda r: r) is Rarity.RARE

    def test_stellar_never_rolls_common_when_others_exist(self):
        rng = random.Random(3)
        items = list(Rarity)
        assert all(roll_pull(items, PullKind.STELLAR, rng, rarity_of=lambda r: r) is not Rarity.COMMON
                   for _ in range(500))

    def test_distribution_1000(self):
        rng = random.Random(4)
        items = list(Rarity)
        got = [roll_pull(items, PullKind.NORMAL, rng, rarity_of=lambda r: r) for _ in range(1000)]
        assert 420 < got.count(Rarity.COMMON) < 580 and got.count(Rarity.LEGENDARY) < 60


class TestPull:
    def test_pays_and_counts(self):
        run = _run(gold=1000)
        price = gacha_price(run, PullKind.NORMAL)
        res = pull(run, PullKind.NORMAL)
        assert (res.success, run.gold, run.gacha_pulls) == (True, 1000 - price, 1)

    def test_pull_does_not_give_the_relic_yet(self):
        run = _run()
        pull(run, PullKind.NORMAL)
        assert run.relics == []

    def test_accept_gives_the_relic(self):
        run = _run()
        res = pull(run, PullKind.NORMAL)
        accept(run, res)
        assert run.relics[-1] is res.relic and res.accepted

    def test_accept_only_once(self):
        run = _run()
        res = pull(run, PullKind.NORMAL)
        accept(run, res)
        assert not accept(run, res) and len(run.relics) == 1

    def test_decline_keeps_nothing_and_no_refund(self):
        run = _run(gold=1000)
        res = pull(run, PullKind.NORMAL)
        decline(res)
        assert (run.relics, run.gold, run.gacha_pulls) == ([], 1000 - res.price, 1)

    def test_cannot_accept_after_decline(self):
        run = _run()
        res = pull(run, PullKind.NORMAL)
        decline(res)
        assert not accept(run, res) and run.relics == []

    def test_failed_pull_cannot_be_accepted(self):
        run = _run(gold=0)
        assert not accept(run, pull(run, PullKind.NORMAL))

    def test_declined_relic_can_come_again(self):
        run = _run(gold=10 ** 60)
        names = set()
        for _ in range(40):
            res = pull(run, PullKind.NORMAL)
            decline(res)
            names.add(res.relic.tag)
        assert len(names) < 40          # nothing was taken out of the pool

    def test_not_enough_gold(self):
        run = _run(gold=79)
        res = pull(run, PullKind.NORMAL)
        assert (res.success, run.gold, run.gacha_pulls, len(run.relics)) == (False, 79, 0, 0)

    def test_exact_gold_is_enough(self):
        run = _run(gold=80)
        assert pull(run, PullKind.NORMAL).success and run.gold == 0

    def test_can_pull(self):
        assert not can_pull(_run(gold=0), PullKind.NORMAL)

    def test_stellar_never_common_in_run(self):
        run = _run(gold=10 ** 30)
        assert all(pull(run, PullKind.STELLAR).relic.rarity is not Rarity.COMMON for _ in range(10))

    def test_deterministic_per_seed(self):
        a, b = _run(seed=9), _run(seed=9)
        assert [pull(a, PullKind.NORMAL).relic.name for _ in range(4)] == \
            [pull(b, PullKind.NORMAL).relic.name for _ in range(4)]

    def test_no_duplicates_while_pool_lasts(self):
        run = _run(gold=10 ** 60)
        names = []
        for _ in range(8):
            res = pull(run, PullKind.NORMAL)
            accept(run, res)
            names.append(res.relic.tag)
        assert len(set(names)) == 8

    def test_duplicates_after_pool_is_empty(self):
        run = _run(gold=10 ** 200)
        results = []
        for _ in range(60):
            res = pull(run, PullKind.NORMAL)
            accept(run, res)
            results.append(res)
        assert any(r.duplicate for r in results) and all(r.success for r in results)

    def test_max_hp_recomputed(self):
        run = _run(gold=10 ** 200)
        for _ in range(60):
            accept(run, pull(run, PullKind.NORMAL))
        assert run.player_max_hp > run.character.stats.max_hp

    def test_stellar_golden_more_often(self):
        TUNING.chroma_chances["golden:relic"] = 0.2
        normal = sum(pull(_run(gold=10 ** 9, seed=s), PullKind.NORMAL).relic.chroma is not None
                     for s in range(300))
        stellar = sum(pull(_run(gold=10 ** 9, seed=s), PullKind.STELLAR).relic.chroma is not None
                      for s in range(300))
        assert stellar > normal * 1.4
