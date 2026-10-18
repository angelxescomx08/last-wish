"""Sprite loader — loads, scales, and caches 32×32 PNG sprites from the
Dungeon Crawl Stone Soup asset pack.

Sprites are scaled with nearest-neighbour to preserve pixel-art crispness.
All lookups are by display name (Spanish), matching Player.name and Enemy.name.
Returns None gracefully when a sprite file is missing or pygame fails.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

_ASSETS = (
    Path(__file__).parent.parent.parent
    / "assets"
    / "dungeon-crawl-stone-soup-full"
)

_HERO_DIR = _ASSETS.parent / "characters"
_HERO_META_PATH = _HERO_DIR / "warrior_sheet.json"

# Player display name -> hero sprite set (files <id>_sheet*.png / <id>_sheet.json)
HERO_IDS: dict[str, str] = {
    "La Guerrera": "warrior", "El Guerrero": "warrior",
    "El Mago": "mage",
    "La Pícara": "rogue", "El Pícaro": "rogue",
}
HERO_NAMES = tuple(HERO_IDS)


@dataclass(frozen=True)
class HeroAnimation:
    """One row of a hero sheet written by generate_<hero>_sprites.py."""
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


@dataclass(frozen=True)
class HeroSheets:
    cell: int                                   # largest cell size (px)
    sheets: dict[int, str]                      # cell size -> file name
    animations: dict[str, HeroAnimation]
    strike_frame: int | None = None             # attack frame where the weapon connects
    strike_point: tuple[float, float] | None = None  # weapon contact on the native 96 px canvas
    cast_frame: int | None = None               # spell release within the cast clip
    cast_point: tuple[float, float] | None = None    # spell release on the native 96 px canvas


def _load_hero_meta(hero: str = "warrior") -> HeroSheets:
    """Read cell size, per-size sheets and animations of one hero."""
    path = _HERO_META_PATH if hero == "warrior" else _HERO_DIR / f"{hero}_sheet.json"
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        cell = int(meta["cell"])
        sheets = {int(k): str(v) for k, v in meta.get("sheets", {str(cell): f"{hero}_sheet.png"}).items()}
        event = meta.get("events", {}).get("attack", {})
        strike = event.get("strike_frame")
        point = event.get("strike_point")
        strike_point = (float(point[0]), float(point[1])) if point is not None and len(point) == 2 else None
        cast_event = meta.get("events", {}).get("cast", {})
        cast_frame = cast_event.get("cast_frame")
        point = cast_event.get("cast_point")
        cast_point = (float(point[0]), float(point[1])) if point is not None and len(point) == 2 else None
        return HeroSheets(cell, sheets, {
            name: HeroAnimation(int(a["row"]), tuple(ms / 1000 for ms in a["durations_ms"]), bool(a["loop"]))
            for name, a in meta["animations"].items()
        }, int(strike) if strike is not None else None, strike_point,
            int(cast_frame) if cast_frame is not None else None, cast_point)
    except (OSError, ValueError, KeyError, TypeError):
        return HeroSheets(192, {192: f"{hero}_sheet.png"}, {"idle": HeroAnimation(0, (0.1,) * 16, True)})


HEROES: dict[str, HeroSheets] = {hero: _load_hero_meta(hero) for hero in sorted(set(HERO_IDS.values()))}

# Warrior aliases kept for existing callers
HERO_CELL = HEROES["warrior"].cell
HERO_SHEETS = HEROES["warrior"].sheets
HERO_ANIMATIONS: dict[str, HeroAnimation] = HEROES["warrior"].animations
IDLE_CYCLE_SECONDS = HERO_ANIMATIONS["idle"].total


def hero_id_for(player_name: str) -> str | None:
    """Hero sprite set used by a player display name, or None for plain sprites."""
    return HERO_IDS.get(player_name)


def has_hero_sprites(player_name: str) -> bool:
    return player_name in HERO_IDS


def hero_animation_seconds(name: str, hero: str = "warrior") -> float:
    """Length of a hero animation in seconds (0.0 when unknown)."""
    sheets = HEROES.get(hero)
    anim = sheets.animations.get(name) if sheets else None
    return anim.total if anim else 0.0


def hero_strike_seconds(hero: str = "warrior") -> float:
    """Seconds from the start of ``attack`` until the weapon connects (0.0 when the sheet has no event)."""
    sheets = HEROES.get(hero)
    anim = sheets.animations.get("attack") if sheets else None
    if anim is None or sheets.strike_frame is None:
        return 0.0
    return sum(anim.durations[:max(0, min(sheets.strike_frame, len(anim.durations)))])


def hero_strike_point(hero: str = "warrior") -> tuple[float, float] | None:
    """Weapon contact offset from the centre of the 192 px combat sprite.

    Metadata points use the native 96 px canvas. Missing points leave the
    presentation's default effect position unchanged.
    """
    sheets = HEROES.get(hero)
    if sheets is None or sheets.strike_point is None:
        return None
    x, y = sheets.strike_point
    return 2 * x - 96, 2 * y - 96


def hero_cast_seconds(hero: str = "warrior") -> float:
    """Seconds until spell release in ``cast`` (0.0 without an authored event)."""
    sheets = HEROES.get(hero)
    anim = sheets.animations.get("cast") if sheets else None
    if anim is None or sheets.cast_frame is None:
        return 0.0
    return sum(anim.durations[:max(0, min(sheets.cast_frame, len(anim.durations)))])


def hero_cast_point(hero: str = "warrior") -> tuple[float, float] | None:
    """Spell release offset from the centre of the 192 px combat sprite.

    Metadata uses native 96 px coordinates. None preserves default effects.
    """
    sheets = HEROES.get(hero)
    if sheets is None or sheets.cast_point is None:
        return None
    x, y = sheets.cast_point
    return 2 * x - 96, 2 * y - 96


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
    "Amuleto de Vitalidad":  "item/amulet/artefact/urand_vitality.png",
    "Trébol de Siete Hojas": "item/amulet/penta_green.png",
    "Broche de Evasión":     "item/amulet/artefact/urand_brooch_of_shielding_new.png",
    "Cuchillo Arrojadizo":   "item/weapon/knife.png",
    "Ankh":                  "item/amulet/celtic_yellow.png",
    "Espejo Singular":       "item/misc/mirror.png",
    "Panacea":               "item/potion/golden.png",
    "Fuente Eterna":         "item/misc/misc_crystal_new.png",
    "Saco de Trapos":        "item/misc/misc_box.png",
    "Pañuelo del Duelista":  "item/armor/back/cloak_3.png",
    "Garfio":                "item/weapon/ankus.png",
    "Cinta Roja":            "item/amulet/ring_red.png",
    "Bolsillo Roto":         "item/armor/back/cloak_2.png",
    "Daga Partida":          "item/weapon/dagger_old.png",
    "Bolsa de Dagas":        "item/weapon/dagger_6.png",
    "Vaina Afilada":         "item/weapon/elven_dagger.png",
    "Frasco de Veneno":      "item/potion/emerald.png",
    "Colmillo de Víbora":    "item/amulet/bone_gray.png",
    "Máscara del Ladrón":    "item/armor/headgear/green_mask.png",
    "Moneda de la Suerte":   "item/gold/gold_pile_1.png",
    "Herradura de Plata":    "item/ring/silver.png",
    "Guante de Seda":        "item/armor/hands/glove_5.png",
    "Botas Silenciosas":     "item/armor/feet/low_boots.png",
    "Hilo de Araña":         "item/misc/misc_disc_new.png",
    "Llave Maestra":         "item/misc/key.png",
    "Reloj Roto":            "item/misc/misc_lamp_old.png",
    "Interés Compuesto":     "item/gold/gold_pile_25.png",
    "Cicatriz":              "item/amulet/stone_2_red.png",
    "Brazal de Guerra":      "item/armor/hands/gauntlet_1.png",
    "Colmillo de Hierro":    "item/misc/misc_horn.png",
    "Venda Empapada":        "item/scroll/scroll-red.png",
    "Copa de Sangre":        "item/potion/purple_red.png",
    "Estandarte Desgarrado": "item/armor/back/cloak_4.png",
    "Corazón de Titán":      "item/amulet/artefact/urand_bloodlust_new.png",
    "Cartas de Diamante": "item/ring/diamond.png",
    "Sello del Coleccionista": "item/misc/misc_deck_legendary_new.png",
    "Sello del Anticuario": "item/misc/misc_rune.png",
    "Escalera": "item/misc/misc_quad.png",
    "Pieza Única": "item/amulet/crystal_white.png",
    "Tijeras del Sastre": "item/weapon/dagger_7.png",
    "Piedra de Afilar": "item/misc/misc_stone_inert.png",
    "Capa Raída": "item/armor/back/cloak_1_leather.png",
    "Vela Votiva": "item/misc/misc_lamp_new.png",
    "Bandera Blanca": "item/scroll/blank_paper.png",
    "Diente de León": "item/food/fruit.png",
    "Lámpara de Aceite": "item/misc/misc_lantern.png",
    "Fruta Silvestre": "item/food/apple.png",
    "Antídoto": "item/potion/cyan_new.png",
    "Cuerno de Guerra": "item/misc/misc_fan_new.png",
    "Saco de Arena": "item/food/bread_ration_new.png",
    "Ficha de Ajedrez": "item/misc/magic_lamp.png",
    "Pergamino Viejo": "item/scroll/scroll_old.png",
    "Pila Ordenada": "item/misc/misc_deck_new.png",
    "Vendas del Monje": "item/armor/hands/glove_1_new.png",
    "Catalejo": "item/rod/rod_2_new.png",
    "Pata de Conejo": "item/food/chunk.png",
    "Corona de Espinas": "item/armor/headgear/helmet_art_2.png",
    "Amuleto de Escarcha": "item/amulet/stone_1_cyan.png",
    "Lanza de Ruptura": "item/weapon/spear_2_new.png",
    "Péndulo": "item/amulet/cylinder_gray.png",
    "Brazalete del Equilibrio": "item/ring/ring_twisted.png",
    "Cuenco Vacío": "item/misc/misc_disc_old.png",
    "Reloj de Arena": "item/misc/misc_phial.png",
    "Ancla": "item/weapon/war_hammer.png",
    "Cartas Marcadas": "item/misc/misc_deck_rare_new.png",
    "Medalla del Veterano": "item/amulet/face_1_gold.png",
    "Hoja de Laurel": "item/food/lemon_new.png",
    "Pluma de Fénix": "item/amulet/penta_orange.png",
    "Talismán del Último Aliento": "item/amulet/eye_magenta.png",
    "Grillete": "item/weapon/flail_1_new.png",
    "Baraja Mágica": "item/misc/misc_deck_old.png",
    "Batería Arcana": "item/misc/misc_crystal_old.png",
    "Corazón de Piedra": "item/misc/misc_bottle.png",
    "Prisma": "item/amulet/crystal_green.png",
    "Piedra de Toque": "item/amulet/stone_3_magenta.png",
    "Bolsa sin Fondo": "item/misc/misc_deck_legendary_old.png",
    "Contrato Maldito": "item/book/book_of_the_dead_new.png",
    "Dado de Veinte Caras": "item/amulet/stone_2_blue.png",
    "Ampolla de Maná": "item/potion/brilliant_blue_new.png",
    "Bolsa Agujereada": "item/gold/gold_pile_3.png",
    "Cantimplora": "item/potion/clear.png",
    "Vale de Descuento": "item/scroll/scroll-yellow.png",
    "Pico de Minero": "item/weapon/hammer_1_new.png",
    "Hucha": "item/gold/gold_pile_6.png",
    "Calavera Sonriente": "item/food/bone.png",
    "Yunque Portátil": "item/weapon/hammer_2_new.png",
    "Dado Cargado": "item/amulet/stone_1_pink.png",
    "Tarjeta de Socio": "item/scroll/scroll-cyan.png",
    "Trofeo de Caza": "item/armor/headgear/helmet_ego_1.png",
    "Martillo del Herrero": "item/weapon/war_axe_1.png",
    "Lima de Hierro": "item/weapon/ancient_sword.png",
    "Lupa del Tasador": "item/ring/glass.png",
    "Moneda de Dos Caras": "item/gold/gold_pile_2.png",
    "Cadena Rota": "item/armor/torso/chain_mail_1.png",
    "Guantelete de Púas": "item/armor/hands/glove_4_gauntlets.png",
    "Muñequera": "item/armor/hands/glove_2_new.png",
    "Venda de Campaña": "item/scroll/scroll-blue.png",
    "Peto Abollado": "item/armor/torso/banded_mail_1.png",
    "Collar de Colmillos": "item/amulet/cameo_blue.png",
    "Hacha Mellada": "item/weapon/war_axe_2.png",
    "Odre de Sangre": "item/potion/ruby_old.png",
    "Gema de Sangre": "item/amulet/cameo_orange.png",
    "Escudo del Mártir": "item/armor/shields/large_shield_2_new.png",
    "Cáliz Carmesí": "item/potion/magenta_new.png",
    "Tambor de Guerra": "item/armor/shields/buckler_2_new.png",
    "Brasero": "item/misc/misc_lamp_inert.png",
    "Rodela Gastada": "item/armor/shields/shield_3_round.png",
    "Yelmo del Berserker": "item/armor/headgear/helmet_4.png",
    "Runa de Sangre": "item/misc/runes/rune_demonic_2.png",
    "Estandarte de la Legión": "item/armor/torso/animal_skin_1_new.png",
    "Corazón Desbocado": "item/amulet/celtic_blue.png",
    "Hierro Fundido": "item/armor/shields/lshield_dd_dk.png",
    "Yesca": "item/wand/gem_copper_new.png",
    "Concha Marina": "item/amulet/eye_cyan.png",
    "Piedra Pómez": "item/amulet/stone_3_green.png",
    "Pluma de Grifo": "item/amulet/artefact/urand_air_new.png",
    "Varita de Sauce": "item/wand/gem_wood_new.png",
    "Reloj de Agua": "item/potion/sky_blue.png",
    "Sombrero Puntiagudo": "item/armor/headgear/wizard_hat_1.png",
    "Piedra de Lava": "item/amulet/stone_1_green.png",
    "Escoba de Brujo": "item/staff/staff_3.png",
    "Caldero": "item/misc/misc_orb_2.png",
    "Ascua de Volcán": "item/amulet/eye_green.png",
    "Orbe de Tormenta": "item/amulet/artefact/urand_four_winds_new.png",
    "Grimorio en Blanco": "item/book/parchment_new.png",
    "Fuente Menor": "item/potion/potion_sky_blue.png",
    "Cristal de Escarcha": "item/amulet/face_2.png",
    "Lente Prismática": "item/ring/opal.png",
    "Capa del Archimago": "item/armor/torso/robe_art_1.png",
    "Anillo de los Cuatro": "item/ring/artefact/urand_octoring.png",
    "Afiladora de Bolsillo": "item/misc/misc_deck_rare_old.png",
    "Navaja Plegable": "item/weapon/dagger_3.png",
    "Bolsa de Canicas": "item/misc/misc_fan_inert.png",
    "Botas de Ratero": "item/armor/feet/boots_1_brown_new.png",
    "Guante de Ladrón": "item/armor/hands/glove_3_new.png",
    "Veneno de Escorpión": "item/potion/black_new.png",
    "Hilo de Seda Negra": "item/misc/misc_fan_old.png",
    "Dado de Hueso": "item/amulet/ring_cyan.png",
    "Frasco de Neblina": "item/potion/cloudy.png",
    "Ganzúa": "item/misc/misc_phantom_mirror.png",
    "Máscara de Arlequín": "item/armor/headgear/cap_jester.png",
    "Capucha de Sombras": "item/armor/headgear/elven_leather_helm.png",
    "Pañuelo Envenenado": "item/armor/torso/animal_skin_2_new.png",
    "Dagas Gemelas": "item/weapon/orcish_dagger.png",
    "Cola de Zorro": "item/food/sausage.png",
    "Reloj de Bolsillo Robado": "item/misc/misc_phial_inert.png",
    "Medallón Singular": "item/amulet/ring_green.png",
    "Corona del Rey Ladrón": "item/armor/headgear/helmet_art_1.png",
}


RELIC_OWN_DIR = _ASSETS.parent / "relics"
_own_relics: dict[str, str] | None = None


def own_relic_sprites() -> dict[str, str]:
    """Relic name → file of its own sprite in ``assets/relics`` (``relics.json``; cached)."""
    global _own_relics
    if _own_relics is None:
        try:
            _own_relics = json.loads((RELIC_OWN_DIR / "relics.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _own_relics = {}
    return _own_relics


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

@lru_cache(maxsize=6)
def _shared_hero_sheet(path: Path) -> pygame.Surface | None:
    """Keep the three heroes at both native resolutions across scene changes."""
    try:
        return pygame.image.load(str(path))
    except (pygame.error, OSError):
        return None


@lru_cache(maxsize=64)
def _shared_hero_frames(path: Path, cell: int, row: int, count: int,
                        size: int) -> tuple[pygame.Surface, ...]:
    sheet = _shared_hero_sheet(path)
    if sheet is None or sheet.get_width() < count * cell or sheet.get_height() < (row + 1) * cell:
        return ()
    cells = [sheet.subsurface((i * cell, row * cell, cell, cell)).copy() for i in range(count)]
    if size != cell:
        cells = [pygame.transform.scale(frame, (size, size)) for frame in cells]
    return tuple(cells)


def prewarm_hero_assets(on_progress: Callable[[int, int], None] | None = None) -> None:
    """Prepare idles; report completed clips between synchronous decode steps."""
    loader = SpriteLoader()
    total = len(HEROES) * 2
    completed = 0
    for hero in HEROES:
        for size in (96, 192):
            if on_progress is not None:
                on_progress(completed, total)
            loader.get_player_animation_frames("idle", size, hero)
            completed += 1
    if on_progress is not None:
        on_progress(completed, total)


class SpriteLoader:
    """Lazy, size-keyed cache for scaled sprite surfaces.

    All sprites in the source pack are 32×32 pixels. This class scales them
    to the requested size using nearest-neighbour so pixel art stays sharp.
    Sprites are loaded once per (path, size) pair and reused on subsequent calls.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int], pygame.Surface | None] = {}
        self._hero_frames: dict[tuple[str, str, int], tuple[pygame.Surface, ...]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_player_animation_frames(self, animation: str = "idle", size: int = 192,
                                    hero: str = "warrior") -> tuple[pygame.Surface, ...]:
        """Frames of one hero animation at ``size`` px.

        The sheet whose cell divides ``size`` is used (192 px for combat, 96 px
        for selection), so pixels are shown 1:1 or enlarged by whole numbers.
        Returns an empty tuple when the sheet or the animation is missing.
        """
        key = (hero, animation, size)
        if key in self._hero_frames:
            return self._hero_frames[key]
        sheets = HEROES.get(hero)
        anim = sheets.animations.get(animation) if sheets else None
        if sheets is not None and anim is not None:
            cells_fit = [c for c in sheets.sheets if size % c == 0]
            cell = max(cells_fit) if cells_fit else sheets.cell
            name = sheets.sheets.get(cell)
            if name:
                frames = _shared_hero_frames(_HERO_DIR / name, cell, anim.row, len(anim.durations), size)
                self._hero_frames[key] = frames
                return frames
        self._hero_frames[key] = ()
        return ()

    def get_player_idle_frames(self, size: int = 192, hero: str = "warrior") -> tuple[pygame.Surface, ...]:
        """Idle loop frames (kept for callers of the previous API)."""
        return self.get_player_animation_frames("idle", size, hero)

    def get_player_sprite(self, player_name: str, size: int = 128, *, elapsed: float = 0.0,
                          animation: str = "idle") -> pygame.Surface | None:
        """Pick the hero frame for ``animation`` after ``elapsed`` seconds.

        Timing comes from elapsed time, never from the render frame rate.
        Non-looping actions hold their last frame (identical to idle frame 0).
        """
        hero = hero_id_for(player_name)
        if hero is not None:
            anims = HEROES[hero].animations
            name = animation if animation in anims else "idle"
            frames = self.get_player_animation_frames(name, size, hero)
            if frames and name in anims:
                return frames[anims[name].frame_at(elapsed)]
            player_name = {"warrior": "El Guerrero", "rogue": "El Pícaro"}.get(hero, player_name)
        rel = PLAYER_SPRITE_PATHS.get(player_name)
        return self._load(rel, size) if rel else None

    def get_enemy_sprite(self, enemy_name: str, size: int = 96) -> pygame.Surface | None:
        """Return a scaled surface for the named enemy, or None."""
        rel = ENEMY_SPRITE_PATHS.get(enemy_name)
        return self._load(rel, size) if rel else None

    def get_relic_sprite(self, relic_name: str, size: int = 32) -> pygame.Surface | None:
        """Return a scaled surface for the named relic icon, or None.

        The relic's own code-drawn sprite (``assets/relics``, ``scripts/generate_relic_sprites.py``)
        wins over the borrowed Dungeon Crawl item.
        """
        own = own_relic_sprites().get(relic_name)
        if own:
            return self._load(f"../relics/{own}", size)
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

    def _hero_sheet(self, hero: str, cell: int) -> pygame.Surface | None:
        sheets = HEROES.get(hero)
        name = sheets.sheets.get(cell) if sheets else None
        return _shared_hero_sheet(_HERO_DIR / name) if name else None

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
