"""Animated enemy sprite sheets (``assets/enemies/<id>_sheet.png`` + ``.json``).

Written by ``scripts/generate_enemy_sprites.py``. Each sheet row is one
animation; cells are native pixel art and are scaled once at load with
nearest-neighbour (``scale`` in the JSON, ×2 by default) and cached.

Lookups are by the enemy's Spanish display name (``Enemy.name``). Enemies
without a sheet keep their static Dungeon Crawl sprite.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pygame

from src.infrastructure.sprite_loader import HeroAnimation

ENEMY_DIR = Path(__file__).parent.parent.parent / "assets" / "enemies"

# Enemy display name -> sheet id (files <id>_sheet.png / <id>_sheet.json)
ENEMY_SHEET_IDS: dict[str, str] = {
    "Espectro": "wraith",
    # Floor-1 bosses (scripts/generate_boss_<id>.py)
    "Reina Micélida": "mycelid",
    "La Tejedora": "weaver",
    "Caballero Hueco": "knight",
    # Regular enemies (scripts/generate_enemy_<id>.py, application/enemy_roster.py)
    "Babosa Ácida": "slime",
    "Gusano de Tumba": "worm",
    "Ojo Vigilante": "eye",
    "Cráneo Ígneo": "skull",
    "Murciélago Vampiro": "bat",
    "Seta Explosiva": "bomb",
    "Gólem de Musgo": "golem",
    "Acólito de Ceniza": "acolyte",
    "Diablillo": "imp",
    "Mímico": "mimic",
}
REGULAR_SHEET_IDS = ("wraith", "slime", "worm", "eye", "skull", "bat", "bomb", "golem", "acolyte",
                     "imp", "mimic")
ENEMY_ANIMATIONS = ("idle", "attack", "hurt", "cast", "death")
BOSS_SHEET_IDS = ("mycelid", "weaver", "knight")


@dataclass(frozen=True)
class EnemySheet:
    """Scaled frames and timing of one animated enemy."""
    sheet_id: str
    size: tuple[int, int]                        # scaled cell size (px)
    anchor: tuple[int, int]                      # ground point inside a scaled cell
    animations: dict[str, HeroAnimation]
    frames: dict[str, tuple[pygame.Surface, ...]]
    # Optional data written by the boss generators:
    strikes: dict[str, tuple[int, ...]] = field(default_factory=dict)   # anim -> frames where hits land
    moves: dict[str, str] = field(default_factory=dict)                 # boss move id -> animation
    is_boss: bool = False                                                 # drawn in the big boss slot
    blade_frames: tuple[pygame.Surface, ...] = ()                         # floating sword rotations
    top: int = 0                     # highest opaque row of idle frame 0, in scaled px from the cell top
    terminal: tuple[str, ...] = ()   # actions that end the enemy like death (Seta: "explode")

    def seconds(self, animation: str) -> float:
        anim = self.animations.get(animation)
        return anim.total if anim is not None else 0.0

    def frame(self, animation: str, elapsed: float) -> pygame.Surface:
        name = animation if animation in self.frames else "idle"
        return self.frames[name][self.animations[name].frame_at(elapsed)]

    def strike_seconds(self, animation: str) -> tuple[float, ...]:
        """Seconds from the start of ``animation`` to each frame where a hit lands.

        Uses ``events.<anim>.strikes`` from the JSON; without it, ``attack`` lands on
        its 4th frame (the Espectro's claws) and other animations land nowhere.
        """
        anim = self.animations.get(animation)
        if anim is None:
            return ()
        frames = self.strikes.get(animation)
        if frames is None:
            frames = (3,) if animation == "attack" else ()
        return tuple(sum(anim.durations[:f]) for f in frames if 0 <= f <= len(anim.durations))

    def animation_for_move(self, move_id: str, fallback: str) -> str:
        """The animation that acts out a boss move (``moves`` in the JSON), else ``fallback``."""
        name = self.moves.get(move_id, "")
        return name if name in self.animations else fallback


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
        strikes = {name: tuple(int(f) for f in ev.get("strikes", ()))
                   for name, ev in meta.get("events", {}).items() if isinstance(ev, dict)}
        moves = {str(k): str(v) for k, v in meta.get("moves", {}).items()}
        return EnemySheet(sheet_id, (cw * scale, ch * scale), (int(ax) * scale, int(ay) * scale),
                          animations, frames, strikes=strikes, moves=moves,
                          is_boss=bool(meta.get("boss", False)),
                          blade_frames=_load_blades(meta.get("blade"), scale),
                          top=_top_row(frames["idle"][0]),
                          terminal=tuple(str(n) for n in meta.get("terminal", ()) if n in frames))
    except (OSError, ValueError, KeyError, TypeError, pygame.error):
        return None


def _load_blades(info, scale: int) -> tuple[pygame.Surface, ...]:
    """Rotations of a floating weapon (a strip of square cells), scaled like the sheet."""
    if not isinstance(info, dict):
        return ()
    strip = pygame.image.load(str(ENEMY_DIR / str(info["sheet"])))
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        strip = strip.convert_alpha()
    size, count = int(info["size"]), int(info["rotations"])
    return tuple(pygame.transform.scale(strip.subsurface((k * size, 0, size, size)),
                                        (size * scale, size * scale)) for k in range(count))


def _top_row(frame: pygame.Surface) -> int:
    rect = frame.get_bounding_rect(min_alpha=1)
    return rect.top if rect.height > 0 else 0


def sheet_for_enemy(name: str) -> EnemySheet | None:
    sheet_id = enemy_sheet_id(name)
    return load_enemy_sheet(sheet_id) if sheet_id else None
