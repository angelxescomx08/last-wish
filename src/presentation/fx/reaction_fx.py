"""The moment of an elemental reaction, so the player sees *what* happened and *why*.

Each reaction (``domain.elements.ReactionEvent``) plays a short show at the enemy:

1. **Clash** (``CLASH`` s): the two element icons fly in from both sides of the enemy
   and meet in the middle, leaving a trail of their colour.
2. **Impact**: burst of particles in the reaction's palette (steam puffs, magma
   sparks, ice shards…), a soft flash, and a small screen shake (``shake_offset``).
3. **Result**: the reaction icon pops in big, with "¡VAPOR!" and what it did
   ("10 de daño"), then rises and fades (``LIFE`` s in total).

``ReactionShow`` holds the active shows; the combat screen calls ``update`` / ``draw``
and adds ``shake_offset()`` to what it draws. Pooled particles come from the scene's
``BurstParticles``.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from src.domain.elements import Element, Reaction
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.fx.bursts import GLOW, SPARK, SQUARE, BurstParticles, soft_glow
from src.presentation.ui import glossary as gl
from src.presentation.ui.pixel_ui import outlined

CLASH = 0.38          # icons travel this long before they meet
LIFE = 1.9            # whole show
SHAKE = 0.22          # screen shake after the impact (s)
SHAKE_PX = 5

_ICON = {Element.FIRE: "fire", Element.WATER: "water", Element.EARTH: "earth", Element.AIR: "air"}

PALETTES: dict[Reaction, tuple] = {
    Reaction.STEAM: ((250, 250, 255), (210, 216, 232), (255, 150, 90), (130, 190, 255)),
    Reaction.MAGMA: ((255, 236, 160), (255, 150, 50), (210, 70, 30), (70, 40, 34)),
    Reaction.WILDFIRE: ((255, 240, 170), (255, 150, 60), (230, 70, 40)),
    Reaction.MUD: ((150, 110, 62), (196, 160, 104), (110, 176, 255), (70, 46, 26)),
    Reaction.FREEZE: ((236, 252, 255), (170, 226, 255), (90, 170, 230)),
    Reaction.SANDSTORM: ((244, 222, 160), (214, 176, 104), (168, 128, 66)),
}


@dataclass
class _Show:
    x: float
    y: float
    reaction: Reaction
    first: Element | None
    second: Element | None
    result: str
    age: float              # negative = waiting
    hit: bool = False


class ReactionShow:
    def __init__(self, bursts: BurstParticles, seed: int = 0) -> None:
        self._bursts = bursts
        self._items: list[_Show] = []
        self._shake = 0.0
        self._rng = random.Random(seed)

    @property
    def busy(self) -> bool:
        return bool(self._items)

    @property
    def count(self) -> int:
        return len(self._items)

    def add(self, pos: tuple[float, float], reaction: Reaction, first: Element | None,
            second: Element | None, result: str, delay: float = 0.0) -> None:
        self._items.append(_Show(pos[0], pos[1], reaction, first, second, result, -max(0.0, delay)))

    def update(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1))
        self._shake = max(0.0, self._shake - dt)
        for s in self._items:
            s.age += dt
            if not s.hit and s.age >= CLASH:
                s.hit = True
                self._impact(s)
        self._items = [s for s in self._items if s.age < LIFE]

    def _impact(self, s: _Show) -> None:
        pal = PALETTES[s.reaction]
        style = SPARK if s.reaction in (Reaction.MAGMA, Reaction.FREEZE, Reaction.WILDFIRE) else SQUARE
        self._bursts.burst(s.x, s.y, 46, palette=pal, speed=(90, 360), life=(0.4, 1.0),
                           size=(2, 5), style=style, drag=2.4, spread=10)
        self._bursts.burst(s.x, s.y, 8, palette=pal[:2], speed=(10, 70), life=(0.5, 0.9),
                           size=(22, 40), style=GLOW, drag=3.0, spread=24)
        if s.reaction is Reaction.STEAM:          # puffs rise
            self._bursts.burst(s.x, s.y, 18, palette=pal[:2], speed=(30, 90), angle=(-2.6, -0.5),
                               life=(0.8, 1.3), size=(4, 7), drag=1.2, gravity=-60)
        self._shake = SHAKE

    def shake_offset(self) -> tuple[int, int]:
        if self._shake <= 0:
            return (0, 0)
        k = self._shake / SHAKE
        return (int(self._rng.uniform(-1, 1) * SHAKE_PX * k), int(self._rng.uniform(-1, 1) * SHAKE_PX * k))

    def draw(self, surface: pygame.Surface, fonts: FontRegistry) -> None:
        for s in self._items:
            if s.age < 0:
                continue
            if s.age < CLASH:
                self._draw_clash(surface, s)
            else:
                self._draw_result(surface, s, fonts)

    def _draw_clash(self, surface: pygame.Surface, s: _Show) -> None:
        u = s.age / CLASH
        ease = u * u                                     # accelerate into each other
        for el, side in ((s.first, -1), (s.second, 1)):
            if el is None:
                continue
            icon = ui_icon(_ICON[el], 3)
            if icon is None:
                continue
            x = s.x + side * 90 * (1 - ease)
            ink = gl.ELEMENT_COLOR[el.value]
            for k in range(1, 4):                          # trail
                tx = s.x + side * 90 * (1 - max(0.0, ease - 0.08 * k))
                pygame.draw.circle(surface, ink, (int(tx), int(s.y)), max(1, 5 - k))
            surface.blit(icon, icon.get_rect(center=(int(x), int(s.y))))

    def _draw_result(self, surface: pygame.Surface, s: _Show, fonts: FontRegistry) -> None:
        t = s.age - CLASH
        rest = LIFE - CLASH
        color = gl.REACTION_COLOR[s.reaction]
        if t < 0.18:                                      # flash
            glow = soft_glow(color, int(40 + 160 * t))
            surface.blit(glow, glow.get_rect(center=(int(s.x), int(s.y))), special_flags=pygame.BLEND_RGB_ADD)
        scale = 5 if t < 0.16 else 4                       # pops in big, settles
        rise = 26 * max(0.0, t - 0.6)
        alpha = 255 if t < rest - 0.5 else int(255 * max(0.0, (rest - t) / 0.5))
        icon = ui_icon(gl.REACTION_ICON[s.reaction], scale)
        y = s.y - rise
        if icon is not None:
            icon = icon.copy()
            icon.set_alpha(alpha)
            surface.blit(icon, icon.get_rect(center=(int(s.x), int(y - 22))))
        label = outlined(fonts.get(32), f"¡{s.reaction.value.upper()}!", color).copy()
        label.set_alpha(alpha)
        surface.blit(label, label.get_rect(center=(int(s.x), int(y + 22))))
        if s.result:
            detail = outlined(fonts.get(16), s.result, (236, 228, 214)).copy()
            detail.set_alpha(alpha)
            surface.blit(detail, detail.get_rect(center=(int(s.x), int(y + 50))))
