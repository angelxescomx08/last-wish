"""Gold counter shown on every run screen (map, shop, gachapón, rewards, events, combat…).

One instance lives in the ``SceneManager`` so it survives scene changes and can
animate what happened between them (the gold of a won fight counts up when the
reward screen appears). It draws:

* a dark plate with a gold border and a pixel-art coin (the gachapón coin
  sprite, ×3) that spins now and then, and every time the amount changes;
* the amount in big outlined gold digits, **counting** towards the real value
  instead of jumping (fast for big changes, never longer than ~0.8 s);
* a floating ``+N`` (green, sparkles) or ``−N`` (red) on every change, and a
  brief border flash.

``update(dt, amount)`` feeds the real gold; ``sync(amount)`` sets it without
animation (new run). ``draw(surface, anchor=…, pos=…)`` places it (default: top
right). Scenes choose a spot with an optional ``gold_hud_pos = (anchor, (x, y))``.
"""
from __future__ import annotations

import math

import pygame

from src.domain.numbers import BigValue
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.gacha_assets import load_gacha_assets
from src.presentation.fx.bursts import GLOW, BurstParticles, soft_glow

GOLD = (255, 214, 90)
GOLD_LIGHT = (255, 244, 190)
GAIN = (130, 240, 120)
LOSS = (255, 110, 100)
_PLATE = (20, 15, 10, 225)
_BORDER = (176, 128, 46)
DEFAULT_POS = ("topright", (1268, 12))
COUNT_TIME = 0.8            # a change finishes counting within this many seconds
SPIN_EVERY = 4.0            # idle coin spin period (s)
_MAX_DELTAS = 6


def format_gold(amount: int) -> str:
    """"1 234" below a million (thin-space groups), then BigValue suffixes ("1.5M")."""
    if abs(amount) >= 1_000_000:
        return BigValue.format_int(amount)
    s = f"{abs(amount):,}".replace(",", " ")
    return ("-" if amount < 0 else "") + s


