"""Pooled one-shot particles for bursts, sparks and glows (pack opening, rewards).

Complements :mod:`particles` (continuous emitters in native art pixels): here
particles live in *screen* pixels and each one carries its own palette, size,
drag, gravity and style, so a single pool mixes confetti, sparks and soft glows.

Same low-CPU design as ``particles.py``:
* fixed-capacity pool stored as parallel lists, dead particles swap-removed;
* ``dt`` is clamped, so a hitch never teleports or multiplies particles;
* glows are cached additive sprites (``BLEND_RGB_ADD``) — no per-pixel work.

Styles:
  SQUARE — crisp pixel square that shrinks over its life (confetti, dust);
  SPARK  — short streak along the velocity (sparks, shards);
  GLOW   — soft additive light blob (motes, flashes).
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import pygame

Color = tuple[int, int, int]
Palette = tuple[Color, ...]
MAX_DT = 0.1

SQUARE, SPARK, GLOW = 0, 1, 2
_GLOW_LEVELS = 6          # brightness steps for fading glows (keeps the cache small)
_GLOW_BASE_R = 24         # glows are drawn once at this radius, then smooth-scaled


@lru_cache(maxsize=256)
def soft_glow(color: Color, radius: int) -> pygame.Surface:
    """Soft round light of ``color`` (black outside), meant for ``BLEND_RGB_ADD``.

    Drawn once at a small radius with a quadratic falloff and smooth-scaled, so
    even a 300 px halo costs one small draw and one scale, then it is cached.
    """
    radius = max(1, int(radius))
    base = pygame.Surface((_GLOW_BASE_R * 2, _GLOW_BASE_R * 2))
    base.fill((0, 0, 0))
    r0, g0, b0 = color
    for r in range(_GLOW_BASE_R, 0, -1):
        k = (1.0 - r / _GLOW_BASE_R) ** 2
        pygame.draw.circle(base, (int(r0 * k), int(g0 * k), int(b0 * k)),
                           (_GLOW_BASE_R, _GLOW_BASE_R), r)
    if radius == _GLOW_BASE_R:
        return base
    return pygame.transform.smoothscale(base, (radius * 2, radius * 2))


def scaled(color: Color, k: float) -> Color:
    """``color`` multiplied by ``k`` (clamped to 0..255)."""
    k = max(0.0, k)
    return (min(255, int(color[0] * k)), min(255, int(color[1] * k)), min(255, int(color[2] * k)))


class BurstParticles:
    """Pool of independent particles; spawn with :meth:`emit`, :meth:`burst`, :meth:`implode`."""

    def __init__(self, capacity: int = 600, *, seed: int = 0) -> None:
        self.capacity = max(0, int(capacity))
        self._rng = random.Random(seed)
        n = self.capacity
        self._x = [0.0] * n
        self._y = [0.0] * n
        self._vx = [0.0] * n
        self._vy = [0.0] * n
        self._age = [0.0] * n
        self._life = [1.0] * n
        self._size = [1.0] * n
        self._drag = [0.0] * n
        self._grav = [0.0] * n
        self._style = [SQUARE] * n
        self._pal: list[Palette] = [((255, 255, 255),)] * n
        self._n = 0

    # ------------------------------------------------------------------ state

    @property
    def count(self) -> int:
        """Number of live particles."""
        return self._n

    def positions(self) -> list[tuple[float, float]]:
        return [(self._x[i], self._y[i]) for i in range(self._n)]

    def clear(self) -> None:
        self._n = 0

    # ------------------------------------------------------------------ spawning

    def emit(self, x: float, y: float, vx: float, vy: float, *, life: float, palette: Palette,
             size: float = 3.0, style: int = SQUARE, drag: float = 0.0, gravity: float = 0.0) -> bool:
        """Spawn one particle. Returns False when the pool is full."""
        if self._n >= self.capacity or not palette:
            return False
        i = self._n
        self._x[i], self._y[i] = float(x), float(y)
        self._vx[i], self._vy[i] = float(vx), float(vy)
        self._age[i] = 0.0
        self._life[i] = max(1e-3, float(life))
        self._size[i] = max(0.5, float(size))
        self._drag[i] = max(0.0, float(drag))
        self._grav[i] = float(gravity)
        self._style[i] = style
        self._pal[i] = palette
        self._n += 1
        return True

    def burst(self, x: float, y: float, n: int, *, palette: Palette,
              speed: tuple[float, float] = (60.0, 240.0),
              angle: tuple[float, float] = (0.0, math.tau),
              life: tuple[float, float] = (0.4, 0.9),
              size: tuple[float, float] = (2.0, 4.0),
              style: int = SQUARE, drag: float = 2.0, gravity: float = 0.0,
              spread: float = 0.0) -> int:
        """Radial explosion from (x, y); ``spread`` jitters the start point. Returns how many spawned."""
        r = self._rng
        made = 0
        for _ in range(max(0, n)):
            a = r.uniform(*angle)
            s = r.uniform(*speed)
            ox = r.uniform(-spread, spread) if spread else 0.0
            oy = r.uniform(-spread, spread) if spread else 0.0
            if not self.emit(x + ox, y + oy, math.cos(a) * s, math.sin(a) * s,
                             life=r.uniform(*life), palette=palette, size=r.uniform(*size),
                             style=style, drag=drag, gravity=gravity):
                break
            made += 1
        return made

    def implode(self, x: float, y: float, n: int, *, palette: Palette,
                radius: tuple[float, float] = (90.0, 180.0),
                life: tuple[float, float] = (0.3, 0.55),
                size: tuple[float, float] = (1.5, 3.0), style: int = SPARK) -> int:
        """Particles born on a ring that reach (x, y) exactly as they die (charging energy)."""
        r = self._rng
        made = 0
        for _ in range(max(0, n)):
            a = r.uniform(0.0, math.tau)
            d = r.uniform(*radius)
            t = r.uniform(*life)
            if not self.emit(x + math.cos(a) * d, y + math.sin(a) * d,
                             -math.cos(a) * d / t, -math.sin(a) * d / t,
                             life=t, palette=palette, size=r.uniform(*size), style=style):
                break
            made += 1
        return made

    # ------------------------------------------------------------------ simulation

    def _kill(self, i: int) -> None:
        last = self._n - 1
        if i != last:
            for arr in (self._x, self._y, self._vx, self._vy, self._age, self._life,
                        self._size, self._drag, self._grav, self._style, self._pal):
                arr[i] = arr[last]
        self._n = last

    def update(self, dt: float) -> None:
        dt = min(MAX_DT, max(0.0, dt))
        if dt == 0.0:
            return
        x, y, vx, vy = self._x, self._y, self._vx, self._vy
        age, life, drag, grav = self._age, self._life, self._drag, self._grav
        i = 0
        while i < self._n:
            age[i] += dt
            if age[i] >= life[i]:
                self._kill(i)
                continue
            if drag[i]:
                k = max(0.0, 1.0 - drag[i] * dt)
                vx[i] *= k
                vy[i] *= k
            vy[i] += grav[i] * dt
            x[i] += vx[i] * dt
            y[i] += vy[i] * dt
            i += 1

    # ------------------------------------------------------------------ drawing

    def draw(self, surface: pygame.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        ox, oy = offset
        fill, blit, line = surface.fill, surface.blit, pygame.draw.line
        x, y, vx, vy = self._x, self._y, self._vx, self._vy
        age, life, size, style, pal = self._age, self._life, self._size, self._style, self._pal
        for i in range(self._n):
            t = age[i] / life[i]
            p = pal[i]
            n = len(p)
            k = int(t * n)
            col = p[k if k < n else n - 1]
            px, py = x[i] + ox, y[i] + oy
            st = style[i]
            if st == GLOW:
                level = max(1, int((1.0 - t) * _GLOW_LEVELS + 0.999))
                r = max(2, int(size[i]))
                g = soft_glow(scaled(col, level / _GLOW_LEVELS), r)
                blit(g, (int(px) - r, int(py) - r), special_flags=pygame.BLEND_RGB_ADD)
            elif st == SPARK:
                w = max(1, int(size[i] * (1.0 - 0.6 * t)))
                line(surface, col, (px, py), (px - vx[i] * 0.035, py - vy[i] * 0.035), w)
            else:
                s = max(1, int(size[i] * (1.0 - 0.7 * t) + 0.5))
                fill(col, (int(px) - s // 2, int(py) - s // 2, s, s))
