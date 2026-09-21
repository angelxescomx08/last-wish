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

_HERO_IDLE_PATH = _ASSETS.parent / "characters" / "redhead_idle.png"
IDLE_FRAME_SECONDS = 0.18
IDLE_SEQUENCE = tuple(range(8)) + tuple(range(6, 0, -1))
IDLE_CYCLE_SECONDS = len(IDLE_SEQUENCE) * IDLE_FRAME_SECONDS

_CARD_ASSETS = (
    Path(__file__).parent.parent.parent
    / "assets"
    / "Card Sprites"
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

# ---------------------------------------------------------------------------
# Card art, rarity badges, pack boosters  (paths relative to _CARD_ASSETS)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Card UI component layers  (paths relative to _CARD_ASSETS)
# ---------------------------------------------------------------------------
# Sprite roles:
#   Alternate (1/2/3) + minion (1) = full portrait card frames (ratio 0.73)
#   minion (4)  = oval portrait frame border  (nearly square, transparent inside)
#   minion (5)  = oval portrait frame variant
#   minion (6)  = name-banner ribbon          (very wide, 1085×493)
#   minion (7)  = mana-gem decoration         (top, protrudes above card, 477×233)
#   minion (2)  = ability/skill box           (wide plate, 933×749)
#   minion (3)  = card-type plate             (center-bottom between hexagons, 717×392)
#   minion (8)  = stat hexagons               (full width, red=ATK left, green=DEF right)
#   _Rarity/rarity (N) = rarity gem (centred below portrait)

CARD_FRAME_PATHS: dict[str, str] = {
    "ATTACK": "Landmark/Alternate (1).png",
    "SKILL":  "Landmark/Alternate (2).png",
    "POWER":  "Landmark/Alternate (3).png",
}

CARD_COMPONENT_PATHS: dict[str, str] = {
    "mana":       "Landmark/landmark (7).png",
    "banner":     "Landmark/landmark (6).png",
    "portrait":   "Landmark/minion (4).png",
    "ability":    "Landmark/landmark (2).png",
    "type_plate": "Landmark/landmark (3).png",
    "stats":      "Landmark/minion (8).png",   # new pack — two hexagons: red ATK | green DEF
}

RARITY_BADGE_PATHS: dict[str, str] = {
    "COMMON":    "_Rarity/rarity (1).png",
    "UNCOMMON":  "_Rarity/rarity (2).png",
    "RARE":      "_Rarity/rarity (3).png",
    "EPIC":      "_Rarity/rarity (4).png",
    "LEGENDARY": "_Rarity/rarity (5).png",
}

PACK_SPRITE_PATHS: dict[str, str] = {
    "acero":  "Booster/booster body wave.png",
    "escudo": "Booster/booster body smooth.png",
    "magia":  "Booster/booster body wave.png",
    "epico":  "Booster/booster body smooth.png",
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
        self._idle_frames: dict[int, tuple[pygame.Surface, ...]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_player_idle_frames(self, size: int = 192) -> tuple[pygame.Surface, ...]:
        """Slice once, align boot anchors, and cache transparent idle frames."""
        if size in self._idle_frames:
            return self._idle_frames[size]
        if size != 96:
            frames = tuple(pygame.transform.scale(frame, (size, size))
                           for frame in self.get_player_idle_frames(96))
            self._idle_frames[size] = frames
            return frames
        try:
            sheet = pygame.image.load(str(_HERO_IDLE_PATH))
        except (pygame.error, OSError):
            self._idle_frames[size] = ()
            return ()
        cells = []
        for row in range(2):
            for col in range(4):
                left, right = (round(c * sheet.get_width() / 4) for c in (col, col + 1))
                top, bottom = (round(r * sheet.get_height() / 2) for r in (row, row + 1))
                cell = sheet.subsurface((left, top, right - left, bottom - top))
                cells.append((cell, cell.get_bounding_rect(min_alpha=32)))
        scale = 86 / max(bounds.height for _, bounds in cells)
        frames = []
        for index, (cell, bounds) in enumerate(cells):
            # Boots remain fixed; breathing lifts only the upper body by 0–2 pixels.
            boots = cell.subsurface((0, bounds.bottom - 60, cell.get_width(), 60))
            anchor = boots.get_bounding_rect(min_alpha=32).centerx
            art = pygame.transform.scale(cell.subsurface(bounds),
                                         (round(bounds.width * scale), round(bounds.height * scale)))
            frame = pygame.Surface((96, 96), pygame.SRCALPHA)
            x = 48 - round((anchor - bounds.x) * scale)
            y = 92 - art.get_height()
            split = round(art.get_height() * 0.65)
            lift = round(2 * index / 7)
            upper = pygame.transform.scale(art.subsurface((0, 0, art.get_width(), split)),
                                           (art.get_width(), split + lift))
            frame.blit(upper, (x, y - lift))
            frame.blit(art, (x, y + split), (0, split, art.get_width(), art.get_height() - split))
            frames.append(frame)
        self._idle_frames[size] = tuple(frames)
        return self._idle_frames[size]

    def get_player_sprite(self, player_name: str, size: int = 128, *, elapsed: float = 0.0) -> pygame.Surface | None:
        """Select idle by elapsed seconds, independently of rendering frame rate."""
        if player_name in ("La Guerrera", "El Guerrero"):
            frames = self.get_player_idle_frames(size)
            if frames:
                tick = int((max(0.0, elapsed) % IDLE_CYCLE_SECONDS) / IDLE_FRAME_SECONDS + 1e-9)
                return frames[IDLE_SEQUENCE[tick % len(IDLE_SEQUENCE)]]
            player_name = "El Guerrero"
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

    def get_rarity_badge(self, rarity_name: str, size: int = 16) -> pygame.Surface | None:
        """Return rarity badge sprite (COMMON/UNCOMMON/RARE/EPIC/LEGENDARY), or None."""
        rel = RARITY_BADGE_PATHS.get(rarity_name)
        return self._load_card(rel, size) if rel else None

    def get_pack_sprite(self, theme_value: str, size: int = 80) -> pygame.Surface | None:
        """Return booster pack sprite for the given PackTheme.value, or None."""
        rel = PACK_SPRITE_PATHS.get(theme_value)
        return self._load_card(rel, size) if rel else None

    def get_card_frame(self, card_type_name: str, w: int, h: int) -> pygame.Surface | None:
        """Return card frame scaled to (w, h) for the given CardType name."""
        rel = CARD_FRAME_PATHS.get(card_type_name)
        if not rel:
            return None
        key = ("_card_" + rel, w * 10000 + h)
        if key in self._cache:
            return self._cache[key]
        surf: pygame.Surface | None = None
        path = _CARD_ASSETS / rel
        if path.is_file():
            try:
                raw  = pygame.image.load(str(path)).convert_alpha()
                surf = pygame.transform.scale(raw, (w, h))
            except pygame.error:
                pass
        self._cache[key] = surf
        return surf

    def get_card_component(self, name: str, w: int, h: int) -> pygame.Surface | None:
        """Return a card component layer scaled to (w, h)."""
        rel = CARD_COMPONENT_PATHS.get(name)
        if not rel:
            return None
        key = ("_card_" + rel, w * 10000 + h)
        if key in self._cache:
            return self._cache[key]
        surf: pygame.Surface | None = None
        path = _CARD_ASSETS / rel
        if path.is_file():
            try:
                raw  = pygame.image.load(str(path)).convert_alpha()
                surf = pygame.transform.scale(raw, (w, h))
            except pygame.error:
                pass
        self._cache[key] = surf
        return surf

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_card(self, rel_path: str, size: int) -> pygame.Surface | None:
        """Load from _CARD_ASSETS (Card Sprites folder)."""
        key = ("_card_" + rel_path, size)
        if key in self._cache:
            return self._cache[key]
        surf: pygame.Surface | None = None
        path = _CARD_ASSETS / rel_path
        if path.is_file():
            try:
                raw  = pygame.image.load(str(path)).convert_alpha()
                surf = pygame.transform.scale(raw, (size, size))
            except pygame.error:
                pass
        self._cache[key] = surf
        return surf

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
