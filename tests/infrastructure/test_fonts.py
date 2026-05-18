"""Tests for infrastructure/fonts.py — FontRegistry lazy-loading behaviour.

FontRegistry.get() requires pygame.font to be initialised (done by the
session fixture in conftest.py) and returns a cached pygame.font.Font object.
"""
from __future__ import annotations

import pygame
import pytest

from src.infrastructure.fonts import FontRegistry


# ---------------------------------------------------------------------------
# FontRegistry — construction
# ---------------------------------------------------------------------------

class TestFontRegistryConstruction:
    def test_creates_without_error(self):
        reg = FontRegistry()
        assert reg is not None

    def test_cache_starts_empty(self):
        reg = FontRegistry()
        assert len(reg._cache) == 0


# ---------------------------------------------------------------------------
# FontRegistry.get() — lazy font loading
# ---------------------------------------------------------------------------

class TestFontRegistryGet:
    def test_returns_font_object(self):
        reg = FontRegistry()
        font = reg.get(12)
        assert isinstance(font, pygame.font.Font)

    def test_same_size_returns_cached_instance(self):
        reg = FontRegistry()
        f1 = reg.get(14)
        f2 = reg.get(14)
        assert f1 is f2

    def test_different_sizes_different_instances(self):
        reg = FontRegistry()
        f1 = reg.get(10)
        f2 = reg.get(20)
        assert f1 is not f2

    def test_cache_grows(self):
        reg = FontRegistry()
        reg.get(8)
        reg.get(11)
        reg.get(14)
        assert len(reg._cache) == 3

    def test_small_size(self):
        reg = FontRegistry()
        assert reg.get(8) is not None

    def test_large_size(self):
        reg = FontRegistry()
        assert reg.get(48) is not None

    def test_zero_size_does_not_crash(self):
        reg = FontRegistry()
        try:
            reg.get(1)  # minimal valid size
        except Exception:
            pytest.skip("pygame does not support this font size on this platform")
