"""Tests for presentation/scenes/combat_scene.py.

CombatScene renders the full battle screen. Tests here cover construction,
initial state, and event handling without visual assertions — all rendering
is smoke-tested (draw() must not raise). The session fixture in conftest.py
initialises pygame so Surface creation works.
"""
from __future__ import annotations

import pygame
import pytest

from src.application.combat_manager import create_sample_combat
from src.infrastructure.fonts import FontRegistry
from src.presentation.scenes.combat_scene import CombatScene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _surface() -> pygame.Surface:
    return pygame.Surface((1280, 720))


def _fonts() -> FontRegistry:
    return FontRegistry()


def _scene() -> CombatScene:
    return CombatScene(create_sample_combat(), _fonts())


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestCombatSceneConstruction:
    def test_creates_without_error(self):
        assert _scene() is not None

    def test_no_overlay_initially(self):
        assert _scene()._overlay is None

    def test_no_hovered_card_initially(self):
        assert _scene()._hovered_card is None

    def test_no_hovered_enemy_initially(self):
        assert _scene()._hovered_enemy is None

    def test_in_targeting_mode_false_initially(self):
        assert not _scene()._in_targeting_mode


# ---------------------------------------------------------------------------
# draw() — smoke test (must not raise)
# ---------------------------------------------------------------------------

class TestCombatSceneDraw:
    def test_draw_initial_state(self):
        scene = _scene()
        scene.draw(_surface())

    def test_draw_multiple_times(self):
        scene = _scene()
        surf = _surface()
        for _ in range(3):
            scene.draw(surf)

    def test_draw_with_selected_card(self):
        scene = _scene()
        scene._state.selected_card_index = 0
        scene.draw(_surface())


# ---------------------------------------------------------------------------
# handle_event() — keyboard
# ---------------------------------------------------------------------------

class TestCombatSceneKeyboard:
    def test_escape_clears_selection(self):
        scene = _scene()
        scene._state.selected_card_index = 0
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
        scene.handle_event(escape)
        assert scene._state.selected_card_index is None

    def test_escape_with_no_selection_does_not_crash(self):
        scene = _scene()
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="")
        scene.handle_event(escape)

    def test_other_key_ignored(self):
        scene = _scene()
        scene._state.selected_card_index = 0
        space = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ")
        scene.handle_event(space)
        assert scene._state.selected_card_index == 0


# ---------------------------------------------------------------------------
# handle_event() — mouse motion
# ---------------------------------------------------------------------------

class TestCombatSceneMouseMotion:
    def test_mouse_motion_does_not_crash(self):
        scene = _scene()
        motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0), buttons=(0, 0, 0))
        scene.handle_event(motion)

    def test_mouse_over_empty_clears_hover(self):
        scene = _scene()
        motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(640, 400), rel=(0, 0), buttons=(0, 0, 0))
        scene.handle_event(motion)
        assert scene._hovered_card is None


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------

class TestCombatSceneUpdate:
    def test_update_without_overlay(self):
        scene = _scene()
        scene.update(1 / 60)

    def test_update_clears_dismissed_overlay(self):
        from src.presentation.ui.pile_viewer import PileViewer
        scene = _scene()
        scene._overlay = PileViewer("Test", [], _fonts())
        scene._overlay.dismissed = True
        scene.update(1 / 60)
        assert scene._overlay is None
