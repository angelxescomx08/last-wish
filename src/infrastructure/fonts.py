"""Game fonts: Pixel Operator (CC0, public domain) + the UI symbols, as crisp pixel text.

``assets/fonts/LastWish.ttf`` (16 px grid) and ``LastWish8.ttf`` (8 px grid) are built by
``scripts/build_game_font.py`` from Jayvee Enaguas' Pixel Operator (CC0 1.0: no credit
required) with the arrows and signs the UI uses drawn in as pixel glyphs.

A pixel font only looks right at whole multiples of its grid, so every requested size is
snapped to the closest of those (``pixel_size``) — the grain matches the ×2 pixel art at the
large sizes — and text is always rendered without antialiasing (on a transparent 32-bit
surface, like antialiased text, so fades and tints work the same). Several requested sizes
share one font object. If the TTFs are missing the old system font is used.

``bold(size)`` gives the Bold version (also CC0, ``LastWish-Bold.ttf`` / ``LastWish8-Bold.ttf``),
used for the text on the cards.

``tiny()`` gives Tiny5 (The Tiny5 Project Authors, github.com/Gissio/font_tiny5; SIL Open Font License — free; its licence text ships
next to it as ``Tiny5-OFL.txt``), a narrow 5 px pixel font for card names that do not fit.
"""
from __future__ import annotations

from pathlib import Path

import pygame

FONT_DIR = Path(__file__).parent.parent.parent / "assets" / "fonts"
FONT_16 = "LastWish.ttf"         # cap height 9 px per 16 px
FONT_8 = "LastWish8.ttf"         # cap height 7 px per 8 px
FONT_TINY = "Tiny5-Regular.ttf"  # cap height 5 px per 8 px, narrow (SIL OFL, see Tiny5-OFL.txt)
_FALLBACK = "segoeuisemibold,arialnarrow,serif"


def pixel_size(size: int) -> tuple[str, int]:
    """(font file, pixel size) used for a requested ``size`` (old point sizes ~ cap × 1.4)."""
    if size <= 11:
        return FONT_8, 8              # cap 7  (card text, small hints)
    if size <= 17:
        return FONT_16, 16            # cap 9  (1 px grain)
    if size <= 23:
        return FONT_8, 16             # cap 14 (2 px grain)
    if size <= 30:
        return FONT_16, 32            # cap 18 (2 px grain)
    if size <= 38:
        return FONT_8, 24             # cap 21 (3 px grain)
    return FONT_8, 8 * max(4, round(size / 10))   # cap ≈ 0.7 × size, whole grain


class PixelFont(pygame.font.Font):
    """A font that always renders hard-edged pixels on a transparent 32-bit surface."""

    def render(self, text, antialias=False, color=(255, 255, 255), background=None):  # noqa: D401
        if background is not None:
            return super().render(text, False, color, background)
        hard = super().render(text, False, color)           # 8-bit, colour-keyed
        out = pygame.Surface(hard.get_size(), pygame.SRCALPHA)
        out.blit(hard, (0, 0))
        return out


class FontRegistry:
    """Loads and caches the game font by requested size (sizes snap to the pixel grid)."""

    def __init__(self, font_dir: Path = FONT_DIR) -> None:
        self._dir = font_dir
        self._cache: dict[int, pygame.font.Font] = {}
        self._by_file: dict[tuple[str, int], pygame.font.Font] = {}

    @property
    def pixel(self) -> bool:
        """True when the pixel font files are present (False: system font fallback)."""
        return (self._dir / FONT_16).is_file() and (self._dir / FONT_8).is_file()

    def get(self, size: int) -> pygame.font.Font:
        size = max(1, int(size))
        font = self._cache.get(size)
        if font is None:
            font = self._cache[size] = self._load(size)
        return font

    def bold(self, size: int) -> pygame.font.Font:
        """Pixel Operator Bold (CC0) at the same snapped size as ``get(size)``: 2 px stems,
        used where the regular face looks too thin (card text). Falls back to ``get``."""
        name, px = pixel_size(max(1, int(size)))
        bold_name = name.replace(".ttf", "-Bold.ttf")
        path = self._dir / bold_name
        if not self.pixel or not path.is_file():
            return self.get(size)
        key = (bold_name, px)
        font = self._by_file.get(key)
        if font is None:
            font = self._by_file[key] = PixelFont(str(path), px)
        return font

    def tiny(self, size: int = 8) -> pygame.font.Font:
        """Narrow pixel font for labels that must fit a small plate (card names). Sizes snap to
        multiples of 8; falls back to ``get(size)`` without the file."""
        path = self._dir / FONT_TINY
        if not path.is_file():
            return self.get(size)
        key = (FONT_TINY, 8 * max(1, round(size / 8)))
        font = self._by_file.get(key)
        if font is None:
            font = self._by_file[key] = PixelFont(str(path), key[1])
        return font

    def _load(self, size: int) -> pygame.font.Font:
        if not self.pixel:
            return pygame.font.SysFont(_FALLBACK, size)
        key = pixel_size(size)
        font = self._by_file.get(key)
        if font is None:
            font = self._by_file[key] = PixelFont(str(self._dir / key[0]), key[1])
        return font