class GoldHud:
    def __init__(self, fonts: FontRegistry, *, seed: int = 9) -> None:
        self._fonts = fonts
        self._target = 0
        self._shown = 0.0
        self._rate = 0.0
        self._time = 0.0
        self._spin = 0.0                    # > 0 while the coin spins (s left)
        self._flash = 0.0
        self._flash_color = GOLD
        self._deltas: list[list] = []       # [text, color, age, direction]
        self._fx = BurstParticles(90, seed=seed)
        self._synced = False
        self._rect = pygame.Rect(0, 0, 0, 0)
        self._coin = self._load_coin()

    @staticmethod
    def _load_coin() -> tuple[pygame.Surface, ...]:
        assets = load_gacha_assets()
        if assets is None:
            return ()
        return tuple(pygame.transform.scale(c, (c.get_width() * 3 // 2, c.get_height() * 3 // 2))
                     for c in assets.coin)

    # ------------------------------------------------------------------ state
    @property
    def shown(self) -> int:
        """The number currently displayed (counts towards the real amount)."""
        return int(round(self._shown))

    @property
    def target(self) -> int:
        return self._target

    @property
    def counting(self) -> bool:
        return self.shown != self._target

    @property
    def rect(self) -> pygame.Rect:
        """Where it was last drawn (the gachapón coin flies from here)."""
        return self._rect

    @property
    def deltas(self) -> list[tuple[str, tuple[int, int, int]]]:
        return [(d[0], d[1]) for d in self._deltas]

    def sync(self, amount: int) -> None:
        """Show ``amount`` at once (new run, first frame)."""
        self._target = int(amount)
        self._shown = float(amount)
        self._deltas.clear()
        self._synced = True

    def update(self, dt: float, amount: int) -> None:
        dt = min(0.1, max(0.0, dt))
        self._time += dt
        amount = int(amount)
        if not self._synced:
            self.sync(amount)
        if amount != self._target:
            diff = amount - self._target
            self._target = amount
            self._rate = max(40.0, abs(self._target - self._shown) / COUNT_TIME)
            gain = diff > 0
            self._deltas.append([("+" if gain else "−") + format_gold(abs(diff)),
                                 GAIN if gain else LOSS, 0.0, -1 if gain else 1])
            del self._deltas[:-_MAX_DELTAS]
            self._flash, self._flash_color = 1.0, GAIN if gain else LOSS
            self._spin = 0.6
            if gain and self._rect.width:
                cx, cy = self._coin_center()
                self._fx.burst(cx, cy, 14, palette=(GOLD_LIGHT, GOLD, (230, 150, 30)),
                               speed=(60, 180), life=(0.3, 0.6), size=(1.5, 3), drag=3.0, gravity=120)
                self._fx.burst(cx, cy, 1, palette=(GOLD,), speed=(0, 5), life=(0.25, 0.35),
                               size=(24, 30), style=GLOW, drag=4.0)
        if self._shown != self._target:
            step = self._rate * dt
            if abs(self._target - self._shown) <= step:
                self._shown = float(self._target)
            else:
                self._shown += step if self._target > self._shown else -step
        if self._time % SPIN_EVERY < dt:
            self._spin = max(self._spin, 0.5)
        self._spin = max(0.0, self._spin - dt)
        self._flash = max(0.0, self._flash - dt * 2.5)
        for d in self._deltas:
            d[2] += dt
        self._deltas = [d for d in self._deltas if d[2] < 1.3]
        self._fx.update(dt)

    # ------------------------------------------------------------------ drawing
    def _coin_center(self) -> tuple[int, int]:
        return self._rect.x + 26, self._rect.centery

    def _outlined(self, text: str, size: int, color) -> pygame.Surface:
        font = self._fonts.get(size)
        base = font.render(text, True, color)
        edge = font.render(text, True, (24, 12, 4))
        out = pygame.Surface((base.get_width() + 4, base.get_height() + 4), pygame.SRCALPHA)
        for dx, dy in ((0, 2), (4, 2), (2, 0), (2, 4), (1, 1), (3, 3), (1, 3), (3, 1)):
            out.blit(edge, (dx, dy))
        out.blit(base, (2, 2))
        return out

    def draw(self, surface: pygame.Surface, anchor: str | None = None,
             pos: tuple[int, int] | None = None) -> pygame.Rect:
        anchor = anchor or DEFAULT_POS[0]
        pos = pos or DEFAULT_POS[1]
        number = self._outlined(format_gold(self.shown), 26, GOLD_LIGHT if self.counting else GOLD)
        w, h = max(132, number.get_width() + 62), 46
        rect = pygame.Rect(0, 0, w, h)
        setattr(rect, anchor, pos)
        self._rect = rect
        plate = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(plate, _PLATE, plate.get_rect(), border_radius=10)
        surface.blit(plate, rect.topleft)
        border = _BORDER
        if self._flash > 0:
            k = self._flash
            border = tuple(int(b + (c - b) * k) for b, c in zip(_BORDER, self._flash_color))
        pygame.draw.rect(surface, border, rect, 2, border_radius=10)
        pygame.draw.line(surface, (90, 66, 30), (rect.x + 10, rect.y + 3), (rect.right - 10, rect.y + 3))
        cx, cy = self._coin_center()
        glow = soft_glow((60, 44, 10), 26)
        surface.blit(glow, glow.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGB_ADD)
        if self._coin:
            k = 0
            if self._spin > 0:
                k = int(self._time * 18) % len(self._coin)
            img = self._coin[k]
            surface.blit(img, img.get_rect(center=(cx, cy + int(math.sin(self._time * 2) * 1))))
        else:
            pygame.draw.circle(surface, GOLD, (cx, cy), 9)
            pygame.draw.circle(surface, (140, 90, 20), (cx, cy), 9, 2)
        surface.blit(number, number.get_rect(midleft=(rect.x + 46, rect.centery)))
        for text, color, age, direction in self._deltas:
            img = self._outlined(text, 20, color)
            img.set_alpha(int(255 * max(0.0, 1 - age / 1.3)))
            if direction < 0:                       # gains rise up towards the plate
                y = rect.bottom + 34 - min(1.0, age / 0.5) * 18
            else:                                   # losses drop away from it
                y = rect.bottom + 16 + age * 22
            surface.blit(img, img.get_rect(midright=(rect.right - 6, int(y))))
        self._fx.draw(surface)
        return rect
