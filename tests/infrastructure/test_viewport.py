"""Tests for infrastructure/viewport.py — constants and pure coordinate math.

The pygame session fixture in conftest.py initialises pygame so Viewport
(which creates a pygame.Surface internally) can be instantiated.
"""
from __future__ import annotations

import pytest

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
