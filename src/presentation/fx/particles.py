"""Reusable pixel-art particle system (rain, splashes, embers, dust, drips, ...).

Design for low CPU use:
* fixed-capacity pools stored as parallel lists — no object per particle and
  no allocation after construction; dead particles are swap-removed in O(1);
* particles live in *native* art pixels and are drawn as small ``fill`` rects
  scaled by a whole number, so they match the pixel grid of the art;
* ``dt`` is clamped, so a long hitch never spawns an avalanche of particles.

A system is configured with an :class:`EmitterConfig`. It can hand particles
that cross ``floor_y`` to a child system (``on_floor``), e.g. rain -> splash.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

Color = tuple[int, int, int]
MAX_DT = 0.1


@dataclass(frozen=True)
class EmitterConfig:
    """How particles are born and move. Units: native pixels and seconds."""
    rate: float                                   # particles per second (0 = bursts only)
    lifetime: tuple[float, float]                 # min, max seconds
    area: tuple[float, float, float, float]       # spawn rect: x, y, w, h
    vx: tuple[float, float] = (0.0, 0.0)
    vy: tuple[float, float] = (0.0, 0.0)
    gravity: float = 0.0                          # px/s^2, + = down
    wobble: float = 0.0                           # sideways sway amplitude, px/s
    colors: tuple[Color, ...] = ((255, 255, 255),)  # colour over lifetime, birth -> death
    size: int = 1                                 # square size in native px
    length: int = 1                               # vertical streak length in native px
    trail: int = 0                                # extra pixels drawn behind, following the velocity
    trail_color: Color | None = None              # colour of the trail (default: last colour)
    floor_y: float | None = None                  # dies when crossing this y
    burst: int = 0                                # particles handed to ``on_floor`` on landing
    capacity: int = 200


class ParticleSystem:
    """Pooled particles drawn as crisp rects at ``scale``x.

    ``clip`` (native rect) limits drawing, e.g. rain seen only through a window.
    """

    def __init__(self, config: EmitterConfig, *, scale: int = 2, seed: int = 0,
                 clip: tuple[int, int, int, int] | None = None, on_floor: ParticleSystem | None = None,
                 budget: float = 1.0) -> None:
        self.config = config
        self.scale = max(1, int(scale))
        self.clip = clip
        self.on_floor = on_floor
        self.capacity = max(0, int(config.capacity * max(0.0, budget)))
        self.rate = config.rate * max(0.0, budget)
        self._rng = random.Random(seed)
        self._accum = 0.0
        self._time = 0.0
        n = self.capacity
        self._x = [0.0] * n
        self._y = [0.0] * n
        self._vx = [0.0] * n
        self._vy = [0.0] * n
        self._age = [0.0] * n
        self._life = [1.0] * n
        self._phase = [0.0] * n
        self._n = 0

    # ------------------------------------------------------------------ state

    @property
    def count(self) -> int:
        """Number of live particles."""
        return self._n

    def positions(self) -> list[tuple[float, float]]:
        return [(self._x[i], self._y[i]) for i in range(self._n)]

    # ------------------------------------------------------------------ spawning

    def emit_at(self, x: float, y: float, n: int) -> int:
        """Spawn up to ``n`` particles at a point (used for bursts). Returns how many."""
        made = 0
        for _ in range(n):
            if not self._spawn(x, y):
                break
            made += 1
        return made

    def _spawn(self, x: float | None = None, y: float | None = None) -> bool:
        if self._n >= self.capacity:
            return False
        c, r, i = self.config, self._rng, self._n
        ax, ay, aw, ah = c.area
        self._x[i] = ax + r.random() * aw if x is None else x
        self._y[i] = ay + r.random() * ah if y is None else y
        self._vx[i] = r.uniform(*c.vx)
        self._vy[i] = r.uniform(*c.vy)
        self._age[i] = 0.0
        self._life[i] = r.uniform(*c.lifetime)
        self._phase[i] = r.random() * math.tau
        self._n += 1
        return True

    def _kill(self, i: int) -> None:
        last = self._n - 1
        if i != last:
            for arr in (self._x, self._y, self._vx, self._vy, self._age, self._life, self._phase):
                arr[i] = arr[last]
        self._n = last

    # ------------------------------------------------------------------ simulation

    def update(self, dt: float) -> None:
        dt = min(MAX_DT, max(0.0, dt))
        if dt == 0.0:
            return
        c = self.config
        self._time += dt
        if self.rate > 0:
            self._accum += self.rate * dt
            while self._accum >= 1.0:
                self._accum -= 1.0
                if not self._spawn():
                    self._accum = 0.0
                    break
        g, wob, floor = c.gravity, c.wobble, c.floor_y
        x, y, vx, vy, age, life, ph = self._x, self._y, self._vx, self._vy, self._age, self._life, self._phase
        i = 0
        while i < self._n:
            age[i] += dt
            if age[i] >= life[i]:
                self._kill(i)
                continue
            vy[i] += g * dt
            x[i] += vx[i] * dt + (wob * math.sin(ph[i] + self._time * 5.0) * dt if wob else 0.0)
            y[i] += vy[i] * dt
            if floor is not None and y[i] >= floor:
                if self.on_floor is not None and c.burst:
                    self.on_floor.emit_at(x[i], floor, c.burst)
                self._kill(i)
                continue
            i += 1
        if self.on_floor is not None:
            self.on_floor.update(dt)

    def prewarm(self, seconds: float, step: float = 1 / 30) -> None:
        """Simulate ahead so the effect is already in full swing on the first frame."""
        t = 0.0
        while t < seconds:
            self.update(step)
            t += step

    # ------------------------------------------------------------------ drawing

    def draw(self, surface: pygame.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        c, s = self.config, self.scale
        colors = c.colors
        nc = len(colors)
        w, h = c.size * s, max(c.size, c.length) * s
        ox, oy = offset
        old_clip = None
        if self.clip is not None:
            old_clip = surface.get_clip()
            cx, cy, cw, ch = self.clip
            surface.set_clip(pygame.Rect(ox + cx * s, oy + cy * s, cw * s, ch * s))
        fill = surface.fill
        x, y, vx, vy, age, life = self._x, self._y, self._vx, self._vy, self._age, self._life
        trail = c.trail
        tcol = c.trail_color or colors[-1]
        for i in range(self._n):
            k = int(age[i] / life[i] * nc)
            px, py = int(x[i]), int(y[i])
            if trail:
                # step back along the motion, one row at a time (slanted streak)
                slope = vx[i] / vy[i] if vy[i] else 0.0
                for j in range(1, trail + 1):
                    fill(tcol, (ox + int(x[i] - slope * j) * s, oy + (py - j) * s, w, s))
            fill(colors[k if k < nc else nc - 1], (ox + px * s, oy + py * s, w, h))
        if self.clip is not None:
            surface.set_clip(old_clip)
        if self.on_floor is not None:
            self.on_floor.draw(surface, offset)
