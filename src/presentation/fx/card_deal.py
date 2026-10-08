"""Card deal: a drawn card flies from the draw pile into its place in the hand.

Instead of sliding straight in, a drawn card follows a short arc out of the draw pile:
it leaves small and tilted, face down, rises, flips over in the air (the back narrows to
an edge, then the face widens), spins upright and settles into its slot with a slight
overshoot, leaving a trail of motes. Several cards are dealt one after another
(``DEAL_STAGGER``), and the scene can hold a card back (``wait``) until the moment it is
really drawn — e.g. the second cast of a golden card.

``deal_pose`` is pure math (easy to test). ``draw_dealt_card`` renders the in-flight
card: the back or the face, squashed horizontally by the flip, rotated. Once the flip is
over the scene draws the card normally (cached, with its chroma/ready effects).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import pygame

from src.infrastructure.card_assets import card_back

DEAL_SECONDS = 0.5           # flight time from the pile to the hand
DEAL_STAGGER = 0.12          # gap between two cards dealt together
FLIP_END = 0.6               # fraction of the flight when the face is fully shown
START_SCALE = 0.34           # size when it leaves the pile
START_ANGLE = -28.0          # tilt when it leaves the pile (degrees)
ARC_HEIGHT = 150.0           # how high the arc rises above the higher end point
TRAIL = ((235, 245, 255), (170, 205, 255), (110, 150, 230))
TRAIL_GOLD = ((255, 250, 210), (255, 214, 90), (230, 150, 30))


@dataclass
class Deal:
    """One card being dealt: ``wait`` s before it leaves the pile, then ``t`` s of flight."""
    wait: float
    start: tuple[float, float]
    t: float = 0.0

    @property
    def waiting(self) -> bool:
        return self.wait > 0.0

    @property
    def progress(self) -> float:
        return 0.0 if self.waiting else min(1.0, self.t / DEAL_SECONDS)

    @property
    def done(self) -> bool:
        return not self.waiting and self.t >= DEAL_SECONDS

    def advance(self, dt: float) -> None:
        dt = max(0.0, dt)                 # a long frame just lands the card (no overshoot)
        if self.wait > 0.0:
            spill = dt - self.wait
            self.wait = max(0.0, self.wait - dt)
            if spill > 0.0:
                self.t += spill
        else:
            self.t += dt


def ease_out_cubic(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return 1.0 - (1.0 - u) ** 3


def ease_out_back(u: float, k: float = 1.6) -> float:
    """0 → 1 with a small overshoot near the end (the card settles into place)."""
    u = max(0.0, min(1.0, u)) - 1.0
    return 1.0 + (k + 1.0) * u ** 3 + k * u ** 2


def flip_width(u: float) -> tuple[float, bool]:
    """(horizontal size factor 0..1, face showing) at flight progress ``u``."""
    f = max(0.0, min(1.0, u / FLIP_END))
    c = math.cos(math.pi * f)
    return abs(c), f >= 0.5


def deal_pose(u: float, start: tuple[float, float], goal: tuple[float, float, float, float]
              ) -> tuple[float, float, float, float]:
    """(x, y, scale, angle) of a card ``u`` (0..1) of the way from the pile to ``goal``.

    ``goal`` = (x, y, scale, angle) of its slot in the hand, read every frame so the card
    lands where the fan is *now* (the fan opens while it flies).
    """
    u = max(0.0, min(1.0, u))
    e = ease_out_cubic(u)
    sx, sy = start
    gx, gy, gscale, gangle = goal
    cx = (sx + gx) / 2.0
    cy = min(sy, gy) - ARC_HEIGHT
    a, b, c = (1 - e) ** 2, 2 * (1 - e) * e, e * e
    x = a * sx + b * cx + c * gx
    y = a * sy + b * cy + c * gy
    scale = START_SCALE + (gscale - START_SCALE) * ease_out_back(u)
    angle = START_ANGLE * (1.0 - e) + gangle * e
    return x, y, scale, angle


@lru_cache(maxsize=4)
def _back(w: int, h: int) -> pygame.Surface | None:
    return card_back(w, h)


def draw_dealt_card(surface: pygame.Surface, face: pygame.Surface, pose: tuple[float, float, float, float],
                    u: float) -> pygame.Rect:
    """Draw the in-flight card (back or ``face``, squashed by the flip). Returns its rect."""
    x, y, scale, angle = pose
    width, showing_face = flip_width(u)
    w0, h0 = face.get_size()
    w = max(1, round(w0 * scale * width))
    h = max(1, round(h0 * scale))
    src = face if showing_face else (_back(w0, h0) or face)
    img = pygame.transform.smoothscale(src, (w, h))
    if abs(angle) > 0.5:
        img = pygame.transform.rotate(img, angle)
    rect = img.get_rect(center=(round(x), round(y)))
    surface.blit(img, rect)
    return rect
