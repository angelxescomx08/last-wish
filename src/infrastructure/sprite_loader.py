"""Sprite loader — loads, scales, and caches 32×32 PNG sprites from the
Dungeon Crawl Stone Soup asset pack.

Sprites are scaled with nearest-neighbour to preserve pixel-art crispness.
All lookups are by display name (Spanish), matching Player.name and Enemy.name.
Returns None gracefully when a sprite file is missing or pygame fails.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pygame

_ASSETS = (
    Path(__file__).parent.parent.parent
    / "assets"
    / "dungeon-crawl-stone-soup-full"
)

_HERO_DIR = _ASSETS.parent / "characters"
_HERO_SHEET_PATH = _HERO_DIR / "warrior_sheet.png"
_HERO_META_PATH = _HERO_DIR / "warrior_sheet.json"
HERO_NAMES = ("La Guerrera", "El Guerrero")


@dataclass(frozen=True)
class HeroAnimation:
    """One row of the native pixel-art sheet written by generate_warrior_sprites.py."""
    row: int
    durations: tuple[float, ...]   # seconds per frame
    loop: bool

    @property
    def total(self) -> float:
        return sum(self.durations)

    def frame_at(self, elapsed: float) -> int:
        """Frame index for ``elapsed`` seconds: wraps when looping, holds the last frame otherwise."""
        t = max(0.0, elapsed)
        if self.loop:
            t %= self.total
        elif t >= self.total:
            return len(self.durations) - 1
        for index, duration in enumerate(self.durations):
            if t < duration - 1e-9:
                return index
            t -= duration
        return len(self.durations) - 1


def _load_hero_meta() -> tuple[int, dict[int, str], dict[str, HeroAnimation]]:
    """Read cell size, per-size sheets and animations from generate_warrior_sprites.py."""
    try:
        meta = json.loads(_HERO_META_PATH.read_text(encoding="utf-8"))
        cell = int(meta["cell"])
        sheets = {int(k): str(v) for k, v in meta.get("sheets", {str(cell): _HERO_SHEET_PATH.name}).items()}
        return cell, sheets, {
            name: HeroAnimation(int(a["row"]), tuple(ms / 1000 for ms in a["durations_ms"]), bool(a["loop"]))
            for name, a in meta["animations"].items()
        }
    except (OSError, ValueError, KeyError, TypeError):
        return 192, {192: _HERO_SHEET_PATH.name}, {"idle": HeroAnimation(0, (0.1,) * 16, True)}


HERO_CELL, HERO_SHEETS, _ANIMS = _load_hero_meta()
HERO_ANIMATIONS: dict[str, HeroAnimation] = _ANIMS
IDLE_CYCLE_SECONDS = HERO_ANIMATIONS["idle"].total


def hero_animation_seconds(name: str) -> float:
    """Length of a hero animation in seconds (0.0 when unknown)."""
    anim = HERO_ANIMATIONS.get(name)
    return anim.total if anim else 0.0


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
        self._hero_frames: dict[tuple[str, int], tuple[pygame.Surface, ...]] = {}
        self._hero_sheets: dict[int, pygame.Surface | None] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_player_animation_frames(self, animation: str = "idle",
                                    size: int = 192) -> tuple[pygame.Surface, ...]:
        """Frames of one animation at ``size`` px.

        The sheet whose cell divides ``size`` is used (192 px for combat, 96 px
        for selection), so pixels are shown 1:1 or enlarged by whole numbers.
        Returns an empty tuple when the sheet or the animation is missing.
        """
        key = (animation, size)
        if key in self._hero_frames:
            return self._hero_frames[key]
        anim = HERO_ANIMATIONS.get(animation)
        frames: tuple[pygame.Surface, ...] = ()
        if anim is not None:
            cells_fit = [c for c in HERO_SHEETS if size % c == 0]
            cell = max(cells_fit) if cells_fit else HERO_CELL
            sheet = self._hero_sheet(cell)
            count = len(anim.durations)
            if sheet is not None and sheet.get_width() >= count * cell \
                    and sheet.get_height() >= (anim.row + 1) * cell:
                cells = [sheet.subsurface((i * cell, anim.row * cell, cell, cell)).copy()
                         for i in range(count)]
                if size != cell:
                    cells = [pygame.transform.scale(c, (size, size)) for c in cells]
                frames = tuple(cells)
        self._hero_frames[key] = frames
        return frames

    def get_player_idle_frames(self, size: int = 192) -> tuple[pygame.Surface, ...]:
        """Idle loop frames (kept for callers of the previous API)."""
        return self.get_player_animation_frames("idle", size)

    def get_player_sprite(self, player_name: str, size: int = 128, *, elapsed: float = 0.0,
                          animation: str = "idle") -> pygame.Surface | None:
        """Pick the hero frame for ``animation`` after ``elapsed`` seconds.

        Timing comes from elapsed time, never from the render frame rate.
        Non-looping actions hold their last frame (identical to idle frame 0).
        """
        if player_name in HERO_NAMES:
            anim = HERO_ANIMATIONS.get(animation) or HERO_ANIMATIONS.get("idle")
            name = animation if animation in HERO_ANIMATIONS else "idle"
            frames = self.get_player_animation_frames(name, size)
            if frames and anim is not None:
                return frames[anim.frame_at(elapsed)]
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

    def _hero_sheet(self, cell: int) -> pygame.Surface | None:
        if cell not in self._hero_sheets:
            name = HERO_SHEETS.get(cell)
            path = _HERO_SHEET_PATH if cell == HERO_CELL else _HERO_DIR / (name or "")
            try:
                self._hero_sheets[cell] = pygame.image.load(str(path)) if name else None
            except (pygame.error, OSError, FileNotFoundError):
                self._hero_sheets[cell] = None
        return self._hero_sheets[cell]

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
