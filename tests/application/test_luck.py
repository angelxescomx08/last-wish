"""Luck in general: the Trébol de Siete Hojas (and any luck) improves packs, rewards,
relics and the gachapón, and the screens show it.

Covers ``application/luck`` (report with and without relic luck, sources, golden
chances, Rara-or-better, gachapón odds, monotonic in luck, huge luck capped), the
statistical effect of the Trébol on pack cards, reward cards, shop packs and gachapón
pulls over many seeds, and the luck badge on the shop, pack opening, reward and
gachapón screens.
"""
from __future__ import annotations

from unittest.mock import Mock

import pygame
import pytest

from src.application.card_rewards import pick_pack_cards, pick_reward_cards
from src.application.gacha import gacha_odds, pull
from src.application.hero_stats import hero_sheet
from src.application.luck import at_least, golden_chance, luck_report
from src.application.run_manager import create_run, pick_shop_stock, run_luck
from src.domain.card_pool import PackTheme
from src.domain.character import ALL_CHARACTERS
from src.domain.gacha import PullKind
from src.domain.rarity import Rarity
from src.domain.relic import Relic, RelicTag
from src.domain.tuning import TUNING
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.combat_reward_scene import CombatRewardScene
from src.presentation.scenes.gacha_scene import GachaScene
from src.presentation.scenes.pack_opening_scene import PackOpeningScene
from src.presentation.scenes.shop_scene import ShopScene
from src.presentation.ui.luck_badge import draw_luck_badge, luck_line

FONTS = FontRegistry()


def _clover() -> Relic:
    return Relic("t", "Trébol de Siete Hojas", "", tag=RelicTag.SEVEN_LEAF_CLOVER)


def _run(seed: int = 3, clover: bool = False, hero: int = 0):
    run = create_run(ALL_CHARACTERS[hero], seed)
    if clover:
        run.relics.append(_clover())
    return run


def _tier_sum(cards) -> int:
    return sum((c.rarity or Rarity.COMMON).value for c in cards)


class TestReport:
    def test_no_bonus_without_relics(self):
        r = luck_report(_run())
        assert r.bonus == 0 and r.sources == () and r.tiers == r.base_tiers

    def test_clover_adds_100(self):
        r = luck_report(_run(clover=True))
        assert r.bonus == 100 and r.sources[0].label == "Trébol de Siete Hojas"

    def test_same_luck_as_drops(self):
        run = _run(clover=True)
        assert luck_report(run).luck == run_luck(run)

    def test_clover_raises_everything(self):
        r = luck_report(_run(clover=True))
        assert r.rare_or_better() > r.rare_or_better(base=True)
        assert all(r.golden[k] > r.base_golden[k] for k in r.golden)
        assert r.gacha(PullKind.NORMAL)[Rarity.LEGENDARY] > r.gacha(PullKind.NORMAL, base=True)[Rarity.LEGENDARY]

    def test_monotonic(self):
        values = [at_least(luck_report(_run()).tiers, Rarity.RARE)]
        for luck in (10, 50, 100, 1000):
            TUNING.extra_luck = luck
            values.append(luck_report(_run()).rare_or_better())
        assert values == sorted(values)

    def test_huge_luck_capped(self):
        TUNING.extra_luck = 10 ** 9
        r = luck_report(_run())
        assert r.golden["card"] == 1.0 and 0 < r.rare_or_better() <= 1.0

    def test_golden_zero_luck_is_base_chance(self):
        assert 0 < golden_chance("card", 0) < golden_chance("card", 50) <= 1.0

    def test_summary(self):
        assert "Suerte 102" in luck_report(_run(clover=True)).summary()

    def test_hero_sheet_says_where(self):
        assert "sobres" in hero_sheet(_run(clover=True)).stat("luck").effect


class TestTheCloverWorks:
    SEEDS = range(60)

    def test_pack_cards_rarer(self):
        plain = sum(_tier_sum(pick_pack_cards(_run(s), PackTheme.ACERO)) for s in self.SEEDS)
        lucky = sum(_tier_sum(pick_pack_cards(_run(s, True), PackTheme.ACERO)) for s in self.SEEDS)
        assert lucky > plain * 1.15

    def test_pack_cards_golden_more_often(self):
        def golden(clover):
            return sum(c.chroma is not None for s in self.SEEDS
                       for c in pick_pack_cards(_run(s, clover), PackTheme.ESCUDO))
        assert golden(True) > golden(False) * 3

    def test_reward_cards_rarer(self):
        plain = sum(_tier_sum(pick_reward_cards(_run(s), "r1")) for s in self.SEEDS)
        lucky = sum(_tier_sum(pick_reward_cards(_run(s, True), "r1")) for s in self.SEEDS)
        assert lucky > plain

    def test_shop_packs_golden_more_often(self):
        def golden(clover):
            return sum(p.chroma is not None for s in self.SEEDS for p in pick_shop_stock(_run(s, clover))[0])
        assert golden(True) > golden(False)

    def test_gacha_odds(self):
        assert gacha_odds(_run(clover=True), PullKind.NORMAL)[Rarity.LEGENDARY] > \
            gacha_odds(_run(), PullKind.NORMAL)[Rarity.LEGENDARY] * 2

    def test_gacha_pulls_rarer(self):
        def tiers(clover):
            total = 0
            for s in self.SEEDS:
                run = _run(s, clover)
                run.gold = 10 ** 6
                total += pull(run, PullKind.NORMAL).relic.rarity.value
            return total
        assert tiers(True) > tiers(False)


