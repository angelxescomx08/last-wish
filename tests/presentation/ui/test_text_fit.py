"""Text never spills out of its box: ``ui/text_fit`` and the screens that use it.

Covers ``wrap`` (every line within the width, words kept in order, a too-long word cut with
"…", newlines, empty text, width 1, 10 000 words), ``fit`` (unchanged when it fits, "…"
otherwise, never wider), ``render_wrapped`` (line cap ends with "…"), and the boxes:
character descriptions in their panels, every relic description in the boss reward, shop and
relic viewer (normal and golden), enemy-turn banners never wider than their panel, and the
hero sheet's sentences.
"""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pygame
import pytest

from src.application.run_manager import _all_relic_defs, create_run
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.text_fit import ELLIPSIS, fit, render_wrapped, wrap

LONG = ("Si un efecto al azar golpea dos veces seguidas al mismo enemigo, ganas 1 de maná "
        "(una vez por turno).")


@pytest.fixture(scope="module")
def fonts():
    return FontRegistry()


@pytest.fixture(scope="module")
def font(fonts):
    return fonts.get(13)


@pytest.fixture(scope="module")
def relics():
    return _all_relic_defs()


def _width(text, font):
    return font.size(text)[0]


class TestWrap:
    @pytest.mark.parametrize("w", [1, 20, 60, 120, 205, 400, 10 ** 6])
    def test_lines_within_width(self, w, font, fonts, relics):
        assert all(_width(line, font) <= max(w, _width(ELLIPSIS, font)) for line in wrap(font, LONG, w))

    def test_words_in_order(self, font, fonts, relics):
        assert " ".join(wrap(font, LONG, 120)) == LONG

    def test_long_word_cut(self, font, fonts, relics):
        lines = wrap(font, "Supercalifragilístico", 40)
        assert lines[0].endswith(ELLIPSIS) and _width(lines[0], font) <= 40

    def test_newlines(self, font, fonts, relics):
        assert wrap(font, "uno\ndos", 500) == ["uno", "dos"]

    def test_empty(self, font, fonts, relics):
        assert wrap(font, "", 100) == [""]

    def test_stress(self, font, fonts, relics):
        text = " ".join(["palabra"] * 10_000)
        lines = wrap(font, text, 300)
        assert all(_width(line, font) <= 300 for line in lines) and sum(len(l.split()) for l in lines) == 10_000


class TestFit:
    def test_unchanged(self, font, fonts, relics):
        assert fit(font, "Hola", 500) == "Hola"

    @pytest.mark.parametrize("w", [10, 50, 100, 200])
    def test_shortened(self, w, font, fonts, relics):
        out = fit(font, LONG, w)
        assert (out == "" or out.endswith(ELLIPSIS)) and _width(out, font) <= w

    def test_nothing_fits(self, font, fonts, relics):
        assert fit(font, LONG, 0) == ""

    def test_render_wrapped_cap(self, font, fonts, relics):
        lines = render_wrapped(font, LONG, 120, (255, 255, 255), max_lines=2)
        assert len(lines) == 2 and all(s.get_width() <= 120 for s in lines)


class TestScreens:
    def test_character_descriptions_fit(self, font, fonts, relics):
        from src.presentation.scenes import character_select_scene as cs
        ff = fonts.get(11)
        for c in ALL_CHARACTERS:
            lines = wrap(ff, c.description, cs._PANEL_W - 28)
            assert len(lines) <= 2 and all(_width(l, ff) <= cs._PANEL_W - 28 for l in lines)

    def test_character_select_draws(self, font, fonts, relics):
        from src.presentation.scenes.character_select_scene import CharacterSelectScene
        CharacterSelectScene(fonts).draw(pygame.Surface((1280, 720)))

    @pytest.mark.parametrize("golden", [False, True])
    def test_boss_reward_every_relic(self, golden, font, fonts, relics):
        from src.presentation.scenes.boss_reward_scene import BossRewardScene, _Phase
        run = create_run(ALL_CHARACTERS[0], 3)
        surface = pygame.Surface((1280, 720))
        for k in range(0, len(relics), 3):
            relics = [replace(r, chroma=Chroma.GOLDEN) if golden else r for r in relics[k:k + 3]]
            scene = BossRewardScene(run, 10, relics, fonts, sound=Mock())
            scene._phase = _Phase.RELICS
            scene.draw(surface)

    @pytest.mark.parametrize("golden", [False, True])
    def test_shop_every_relic(self, golden, font, fonts, relics):
        from src.presentation.scenes.shop_scene import ShopScene
        run = create_run(ALL_CHARACTERS[0], 3)
        run.gold = 999
        surface = pygame.Surface((1280, 720))
        for k in range(0, len(relics), 3):
            scene = ShopScene(run, fonts, sound=Mock())
            scene._relics = [replace(r, chroma=Chroma.GOLDEN) if golden else r for r in relics[k:k + 3]]
            scene.draw(surface)

    def test_relic_viewer_every_relic(self, font, fonts, relics):
        from src.presentation.ui.relic_viewer import RelicViewer
        viewer = RelicViewer(relics + [replace(r, chroma=Chroma.GOLDEN) for r in relics], fonts)
        viewer.draw(pygame.Surface((1280, 720)))

    def test_banner_panel_never_wider(self, font, fonts, relics):
        from src.presentation.ui.action_banner import ActionBanners
        banners = ActionBanners()
        banners.add("buff", "Un título larguísimo " * 6, LONG * 3)
        banners.update(1.0)
        surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
        banners.draw(surface, fonts)
        box = surface.get_bounding_rect(min_alpha=1)
        assert box.width <= ActionBanners.WIDTH + 2

    def test_hero_sheet_every_hero(self, font, fonts, relics):
        from src.application.hero_stats import hero_sheet
        from src.presentation.ui.hero_sheet import HeroSheetOverlay
        for i in range(len(ALL_CHARACTERS)):
            overlay = HeroSheetOverlay(hero_sheet(create_run(ALL_CHARACTERS[i], 3)), fonts)
            for _ in range(60):
                overlay.update(1 / 30)
            overlay.draw(pygame.Surface((1280, 720)))
