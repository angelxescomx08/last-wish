"""Per-enemy animation player with its own particles (idle, attack, hurt, cast, death).

Plays an :class:`~src.infrastructure.enemy_sprites.EnemySheet` by elapsed time
(never by frame count) and adds what a baked sheet cannot: a floor shadow, a
pulsing spectral floor glow, rising ghost wisps, and one-shot bursts timed to
the action (claw sparks on the strike, ectoplasm on a hit, soul motes while
dying, sparks spiralling into the chest while casting).

* Actions return to idle at their end (every non-death action ends on idle
  frame 0, so there is no pop). ``death`` latches and holds its last (empty)
  frame; particles still finish.
* ``play(name, delay=…)`` queues an action, so several enemies can be staggered.
* Particles live in a small pooled :class:`BurstParticles` in screen px; cues
  use the anchor of the previous draw.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import pygame

from src.infrastructure.enemy_sprites import EnemySheet
from src.presentation.fx.bursts import GLOW, SPARK, BurstParticles, soft_glow

MAX_DT = 0.1

_WISP = ((150, 255, 230), (90, 210, 190), (50, 140, 140), (26, 70, 80))
_ECTO = ((230, 255, 245), (130, 235, 215), (60, 170, 160), (40, 31, 64))
_SPARK = ((255, 255, 255), (200, 255, 240), (110, 220, 200))
_VIOLET = ((180, 160, 230), (116, 98, 160), (58, 45, 90))
_GLOW_COL = (40, 150, 140)

# Screen offsets from the anchor (ground point), for a ×2 sheet.
CHEST = (-4, -96)
EYES = (-6, -124)
BODY = (0, -84)
CLAW = (-118, -80)          # where the lunge's claws land (towards the hero)


@lru_cache(maxsize=8)
def _shadow(w: int, h: int) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(6, 0, -1):
        k = i / 6
        pygame.draw.ellipse(s, (0, 0, 0, int(26 * (1.2 - k) + 10)),
                            (w * (1 - k) / 2, h * (1 - k) / 2, w * k, h * k))
    return s


@lru_cache(maxsize=16)
def _floor_glow(level: int) -> pygame.Surface:
    """Flattened additive teal glow, ``level`` 1..6 in brightness."""
    k = level / 6
    base = soft_glow((int(_GLOW_COL[0] * k), int(_GLOW_COL[1] * k), int(_GLOW_COL[2] * k)), 40)
    return pygame.transform.smoothscale(base, (190, 44))


class EnemyAnimator:
    """Animation state + particles of one animated enemy on screen."""

    def __init__(self, sheet: EnemySheet, *, seed: int = 0, phase: float = 0.0,
                 particles: int = 220) -> None:
        self.sheet = sheet
        self._rng = random.Random(seed)
        self._idle_time = phase % max(1e-6, sheet.seconds("idle"))
        self._action: str | None = None
        self._action_time = 0.0
        self._queue: list[list] = []                  # [name, delay]
        self._dead = False
        self._wisp_clock = self._rng.uniform(0.0, 0.2)
        self._fx_time = self._rng.uniform(0.0, 10.0)
        self._anchor: tuple[float, float] | None = None
        self._fired: set[str] = set()
        self.particles = BurstParticles(particles, seed=seed + 7)

    # ------------------------------------------------------------------ state
    @property
    def action(self) -> str | None:
        """Action currently playing (attack/hurt/cast/death), None while idle."""
        return self._action

    @property
    def dead(self) -> bool:
        return self._dead

    @property
    def death_done(self) -> bool:
        """The death animation has fully played (the sprite is gone)."""
        return self._dead and self._action_time >= self.sheet.seconds("death")

    @property
    def busy(self) -> bool:
        """An action is playing or queued."""
        if self._dead:
            return not self.death_done
        return self._action is not None or bool(self._queue)

    def seconds(self, name: str) -> float:
        return self.sheet.seconds(name)

    def strike_time(self) -> float:
        """Seconds from the start of ``attack`` to the frame where the claws land."""
        anim = self.sheet.animations.get("attack")
        return sum(anim.durations[:3]) if anim else 0.0

    def play(self, name: str, *, delay: float = 0.0) -> None:
        """Start (or queue after ``delay`` s) an action. Unknown names are ignored."""
        if self._dead or name not in self.sheet.animations or name == "idle":
            return
        if delay > 0:
            self._queue.append([name, delay])
            return
        self._start(name)

    def _start(self, name: str) -> None:
        if self._dead:
            return
        if name == "death":
            self._dead = True
            self._queue.clear()
        self._action = name
        self._action_time = 0.0
        self._fired = set()

    # ------------------------------------------------------------------ simulation
    def update(self, dt: float) -> None:
        dt = min(MAX_DT, max(0.0, dt))
        self._fx_time += dt
        for item in list(self._queue):
            item[1] -= dt
            if item[1] <= 0:
                self._queue.remove(item)
                self._start(item[0])
        if self._action is not None:
            self._action_time += dt
            self._cues()
            if not self._dead and self._action_time >= self.sheet.seconds(self._action):
                self._action = None
                self._action_time = 0.0
                self._idle_time = 0.0
        else:
            self._idle_time = (self._idle_time + dt) % max(1e-6, self.sheet.seconds("idle"))
        self._ambient(dt)
        self.particles.update(dt)

    def _once(self, key: str, at: float) -> bool:
        if key in self._fired or self._action_time < at:
            return False
        self._fired.add(key)
        return True

    def _cues(self) -> None:
        if self._anchor is None:
            return
        ax, ay = self._anchor
        p, r = self.particles, self._rng
        name = self._action
        if name == "attack" and self._once("strike", self.strike_time() - 0.05):
            x, y = ax + CLAW[0], ay + CLAW[1]
            p.burst(x, y, 22, palette=_SPARK, speed=(160, 420), angle=(math.pi * 0.55, math.pi * 1.25),
                    life=(0.18, 0.4), size=(1.5, 2.5), style=SPARK, drag=4.0)
            p.burst(x, y, 14, palette=_WISP, speed=(40, 160), life=(0.4, 0.8), size=(2, 4),
                    drag=3.0, gravity=-60, spread=18)
            p.burst(x, y, 3, palette=_WISP, speed=(0, 30), life=(0.25, 0.4), size=(26, 36),
                    style=GLOW, drag=4.0)
        elif name == "hurt" and self._once("splash", 0.0):
            x, y = ax + BODY[0], ay + BODY[1]
            p.burst(x, y, 26, palette=_ECTO, speed=(90, 280), angle=(-math.pi * 0.45, math.pi * 0.45),
                    life=(0.35, 0.8), size=(2, 4), drag=2.2, gravity=380, spread=10)
            p.burst(x, y, 10, palette=_VIOLET, speed=(60, 200), life=(0.3, 0.6), size=(2, 3),
                    drag=2.5, gravity=200, spread=14)
            p.burst(x, y, 2, palette=_ECTO, speed=(0, 10), life=(0.15, 0.25), size=(36, 46),
                    style=GLOW, drag=4.0)
        elif name == "cast":
            if self._once("charge", 0.0):
                p.implode(ax + CHEST[0], ay + CHEST[1], 24, palette=_WISP, radius=(70, 130),
                          life=(0.35, 0.55))
            if self._once("rune", 0.3):
                for _ in range(16):
                    a = r.uniform(0, math.tau)
                    p.emit(ax + math.cos(a) * 52, ay - 2 + math.sin(a) * 12, 0, r.uniform(-90, -40),
                           life=r.uniform(0.6, 1.1), palette=_WISP, size=r.uniform(2, 3), drag=1.0)
                p.burst(ax + CHEST[0], ay + CHEST[1], 2, palette=_WISP, speed=(0, 10),
                        life=(0.3, 0.45), size=(40, 52), style=GLOW, drag=4.0)
        elif name == "death":
            if self._once("pop", 0.0):
                x, y = ax + BODY[0], ay + BODY[1]
                p.burst(x, y, 30, palette=_ECTO, speed=(120, 320), life=(0.4, 0.9), size=(2, 4),
                        drag=2.0, gravity=300, spread=12)
                p.burst(ax + EYES[0], ay + EYES[1], 3, palette=_ECTO, speed=(0, 10), life=(0.3, 0.5),
                        size=(40, 56), style=GLOW, drag=4.0)
            total = self.sheet.seconds("death")
            u = self._action_time / max(1e-6, total)
            if 0.2 < u < 0.95:                        # motes torn off the dissolving front
                front = ay - 8 - (u - 0.2) / 0.75 * 170
                for _ in range(3):
                    p.emit(ax + r.uniform(-44, 48), front + r.uniform(-8, 8), r.uniform(-25, 25),
                           r.uniform(-140, -60), life=r.uniform(0.5, 1.1), palette=_WISP,
                           size=r.uniform(2, 4), drag=1.2)
            if self._once("soul", total * 0.8):
                x, y = ax + EYES[0], ay + EYES[1]
                p.burst(x, y, 24, palette=_SPARK, speed=(100, 300), life=(0.3, 0.7), size=(1.5, 2.5),
                        style=SPARK, drag=3.0)
                p.burst(x, y, 6, palette=_WISP, speed=(10, 60), angle=(-math.pi * 0.7, -math.pi * 0.3),
                        life=(0.8, 1.4), size=(14, 24), style=GLOW, drag=0.5, gravity=-90)

    def _ambient(self, dt: float) -> None:
        if self._anchor is None or self._dead:
            return
        self._wisp_clock -= dt
        if self._wisp_clock > 0:
            return
        self._wisp_clock += self._rng.uniform(0.12, 0.26)
        ax, ay = self._anchor
        r = self._rng
        x = ax + r.uniform(-42, 46)
        if r.random() < 0.55:
            self.particles.emit(x, ay - r.uniform(8, 30), r.uniform(-8, 8), r.uniform(-50, -22),
                                life=r.uniform(1.0, 1.8), palette=_WISP, size=r.uniform(1.5, 3.0),
                                drag=0.3)
        else:
            self.particles.emit(x, ay - r.uniform(10, 40), r.uniform(-6, 6), r.uniform(-30, -14),
                                life=r.uniform(1.2, 2.0), palette=_WISP, size=r.uniform(6, 11),
                                style=GLOW, drag=0.2)

    # ------------------------------------------------------------------ drawing
    def current_frame(self) -> pygame.Surface:
        if self._action is not None:
            return self.sheet.frame(self._action, self._action_time)
        return self.sheet.frame("idle", self._idle_time)

    def draw(self, surface: pygame.Surface, anchor: tuple[float, float]) -> None:
        """Shadow, floor glow, sprite and particles; ``anchor`` = ground point under the enemy."""
        self._anchor = (float(anchor[0]), float(anchor[1]))
        ax, ay = int(anchor[0]), int(anchor[1])
        fade = 1.0
        if self._dead:
            fade = max(0.0, 1.0 - self._action_time / max(1e-6, self.sheet.seconds("death")))
        if fade > 0:
            sh = _shadow(150, 26)
            if fade < 1.0:
                sh = sh.copy()
                sh.set_alpha(int(255 * fade))
            surface.blit(sh, (ax - 75, ay - 13))
            pulse = 0.5 + 0.5 * math.sin(self._fx_time * 2.4)
            boost = 2 if self._action in ("cast", "attack") else 0
            level = max(1, min(6, int((2 + 2 * pulse + boost) * fade + 0.5)))
            glow = _floor_glow(level)
            surface.blit(glow, (ax - 95, ay - 22), special_flags=pygame.BLEND_RGB_ADD)
        if not self.death_done:
            frame = self.current_frame()
            w, h = self.sheet.anchor
            surface.blit(frame, (ax - w, ay - h))
        self.particles.draw(surface)
