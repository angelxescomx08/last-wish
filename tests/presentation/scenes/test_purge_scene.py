"""Altar de Purga scene: pick a card, confirm, watch it burn, the room closes. Card burn effect.

Covers clicking a card → confirmation panel → "Eliminar" removes that card and pays; cancel
by button / Escape / click outside; a blocked removal (no gold, minimum deck) says why and
opens nothing; only one card per altar (the room closes after the burn, clicks hurry it);
"Salir" leaves without removing; the pause overlay rule; every screen draws; the
SceneManager opens the altar from a PURGE map node and pops it when it clears; and
``fx/card_burn`` (bottom first, edge embers, gone at the end, edge points capped, 10 000
random progress values).
"""
import random

import pygame
import pytest

from src.application.purge import MIN_DECK, purge_price
from src.application.run_manager import create_run
from src.domain.character import ALL_CHARACTERS
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx.card_burn import BURN_SECONDS, CELL, EDGE, CardBurn
from src.presentation.scenes.purge_scene import PurgeScene

FONTS = FontRegistry()


class Sound:
    def __getattr__(self, name):
        return lambda *a: None


def _scene(gold=1000):
    run = create_run(ALL_CHARACTERS[0], 1)
    run.gold = gold
    scene = PurgeScene(run, FONTS, sound=Sound())
    scene.draw(pygame.Surface((1280, 720)))
    return scene, run


def _click(scene, pos):
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


def _key(scene, key):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))


def _steps(scene, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt) + 1):
        scene.update(dt)


class TestFlow:
    def test_click_confirm_removes_that_card(self):
        scene, run = _scene()
        target, n = run.deck[2], len(run.deck)
        _click(scene, scene._grid._item_rects[2].center)
        assert scene.selected_index == 2 and scene._overlay == 2
        scene.draw(pygame.Surface((1280, 720)))
        _click(scene, scene._confirm_rect.center)
        assert all(c is not target for c in run.deck) and len(run.deck) == n - 1 and run.gold == 1000 - 75
        assert scene.removed is target and scene.burning

    def test_enter_confirms(self):
        scene, run = _scene()
        scene.select(0)
        _key(scene, pygame.K_RETURN)
        assert run.cards_removed == 1

    def test_cancel_button(self):
        scene, run = _scene()
        scene.select(0)
        scene.draw(pygame.Surface((1280, 720)))
        _click(scene, scene._cancel_rect.center)
        assert scene.selected_index is None and run.cards_removed == 0

    def test_escape_and_outside_click_cancel(self):
        scene, run = _scene()
        scene.select(0)
        _key(scene, pygame.K_ESCAPE)
        assert scene.selected_index is None
        scene.select(0)
        _click(scene, (5, 5))
        assert scene.selected_index is None and run.cards_removed == 0

    def test_closes_after_the_burn(self):
        scene, _ = _scene()
        scene.select(0)
        scene.confirm()
        _steps(scene, BURN_SECONDS * 0.5)
        assert not scene.cleared and scene._overlay == -1
        _steps(scene, BURN_SECONDS + 1.0)
        assert scene.cleared and not scene.burning

    def test_click_hurries_the_burn(self):
        scene, _ = _scene()
        scene.select(0)
        scene.confirm()
        _click(scene, (640, 360))
        scene.update(1 / 60)
        assert scene.cleared

    def test_only_one_card(self):
        scene, run = _scene()
        scene.select(0)
        scene.confirm()
        scene.select(0)                     # ignored while burning
        assert scene.selected_index is None and run.cards_removed == 1

    def test_leave_without_removing(self):
        scene, run = _scene()
        _click(scene, scene._grid._close_rect.center)
        assert scene.cleared and run.cards_removed == 0

    def test_no_gold_says_why(self):
        scene, run = _scene(gold=10)
        scene.select(0)
        assert scene.selected_index is None and "oro" in scene._message
        assert len(run.deck) > MIN_DECK

    def test_minimum_deck_says_why(self):
        scene, run = _scene()
        run.deck = run.deck[:MIN_DECK]
        scene.select(0)
        assert scene.selected_index is None and "última carta" in scene._message

    def test_price_rises_on_next_altar(self):
        scene, run = _scene()
        scene.select(0)
        scene.confirm()
        assert purge_price(run) == 100

    @pytest.mark.parametrize("phase", ["grid", "confirm", "burn", "poor"])
    def test_draws(self, phase):
        scene, run = _scene(gold=10 if phase == "poor" else 1000)
        if phase in ("confirm", "burn"):
            scene.select(0)
        if phase == "burn":
            scene.confirm()
            _steps(scene, 0.8)
        scene.draw(pygame.Surface((1280, 720)))

    def test_tooltip(self):
        scene, run = _scene()
        tip = scene._grid._tooltip(run.deck[0])
        assert "Eliminar por 75 de oro" in tip.lines[0]


class TestManager:
    def test_room_opens_and_closes(self):
        import main
        from src.domain.map_node import RoomType
        from src.infrastructure.preferences import UserPreferences
        from src.presentation.scenes.map_scene import MapScene
        m = main.SceneManager(main.MainMenuScene(FONTS), FONTS, UserPreferences())
        run = create_run(ALL_CHARACTERS[0], 3)
        run.gold = 500
        m._run = run
        node = next(n for n in run.current_map.nodes.values() if n.room_type is RoomType.PURGE)
        scene = MapScene(run, FONTS)
        m.push(scene)
        scene.selected_node = node
        m._t_map(scene)
        assert isinstance(m._stack[-1], PurgeScene)
        m._stack[-1].cleared = True
        m.update(1 / 60)
        assert isinstance(m._stack[-1], MapScene)


class TestBurn:
    def _burn(self):
        return CardBurn(pygame.Surface((150, 210), pygame.SRCALPHA), seed=3)

    def test_whole_at_zero(self):
        b = self._burn()
        assert not any(b.burnt(r, c, 0.0) for r in range(b.rows) for c in range(b.cols))

    def test_bottom_first(self):
        b = self._burn()
        p = 0.4
        bottom = sum(b.burnt(b.rows - 1, c, p) for c in range(b.cols))
        top = sum(b.burnt(0, c, p) for c in range(b.cols))
        assert bottom > top

    def test_gone(self):
        b = self._burn()
        assert b.gone(1.0 + EDGE) and not b.gone(0.5)
        frame = b.frame(1.0 + EDGE)
        assert frame.get_bounding_rect(min_alpha=1).width == 0

    def test_edge_glows(self):
        face = pygame.Surface((150, 210), pygame.SRCALPHA)
        face.fill((20, 20, 60, 255))
        b = CardBurn(face, seed=1)
        frame = b.frame(0.5)
        colors = {tuple(frame.get_at((c * CELL + 1, r * CELL + 1)))[:3]
                  for r in range(b.rows) for c in range(b.cols)}
        assert any(col[0] > 200 for col in colors)

    def test_edge_points_capped(self):
        b = self._burn()
        assert 0 < len(b.edge_points(0.5, limit=5)) <= 5

    def test_tiny_face(self):
        b = CardBurn(pygame.Surface((1, 1), pygame.SRCALPHA))
        assert b.rows == b.cols == 1 and b.frame(0.5).get_size() == (1, 1)

    def test_stress(self):
        b = self._burn()
        rng = random.Random(5)
        for _ in range(10_000):
            p = rng.uniform(-1, 3)
            b.burnt(rng.randrange(b.rows), rng.randrange(b.cols), p)
        for p in (-5, 0, 0.3, 0.9, 1.2, 10 ** 9):
            b.frame(p)
            b.edge_points(p)
