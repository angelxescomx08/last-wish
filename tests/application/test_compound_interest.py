"""Interés Compuesto: neutral Épica relic — every gold gain pays 10 % of your total gold.

Covers the rate query (normal / golden / inactive / stacked), ``gain_gold`` (10 % of
the total *after* the gain, rounded down, no interest on 0 or negative gains, the
interest does not compound on itself, bookkeeping in ``Run``), combat victories and
events going through it, the relic in the catalogue, and the visible feedback
(gold counter note, reward screens).
"""
from __future__ import annotations

from unittest.mock import Mock

import pygame

from src.application import relic_effects
from src.application.run_manager import _all_relic_defs, apply_combat_victory, create_run, gain_gold
from src.domain.card import CardClass
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma
from src.domain.rarity import Rarity
from src.domain.relic import Relic, RelicTag
from src.infrastructure.fonts import FontRegistry

FONTS = FontRegistry()


def _interest(chroma=None, active=True) -> Relic:
    return Relic("r_interest", "Interés Compuesto", "", tag=RelicTag.COMPOUND_INTEREST,
                 chroma=chroma, is_active=active)


def _run(*relics: Relic, gold: int = 0):
    run = create_run(ALL_CHARACTERS[0], 3)
    run.relics.extend(relics)
    run.gold = gold
    return run


class TestRate:
    def test_ten_percent(self):
        assert relic_effects.compound_interest_percent([_interest()]) == 10

    def test_golden_twenty(self):
        assert relic_effects.compound_interest_percent([_interest(Chroma.GOLDEN)]) == 20

    def test_none_or_inactive(self):
        assert relic_effects.compound_interest_percent([]) == 0
        assert relic_effects.compound_interest_percent([_interest(active=False)]) == 0

    def test_two_stack(self):
        assert relic_effects.compound_interest_percent([_interest(), _interest()]) == 20


class TestGainGold:
    def test_without_relic_plain_gain(self):
        run = _run(gold=100)
        assert gain_gold(run, 50) == 0 and run.gold == 150 and run.last_interest == 0

    def test_ten_percent_of_total_after_gain(self):
        run = _run(_interest(), gold=100)
        assert gain_gold(run, 50) == 15          # 10 % of 150
        assert run.gold == 165

    def test_rounds_down(self):
        run = _run(_interest(), gold=0)
        assert gain_gold(run, 9) == 0 and run.gold == 9
        assert gain_gold(run, 10) == 1 and run.gold == 20

    def test_golden(self):
        run = _run(_interest(Chroma.GOLDEN), gold=50)
        assert gain_gold(run, 50) == 20 and run.gold == 120

    def test_no_gain_no_interest(self):
        run = _run(_interest(), gold=500)
        assert gain_gold(run, 0) == 0 and gain_gold(run, -30) == 0
        assert run.gold == 500

    def test_bookkeeping(self):
        run = _run(_interest(), gold=100)
        gain_gold(run, 100)                        # +20
        gain_gold(run, 30)                         # 250 → +25
        assert run.interest_earned == 45 and run.last_interest == 25
        gain_gold(run, 0)
        assert run.last_interest == 0 and run.interest_earned == 45

    def test_snowballs_over_gains(self):
        run = _run(_interest(), gold=0)
        for _ in range(10):
            gain_gold(run, 100)
        assert run.gold > 1000 + 500                # interest on interest across gains

    def test_huge_numbers(self):
        run = _run(_interest(), gold=10 ** 100)
        assert gain_gold(run, 1) == (10 ** 100 + 1) // 10


class TestWhereItApplies:
    def test_combat_victory(self):
        run = _run(_interest(), gold=1000)
        gold = apply_combat_victory(run, run.player_max_hp, [], bonus_gold=40)
        assert gold >= 40 and run.last_interest == (1000 + gold) // 10
        assert run.gold == 1000 + gold + run.last_interest

    def test_event_through_manager(self):
        import main
        src = open(main.__file__, encoding="utf-8").read()
        assert "gain_gold(run, scene._gold)" in src

    def test_spending_never_pays(self):
        run = _run(_interest(), gold=300)
        run.gold -= 100                            # shop purchases subtract directly
        assert run.last_interest == 0 and run.interest_earned == 0


class TestCatalogue:
    def test_defined_neutral_epic(self):
        relic = next(r for r in _all_relic_defs() if r.tag == RelicTag.COMPOUND_INTEREST)
        assert relic.name == "Interés Compuesto"
        assert relic.relic_class == CardClass.NEUTRAL
        assert relic.rarity is None or relic.rarity == Rarity.EPIC
        from src.domain.relic import RELIC_RARITY
        assert RELIC_RARITY[RelicTag.COMPOUND_INTEREST] == Rarity.EPIC

    def test_has_sprite(self):
        from src.infrastructure.sprite_loader import RELIC_SPRITE_PATHS
        assert "Interés Compuesto" in RELIC_SPRITE_PATHS


class TestFeedback:
    def test_gold_hud_note_appears_after_a_beat(self):
        from src.presentation.ui.gold_hud import GoldHud
        hud = GoldHud(FONTS)
        hud.sync(100)
        hud.note("+15 interés")
        assert ("+15 interés", (200, 160, 255)) in hud.deltas
        hud.update(0.5, 100)
        assert ("+15 interés", (200, 160, 255)) in hud.deltas

    def test_manager_notes_interest(self):
        import main
        from src.infrastructure.preferences import UserPreferences
        from src.presentation.scenes.map_scene import MapScene
        m = main.SceneManager(main.MainMenuScene(FONTS), FONTS, UserPreferences())
        m._run = _run(_interest(), gold=100)
        m.push(MapScene(m._run, FONTS))
        m.update(0.016)
        gain_gold(m._run, 100)
        m.update(0.016)
        texts = [d[0] for d in m.gold_hud.deltas]
        assert "+20 interés" in texts and "+120" in texts

    def test_reward_screens_show_interest(self):
        from src.presentation.scenes.boss_reward_scene import BossRewardScene
        from src.presentation.scenes.combat_reward_scene import CombatRewardScene
        run = _run(_interest(), gold=100)
        gain_gold(run, 50)
        surf = pygame.Surface((1280, 720))
        scene = CombatRewardScene(run, 50, [], FONTS, sound=Mock())
        assert scene._interest == 15
        scene.draw(surf)
        boss = BossRewardScene(run, 50, [], FONTS, sound=Mock())
        assert boss._interest == 15
        boss.draw(surf)
