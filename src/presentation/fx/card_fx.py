""""Ready" effects for cards whose keyword condition is met right now (Combo, Singular…).

A ready card must read as ready at a glance and stay readable on top of any other
card effect (the golden chroma's gilded frame, sheen, halo and motes, or future
chromas). So the ready effect uses shapes no other effect uses, in the keyword's
own colour, and never touches the card face:

* **Behind** — a breathing aura in the keyword colour (``draw_ready_back``). With
  several ready keywords the aura cycles through their colours.
* **In front** — bright comets running around the card's edge with fading trails
  (golden motes float; comets travel the border), small flares at the corners, and
  a **badge** above the card ("¡COMBO!", with the keyword icon) that bobs and
  pulses (``draw_ready_front``). Several keywords share one badge.

Both follow the card's tilt and scale. New keyword → one ``ReadyStyle`` in
``READY_STYLES``; the widgets pick it up.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from src.domain.card import Card
from src.domain.keywords import Keyword
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.fx import chroma_fx
from src.presentation.fx.bursts import soft_glow

Color = tuple[int, int, int]


@dataclass(frozen=True)
class ReadyStyle:
    label: str        # badge text
    color: Color      # main colour (aura, comets, border)
    light: Color      # comet heads and badge text
    icon: str         # ui icon name


READY_STYLES: dict[Keyword, ReadyStyle] = {
    Keyword.COMBO: ReadyStyle("¡COMBO!", (60, 230, 170), (200, 255, 230), "combo"),
    Keyword.SPOIL: ReadyStyle("¡DESPOJO!", (250, 150, 50), (255, 222, 170), "spoil"),
    Keyword.VOID: ReadyStyle("¡VACÍO!", (90, 160, 255), (200, 225, 255), "void"),
    Keyword.SINGULAR: ReadyStyle("¡SINGULAR!", (190, 130, 255), (236, 214, 255), "singular"),
}
_ORDER = (Keyword.COMBO, Keyword.SPOIL, Keyword.VOID, Keyword.SINGULAR)

COMET_SPEED = 0.32          # laps per second
COMETS_PER_KEYWORD = 3
TRAIL = 9


def ready_keywords(card: Card, combo: bool = False, singular: bool = False,
                   void: bool = False, spoil: bool = False) -> list[Keyword]:
    """The card's keywords whose condition holds now (only layers the card really has)."""
    flags = {
        Keyword.COMBO: combo and bool(card.combo_effects()),
        Keyword.SPOIL: spoil and bool(card.spoil_effects()),
        Keyword.VOID: void and bool(card.void_effects()),
        Keyword.SINGULAR: singular and bool(card.singular_effects()),
    }
    return [k for k in _ORDER if flags[k]]


def _styles(keywords) -> list[ReadyStyle]:
    return [READY_STYLES[k] for k in keywords if k in READY_STYLES]


def current_color(keywords, t: float) -> Color | None:
    """Aura colour now: the only one, or cycling through several (1.2 s each)."""
    styles = _styles(keywords)
    if not styles:
        return None
    if len(styles) == 1:
        return styles[0].color
    i = int(t / 1.2) % len(styles)
    k = (t / 1.2) % 1.0
    a, b = styles[i].color, styles[(i + 1) % len(styles)].color
    k = max(0.0, (k - 0.75) / 0.25)                  # hold, then blend into the next
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def draw_ready_back(surface: pygame.Surface, body: pygame.Surface, center: tuple[float, float],
                    keywords, t: float, *, key: tuple, angle: float = 0.0) -> None:
    color = current_color(keywords, t)
    if color is not None:
        chroma_fx.draw_silhouette_aura(surface, body, center, color, t, key=key, angle=angle, speed=5.0)
        chroma_fx.draw_silhouette_aura(surface, body, center, color, t + 0.6, key=key, angle=angle, speed=5.0)


def perimeter_point(u: float, w: float, h: float) -> tuple[float, float]:
    """Point at fraction ``u`` (0..1, clockwise from the top-left) of a w×h rect centred on 0."""
    u %= 1.0
    p = 2 * (w + h)
    d = u * p
    if d < w:
        return -w / 2 + d, -h / 2
    d -= w
    if d < h:
        return w / 2, -h / 2 + d
    d -= h
    if d < w:
        return w / 2 - d, h / 2
    d -= w
    return -w / 2, h / 2 - d


def _rotate(x: float, y: float, angle: float) -> tuple[float, float]:
    """Rotate like ``pygame.transform.rotozoom(angle)`` (counter-clockwise on screen)."""
    if not angle:
        return x, y
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    return x * c + y * s, -x * s + y * c


