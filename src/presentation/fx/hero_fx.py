"""Particles and floor shadow for a code-drawn hero (La Guerrera), Espectro method.

The hero's sheet already bakes the slash arc, ward crescent, blade glow and hit
flash; this layer adds what moves freely in screen space, timed to the action:

  attack  warm sparks where the blade connects (at ``strike`` seconds) + a dust kick
  guard   blue shards bursting off the ward + drifting motes
  hurt    ember sparks thrown back from the chest + a short white glow
  cast    golden motes rising around her, sparks spiralling into the blade tip
  death   the hurt burst, then a dust puff when the knee hits the floor

Positions are offsets from the centre of the 192 px combat sprite (the sheet is
96 px native shown ×2, so native ``(x, y)`` maps to ``(2x - 96, 2y - 96)``).
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import pygame

from src.presentation.fx.bursts import GLOW, SPARK, BurstParticles

MAX_DT = 0.1

WARM = ((255, 255, 236), (255, 214, 124), (236, 136, 44), (130, 54, 20))
WARD = ((236, 250, 255), (150, 204, 255), (70, 134, 224), (30, 64, 130))
EMBER = ((255, 236, 210), (255, 140, 90), (200, 50, 40), (90, 20, 20))
DUST = ((150, 128, 110), (110, 92, 80), (70, 58, 54))
GOLD = ((255, 250, 210), (255, 214, 90), (230, 150, 30), (140, 80, 10))

# Offsets from the sprite centre (screen px).
BLADE_HIT = (82, 36)
WARD_AT = (36, -14)
CHEST = (-4, -4)
CAST_TIP = (12, -92)
FEET = (0, 94)
FRONT_FOOT = (24, 92)

DEATH_KNEEL = 0.18          # seconds into "death" when the knee touches the floor


@lru_cache(maxsize=4)
def _shadow(w: int, h: int) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(6, 0, -1):
        k = i / 6
        pygame.draw.ellipse(s, (0, 0, 0, int(28 * (1.2 - k) + 12)),
                            (w * (1 - k) / 2, h * (1 - k) / 2, w * k, h * k))
    return s


class HeroFx:
    """Timed particle cues for the hero's actions (one per combat)."""

    def __init__(self, *, strike: float, seed: int = 0, particles: int = 260) -> None:
        self.strike = max(0.0, strike)
        self._rng = random.Random(seed)
        self.particles = BurstParticles(particles, seed=seed + 13)
        self._action: str | None = None
        self._t = 0.0
        self._fired: set[str] = set()
        self._queue: list[list] = []
        self._center: tuple[float, float] | None = None

    @property
    def action(self) -> str | None:
        return self._action

    def play(self, action: str, *, delay: float = 0.0) -> None:
        """Start the cues of ``action`` (after ``delay`` s). Unknown actions are ignored."""
        if action not in ("attack", "guard", "hurt", "cast", "death"):
            return
        if delay > 0:
            self._queue.append([action, delay])
            return
        self._action, self._t, self._fired = action, 0.0, set()

    def update(self, dt: float) -> None:
        dt = min(MAX_DT, max(0.0, dt))
        for item in list(self._queue):
            item[1] -= dt
            if item[1] <= 0:
                self._queue.remove(item)
                self.play(item[0])
        if self._action is not None:
            self._t += dt
            self._cues(dt)
            if self._t > 2.0:
                self._action = None
        self.particles.update(dt)

    def _once(self, key: str, at: float) -> bool:
        if key in self._fired or self._t < at:
            return False
        self._fired.add(key)
        return True

    def _at(self, off) -> tuple[float, float]:
        cx, cy = self._center
        return cx + off[0], cy + off[1]

    def _cues(self, dt: float) -> None:
        if self._center is None:
            return
        p, r, a = self.particles, self._rng, self._action
        if a == "attack":
            if self._once("kick", 0.12):
                x, y = self._at(FRONT_FOOT)
                p.burst(x, y, 10, palette=DUST, speed=(30, 110), angle=(math.pi * 1.05, math.pi * 1.6),
                        life=(0.3, 0.6), size=(2, 4), drag=3.0, gravity=200)
            if self._once("hit", max(0.0, self.strike - 0.02)):
                x, y = self._at(BLADE_HIT)
                p.burst(x, y, 26, palette=WARM, speed=(180, 460), angle=(-math.pi * 0.45, math.pi * 0.35),
                        life=(0.16, 0.38), size=(1.5, 2.5), style=SPARK, drag=4.0)
                p.burst(x, y, 12, palette=WARM, speed=(40, 160), life=(0.3, 0.7), size=(2, 3),
                        drag=3.0, gravity=240, spread=10)
                p.burst(x, y, 3, palette=WARM, speed=(0, 20), life=(0.18, 0.3), size=(28, 40),
                        style=GLOW, drag=4.0)
        elif a == "guard":
            if self._once("ward", 0.06):
                x, y = self._at(WARD_AT)
                p.burst(x, y, 20, palette=WARD, speed=(80, 260), angle=(-math.pi * 0.5, math.pi * 0.5),
                        life=(0.25, 0.55), size=(1.5, 3), style=SPARK, drag=3.5, spread=20)
                p.burst(x, y, 2, palette=WARD, speed=(0, 10), life=(0.25, 0.4), size=(34, 46),
                        style=GLOW, drag=4.0)
            if self._once("motes", 0.18):
                for _ in range(10):
                    x, y = self._at((WARD_AT[0] + r.uniform(-6, 10), WARD_AT[1] + r.uniform(-34, 34)))
                    p.emit(x, y, r.uniform(-10, 20), r.uniform(-40, -10), life=r.uniform(0.5, 0.9),
                           palette=WARD, size=r.uniform(1.5, 2.5), drag=1.0)
        elif a in ("hurt", "death"):
            if self._once("hit", 0.0):
                x, y = self._at(CHEST)
                p.burst(x, y, 22, palette=EMBER, speed=(120, 320), angle=(math.pi * 0.6, math.pi * 1.4),
                        life=(0.25, 0.55), size=(1.5, 2.5), style=SPARK, drag=3.5)
                p.burst(x, y, 2, palette=EMBER, speed=(0, 10), life=(0.12, 0.22), size=(34, 44),
                        style=GLOW, drag=4.0)
            if a == "death" and self._once("kneel", DEATH_KNEEL):
                x, y = self._at(FEET)
                p.burst(x, y, 24, palette=DUST, speed=(40, 160), angle=(math.pi, math.tau),
                        life=(0.4, 0.9), size=(2, 4), drag=2.5, gravity=120, spread=24)
        elif a == "cast":
            if self._once("charge", 0.05):
                x, y = self._at(CAST_TIP)
                p.implode(x, y, 20, palette=GOLD, radius=(50, 100), life=(0.25, 0.4))
            if 0.1 < self._t < 0.55:
                for _ in range(2):
                    x, y = self._at((r.uniform(-50, 50), r.uniform(10, 90)))
                    p.emit(x, y, r.uniform(-8, 8), r.uniform(-120, -60), life=r.uniform(0.5, 0.9),
                           palette=GOLD, size=r.uniform(1.5, 3), drag=0.8)
            if self._once("flare", 0.25):
                x, y = self._at(CAST_TIP)
                p.burst(x, y, 3, palette=GOLD, speed=(0, 10), life=(0.3, 0.45), size=(30, 44),
                        style=GLOW, drag=4.0)

    def draw_shadow(self, surface: pygame.Surface, center: tuple[float, float]) -> None:
        """Soft floor shadow under the hero's feet (call before the sprite)."""
        self._center = (float(center[0]), float(center[1]))
        x, y = self._at(FEET)
        sh = _shadow(120, 22)
        surface.blit(sh, (int(x) - 60, int(y) - 9))

    def draw(self, surface: pygame.Surface, center: tuple[float, float]) -> None:
        """Particles (call after the sprite)."""
        self._center = (float(center[0]), float(center[1]))
        self.particles.draw(surface)
