"""Tests for presentation/ui/pile_viewer.py.

PileViewer renders a modal overlay onto a pygame.Surface.
The session fixture in conftest.py initialises pygame.
"""
from __future__ import annotations

import pygame
import pytest

from src.domain.card import Card, CardEffect, CardType
from src.domain.numbers import BigValue
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.pile_viewer import PileViewer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _surface() -> pygame.Surface:
    return pygame.Surface((1280, 720))


def _fonts() -> FontRegistry:
    return FontRegistry()


def _card(name: str = "Golpe", damage: int = 6) -> Card:
    return Card(
        id=name, name=name, card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect(name, damage=BigValue(damage)),
    )


def _cards(n: int) -> list[Card]:
    return [_card(f"Carta {i}") for i in range(n)]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestPileViewerConstruction:
    def test_creates_with_empty_pile(self):
        viewer = PileViewer("Pila de Robo", [], _fonts())
        assert viewer is not None

    def test_creates_with_cards(self):
        viewer = PileViewer("Pila de Robo", _cards(5), _fonts())
        assert viewer is not None

    def test_not_dismissed_initially(self):
        viewer = PileViewer("Pila de Robo", _cards(3), _fonts())
        assert not viewer.dismissed

    def test_stores_title(self):
        viewer = PileViewer("Pila de Descarte", _cards(1), _fonts())
        assert "Descarte" in viewer._title

    def test_large_pile(self):
        PileViewer("Pila", _cards(30), _fonts())


# ---------------------------------------------------------------------------
# draw() — smoke tests
# ---------------------------------------------------------------------------

class TestPileViewerDraw:
    def test_draw_empty(self):
        viewer = PileViewer("Robo", [], _fonts())
        viewer.draw(_surface())

    def test_draw_with_cards(self):
        viewer = PileViewer("Robo", _cards(5), _fonts())
        viewer.draw(_surface())

    def test_draw_large_pile(self):
        viewer = PileViewer("Robo", _cards(20), _fonts())
        viewer.draw(_surface())


# ---------------------------------------------------------------------------
# handle_event() — dismiss on Escape or click outside
# ---------------------------------------------------------------------------

class TestPileViewerHandleEvent:
    def test_escape_dismisses(self):
        viewer = PileViewer("Robo", _cards(3), _fonts())
        # Draw first so the viewer has a defined layout
        viewer.draw(_surface())
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
        viewer.handle_event(escape)
        assert viewer.dismissed

    def test_non_escape_key_does_not_dismiss(self):
        viewer = PileViewer("Robo", _cards(3), _fonts())
        viewer.draw(_surface())
        space = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ")
        viewer.handle_event(space)
        assert not viewer.dismissed
