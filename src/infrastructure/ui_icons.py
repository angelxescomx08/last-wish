"""UI icons (``assets/ui/icons.png`` + ``icons.json``, from ``scripts/generate_ui_icons.py``).

``ui_icon(name, scale=2)`` returns the icon scaled ×``scale`` (nearest neighbour,
cached), or ``None`` when the name or the files are missing so callers can fall
back to plain shapes. ``has_ui_icon(name)`` tells whether the strip has it.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pygame

UI_DIR = Path(__file__).parent.parent.parent / "assets" / "ui"


@lru_cache(maxsize=1)
def _strip() -> tuple[pygame.Surface, dict] | None:
    try:
        img = pygame.image.load(str(UI_DIR / "icons.png"))
        meta = json.loads((UI_DIR / "icons.json").read_text(encoding="utf-8"))["icons"]
    except (OSError, pygame.error, ValueError, KeyError):
        return None
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        img = img.convert_alpha()
    return img, meta


def has_ui_icon(name: str) -> bool:
    data = _strip()
    return data is not None and name in data[1]


@lru_cache(maxsize=256)
def ui_icon(name: str, scale: int = 2) -> pygame.Surface | None:
    data = _strip()
    if data is None or name not in data[1]:
        return None
    img, meta = data
    x, y, w, h = meta[name]
    cell = img.subsurface((x, y, w, h))
    return pygame.transform.scale(cell, (w * scale, h * scale)) if scale != 1 else cell.copy()
