"""Card frames, pack art and card illustrations (assets/cards-v2), cached per size.

Frames are high-resolution paintings (~1064 x 1478), so they are reduced with
``smoothscale`` (area filtering) once per requested size; nearest-neighbour
would alias their fine ornaments at card size. Zones for text and art come from
``assets/cards-v2/layout.json`` (see scripts/measure_card_frames.py) as
fractions of the frame, so any card size works.

Illustrations: ``assets/cards-v2/art/<card id>.png`` when present; otherwise a
provisional pixel-art icon chosen by card type from the Dungeon Crawl pack.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pygame

CARDS_DIR = Path(__file__).parent.parent.parent / "assets" / "cards-v2"
LAYOUT_PATH = CARDS_DIR / "layout.json"
ART_DIR = CARDS_DIR / "art"
_DCSS = Path(__file__).parent.parent.parent / "assets" / "dungeon-crawl-stone-soup-full"
CARD_BACK_PATH = (Path(__file__).parent.parent.parent / "assets" / "Card Sprites" / "Card Back"
                  / "crystal (1).png")

# Provisional illustrations by card type until real art exists in ART_DIR
PLACEHOLDER_ART: dict[str, str] = {
    "ATTACK": "item/weapon/long_sword_1_new.png",
    "SKILL":  "item/armor/shields/shield_2_kite.png",
    "POWER":  "item/misc/misc_orb.png",
}


@lru_cache(maxsize=1)
def card_layout() -> dict | None:
    try:
        return json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load(path: Path) -> pygame.Surface | None:
    try:
        surf = pygame.image.load(str(path))
    except (pygame.error, OSError, FileNotFoundError):
        return None
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        surf = surf.convert_alpha()
    return surf


@lru_cache(maxsize=64)
def card_frame(rarity: str, w: int, h: int) -> pygame.Surface | None:
    """Rarity frame scaled to (w, h), or None when the asset is missing."""
    layout = card_layout()
    info = layout["frames"].get(rarity) if layout else None
    src = _load(CARDS_DIR / info["file"]) if info else None
    if src is None:
        return None
    return pygame.transform.smoothscale(src, (w, h))


@lru_cache(maxsize=8)
def card_back(w: int, h: int) -> pygame.Surface | None:
    """Face-down card (crystal back, same aspect as the frames) scaled to (w, h)."""
    src = _load(CARD_BACK_PATH)
    if src is None:
        return None
    return pygame.transform.smoothscale(src, (max(1, w), max(1, h)))


@lru_cache(maxsize=16)
def pack_art(theme: str, height: int) -> pygame.Surface | None:
    """Closed booster for a PackTheme value, scaled to ``height`` keeping its aspect ratio."""
    layout = card_layout()
    rel = layout["packs"].get(theme) if layout else None
    src = _load(CARDS_DIR / rel) if rel else None
    if src is None:
        return None
    bounds = src.get_bounding_rect(min_alpha=16)
    src = src.subsurface(bounds).copy()
    w = max(1, round(src.get_width() * height / src.get_height()))
    return pygame.transform.smoothscale(src, (w, height))


@lru_cache(maxsize=128)
def card_illustration(card_id: str, card_type: str, w: int, h: int) -> pygame.Surface | None:
    """Art for the illustration window, cropped to fill (w, h) without distortion.

    Pixel-art icons are enlarged by the largest whole factor that fits, so their
    pixels stay square; painted art is scaled smoothly to cover the window.
    """
    custom = _load(ART_DIR / f"{card_id}.png")
    if custom is not None:
        cw, ch = custom.get_size()
        k = max(w / cw, h / ch)
        big = pygame.transform.smoothscale(custom, (max(w, round(cw * k)), max(h, round(ch * k))))
        x, y = (big.get_width() - w) // 2, (big.get_height() - h) // 2
        return big.subsurface((x, y, w, h)).copy()
    rel = PLACEHOLDER_ART.get(card_type)
    icon = _load(_DCSS / rel) if rel else None
    if icon is None:
        return None
    k = max(1, min(w // icon.get_width(), h // icon.get_height()))
    return pygame.transform.scale(icon, (icon.get_width() * k, icon.get_height() * k))
