"""Sprite loader — loads, scales, and caches 32×32 PNG sprites from the
Dungeon Crawl Stone Soup asset pack.

Sprites are scaled with nearest-neighbour to preserve pixel-art crispness.
All lookups are by display name (Spanish), matching Player.name and Enemy.name.
Returns None gracefully when a sprite file is missing or pygame fails.
"""
from __future__ import annotations

from pathlib import Path

import pygame

_ASSETS = (
    Path(__file__).parent.parent.parent
    / "assets"
    / "dungeon-crawl-stone-soup-full"
)

# ---------------------------------------------------------------------------
# Sprite mapping tables  (display name → path relative to _ASSETS)
# ---------------------------------------------------------------------------

PLAYER_SPRITE_PATHS: dict[str, str] = {
    "El Guerrero": "player/base/human_male.png",
    "El Mago":     "player/base/deep_elf_male.png",
    "El Pícaro":   "player/base/halfling_male.png",
}

ENEMY_SPRITE_PATHS: dict[str, str] = {
    "Cultista":           "monster/demons/imp.png",
    "Guardián":           "monster/nonliving/guardian_golem.png",
    "Brujo":              "monster/necromancer_new.png",
    "Esqueleto":          "monster/undead/skeletons/skeleton_humanoid_small_new.png",
    "Golem":              "monster/nonliving/stone_golem.png",
    "Asesino":            "monster/demons/reaper_new.png",
    "Señor de la Cripta": "monster/undead/ancient_lich_new.png",
}

RELIC_SPRITE_PATHS: dict[str, str] = {
    "Amuleto de Combate":  "item/amulet/celtic_red.png",
    "Tótem Roto":          "item/misc/misc_stone_old.png",
    "Orbe de Fuego":       "item/misc/misc_orb.png",
    "Escudo Espectral":    "item/armor/shields/shield_of_reflection.png",
    "Piedra de Energía":   "item/misc/misc_stone_new.png",
    "Anillo de Oro":       "item/ring/gold.png",
    "Corazón de Hierro":   "item/amulet/crystal_red.png",
    "Poción de Sangre":    "item/potion/ruby_new.png",
}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class SpriteLoader:
    """Lazy, size-keyed cache for scaled sprite surfaces.

    All sprites in the source pack are 32×32 pixels. This class scales them
    to the requested size using nearest-neighbour so pixel art stays sharp.
    Sprites are loaded once per (path, size) pair and reused on subsequent calls.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int], pygame.Surface | None] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_player_sprite(self, player_name: str, size: int = 128) -> pygame.Surface | None:
        """Return a scaled surface for the named player character, or None."""
        rel = PLAYER_SPRITE_PATHS.get(player_name)
        return self._load(rel, size) if rel else None

    def get_enemy_sprite(self, enemy_name: str, size: int = 96) -> pygame.Surface | None:
        """Return a scaled surface for the named enemy, or None."""
        rel = ENEMY_SPRITE_PATHS.get(enemy_name)
        return self._load(rel, size) if rel else None

    def get_relic_sprite(self, relic_name: str, size: int = 32) -> pygame.Surface | None:
        """Return a scaled surface for the named relic icon, or None."""
        rel = RELIC_SPRITE_PATHS.get(relic_name)
        return self._load(rel, size) if rel else None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self, rel_path: str, size: int) -> pygame.Surface | None:
        key = (rel_path, size)
        if key in self._cache:
            return self._cache[key]
        surf: pygame.Surface | None = None
        path = _ASSETS / rel_path
        if path.is_file():
            try:
                raw  = pygame.image.load(str(path)).convert_alpha()
                surf = pygame.transform.scale(raw, (size, size))
            except pygame.error:
                pass
        self._cache[key] = surf
        return surf
