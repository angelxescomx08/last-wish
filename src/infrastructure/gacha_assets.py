"""Gachapón pixel art (``assets/gacha/``, written by ``scripts/generate_gacha_sprites.py``).

``load_gacha_assets()`` loads every strip once, slices it and scales it ×``scale``
(nearest neighbour, the same grain as the room) and caches the result. ``None``
when the files are missing or broken, so the scene can fall back to shapes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pygame

GACHA_DIR = Path(__file__).parent.parent.parent / "assets" / "gacha"
CAPSULE_PARTS = ("closed", "top", "bottom")


@dataclass(frozen=True)
class GachaAssets:
    scale: int
    machine: pygame.Surface
    glass: pygame.Surface
    crank: tuple[pygame.Surface, ...]
    small: tuple[pygame.Surface, ...]              # decorative capsules (pile)
    drop: tuple[pygame.Surface, ...]               # prize capsule per tier (drop size)
    big: tuple[dict[str, pygame.Surface], ...]     # per tier: closed / top / bottom (stage size)
    coin: tuple[pygame.Surface, ...]
    flap: tuple[pygame.Surface, ...]
    meta: dict

    def point(self, name: str) -> tuple[int, int]:
        """A native anchor from the JSON (e.g. "slot", "crank"), in scaled px from the machine's corner."""
        x, y = self.meta[name][:2]
        return int(x * self.scale), int(y * self.scale)

    def rect(self, name: str) -> pygame.Rect:
        """A native (x0, y0, x1, y1) box from the JSON, scaled, relative to the machine's corner."""
        x0, y0, x1, y1 = self.meta[name]
        s = self.scale
        return pygame.Rect(x0 * s, y0 * s, (x1 - x0) * s, (y1 - y0) * s)


def _img(name: str) -> pygame.Surface:
    surf = pygame.image.load(str(GACHA_DIR / name))
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        surf = surf.convert_alpha()
    return surf


def _scaled(surf: pygame.Surface, k: int) -> pygame.Surface:
    return pygame.transform.scale(surf, (surf.get_width() * k, surf.get_height() * k))


def _cells(strip: pygame.Surface, w: int, h: int, count: int, row: int = 0) -> list[pygame.Surface]:
    return [strip.subsurface((i * w, row * h, w, h)).copy() for i in range(count)]


@lru_cache(maxsize=1)
def load_gacha_assets() -> GachaAssets | None:
    try:
        meta = json.loads((GACHA_DIR / "gacha.json").read_text(encoding="utf-8"))
        k = max(1, int(meta.get("scale", 2)))
        cs, cn = int(meta["crank_size"]), int(meta["crank_frames"])
        sm, nsm = int(meta["small"]), int(meta["small_colors"])
        dr, big, tiers = int(meta["drop"]), int(meta["big"]), int(meta["tiers"])
        co, nco = int(meta["coin"]), int(meta["coin_frames"])
        flap = _img("flap.png")
        fw = flap.get_width() // 3
        big_strip = _img("capsule_big.png")
        return GachaAssets(
            scale=k,
            machine=_scaled(_img("machine.png"), k),
            glass=_scaled(_img("glass.png"), k),
            crank=tuple(_scaled(c, k) for c in _cells(_img("crank.png"), cs, cs, cn)),
            small=tuple(_scaled(c, k) for c in _cells(_img("capsule_small.png"), sm, sm, nsm)),
            drop=tuple(_scaled(c, k) for c in _cells(_img("capsule.png"), dr, dr, tiers)),
            big=tuple({part: _scaled(c, k) for part, c in zip(CAPSULE_PARTS, _cells(big_strip, big, big, 3, t))}
                      for t in range(tiers)),
            coin=tuple(_scaled(c, k) for c in _cells(_img("coin.png"), co, co, nco)),
            flap=tuple(_scaled(c, k) for c in _cells(flap, fw, flap.get_height(), 3)),
            meta=meta,
        )
    except (OSError, ValueError, KeyError, TypeError, pygame.error):
        return None
