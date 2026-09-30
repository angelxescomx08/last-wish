"""El Brujo: prices by rarity, paying gold, caps and map placement. No pygame."""
from __future__ import annotations

import pytest

from src.application.map_generator import generate_map
from src.application.run_manager import create_run
from src.application.warlock import UPGRADE_PRICE, buy_upgrade, can_buy_upgrade, upgrade_price
from src.domain.card import Card, CardEffect, CardType, CardUpgrade
from src.domain.character import ALL_CHARACTERS
from src.domain.map_node import RoomType
from src.domain.numbers import BigValue
from src.domain.rarity import Rarity


def _card(rarity=Rarity.COMMON, **kw):
    return Card(id="c", name="C", card_type=CardType.ATTACK, cost=1, rarity=rarity,
                base_effect=CardEffect(name="C", damage=BigValue(6)), **kw)


def _run(gold=1000):
    run = create_run(ALL_CHARACTERS[0], 1)
    run.gold = gold
    return run


class TestPrice:
    def test_every_rarity_has_a_price_growing_with_tier(self):
        prices = [UPGRADE_PRICE[r] for r in sorted(Rarity, key=lambda r: r.value)]
        assert len(prices) == 5 and prices == sorted(prices) and len(set(prices)) == 5

    @pytest.mark.parametrize("rarity", list(Rarity))
    def test_first_upgrade_is_base_price(self, rarity):
        assert upgrade_price(_card(rarity)) == UPGRADE_PRICE[rarity]

    def test_unlimited_cards_get_pricier(self):
        c = _card(max_upgrades=None, upgrade=CardUpgrade(damage=1))
        c.upgrade_level = 4
        assert upgrade_price(c) == UPGRADE_PRICE[Rarity.COMMON] * 5


class TestBuy:
    def test_pays_and_upgrades(self):
        run = _run(gold=500)
        run.deck = [_card(Rarity.RARE)]
        assert buy_upgrade(run, 0)
        assert run.gold == 500 - UPGRADE_PRICE[Rarity.RARE]
        assert run.deck[0].is_upgraded and run.deck[0].total_damage() == 9

    def test_exact_gold_is_enough(self):
        run = _run(gold=UPGRADE_PRICE[Rarity.COMMON])
        run.deck = [_card()]
        assert buy_upgrade(run, 0) and run.gold == 0

    def test_not_enough_gold(self):
        run = _run(gold=UPGRADE_PRICE[Rarity.COMMON] - 1)
        run.deck = [_card()]
        assert not can_buy_upgrade(run, run.deck[0])
        assert not buy_upgrade(run, 0)
        assert run.gold == UPGRADE_PRICE[Rarity.COMMON] - 1 and not run.deck[0].is_upgraded

    def test_normal_card_only_once(self):
        run = _run(gold=10_000)
        run.deck = [_card()]
        assert buy_upgrade(run, 0)
        gold = run.gold
        assert not buy_upgrade(run, 0)
        assert run.gold == gold

    def test_unlimited_card(self):
        run = _run(gold=10_000)
        run.deck = [_card(max_upgrades=None, upgrade=CardUpgrade(damage=1))]
        for _ in range(5):
            assert buy_upgrade(run, 0)
        assert run.deck[0].upgrade_level == 5
        assert run.gold == 10_000 - 50 * (1 + 2 + 3 + 4 + 5)

    @pytest.mark.parametrize("index", [-1, 1, 99])
    def test_bad_index(self, index):
        run = _run()
        run.deck = [_card()]
        assert not buy_upgrade(run, index)

    def test_only_that_copy_is_upgraded(self):
        run = _run()
        before = run.deck[1].total_damage()
        buy_upgrade(run, 0)
        assert run.deck[0].is_upgraded and not run.deck[1].is_upgraded
        assert run.deck[1].total_damage() == before


class TestMap:
    @pytest.mark.parametrize("floor", range(1, 11))
    def test_exactly_one_warlock_per_floor(self, floor):
        for seed in range(40):
            gm = generate_map(seed, floor)
            warlocks = [n for n in gm.nodes.values() if n.room_type is RoomType.WARLOCK]
            assert len(warlocks) == 1
            assert 0 < warlocks[0].row < gm.rows - 1

    def test_other_special_rooms_still_there(self):
        gm = generate_map(5, 1)
        types = {n.room_type for n in gm.nodes.values()}
        assert {RoomType.TREASURE, RoomType.SHOP, RoomType.EVENT, RoomType.BOSS, RoomType.WARLOCK} <= types
