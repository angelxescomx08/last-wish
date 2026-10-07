"""HUD kit pieces (``assets/ui/kit.png`` + ``kit.json``, from ``scripts/generate_ui_kit.py``).

* ``kit_piece(name, scale=2)`` — one piece scaled ×``scale`` (nearest), cached.
* ``kit_slice(name, w, h, scale=2)`` — a stretchable piece (``slice`` margins in the
  JSON) built at ``w×h`` screen px: corners kept, edges and centre **tiled** (never
  stretched) so the pixel grain stays the same at any size. Pieces with no vertical
  margins (buttons, ribbon) are 3-slices: built at their native height, then scaled to
  ``h`` if it differs. Cached per size.
* ``has_kit()`` — False when the files are missing (widgets then draw plain shapes).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pygame

UI_DIR = Path(__file__).parent.parent.parent / "assets" / "ui"


@lru_cache(maxsize=1)
def _sheet() -> tuple[pygame.Surface, dict] | None:
    try:
        img = pygame.image.load(str(UI_DIR / "kit.png"))
        meta = json.loads((UI_DIR / "kit.json").read_text(encoding="utf-8"))["pieces"]
    except (OSError, pygame.error, ValueError, KeyError):
        return None
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        img = img.convert_alpha()
    return img, meta


def has_kit() -> bool:
    return _sheet() is not None


def kit_names() -> list[str]:
    data = _sheet()
    return list(data[1]) if data else []


def _native(name: str) -> tuple[pygame.Surface, list[int] | None] | None:
    data = _sheet()
    if data is None or name not in data[1]:
        return None
    img, meta = data
    x, y, w, h = meta[name]["rect"]
    return img.subsurface((x, y, w, h)), meta[name].get("slice")


@lru_cache(maxsize=128)
def kit_piece(name: str, scale: int = 2) -> pygame.Surface | None:
    found = _native(name)
    if found is None:
        return None
    cell = found[0]
    return pygame.transform.scale(cell, (cell.get_width() * scale, cell.get_height() * scale))


def _tile(dst: pygame.Surface, src: pygame.Surface, area: pygame.Rect, rect: pygame.Rect) -> None:
    """Fill ``rect`` of ``dst`` by repeating ``area`` of ``src``."""
    if area.w <= 0 or area.h <= 0 or rect.w <= 0 or rect.h <= 0:
        return
    piece = src.subsurface(area)
    for y in range(rect.y, rect.bottom, area.h):
        for x in range(rect.x, rect.right, area.w):
            w, h = min(area.w, rect.right - x), min(area.h, rect.bottom - y)
            dst.blit(piece, (x, y), pygame.Rect(0, 0, w, h))


def _build(cell: pygame.Surface, sl: list[int], w: int, h: int) -> pygame.Surface:
    """Native-px slice of ``cell`` to ``w×h`` (tiling the stretchable parts)."""
    left, top, right, bottom = sl
    cw, ch = cell.get_size()
    out = pygame.Surface((max(w, left + right), max(h, top + bottom)), pygame.SRCALPHA)
    w, h = out.get_size()
    mid_w, mid_h = cw - left - right, ch - top - bottom
    cols = ((0, left, 0, left), (left, mid_w, left, w - left - right), (cw - right, right, w - right, right))
    rows = ((0, top, 0, top), (top, mid_h, top, h - top - bottom), (ch - bottom, bottom, h - bottom, bottom))
    for sx, sw, dx, dw in cols:
        for sy, sh, dy, dh in rows:
            _tile(out, cell, pygame.Rect(sx, sy, sw, sh), pygame.Rect(dx, dy, dw, dh))
    return out


@lru_cache(maxsize=256)
def kit_slice(name: str, w: int, h: int, scale: int = 2) -> pygame.Surface | None:
    found = _native(name)
    if found is None:
        return None
    cell, sl = found
    sl = sl or [0, 0, 0, 0]
    native_w = max(1, round(w / scale))
    if sl[1] == 0 and sl[3] == 0:                        # 3-slice: fixed native height
        built = _build(cell, sl, native_w, cell.get_height())
        out = pygame.transform.scale(built, (built.get_width() * scale, built.get_height() * scale))
        return out if out.get_height() == h and out.get_width() == w else pygame.transform.scale(out, (w, h))
    built = _build(cell, sl, native_w, max(1, round(h / scale)))
    out = pygame.transform.scale(built, (built.get_width() * scale, built.get_height() * scale))
    return out if out.get_size() == (w, h) else pygame.transform.scale(out, (w, h))
