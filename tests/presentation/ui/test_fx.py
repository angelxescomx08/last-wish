"""Tests for src/presentation/ui/fx.py.

Verifies that FxLayer manages effect lifecycles correctly: effects are
added, updated frame by frame, and removed once their lifetime expires.
No surface rendering is exercised here — only the logic layer.
"""
import pygame
import pytest

from src.presentation.ui.fx import FxLayer


def _layer() -> FxLayer:
    pygame.init()
    font = pygame.font.Font(None, 16)
    return FxLayer(font)


class TestFxLayerInit:
    def test_starts_empty(self) -> None:
        layer = _layer()
        assert len(layer._effects) == 0


class TestFxLayerHitFlash:
    def test_add_hit_flash_creates_two_effects(self) -> None:
        layer = _layer()
        layer.add_hit_flash(pygame.Rect(0, 0, 100, 100), 10)
        assert len(layer._effects) == 2

    def test_add_block_flash_creates_two_effects(self) -> None:
        layer = _layer()
        layer.add_block_flash(pygame.Rect(0, 0, 100, 100), 5)
        assert len(layer._effects) == 2

    def test_add_death_flash_creates_one_effect(self) -> None:
        layer = _layer()
        layer.add_death_flash(pygame.Rect(0, 0, 100, 100))
        assert len(layer._effects) == 1


class TestFxLayerUpdate:
    def test_effects_removed_after_lifetime(self) -> None:
        layer = _layer()
        layer.add_hit_flash(pygame.Rect(0, 0, 50, 50), 8)
        layer.update(1.0)   # 1 second >> 0.25 s lifetime
        assert len(layer._effects) == 0

    def test_effects_alive_before_lifetime(self) -> None:
        layer = _layer()
        layer.add_hit_flash(pygame.Rect(0, 0, 50, 50), 8)
        layer.update(0.05)  # well within lifetime
        assert len(layer._effects) == 2

    def test_multiple_effects_expire_independently(self) -> None:
        layer = _layer()
        layer.add_hit_flash(pygame.Rect(0, 0, 50, 50), 3)   # HitFlash 0.25s + FloatingNumber 0.8s
        layer.add_death_flash(pygame.Rect(0, 0, 50, 50))     # HitFlash 0.40s
        layer.update(0.30)  # HitFlash(0.25s) expired; FloatingNumber(0.8s) + death HitFlash(0.40s) alive
        assert len(layer._effects) == 2

    def test_update_zero_dt_keeps_all_effects(self) -> None:
        layer = _layer()
        layer.add_hit_flash(pygame.Rect(0, 0, 50, 50), 10)
        layer.update(0.0)
        assert len(layer._effects) == 2

    def test_floating_number_moves_upward(self) -> None:
        layer = _layer()
        layer.add_hit_flash(pygame.Rect(100, 200, 80, 120), 15)
        # Find the FloatingNumber effect (second one added)
        from src.presentation.ui.fx import _FloatingNumber
        numbers = [e for e in layer._effects if isinstance(e, _FloatingNumber)]
        initial_y = numbers[0]._y
        layer.update(0.1)
        assert numbers[0]._y < initial_y   # must have moved up


class TestFxLayerDraw:
    def test_draw_does_not_raise_with_active_effects(self) -> None:
        pygame.init()
        surface = pygame.Surface((400, 300))
        layer   = _layer()
        layer.add_hit_flash(pygame.Rect(10, 10, 80, 100), 20)
        layer.add_block_flash(pygame.Rect(200, 50, 80, 120), 6)
        layer.draw(surface)   # must not raise

    def test_draw_empty_layer_does_not_raise(self) -> None:
        pygame.init()
        surface = pygame.Surface((400, 300))
        layer   = _layer()
        layer.draw(surface)
