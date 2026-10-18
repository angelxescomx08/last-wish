"""Tests for infrastructure/viewport.py — constants and pure coordinate math.

The pygame session fixture in conftest.py initialises pygame so Viewport
(which creates a pygame.Surface internally) can be instantiated.
"""
from __future__ import annotations

import pytest
import pygame

from src.infrastructure.viewport import VIRTUAL_H, VIRTUAL_W, Viewport


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

class TestVirtualDimensions:
    def test_virtual_width(self):
        assert VIRTUAL_W == 1280

    def test_virtual_height(self):
        assert VIRTUAL_H == 720

    def test_aspect_ratio(self):
        # 16:9
        assert VIRTUAL_W / VIRTUAL_H == pytest.approx(16 / 9)


# ---------------------------------------------------------------------------
# Viewport._update — scale and offset math
# ---------------------------------------------------------------------------

class TestViewportUpdate:
    def test_native_resolution_scale_one(self):
        vp = Viewport(1280, 720)
        assert vp._scale == pytest.approx(1.0)
        assert vp._off_x == 0
        assert vp._off_y == 0

    def test_double_resolution_scale_two(self):
        vp = Viewport(2560, 1440)
        assert vp._scale == pytest.approx(2.0)
        assert vp._off_x == 0
        assert vp._off_y == 0

    def test_half_resolution_scale_half(self):
        vp = Viewport(640, 360)
        assert vp._scale == pytest.approx(0.5)

    def test_wider_screen_pillarbox(self):
        # 1920×720 → sx=1.5, sy=1.0 → scale=1.0 → dest_w=1280, off_x=320
        vp = Viewport(1920, 720)
        assert vp._scale == pytest.approx(1.0)
        assert vp._off_x == 320
        assert vp._off_y == 0

    def test_taller_screen_letterbox(self):
        # 1280×900 → sx=1.0, sy=1.25 → scale=1.0 → dest_h=720, off_y=90
        vp = Viewport(1280, 900)
        assert vp._scale == pytest.approx(1.0)
        assert vp._off_x == 0
        assert vp._off_y == 90

    def test_1080p_scale(self):
        # 1920×1080 → sx=1.5, sy=1.5 → scale=1.5
        vp = Viewport(1920, 1080)
        assert vp._scale == pytest.approx(1.5)

    def test_4k_scale(self):
        vp = Viewport(3840, 2160)
        assert vp._scale == pytest.approx(3.0)

    def test_resize_updates_scale(self):
        vp = Viewport(1280, 720)
        vp.resize(2560, 1440)
        assert vp._scale == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Viewport.to_virtual — coordinate transform
# ---------------------------------------------------------------------------

class TestToVirtual:
    def test_identity_at_native_resolution(self):
        vp = Viewport(1280, 720)
        assert vp.to_virtual((100, 200)) == (100, 200)

    def test_scale_two_halves_coordinates(self):
        vp = Viewport(2560, 1440)
        assert vp.to_virtual((200, 400)) == (100, 200)

    def test_scale_half_doubles_coordinates(self):
        vp = Viewport(640, 360)
        assert vp.to_virtual((50, 100)) == (100, 200)

    def test_origin_always_maps_to_offset(self):
        # At native resolution offset is (0,0), so (0,0) → (0,0)
        vp = Viewport(1280, 720)
        vx, vy = vp.to_virtual((0, 0))
        assert vx == 0
        assert vy == 0

    def test_pillarbox_offset_applied(self):
        # 1920×720: scale=1.0, off_x=320, off_y=0
        # actual (320, 0) → virtual (0, 0)
        vp = Viewport(1920, 720)
        vx, vy = vp.to_virtual((320, 0))
        assert vx == 0
        assert vy == 0

    def test_corner_point_native(self):
        vp = Viewport(1280, 720)
        assert vp.to_virtual((1279, 719)) == (1279, 719)

    def test_corner_point_double(self):
        vp = Viewport(2560, 1440)
        assert vp.to_virtual((2560, 1440)) == (1280, 720)

    def test_returns_integers(self):
        vp = Viewport(1280, 720)
        result = vp.to_virtual((100, 200))
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)


class TestPresentation:
    @pytest.mark.parametrize("size", [(1280, 720), (640, 360), (1920, 1080),
                                      (2560, 1440), (1920, 720), (1280, 901), (1279, 719)])
    def test_pixels_match_original_smoothscale_after_resize(self, size):
        viewport = Viewport(1920, 1080)
        viewport.surface.fill((43, 79, 121))
        pygame.draw.circle(viewport.surface, (245, 91, 33), (631, 359), 157)
        pygame.draw.line(viewport.surface, (17, 241, 67), (0, 0), (1279, 719), 3)
        viewport.present(pygame.Surface((1920, 1080)))
        viewport.resize(*size)
        actual = pygame.Surface(size)
        actual.fill((255, 0, 255))
        expected = pygame.Surface(size)
        expected.fill((0, 0, 0))
        scaled = pygame.transform.smoothscale(viewport.surface, (viewport._dest_w, viewport._dest_h))
        expected.blit(scaled, (viewport._off_x, viewport._off_y))
        viewport.present(actual)
        assert pygame.image.tobytes(actual, "RGB") == pygame.image.tobytes(expected, "RGB")

    def test_native_resolution_does_not_scale(self, monkeypatch):
        def unexpected_scale(*args, **kwargs):
            pytest.fail("Native-sized presentation must not scale")
        monkeypatch.setattr(pygame.transform, "smoothscale", unexpected_scale)
        Viewport(1280, 720).present(pygame.Surface((1280, 720)))

    def test_scaled_frames_reuse_destination(self, monkeypatch):
        original = pygame.transform.smoothscale
        destinations = []
        def record(source, size, dest_surface=None):
            destinations.append(dest_surface)
            return original(source, size, dest_surface) if dest_surface is not None else original(source, size)
        monkeypatch.setattr(pygame.transform, "smoothscale", record)
        viewport = Viewport(1920, 1080)
        screen = pygame.Surface((1920, 1080))
        viewport.present(screen)
        viewport.present(screen)
        assert destinations[0] is not None
        assert destinations[0] is destinations[1]
