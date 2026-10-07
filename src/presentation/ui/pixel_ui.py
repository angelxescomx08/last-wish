"""Pixel-art HUD widgets built from the UI kit (``infrastructure/ui_kit``) and icons.

* ``draw_panel`` — iron 9-slice frame.
* ``draw_button`` — bronze / gold 3-slice button with icon, outlined label and
  key cap; hover lifts it and sweeps a light across, press sinks it, ``glow``
  adds a pulsing aura (End Turn when nothing is left to play).
* ``draw_keycap`` — a small key ("Esc", "C", "E") so shortcuts are visible.
* ``draw_topbar`` / ``draw_trim`` / ``draw_ribbon`` — top bar plate, gold edge, turn ribbon.
* ``outlined`` — text with a 1 px dark outline (readable on any background).
* ``ManaOrb`` — the animated mana orb: swirling liquid cut at the mana level with a
  moving crest, splash and drops when mana is spent, a glow and rising motes when it
  refills, a shake and red rim when a card cannot be paid.

Every helper falls back to plain shapes when the kit files are missing.
"""
from __future__ import annotations

import math
from functools import lru_cache

import pygame

from src.domain.mana import Mana
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.infrastructure.ui_kit import kit_piece, kit_slice
from src.presentation.fx.bursts import GLOW, SQUARE, BurstParticles

CREAM = (250, 236, 206)
INK = (14, 10, 18)


@lru_cache(maxsize=512)
def _outlined_cached(font: pygame.font.Font, text: str, color, outline) -> pygame.Surface:
    base = font.render(text, True, color)
    edge = font.render(text, True, outline)
    out = pygame.Surface((base.get_width() + 2, base.get_height() + 2), pygame.SRCALPHA)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2), (0, 0), (2, 2), (0, 2), (2, 0)):
        out.blit(edge, (dx, dy))
    out.blit(base, (1, 1))
    return out


def outlined(font: pygame.font.Font, text: str, color=CREAM, outline=INK) -> pygame.Surface:
    return _outlined_cached(font, text, tuple(color[:3]), tuple(outline[:3]))


# ---------------------------------------------------------------- frames

def draw_panel(surface: pygame.Surface, rect: pygame.Rect, *, alpha: int = 255) -> None:
    frame = kit_slice("panel", rect.w, rect.h)
    if frame is None:
        pygame.draw.rect(surface, (22, 20, 32), rect, border_radius=6)
        pygame.draw.rect(surface, (150, 120, 70), rect, 2, border_radius=6)
        return
    if alpha < 255:
        frame = frame.copy()
        frame.set_alpha(alpha)
    surface.blit(frame, rect.topleft)


def draw_topbar(surface: pygame.Surface, height: int = 68) -> None:
    tile = kit_piece("topbar")
    if tile is None:
        pygame.draw.rect(surface, (22, 20, 32), (0, 0, surface.get_width(), height))
        return
    for x in range(0, surface.get_width(), tile.get_width()):
        surface.blit(tile, (x, height - tile.get_height()))


