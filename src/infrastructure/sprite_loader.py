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

CARD_ART_PATHS: dict[str, str] = {
    # Starter
    "golpe_base":    "Minion/minion (1).png",
    "defender_base": "Minion/minion (5).png",
    "embate_base":   "Minion/minion (2).png",
    "guardia_base":  "Minion/minion (6).png",
    # ACERO — attack pack (minion 1–4)
    "a_golpe_ferreo":   "Minion/minion (1).png",
    "a_tajo":           "Minion/minion (2).png",
    "a_arremetida":     "Minion/minion (3).png",
    "a_furia":          "Minion/minion (4).png",
    "a_punio":          "Minion/minion (1).png",
    "a_golpe_pesado":   "Minion/minion (2).png",
    "a_patada":         "Minion/minion (3).png",
    "a_corte_rapido":   "Minion/minion (4).png",
    "a_embestida":      "Minion/minion (1).png",
    "a_gran_golpe":     "Minion/minion (4).png",
    # ESCUDO — defense pack (minion 5–8)
    "e_guardia_solida":  "Minion/minion (5).png",
    "e_escudo_solido":   "Minion/minion (6).png",
    "e_fortaleza":       "Minion/minion (7).png",
    "e_baluarte":        "Minion/minion (8).png",
    "e_parada":          "Minion/minion (5).png",
    "e_capa_hierro":     "Minion/minion (6).png",
    "e_torre":           "Minion/minion (7).png",
    "e_escudo_reactivo": "Minion/minion (5).png",
    "e_agilidad":        "Minion/minion (6).png",
    "e_gran_muralla":    "Minion/minion (8).png",
    # MAGIA — magic pack (minion 7–8 + Alternate 1–3)
    "m_chispa":         "Minion/minion (7).png",
    "m_rayo":           "Minion/minion (8).png",
    "m_absorcion":      "Minion/minion (7).png",
    "m_impulso":        "Minion/minion (6).png",
    "m_torbellino":     "Minion/Alternate (1).png",
    "m_barrera_magica": "Minion/minion (8).png",
    "m_vision":         "Minion/Alternate (2).png",
    "m_hechizo_menor":  "Minion/minion (7).png",
    "m_concentracion":  "Minion/Alternate (3).png",
    "m_conjuro":        "Minion/Alternate (1).png",
    # EPICO — legendary pack (Alternate 1–3 cycling)
    "ep_golpe_mortal":   "Minion/Alternate (1).png",
    "ep_escudo_impenet": "Minion/Alternate (2).png",
    "ep_tormenta":       "Minion/Alternate (3).png",
    "ep_poder_oculto":   "Minion/Alternate (1).png",
    "ep_ejecucion":      "Minion/Alternate (2).png",
    "ep_bastion":        "Minion/Alternate (3).png",
    "ep_descarga":       "Minion/Alternate (1).png",
    "ep_escudo_arcano":  "Minion/Alternate (2).png",
}

# Card component layers (paths relative to _CARD_ASSETS)
CARD_FRAME_PATHS: dict[str, str] = {
    "ATTACK": "Minion/Alternate (1).png",
    "SKILL":  "Minion/Alternate (2).png",
    "POWER":  "Minion/Alternate (3).png",
}

CARD_COMPONENT_PATHS: dict[str, str] = {
    "mana":        "Minion/minion (7).png",   # top decoration — mana cost
    "title":       "Minion/minion (6).png",   # title/name decoration
    "description": "Minion/minion (2).png",   # description box
    "stats":       "Minion/minion (8).png",   # two hexagons: red ATK | green DEF
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

    def get_card_art(self, card_id: str, size: int = 52) -> pygame.Surface | None:
        """Return card art for the given card ID, or None."""
        rel = CARD_ART_PATHS.get(card_id)
        return self._load_card(rel, size) if rel else None

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