class TestBadge:
    def test_line_marks_bonus(self):
        assert "▲" in luck_line(luck_report(_run(clover=True)))[0]
        assert "▲" not in luck_line(luck_report(_run()))[0]

    def test_draw_anchor(self):
        rect = draw_luck_badge(pygame.Surface((1280, 720)), "bottomleft", (16, 704),
                               luck_report(_run(clover=True)), FONTS)
        assert rect.bottomleft == (16, 704)

    def test_screens_draw_with_luck(self):
        run = _run(clover=True)
        run.gold = 900
        surf = pygame.Surface((1280, 720))
        ShopScene(run, FONTS, sound=Mock()).draw(surf)
        GachaScene(run, FONTS, sound=Mock()).draw(surf)
        CombatRewardScene(run, 10, pick_reward_cards(run, "r1"), FONTS, sound=Mock()).draw(surf)
        pack = PackOpeningScene(pick_pack_cards(run, PackTheme.ACERO), "Sobre", FONTS, sound=Mock(),
                                luck=luck_report(run))
        pack.skip_animation()
        pack.draw(surf)

    def test_manager_passes_luck_to_packs(self):
        import main
        src = open(main.__file__, encoding="utf-8").read()
        assert src.count("luck=luck_report(run)") >= 2


class TestLuckyCards:
    def test_chances(self):
        from src.domain.rarity import lucky_card_chances
        assert [lucky_card_chances(x) for x in (0, -5, 50, 100, 200, 300, 10 ** 9)] == \
            [(0.0, 0.0), (0.0, 0.0), (0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (1.0, 1.0), (1.0, 1.0)]

    def test_count_range(self):
        import random
        from src.domain.rarity import lucky_card_count
        rng = random.Random(1)
        assert {lucky_card_count(250, rng) for _ in range(500)} == {1, 2}
        assert {lucky_card_count(0, rng) for _ in range(100)} == {0}

    def test_clover_guarantees_one_in_packs_and_rewards(self):
        for s in range(30):
            run = _run(s, True)
            assert sum(c.lucky_drop for c in pick_pack_cards(run, PackTheme.MAGIA)) >= 1
            assert sum(c.lucky_drop for c in pick_reward_cards(run, f"r{s}")) >= 1

    def test_lucky_cards_are_rare_or_better_and_new(self):
        for s in range(30):
            cards = pick_pack_cards(_run(s, True), PackTheme.ACERO)
            lucky = [c for c in cards if c.lucky_drop]
            assert all(c.rarity.value >= Rarity.RARE.value for c in lucky)
            assert len({c.id for c in cards}) == len(cards)

    def test_lucky_cards_allowed_classes(self):
        from src.application.card_rewards import allowed_card_classes
        run = _run(4, True, hero=2)
        assert all(c.card_class in allowed_card_classes(run) for c in pick_pack_cards(run, PackTheme.EPICO))

    def test_deterministic(self):
        a = [c.id for c in pick_pack_cards(_run(7, True), PackTheme.ESCUDO)]
        b = [c.id for c in pick_pack_cards(_run(7, True), PackTheme.ESCUDO)]
        assert a == b

    def test_base_heroes_rarely(self):
        total = sum(c.lucky_drop for s in range(200) for c in pick_reward_cards(_run(s), "r1"))
        assert 0 <= total < 40

    def test_report_extra_card(self):
        assert luck_report(_run(clover=True)).extra_card == 1.0
        assert "carta extra 100%" in luck_line(luck_report(_run(clover=True)))[1]

    def test_screens_mark_lucky_cards(self):
        run = _run(3, True)
        surf = pygame.Surface((1280, 720))
        cards = pick_reward_cards(run, "r1")
        scene = CombatRewardScene(run, 10, cards, FONTS, sound=Mock())
        scene.update(0.3)
        scene.draw(surf)
        pack = PackOpeningScene(pick_pack_cards(run, PackTheme.ACERO), "Sobre", FONTS, sound=Mock(),
                                luck=luck_report(run))
        pack.skip_animation()
        pack.draw(surf)
        assert any(c.lucky_drop for c in cards)

    def test_lucky_marks_draw(self):
        from src.presentation.fx import card_fx
        surf = pygame.Surface((400, 400))
        rect = pygame.Rect(100, 100, 150, 210)
        card_fx.draw_lucky_back(surf, rect, 0.5)
        badge = card_fx.draw_lucky_front(surf, rect, 0.5, FONTS)
        assert badge is not None and badge.bottom <= rect.top + 2