def comet_positions(keywords, w: float, h: float, t: float, angle: float = 0.0) -> list[tuple[float, float, int]]:
    """Head positions (dx, dy relative to the card centre) and style index of every comet."""
    styles = _styles(keywords)
    n = len(styles) * COMETS_PER_KEYWORD
    out = []
    for i in range(n):
        u = t * COMET_SPEED + i / max(1, n)
        x, y = _rotate(*perimeter_point(u, w, h), angle)
        out.append((x, y, i % len(styles)))
    return out


def draw_ready_front(surface: pygame.Surface, center: tuple[float, float], size: tuple[int, int],
                     keywords, t: float, fonts: FontRegistry | None = None, *, angle: float = 0.0) -> pygame.Rect | None:
    """Comets on the edge, corner flares and the badge. Returns the badge rect (or None)."""
    styles = _styles(keywords)
    if not styles:
        return None
    cx, cy = center
    w, h = size[0] + 4, size[1] + 4
    scale = max(0.6, size[0] / 150)
    n = len(styles) * COMETS_PER_KEYWORD
    perim = 2 * (w + h)
    step = 5.0 / perim                                  # ~5 px between trail dots
    for i in range(n):
        st = styles[i % len(styles)]
        u0 = t * COMET_SPEED + i / n
        for k in range(TRAIL, -1, -1):                  # tail first, head last
            x, y = _rotate(*perimeter_point(u0 - k * step, w, h), angle)
            fade = 1 - k / (TRAIL + 1)
            px, py = int(cx + x), int(cy + y)
            if k == 0:
                glow = soft_glow(st.color, int(11 * scale))
                surface.blit(glow, (px - glow.get_width() // 2, py - glow.get_height() // 2),
                             special_flags=pygame.BLEND_RGB_ADD)
                s = max(3, int(4 * scale))
                pygame.draw.rect(surface, st.light, (px - s // 2, py - s // 2, s, s))
            else:
                s = max(1, int((3.2 * fade) * scale))
                col = tuple(int(c * (0.35 + 0.65 * fade)) for c in st.color)
                pygame.draw.rect(surface, col, (px - s // 2, py - s // 2, s, s))

    pulse = 0.5 + 0.5 * math.sin(t * 6.0)
    for corner in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)):   # flares at the corners
        x, y = _rotate((corner[0] - 0.5) * w, (corner[1] - 0.5) * h, angle)
        glow = soft_glow(styles[0].color, int((6 + 5 * pulse) * scale))
        surface.blit(glow, (int(cx + x) - glow.get_width() // 2, int(cy + y) - glow.get_height() // 2),
                     special_flags=pygame.BLEND_RGB_ADD)

    if fonts is None:
        return None
    return _draw_badge(surface, (cx, cy), h, styles, t, fonts, scale, angle)


def _draw_badge(surface, center, h, styles, t, fonts, scale, angle) -> pygame.Rect:
    font = fonts.get(max(10, int(13 * scale)))
    parts = []
    for st in styles:
        icon = ui_icon(st.icon, 1)
        text = font.render(st.label, True, st.light)
        edge = font.render(st.label, True, (10, 6, 14))
        parts.append((icon, text, edge, st))
    width = sum((p[0].get_width() + 3 if p[0] else 0) + p[1].get_width() for p in parts) + 10 * (len(parts) - 1) + 16
    height = max(font.get_height(), 14) + 6
    bob = math.sin(t * 4.0) * 2 * scale
    x, y = _rotate(0, -h / 2 - height / 2 - 2, angle)
    rect = pygame.Rect(0, 0, width, height)
    rect.center = (int(center[0] + x), int(center[1] + y + bob))
    pulse = 0.5 + 0.5 * math.sin(t * 6.0)
    main = styles[int(t / 1.2) % len(styles)].color if len(styles) > 1 else styles[0].color
    glow = soft_glow(main, int(width * 0.45))
    surface.blit(glow, glow.get_rect(center=rect.center), special_flags=pygame.BLEND_RGB_ADD)
    pygame.draw.rect(surface, (12, 8, 18), rect, border_radius=height // 2)
    border = tuple(int(c * (0.7 + 0.3 * pulse)) for c in main)
    pygame.draw.rect(surface, border, rect, 2, border_radius=height // 2)
    px = rect.x + 8
    for icon, text, edge, _ in parts:
        if icon is not None:
            surface.blit(icon, icon.get_rect(midleft=(px, rect.centery)))
            px += icon.get_width() + 3
        ty = rect.centery - text.get_height() // 2
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            surface.blit(edge, (px + dx, ty + dy))
        surface.blit(text, (px, ty))
        px += text.get_width() + 10
    return rect
