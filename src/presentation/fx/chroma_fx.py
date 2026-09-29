"""Chroma visuals for cards and relics (golden now; more kinds later).

Everything is keyed by :class:`~src.domain.chroma.Chroma` through
``STYLES``, so a new chroma only needs a ``ChromaStyle`` entry here.

Layers (cheap, cached; only a small blit or two per frame):
* ``gild_frame``      — static recolour of a card frame (silver/iron → gold),
                         baked once into the cached card face;
* ``sheen_frame``     — a diagonal light band that sweeps the card every few
                         seconds (pre-rendered frames, added with BLEND_RGB_ADD
                         onto the card copy, so it is clipped by the card alpha);
* ``draw_twinkles``   — little 4-point stars that pulse at fixed spots;
* ``draw_halo``       — an edge-lit aura hugging the silhouette (rim + haze), breathing;
* ``draw_motes``      — stateless golden motes rising around the card;
* ``draw_chroma_box`` — the same language for relic boxes and tiles.
"""
from __future__ import annotations

import math
import random
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache

import pygame

from src.domain.chroma import Chroma

Color = tuple[int, int, int]


@dataclass(frozen=True)
class ChromaStyle:
    bright: Color
    main: Color
    dark: Color
    frame_mult: Color   # multiplied into a card frame (recolours it)
    frame_add: Color    # then added (warms the shadows)
    sheen: Color        # peak colour of the sweeping band
    glow: Color         # halo colour


STYLES: dict[Chroma, ChromaStyle] = {
    Chroma.GOLDEN: ChromaStyle(
        bright=(255, 246, 196), main=(255, 204, 72), dark=(120, 74, 10),
        frame_mult=(255, 214, 122), frame_add=(52, 32, 0),
        sheen=(255, 232, 160), glow=(255, 168, 36),
    ),
}

SHEEN_CYCLE = 3.2      # seconds between sweeps
SHEEN_SWEEP = 1.1      # seconds a sweep takes
SHEEN_FRAMES = 28
_TWINKLES = ((0.18, 0.13, 0.0), (0.83, 0.34, 2.1), (0.25, 0.70, 4.2), (0.76, 0.84, 1.3),
             (0.55, 0.22, 3.3), (0.12, 0.47, 5.1), (0.66, 0.60, 0.7))


def style(chroma: Chroma) -> ChromaStyle:
    return STYLES[chroma]


def now() -> float:
    """Animation clock in seconds."""
    return pygame.time.get_ticks() / 1000.0


def _scaled(color: Color, k: float) -> Color:
    return (min(255, int(color[0] * k)), min(255, int(color[1] * k)), min(255, int(color[2] * k)))


def _lerp(a: Color, b: Color, k: float) -> Color:
    return (int(a[0] + (b[0] - a[0]) * k), int(a[1] + (b[1] - a[1]) * k), int(a[2] + (b[2] - a[2]) * k))


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------

