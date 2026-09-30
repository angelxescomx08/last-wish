"""Card upgrades: default rules, custom upgrades, caps, names and previews. No pygame."""
from __future__ import annotations

import pytest

from src.domain.card import Card, CardEffect, CardType, CardUpgrade
from src.domain.card_pool import card_factories_for_classes, starter_deck
from src.domain.card import CardClass
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma
from src.domain.card_upgrade import (
    apply_upgrade,
    can_upgrade,
    default_upgrade,
    describe_upgrade,
    upgraded_name,
    upgraded_preview,
)
from src.domain.numbers import BigValue


def _card(dmg=0, blk=0, cost=1, draw=0, **kw):
    return Card(id="c", name="Golpe", card_type=CardType.ATTACK, cost=cost,
                base_effect=CardEffect(name="Golpe", damage=BigValue(dmg), block=BigValue(blk), draw=draw), **kw)


class TestDefaultUpgrade:
    def test_damage_plus_three(self):
        assert default_upgrade(_card(dmg=6)) == CardUpgrade(damage=3)

    def test_block_plus_three(self):
        assert default_upgrade(_card(blk=5)) == CardUpgrade(block=3)

    def test_both(self):
        assert default_upgrade(_card(dmg=6, blk=6)) == CardUpgrade(damage=3, block=3)

    def test_big_values_scale(self):
        assert default_upgrade(_card(dmg=30)) == CardUpgrade(damage=10)

    def test_no_stats_costs_one_less(self):
        assert default_upgrade(_card(cost=2, draw=2)) == CardUpgrade(cost=-1)

    def test_free_card_draws_one_more(self):
        assert default_upgrade(_card(cost=0)) == CardUpgrade(draw=1)

    def test_huge_numbers(self):
        up = default_upgrade(_card(dmg=3 * 10**100))
        assert up.damage == 10**100


class TestApply:
    def test_one_upgrade_by_default(self):
        c = _card(dmg=6)
        assert can_upgrade(c) and not c.is_upgraded
        assert apply_upgrade(c)
        assert c.total_damage() == 9 and c.name == "Golpe+" and c.is_upgraded
        assert not can_upgrade(c)
        assert not apply_upgrade(c)
        assert c.total_damage() == 9 and c.upgrade_level == 1

    def test_cost_never_negative(self):
        c = _card(cost=0, dmg=0, upgrade=CardUpgrade(cost=-3))
        apply_upgrade(c)
        assert c.cost == 0

    def test_cost_upgrade(self):
        c = _card(cost=2, draw=1)
        apply_upgrade(c)
        assert c.cost == 1 and c.total_draw() == 1

    def test_custom_upgrade(self):
        c = _card(dmg=4, upgrade=CardUpgrade(cost=-1, damage=1, block=2, draw=1, mana_gain=1))
        apply_upgrade(c)
        assert (c.cost, c.total_damage(), c.total_block(), c.total_draw(), c.total_mana_gain()) == (0, 5, 2, 1, 1)

    def test_custom_on_play_and_text(self):
        calls = []
        c = _card(upgrade=CardUpgrade(on_play=lambda st: calls.append(st), text="aplica 5 de Veneno"))
        apply_upgrade(c)
        c.base_effect.on_play("state")
        assert calls == ["state"] and c.base_effect.text == "aplica 5 de Veneno"

    def test_unlimited_upgrades(self):
        c = _card(dmg=6, max_upgrades=None, upgrade=CardUpgrade(damage=2))
        for _ in range(50):
            assert apply_upgrade(c)
        assert c.total_damage() == 6 + 100
        assert c.upgrade_level == 50 and c.name == "Golpe+50"
        assert can_upgrade(c)

    def test_custom_cap(self):
        c = _card(dmg=6, max_upgrades=3)
        assert [apply_upgrade(c) for _ in range(5)] == [True, True, True, False, False]
        assert c.name == "Golpe+3"

    def test_zero_cap(self):
        c = _card(dmg=6, max_upgrades=0)
        assert not can_upgrade(c) and not apply_upgrade(c)

    def test_golden_keeps_chroma_and_casts(self):
        c = _card(dmg=6, chroma=Chroma.GOLDEN)
        apply_upgrade(c)
        assert c.chroma is Chroma.GOLDEN and c.casts() == 2 and c.total_damage() == 9

    def test_keeps_keyword_layers(self):
        c = _card(dmg=6)
        c.base_effect.combo = CardEffect(name="Combo", damage=BigValue(4))
        apply_upgrade(c)
        assert c.total_damage(combo=True) == 13


class TestPreviewAndText:
    def test_preview_does_not_touch_original(self):
        c = _card(dmg=6)
        p = upgraded_preview(c)
        assert p.total_damage() == 9 and p.name == "Golpe+"
        assert c.total_damage() == 6 and c.name == "Golpe" and c.upgrade_level == 0

    def test_names(self):
        assert upgraded_name("Golpe", 0) == "Golpe"
        assert upgraded_name("Golpe", 1) == "Golpe+"
        assert upgraded_name("Golpe", 2) == "Golpe+2"

    def test_base_name_set(self):
        assert _card().base_name == "Golpe"

    @pytest.mark.parametrize("card, text", [
        (_card(dmg=6), "+3 de daño"),
        (_card(blk=6), "+3 de escudo"),
        (_card(cost=2), "-1 de maná"),
        (_card(cost=0), "roba 1 más"),
    ])
    def test_describe(self, card, text):
        assert describe_upgrade(card) == text

    def test_custom_description(self):
        assert describe_upgrade(_card(upgrade=CardUpgrade(description="Algo raro"))) == "Algo raro"


class TestEveryCardCanBeUpgraded:
    def test_whole_pool_and_starters(self):
        cards = [f() for f in card_factories_for_classes(frozenset(CardClass))]
        cards += [c for ch in ALL_CHARACTERS for c in starter_deck(ch.id)]
        for c in cards:
            before = (c.cost, c.total_damage(), c.total_block(), c.total_draw())
            assert can_upgrade(c), c.id
            assert apply_upgrade(c), c.id
            after = (c.cost, c.total_damage(), c.total_block(), c.total_draw())
            assert after != before, c.id
            assert c.name.endswith("+")

    def test_starter_copies_are_independent(self):
        deck = starter_deck(ALL_CHARACTERS[0].id)
        apply_upgrade(deck[0])
        assert deck[1].total_damage() < deck[0].total_damage()
