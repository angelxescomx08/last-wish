"""Loads the dungeon pixel-art pack once and keeps pre-scaled copies.

The pack is produced by ``scripts/generate_dungeon_assets.py``. Everything is
scaled to screen size a single time here (nearest neighbour, whole-number
factor) so that drawing a frame is only plain blits — no per-frame scaling.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

DUNGEON_DIR = Path(__file__).parent.parent.parent / "assets" / "dungeon"
META_PATH = DUNGEON_DIR / "dungeon.json"


@dataclass(frozen=True)
class DungeonAssets:
    meta: dict
    scale: int
    room: pygame.Surface                     # full backdrop, already at screen size
    flame_frames: tuple[pygame.Surface, ...]
    flame_durations: tuple[float, ...]       # seconds
    glow_frames: tuple[pygame.Surface, ...]  # additive light, black = none


def _optimize(surface: pygame.Surface, alpha: bool) -> pygame.Surface:
    """Match the display pixel format when a display exists (much faster blits)."""
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surface.convert_alpha() if alpha else surface.convert()
    return surface


def _strip(sheet: pygame.Surface, w: int, h: int, n: int, scale: int, alpha: bool) -> tuple[pygame.Surface, ...]:
    frames = []
    for i in range(n):
        cell = sheet.subsurface((i * w, 0, w, h)).copy()
        frames.append(_optimize(pygame.transform.scale(cell, (w * scale, h * scale)), alpha))
    return tuple(frames)


@lru_cache(maxsize=1)
def load_dungeon_assets() -> DungeonAssets | None:
    """Return the cached pack, or ``None`` when files are missing or unreadable."""
    try:
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        scale = int(meta["scale"])
        room_meta = meta["room"]
        rw, rh = room_meta["size"]
        room = pygame.image.load(str(DUNGEON_DIR / room_meta["image"]))
        room = _optimize(pygame.transform.scale(room, (rw * scale, rh * scale)), False)
        fm = meta["flame"]
        flames = _strip(pygame.image.load(str(DUNGEON_DIR / fm["image"])), fm["size"][0], fm["size"][1],
                        fm["frames"], scale, True)
        gm = meta["glow"]
        glows = _strip(pygame.image.load(str(DUNGEON_DIR / gm["image"])), gm["size"], gm["size"],
                       gm["frames"], scale, False)
        return DungeonAssets(meta, scale, room, flames, tuple(ms / 1000 for ms in fm["durations_ms"]), glows)
    except (OSError, ValueError, KeyError, TypeError, pygame.error):
        return None