def gild_frame(frame: pygame.Surface, chroma: Chroma) -> pygame.Surface:
    """Recoloured copy of a (SRCALPHA) card frame."""
    st = STYLES[chroma]
    out = frame.copy()
    out.fill((*st.frame_mult, 255), special_flags=pygame.BLEND_RGBA_MULT)
    out.fill((*st.frame_add, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return out


# ---------------------------------------------------------------------------
# Sweeping sheen
# ---------------------------------------------------------------------------

@lru_cache(maxsize=48)
def _sheen_frames(w: int, h: int, chroma: Chroma) -> tuple[pygame.Surface, ...]:
    st = STYLES[chroma]
    slant = h * 0.45
    bw = max(5.0, w * 0.10)
    frames = []
    for i in range(SHEEN_FRAMES):
        u = i / (SHEEN_FRAMES - 1)
        cx = -bw + u * (w + slant + 2 * bw)
        f = pygame.Surface((max(1, w), max(1, h)))
        f.fill((0, 0, 0))
        for hw, k in ((bw, 0.22), (bw * 0.6, 0.45), (bw * 0.28, 0.85)):
            pygame.draw.polygon(f, _scaled(st.sheen, k), [
                (cx - hw, 0), (cx + hw, 0), (cx + hw - slant, h), (cx - hw - slant, h)])
        frames.append(f)
    return tuple(frames)


def sheen_frame(w: int, h: int, chroma: Chroma, t: float) -> pygame.Surface | None:
    """Additive band for time ``t`` (None between sweeps)."""
    phase = t % SHEEN_CYCLE
    if phase >= SHEEN_SWEEP or w <= 0 or h <= 0:
        return None
    frames = _sheen_frames(w, h, chroma)
    return frames[min(SHEEN_FRAMES - 1, int(phase / SHEEN_SWEEP * SHEEN_FRAMES))]


@lru_cache(maxsize=48)
def _box_mask(w: int, h: int, radius: int) -> pygame.Surface:
    m = pygame.Surface((max(1, w), max(1, h)))
    m.fill((0, 0, 0))
    pygame.draw.rect(m, (255, 255, 255), (0, 0, w, h), border_radius=radius)
    return m


@lru_cache(maxsize=48)
def _box_sheen_frames(w: int, h: int, chroma: Chroma, radius: int) -> tuple[pygame.Surface, ...]:
    out = []
    mask = _box_mask(w, h, radius)
    for f in _sheen_frames(w, h, chroma):
        g = f.copy()
        g.blit(mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        out.append(g)
    return tuple(out)


# ---------------------------------------------------------------------------
# Twinkles and halo
# ---------------------------------------------------------------------------

def draw_twinkles(surface: pygame.Surface, rect: pygame.Rect, chroma: Chroma, t: float,
                  scale: float = 1.0) -> None:
    st = STYLES[chroma]
    for fx, fy, ph in _TWINKLES:
        k = math.sin(t * 2.6 + ph)
        if k <= 0.35:
            continue
        k = (k - 0.35) / 0.65
        r = max(2, int((2 + 5 * k) * scale))
        x = rect.x + int(fx * rect.w)
        y = rect.y + int(fy * rect.h)
        col = _lerp(st.main, st.bright, k)
        pygame.draw.line(surface, col, (x - r, y), (x + r, y), 1)
        pygame.draw.line(surface, col, (x, y - r), (x, y + r), 1)
        d = max(1, r // 3)
        pygame.draw.line(surface, st.bright, (x - d, y - d), (x + d, y + d), 1)
        pygame.draw.line(surface, st.bright, (x - d, y + d), (x + d, y - d), 1)
        surface.fill(st.bright, (x - 1, y - 1, 2, 2))


def _blur(surf: pygame.Surface, levels: int) -> pygame.Surface:
    """Smooth blur by a downscale pyramid (halve ``levels`` times, then back up).

    Much softer than one big down/up jump, which leaves a visible box edge.
    """
    sizes = []
    out = surf
    for _ in range(levels):
        sizes.append(out.get_size())
        out = pygame.transform.smoothscale(out, (max(1, out.get_width() // 2), max(1, out.get_height() // 2)))
    for size in reversed(sizes):
        out = pygame.transform.smoothscale(out, size)
    return out


@lru_cache(maxsize=48)
def _aura(w: int, h: int, chroma: Chroma, level: int, radius: int) -> pygame.Surface:
    """Edge-lit glow around a (w, h) rounded rect: bright rim that fades out smoothly.

    Two blurred layers are added — a tight bright rim and a wide faint haze — and
    the inside is cleared, so the light hugs the silhouette instead of filling a box.
    """
    st = STYLES[chroma]
    pad = max(12, min(w, h) // 4)
    size = (w + 2 * pad, h + 2 * pad)
    k = level / 4
    rim = pygame.Surface(size)
    rim.fill((0, 0, 0))
    pygame.draw.rect(rim, _scaled(st.glow, 1.0 * k), (pad - 2, pad - 2, w + 4, h + 4),
                     max(2, pad // 5), border_radius=radius + 2)
    rim = _blur(rim, 2)
    haze = pygame.Surface(size)
    haze.fill((0, 0, 0))
    pygame.draw.rect(haze, _scaled(st.glow, 0.55 * k), (pad, pad, w, h), border_radius=radius)
    haze = _blur(haze, 4)
    rim.blit(haze, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    inset = max(2, min(w, h) // 20)
    pygame.draw.rect(rim, (0, 0, 0), (pad + inset, pad + inset, w - 2 * inset, h - 2 * inset),
                     border_radius=max(0, radius - inset))
    return rim


_card_aura_cache: "OrderedDict[tuple, pygame.Surface]" = OrderedDict()
_CARD_AURA_MAX = 64


def silhouette_aura(body: pygame.Surface, color: Color, level: int, key: tuple) -> tuple[pygame.Surface, int]:
    """Aura built from a sprite's own silhouette (its alpha), so it hugs the shape.

    Card frames do not fill their rectangle (transparent margins), so a rect glow
    shows a box around them. Here the opaque pixels are blurred twice (tight rim +
    wide haze), tinted and the silhouette itself is subtracted. Cached by ``key``
    (size + frame), colour and brightness level. Returns the surface and its padding.
    Reused for chromas and for keyword highlights (Combo ready).
    """
    ck = (key, color, level)
    hit = _card_aura_cache.get(ck)
    w, h = body.get_size()
    pad = max(12, min(w, h) // 4)
    if hit is not None:
        _card_aura_cache.move_to_end(ck)
        return hit, pad
    k = level / 4
    white = body.copy()
    white.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
    base = pygame.Surface((w + 2 * pad, h + 2 * pad))
    base.fill((0, 0, 0))
    base.blit(white, (pad, pad))
    rim = _blur(base, 2)
    rim.fill(_scaled(color, 1.0 * k), special_flags=pygame.BLEND_RGB_MULT)
    haze = _blur(base, 4)
    haze.fill(_scaled(color, 0.6 * k), special_flags=pygame.BLEND_RGB_MULT)
    rim.blit(haze, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    rim.blit(base, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
    _card_aura_cache[ck] = rim
    if len(_card_aura_cache) > _CARD_AURA_MAX:
        _card_aura_cache.popitem(last=False)
    return rim, pad


def card_aura(body: pygame.Surface, chroma: Chroma, level: int, key: tuple) -> tuple[pygame.Surface, int]:
    """Chroma-coloured silhouette aura (see ``silhouette_aura``)."""
    return silhouette_aura(body, STYLES[chroma].glow, level, key)


def draw_silhouette_aura(surface: pygame.Surface, body: pygame.Surface, center: tuple[float, float],
                         color: Color, t: float, key: tuple, angle: float = 0.0, speed: float = 1.8) -> None:
    """Breathing aura of ``color`` behind a sprite (additive); ``angle`` tilts it with the sprite."""
    breath = 0.5 + 0.5 * math.sin(t * speed)
    level = 2 + int(breath * 1.999)                    # 2..3
    aura, _ = silhouette_aura(body, color, level, key)
    if angle:
        aura = pygame.transform.rotozoom(aura, angle, 1.0)
    surface.blit(aura, aura.get_rect(center=(int(center[0]), int(center[1]))),
                 special_flags=pygame.BLEND_RGB_ADD)


def draw_card_aura(surface: pygame.Surface, body: pygame.Surface, center: tuple[float, float],
                   chroma: Chroma, t: float, key: tuple, angle: float = 0.0) -> None:
    """Breathing chroma aura behind a card (additive); ``angle`` tilts it with the card."""
    draw_silhouette_aura(surface, body, center, STYLES[chroma].glow, t, key, angle)


def draw_halo(surface: pygame.Surface, center: tuple[int, int], size: tuple[int, int],
              chroma: Chroma, t: float, *, strong: bool = True, radius: int = 10) -> None:
    """Soft glow hugging a card or box (additive), breathing slowly."""
    breath = 0.5 + 0.5 * math.sin(t * 1.8)
    level = (2 if strong else 1) + int(breath * 1.999)       # 2..3 strong, 1..2 soft
    g = _aura(int(size[0]), int(size[1]), chroma, level, radius)
    surface.blit(g, g.get_rect(center=(int(center[0]), int(center[1]))),
                 special_flags=pygame.BLEND_RGB_ADD)


# Procedural motes: deterministic, stateless (x fraction, period s, phase, size, sway)
_MOTE_RNG = random.Random(1717)
_MOTES = tuple((_MOTE_RNG.uniform(-0.08, 1.08), _MOTE_RNG.uniform(1.6, 3.0), _MOTE_RNG.uniform(0, 3.0),
                _MOTE_RNG.uniform(1.5, 3.2), _MOTE_RNG.uniform(2.0, 7.0)) for _ in range(18))


def draw_motes(surface: pygame.Surface, rect: pygame.Rect, chroma: Chroma, t: float, *,
               count: int = 14, scale: float = 1.0) -> None:
    """Golden motes rising along and around ``rect`` (drawn over it, no state kept)."""
    st = STYLES[chroma]
    rise = rect.h * 0.95 + 24 * scale
    for i, (fx, period, phase, sz, sway) in enumerate(_MOTES[:count]):
        u = ((t + phase) / period) % 1.0
        a = math.sin(math.pi * u)
        x = rect.left + fx * rect.w + math.sin((t + phase) * 2.1 + i) * sway * scale
        y = rect.bottom + 4 * scale - u * rise
        s = max(1, int(sz * scale * (0.45 + 0.55 * a)))
        col = _lerp(st.dark, st.bright, a) if a < 0.75 else st.bright
        surface.fill(col, (int(x) - s // 2, int(y) - s // 2, s, s))
        if a > 0.55:
            gr = max(2, int(s * 2.2))
            surface.blit(_mote_glow(chroma, gr), (int(x) - gr, int(y) - gr),
                         special_flags=pygame.BLEND_RGB_ADD)


@lru_cache(maxsize=32)
def _mote_glow(chroma: Chroma, r: int) -> pygame.Surface:
    g = pygame.Surface((r * 2, r * 2))
    g.fill((0, 0, 0))
    col = STYLES[chroma].glow
    for rr in range(r, 0, -1):
        k = (1 - rr / r) ** 2 * 0.7
        pygame.draw.circle(g, _scaled(col, k), (r, r), rr)
    return g


# ---------------------------------------------------------------------------
# Composites
# ---------------------------------------------------------------------------

def animate_card_face(body: pygame.Surface, chroma: Chroma, t: float,
                      base_w: int = 140) -> pygame.Surface:
    """Copy of a card face with the sheen and twinkles for time ``t``."""
    out = body.copy()
    w, h = out.get_size()
    band = sheen_frame(w, h, chroma, t)
    if band is not None:
        out.blit(band, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    draw_twinkles(out, out.get_rect(), chroma, t, scale=max(0.5, w / base_w))
    return out


def draw_chroma_box(surface: pygame.Surface, rect: pygame.Rect, chroma: Chroma, t: float,
                    *, radius: int = 6, halo: bool = True) -> None:
    """Chroma treatment for a relic box/tile, drawn over its content."""
    st = STYLES[chroma]
    if halo:
        draw_halo(surface, rect.center, rect.size, chroma, t, strong=False, radius=radius)
    phase = t % SHEEN_CYCLE
    if phase < SHEEN_SWEEP and rect.w > 0 and rect.h > 0:
        frames = _box_sheen_frames(rect.w, rect.h, chroma, radius)
        surface.blit(frames[min(SHEEN_FRAMES - 1, int(phase / SHEEN_SWEEP * SHEEN_FRAMES))],
                     rect.topleft, special_flags=pygame.BLEND_RGB_ADD)
    pulse = 0.5 + 0.5 * math.sin(t * 2.2)
    pygame.draw.rect(surface, _lerp(st.main, st.bright, pulse * 0.6), rect, 2, border_radius=radius)
    if rect.w > 8 and rect.h > 8:
        pygame.draw.rect(surface, st.dark, rect.inflate(-4, -4), 1, border_radius=max(0, radius - 2))
    scale = min(1.0, max(0.5, rect.w / 140))
    draw_twinkles(surface, rect, chroma, t, scale=scale)
    draw_motes(surface, rect, chroma, t, count=6 if rect.w < 100 else 10, scale=scale)
