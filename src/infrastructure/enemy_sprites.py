"""Animated enemy sprite sheets (``assets/enemies/<id>_sheet.png`` + ``.json``).

Written by ``scripts/generate_enemy_sprites.py``. Each sheet row is one
animation; cells are native pixel art and are scaled once at load with
nearest-neighbour (``scale`` in the JSON, ×2 by default) and cached.

Lookups are by the enemy's Spanish display name (``Enemy.name``). Enemies
without a sheet keep their static Dungeon Crawl sprite.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

from src.infrastructure.sprite_loader import HeroAnimation

ENEMY_DIR = Path(__file__).parent.parent.parent / "assets" / "enemies"

# Enemy display name -> sheet id (files <id>_sheet.png / <id>_sheet.json)
ENEMY_SHEET_IDS: dict[str, str] = {
    "Espectro": "wraith",
}
ENEMY_ANIMATIONS = ("idle", "attack", "hurt", "cast", "death")


@dataclass(frozen=True)
class EnemySheet:
    """Scaled frames and timing of one animated enemy."""
    sheet_id: str
    size: tuple[int, int]                        # scaled cell size (px)
    anchor: tuple[int, int]                      # ground point inside a scaled cell
    animations: dict[str, HeroAnimation]
    frames: dict[str, tuple[pygame.Surface, ...]]

    def seconds(self, animation: str) -> float:
        anim = self.animations.get(animation)
        return anim.total if anim is not None else 0.0

    def frame(self, animation: str, elapsed: float) -> pygame.Surface:
        name = animation if animation in self.frames else "idle"
        return self.frames[name][self.animations[name].frame_at(elapsed)]


def enemy_sheet_id(name: str) -> str | None:
    """Sheet id for an enemy display name, or None."""
    return ENEMY_SHEET_IDS.get(name)


@lru_cache(maxsize=8)
def load_enemy_sheet(sheet_id: str) -> EnemySheet | None:
    """Load, slice and scale one sheet (cached). None when files are missing or invalid."""
    try:
        meta = json.loads((ENEMY_DIR / f"{sheet_id}_sheet.json").read_text(encoding="utf-8"))
        cw, ch = int(meta["cell_w"]), int(meta["cell_h"])
        scale = max(1, int(meta.get("scale", 2)))
        sheet = pygame.image.load(str(ENEMY_DIR / meta["sheet"]))
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            sheet = sheet.convert_alpha()
        animations: dict[str, HeroAnimation] = {}
        frames: dict[str, tuple[pygame.Surface, ...]] = {}
        for name, a in meta["animations"].items():
            row, count = int(a["row"]), int(a["frames"])
            animations[name] = HeroAnimation(row, tuple(ms / 1000 for ms in a["durations_ms"]),
                                             bool(a["loop"]))
            frames[name] = tuple(
                pygame.transform.scale(sheet.subsurface((col * cw, row * ch, cw, ch)),
                                       (cw * scale, ch * scale))
                for col in range(count))
        if "idle" not in frames:
            return None
        ax, ay = meta.get("anchor", (cw // 2, ch))
        return EnemySheet(sheet_id, (cw * scale, ch * scale), (int(ax) * scale, int(ay) * scale),
                          animations, frames)
    except (OSError, ValueError, KeyError, TypeError, pygame.error):
        return None


def sheet_for_enemy(name: str) -> EnemySheet | None:
    sheet_id = enemy_sheet_id(name)
    return load_enemy_sheet(sheet_id) if sheet_id else None
