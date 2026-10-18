"""Screens the 2026-10-17 relics touch: the deck choice (Tijeras del Sastre, Cartas Marcadas),
the pack reroll (Dado Cargado), free / half price shop offers (Vale de Descuento, Tarjeta de
Socio), the Catalejo pile tooltip and diamond cards.
"""
from __future__ import annotations

import pygame
import pytest

from src.application.card_rewards import pick_pack_cards
from src.application.run_manager import acquire_relic, create_run
from src.domain.card_pool import PackTheme
from src.domain.character import ALL_CHARACTERS
from src.domain.chroma import Chroma
from src.domain.relic import Relic, RelicTag
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.deck_choice_scene import DeckChoiceScene
from src.presentation.scenes.pack_opening_scene import PackOpeningScene
from src.presentation.scenes.shop_scene import ShopScene
from src.presentation.ui.card_widget import draw_card
from src.presentation.ui.tooltip import pile_tooltip

FONTS = FontRegistry()


@pytest.fixture(autouse=True)
def _display():
    pygame.init()
    pygame.display.set_mode((1, 1))


def _run(relics=(), gold=0):
    run = create_run(ALL_CHARACTERS[0], 4)
    run.gold = gold
    for tag in relics:
        acquire_relic(run, Relic("r", "R", "d", tag=tag))
    return run


def _click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


class TestDeckChoice:
    def test_toggle_limit_and_confirm_remove(self):
        run = _run()
        n = len(run.deck)
        scene = DeckChoiceScene(run, "remove", 3, FONTS)
        for i in range(5):
            scene.toggle(i)
        assert scene.selected == [0, 1, 2]
        scene.toggle(1)
        assert scene.selected == [0, 2]
        scene.confirm()
        assert scene.cleared and len(run.deck) == n - 2

    def test_innate(self):
        run = _run()
        scene = DeckChoiceScene(run, "innate", 1, FONTS)
        scene.toggle(3)
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert scene.cleared and run.deck[3].innate

    def test_escape_does_not_skip(self):
        scene = DeckChoiceScene(_run(), "remove", 3, FONTS)
        scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert not scene.cleared

    def test_draw_and_click_a_card(self):
        scene = DeckChoiceScene(_run(), "remove", 3, FONTS)
        surf = pygame.Surface((1280, 720))
        scene.draw(surf)
        rect = next(iter(scene._grid._item_rects.values()))
        _click(scene, rect.center)
        scene.draw(surf)
        assert scene.selected == [0]

    def test_confirm_button(self):
        scene = DeckChoiceScene(_run(), "innate", 1, FONTS)
        scene.draw(pygame.Surface((1280, 720)))
        _click(scene, scene._grid._close_rect.center)
        assert scene.cleared


class TestPackReroll:
    def _scene(self, reroll):
        run = _run()
        cards = pick_pack_cards(run, PackTheme.ACERO)
        scene = PackOpeningScene(cards, "Sobre", FONTS, reroll=reroll)
        scene.skip_animation()
        for _ in range(200):
            scene.update(0.05)
        return scene, run

    def test_reroll_once(self):
        run = _run()
        new = pick_pack_cards(run, PackTheme.ACERO, reroll=1)
        scene, _ = self._scene(lambda: new)
        assert scene.phase == "pick" and scene.can_reroll
        assert scene.reroll() and scene._cards is new
        assert not scene.can_reroll and not scene.reroll()
        scene.draw(pygame.Surface((1280, 720)))

    def test_no_reroll_without_relic(self):
        scene, _ = self._scene(None)
        assert not scene.can_reroll

    def test_no_reroll_after_choosing(self):
        scene, _ = self._scene(lambda: [])
        scene.choose(0)
        assert not scene.can_reroll

    def test_picks_override(self):
        run = _run()
        cards = pick_pack_cards(run, PackTheme.ACERO)
        scene = PackOpeningScene(cards, "Sobre", FONTS, chroma=Chroma.GOLDEN, picks=3)
        assert scene._picks == 3


class TestShop:
    def test_voucher_shows_free_and_is_spent(self):
        run = _run([RelicTag.VOUCHER], gold=0)
        scene = ShopScene(run, FONTS)
        scene.draw(pygame.Surface((1280, 720)))
        _click(scene, scene._relic_rects[0].center)
        assert len(run.relics) == 2 and run.gold == 0
        assert not run.relics[0].is_active

    def test_member_card_half_first(self):
        run = _run([RelicTag.MEMBER_CARD], gold=1000)
        scene = ShopScene(run, FONTS)
        scene.draw(pygame.Surface((1280, 720)))
        _click(scene, scene._relic_rects[0].center)
        assert run.gold == 1000 - 75


class TestMisc:
    def test_spyglass_tooltip(self):
        tip = pile_tooltip("ROBO", 5, is_draw=True, next_cards=["A", "B", "C"])
        assert any("1. A" in line for line in tip.lines)

    def test_diamond_card_draws(self):
        run = _run()
        card = run.deck[0]
        card.chroma = Chroma.DIAMOND
        draw_card(pygame.Surface((300, 300)), card, 10, 10, FONTS)
