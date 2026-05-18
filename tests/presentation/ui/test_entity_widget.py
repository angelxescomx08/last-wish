"""Tests for presentation/ui/entity_widget.py.

draw_player() and draw_enemy() render onto a pygame.Surface.
The session fixture in conftest.py initialises pygame.
"""
from __future__ import annotations

import pygame
import pytest

from src.domain.entities import Enemy, Intent, IntentType, Player, StatusEffect
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.entity_widget import ENEMY_W, PLAYER_W, draw_enemy, draw_player


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _surface() -> pygame.Surface:
    return pygame.Surface((600, 400))


def _fonts() -> FontRegistry:
    return FontRegistry()


def _player(hp: int = 80, block: int = 0) -> Player:
    return Player(name="Viajero", max_hp=80, current_hp=hp, block=block)


def _enemy(hp: int = 50, block: int = 0) -> Enemy:
    return Enemy(
        id="e", name="Cultista", max_hp=50, current_hp=hp, block=block,
        intent=Intent(IntentType.ATTACK, 10),
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestEntityWidgetConstants:
    def test_player_width_positive(self):
        assert PLAYER_W > 0

    def test_enemy_width_positive(self):
        assert ENEMY_W > 0


# ---------------------------------------------------------------------------
# draw_player() — return value and smoke tests
# ---------------------------------------------------------------------------

class TestDrawPlayer:
    def test_returns_rect(self):
        rect = draw_player(_surface(), _player(), 10, 10, _fonts())
        assert isinstance(rect, pygame.Rect)

    def test_rect_x_matches_requested(self):
        rect = draw_player(_surface(), _player(), 50, 30, _fonts())
        assert rect.x == 50

    def test_full_hp(self):
        draw_player(_surface(), _player(hp=80), 0, 0, _fonts())

    def test_low_hp(self):
        draw_player(_surface(), _player(hp=1), 0, 0, _fonts())

    def test_zero_hp(self):
        draw_player(_surface(), _player(hp=0), 0, 0, _fonts())

    def test_with_block(self):
        draw_player(_surface(), _player(block=5), 0, 0, _fonts())

    def test_with_status_effect(self):
        p = _player()
        p.status_effects = [StatusEffect("Fuerza", 2, is_buff=True)]
        draw_player(_surface(), p, 0, 0, _fonts())

    def test_multiple_status_effects(self):
        p = _player()
        p.status_effects = [
            StatusEffect("Fuerza", 2, is_buff=True),
            StatusEffect("Veneno", 3, is_buff=False),
        ]
        draw_player(_surface(), p, 0, 0, _fonts())


# ---------------------------------------------------------------------------
# draw_enemy() — return value and smoke tests
# ---------------------------------------------------------------------------

class TestDrawEnemy:
    def test_returns_rect(self):
        rect = draw_enemy(_surface(), _enemy(), 10, 10, _fonts())
        assert isinstance(rect, pygame.Rect)

    def test_rect_x_matches_requested(self):
        rect = draw_enemy(_surface(), _enemy(), 30, 40, _fonts())
        assert rect.x == 30

    def test_full_hp(self):
        draw_enemy(_surface(), _enemy(hp=50), 0, 0, _fonts())

    def test_low_hp(self):
        draw_enemy(_surface(), _enemy(hp=1), 0, 0, _fonts())

    def test_zero_hp(self):
        draw_enemy(_surface(), _enemy(hp=0), 0, 0, _fonts())

    def test_with_block(self):
        draw_enemy(_surface(), _enemy(block=8), 0, 0, _fonts())

    def test_targeted(self):
        draw_enemy(_surface(), _enemy(), 0, 0, _fonts(), targeted=True)

    def test_highlighted(self):
        draw_enemy(_surface(), _enemy(), 0, 0, _fonts(), highlighted=True)

    def test_block_intent(self):
        e = _enemy()
        e.intent = Intent(IntentType.BLOCK, 8)
        draw_enemy(_surface(), e, 0, 0, _fonts())

    def test_buff_intent(self):
        e = _enemy()
        e.intent = Intent(IntentType.BUFF, 0)
        draw_enemy(_surface(), e, 0, 0, _fonts())

    def test_with_status_effect(self):
        e = _enemy()
        e.status_effects = [StatusEffect("Vulnerable", 2, is_buff=False)]
        draw_enemy(_surface(), e, 0, 0, _fonts())