def draw_trim(surface: pygame.Surface, y: int, *, flip: bool = False) -> None:
    tile = kit_piece("trim")
    if tile is None:
        pygame.draw.line(surface, (180, 140, 60), (0, y), (surface.get_width(), y), 2)
        return
    if flip:
        tile = pygame.transform.flip(tile, False, True)
    for x in range(0, surface.get_width(), tile.get_width()):
        surface.blit(tile, (x, y - tile.get_height() // 2))


def draw_ribbon(surface: pygame.Surface, center: tuple[int, int], text: str, fonts: FontRegistry,
                *, size: int = 15) -> pygame.Rect:
    label = outlined(fonts.get(size), text, (255, 236, 200))
    w = label.get_width() + 44
    band = kit_slice("ribbon", w, 32)
    rect = pygame.Rect(0, 0, w, 32)
    rect.center = center
    if band is not None:
        surface.blit(band, rect)
    else:
        pygame.draw.rect(surface, (150, 30, 40), rect, border_radius=4)
    surface.blit(label, label.get_rect(center=(rect.centerx, rect.centery - 1)))
    return rect


def draw_keycap(surface: pygame.Surface, center: tuple[int, int], text: str, fonts: FontRegistry) -> pygame.Rect:
    label = fonts.get(11).render(text, True, (40, 30, 24))
    w = max(18, label.get_width() + 8)
    rect = pygame.Rect(0, 0, w, 18)
    rect.center = center
    pygame.draw.rect(surface, (18, 12, 14), rect.inflate(2, 2), border_radius=4)
    pygame.draw.rect(surface, (150, 136, 116), rect.move(0, 1), border_radius=3)
    pygame.draw.rect(surface, (232, 220, 196), pygame.Rect(rect.x, rect.y, rect.w, rect.h - 2), border_radius=3)
    surface.blit(label, label.get_rect(center=(rect.centerx, rect.centery - 1)))
    return rect


# ---------------------------------------------------------------- buttons

@lru_cache(maxsize=32)
def _glow_rect(w: int, h: int, color) -> pygame.Surface:
    pad = 14
    surf = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    for k in range(pad, 0, -2):
        a = int(70 * (1 - k / pad) ** 1.5)
        pygame.draw.rect(surf, (*color, a), pygame.Rect(pad - k, pad - k, w + 2 * k, h + 2 * k),
                         border_radius=k + 4)
    return surf


def _sheen(surface: pygame.Surface, rect: pygame.Rect, phase: float, strength: int) -> None:
    """A slanted light band crossing the button face (``phase`` 0..1), added on top."""
    inner = rect.inflate(-10, -10)
    if inner.w <= 0 or inner.h <= 0:
        return
    band = pygame.Surface(inner.size)
    x = int(-inner.h + phase * (inner.w + inner.h * 2))
    pygame.draw.polygon(band, (strength, strength, max(0, strength - 10)),
                        [(x, inner.h), (x + inner.h * 0.6, 0), (x + inner.h * 0.6 + 10, 0), (x + 10, inner.h)])
    surface.blit(band, inner.topleft, special_flags=pygame.BLEND_RGB_ADD)


def draw_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    fonts: FontRegistry,
    *,
    style: str = "bronze",
    state: str = "idle",
    icon: str | None = None,
    key: str | None = None,
    t: float = 0.0,
    glow: float = 0.0,
    size: int = 15,
) -> pygame.Rect:
    """Draw a kit button; ``state`` is idle / hover / press / off. Returns the hit rect."""
    shown = rect.move(0, 2 if state == "press" else -1 if state == "hover" else 0)
    if glow > 0 and state != "off":
        g = _glow_rect(rect.w, rect.h, (255, 200, 90))
        g = g.copy()
        g.set_alpha(int(255 * glow))
        surface.blit(g, g.get_rect(center=shown.center), special_flags=pygame.BLEND_RGB_ADD)
    body = kit_slice(f"btn_{style}_{state}", rect.w, rect.h)
    if body is not None:
        surface.blit(body, shown.topleft)
    else:
        col = (90, 90, 96) if state == "off" else (150, 110, 40) if style == "gold" else (110, 50, 50)
        pygame.draw.rect(surface, col, shown, border_radius=6)
        pygame.draw.rect(surface, (230, 190, 100), shown, 2, border_radius=6)
    if state == "hover" or (style == "gold" and state == "idle"):
        cycle = 1.4 if state == "hover" else 3.6
        phase = (t % cycle) / cycle
        if state == "hover" or phase < 0.4:
            _sheen(surface, shown, phase / (1.0 if state == "hover" else 0.4), 70 if state == "hover" else 45)

    ink = (176, 172, 168) if state == "off" else CREAM
    text = outlined(fonts.get(size), label, ink) if label else None
    icon_s = ui_icon(icon, 2) if icon else None
    key_w = (max(18, fonts.get(11).size(key)[0] + 8) + 6) if key else 0
    content_w = (icon_s.get_width() + 4 if icon_s else 0) + (text.get_width() if text else 0) + key_w
    x = shown.centerx - content_w // 2
    cy = shown.centery - (1 if state != "press" else 0)
    if icon_s is not None:
        if state == "off":
            icon_s = icon_s.copy()
            icon_s.fill((140, 140, 140, 255), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(icon_s, icon_s.get_rect(midleft=(x, cy)))
        x += icon_s.get_width() + 4
    if text is not None:
        surface.blit(text, text.get_rect(midleft=(x, cy)))
        x += text.get_width()
    if key:
        draw_keycap(surface, (x + key_w // 2 + 3, cy), key, fonts)
    return rect


def button_state(rect: pygame.Rect, mouse: tuple[int, int], pressed: bool, *, enabled: bool = True) -> str:
    if not enabled:
        return "off"
    if rect.collidepoint(mouse):
        return "press" if pressed else "hover"
    return "idle"


# ---------------------------------------------------------------- mana orb

_ORB_C = 23.5
_ORB_R = 18.5
_LIQUID_SPLASH = [(160, 214, 255), (78, 156, 246), (232, 248, 255)]
_MOTES = [(232, 248, 255), (160, 214, 255), (120, 190, 255)]


class ManaOrb:
    """Animated mana orb. Call ``update(dt, mana)`` every frame, ``error()`` on a failed play."""

    SCALE = 2
    SIZE = 48 * SCALE

    def __init__(self, seed: int = 3) -> None:
        self.level: float | None = None      # displayed fill 0..1 (eases towards the real one)
        self.shown: int | None = None        # last mana value seen
        self.t = 0.0
        self.flash = 0.0                      # refill glow
        self.splash = 0.0                     # spend ripple
        self.shake = 0.0                      # can't pay
        self.center = (68, 595)
        self._particles = BurstParticles(capacity=160, seed=seed)
        self._native = pygame.Surface((48, 48), pygame.SRCALPHA)

    @staticmethod
    def target(mana: Mana) -> float:
        return max(0.0, min(1.0, mana.current / mana.maximum)) if mana.maximum > 0 else 0.0

    def error(self) -> None:
        self.shake = 0.45

    def update(self, dt: float, mana: Mana) -> None:
        dt = max(0.0, min(dt, 0.1))
        self.t += dt
        goal = self.target(mana)
        if self.level is None:
            self.level, self.shown = goal, mana.current
        self.level += (goal - self.level) * min(1.0, dt * 7.0)
        cx, cy = self.center
        if mana.current < self.shown:          # spent: the liquid drops with a splash
            self.splash = 0.5
            n = 6 + 3 * min(5, self.shown - mana.current)
            self._particles.burst(cx, cy - 6, n, palette=_LIQUID_SPLASH, speed=(60, 170),
                                  angle=(math.pi * 1.1, math.pi * 1.9), life=(0.35, 0.7),
                                  size=(2, 4), gravity=420, drag=1.0)
        elif mana.current > self.shown:        # refilled: glow + motes rising out of the orb
            self.flash = 0.7
            for k in range(14):
                a = k / 14 * math.tau
                self._particles.emit(cx + math.cos(a) * 30, cy + math.sin(a) * 30,
                                     math.cos(a) * 15, -70 - 40 * (k % 3), life=0.9,
                                     palette=_MOTES, size=3, style=GLOW, drag=1.5)
        self.shown = mana.current
        self.flash = max(0.0, self.flash - dt)
        self.splash = max(0.0, self.splash - dt)
        self.shake = max(0.0, self.shake - dt)
        if mana.current > 0 and self._particles.count < 40 and int(self.t * 6) != int((self.t - dt) * 6):
            # a bubble now and then
            self._particles.emit(cx + (math.sin(self.t * 13) * 14), cy + 26, 0, -40, life=0.7,
                                 palette=_MOTES, size=2, style=SQUARE)
        self._particles.update(dt)

    def _compose(self) -> pygame.Surface:
        surf = self._native
        surf.fill((0, 0, 0, 0))
        back = kit_piece("orb_back", 1)
        if back is not None:
            surf.blit(back, (0, 0))
        level = self.level or 0.0
        liquid = kit_piece(f"orb_liquid_{int(self.t * 8) % 8}", 1)
        if liquid is not None and level > 0.001:
            top = _ORB_C - _ORB_R
            surface_y = top + (1 - level) * (_ORB_R * 2)
            amp = (1.0 + 1.5 * self.splash) if level < 0.999 else 0.0
            for x in range(4, 44):
                wave = surface_y + math.sin(x * 0.45 + self.t * 3.2) * amp
                y0 = max(0, int(round(wave)))
                if y0 >= 47:
                    continue
                surf.blit(liquid, (x, y0), pygame.Rect(x, y0, 1, 48 - y0))
                if level < 0.999 and math.hypot(x + 0.5 - _ORB_C, y0 + 0.5 - _ORB_C) < _ORB_R - 0.5:
                    surf.set_at((x, y0), (220, 244, 255, 255))
        glass = kit_piece("orb_glass", 1)
        frame = kit_piece("orb_frame", 1)
        if glass is not None:
            surf.blit(glass, (0, 0))
        if frame is not None:
            surf.blit(frame, (0, 0))
        return surf

    def draw(self, surface: pygame.Surface, center: tuple[int, int], fonts: FontRegistry, mana: Mana) -> pygame.Rect:
        self.center = center
        dx = int(math.sin(self.t * 70) * 4 * (self.shake / 0.45)) if self.shake > 0 else 0
        cx, cy = center[0] + dx, center[1]
        if kit_piece("orb_frame", 1) is None:
            pygame.draw.circle(surface, (20, 30, 70), (cx, cy), 40)
            pygame.draw.circle(surface, (120, 170, 255), (cx, cy), 40, 2)
        else:
            if self.flash > 0:
                halo = _glow_circle(self.SIZE // 2 + 16, (90, 170, 255))
                halo = halo.copy()
                halo.set_alpha(int(255 * min(1.0, self.flash / 0.5)))
                surface.blit(halo, halo.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGB_ADD)
            orb = pygame.transform.scale(self._compose(), (self.SIZE, self.SIZE))
            surface.blit(orb, orb.get_rect(center=(cx, cy)))
            if self.shake > 0:
                pygame.draw.circle(surface, (255, 70, 60), (cx, cy), self.SIZE // 2 - 4, 3)
        empty = mana.current <= 0
        num_col = (255, 140, 130) if empty or self.shake > 0 else (255, 255, 255)
        big = outlined(fonts.get(34), str(mana.current), num_col, (6, 14, 40))
        small = outlined(fonts.get(15), f"/{mana.maximum}", (190, 220, 255), (6, 14, 40))
        total = big.get_width() + small.get_width()
        surface.blit(big, big.get_rect(midleft=(cx - total // 2, cy - 2)))
        surface.blit(small, small.get_rect(bottomleft=(cx - total // 2 + big.get_width(), cy + 12)))
        self._particles.draw(surface)
        return pygame.Rect(cx - self.SIZE // 2, cy - self.SIZE // 2, self.SIZE, self.SIZE)


@lru_cache(maxsize=8)
def _glow_circle(radius: int, color) -> pygame.Surface:
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        a = int(90 * (1 - r / radius) ** 1.4)
        pygame.draw.circle(surf, (*color, a), (radius, radius), r)
    return surf

