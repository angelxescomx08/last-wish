"""Tests for presentation/ui/hud_widget.py.

All hud drawing functions render onto a pygame.Surface.
The session fixture in conftest.py initialises pygame.
"""
from __future__ import annotations

import pygame
import pytest

from src.domain.mana import Mana
from src.domain.relic import Relic, RelicTag
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.hud_widget import (
    draw_end_turn_button,
    draw_mana,
    draw_pile_widget,
    draw_relics,
    draw_turn_counter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _surface() -> pygame.Surface:
    return pygame.Surface((1280, 720))


def _fonts() -> FontRegistry:
    return FontRegistry()


def _relics() -> list[Relic]:
    return [
        Relic("r1", "Amuleto", "Desc", tag=RelicTag.COMBAT_AMULET),
        Relic("r2", "Tótem",   "Desc", tag=RelicTag.BROKEN_TOTEM),
        Relic("r3", "Orbe",    "Desc", tag=RelicTag.FIRE_ORB),
        Relic("r4", "Escudo",  "Desc", tag=RelicTag.SPECTRAL_SHIELD, is_active=False),
    ]


# ---------------------------------------------------------------------------
# draw_turn_counter()
# ---------------------------------------------------------------------------

class TestDrawTurnCounter:
    def test_turn_one(self):
        draw_turn_counter(_surface(), 1, 640, 34, _fonts())

    def test_turn_large(self):
        draw_turn_counter(_surface(), 999, 640, 34, _fonts())

    def test_turn_zero(self):
        draw_turn_counter(_surface(), 0, 640, 34, _fonts())


# ---------------------------------------------------------------------------
# draw_mana()
# ---------------------------------------------------------------------------

class TestDrawMana:
    def test_full_mana(self):
        draw_mana(_surface(), Mana(current=3, maximum=3), 68, 595, _fonts())

    def test_empty_mana(self):
        draw_mana(_surface(), Mana(current=0, maximum=3), 68, 595, _fonts())

    def test_partial_mana(self):
        draw_mana(_surface(), Mana(current=1, maximum=4), 68, 595, _fonts())


# ---------------------------------------------------------------------------
# draw_pile_widget() — returns a Rect
# ---------------------------------------------------------------------------

class TestDrawPileWidget:
    def test_returns_rect(self):
        rect = draw_pile_widget(_surface(), "ROBO", 10, 100, 100, _fonts())
        assert isinstance(rect, pygame.Rect)

    def test_zero_count(self):
        draw_pile_widget(_surface(), "ROBO", 0, 100, 100, _fonts())

    def test_large_count(self):
        draw_pile_widget(_surface(), "DESCARTE", 999, 100, 100, _fonts())


# ---------------------------------------------------------------------------
# draw_relics() — returns list of Rects
# ---------------------------------------------------------------------------

class TestDrawRelics:
    def test_returns_list(self):
        result = draw_relics(_surface(), _relics(), 10, 10, _fonts())
        assert isinstance(result, list)

    def test_one_rect_per_relic(self):
        relics = _relics()
        rects = draw_relics(_surface(), relics, 10, 10, _fonts())
        assert len(rects) == len(relics)

    def test_empty_relics(self):
        rects = draw_relics(_surface(), [], 10, 10, _fonts())
        assert rects == []

    def test_single_relic(self):
        r = [Relic("r", "R", "D", tag=RelicTag.FIRE_ORB)]
        rects = draw_relics(_surface(), r, 10, 10, _fonts())
        assert len(rects) == 1

    def test_inactive_relic_does_not_crash(self):
        r = [Relic("r", "R", "D", tag=RelicTag.SPECTRAL_SHIELD, is_active=False)]
        draw_relics(_surface(), r, 10, 10, _fonts())

    def test_hovered_relic(self):
        draw_relics(_surface(), _relics(), 10, 10, _fonts(), hovered_index=0)


# ---------------------------------------------------------------------------
# draw_end_turn_button() — returns a Rect
# ---------------------------------------------------------------------------

class TestDrawEndTurnButton:
    def test_returns_rect(self):
        rect = draw_end_turn_button(_surface(), 1085, 15, 183, 38, _fonts())
        assert isinstance(rect, pygame.Rect)

    def test_hovered(self):
        rect = draw_end_turn_button(_surface(), 1085, 15, 183, 38, _fonts(), hovered=True)
        assert isinstance(rect, pygame.Rect)

    def test_rect_position(self):
        rect = draw_end_turn_button(_surface(), 100, 50, 183, 38, _fonts())
        assert rect.x == 100
        assert rect.y == 50
