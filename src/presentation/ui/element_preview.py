"""Mage elements on the battlefield: what an aimed card will do, and who would react.

* ``draw_preview_bubble`` — while you aim a Mage card, a panel under the target:
  "[fuego]3 + [agua]2 = [vapor] ¡VAPOR!" / what the reaction does / the HP it will cost. Built
  from ``application.play_preview`` (the play simulated on a copy of the combat).
* ``draw_react_hint`` — while a card is hovered or held, every enemy it would react
  with shows the reaction icon bobbing next to its element badge.
* ``draw_element_floor`` — a soft pulsing glow under an enemy that holds an element.

Rows are lists of parts: ``"@icon"`` (a ui icon) or ``(text, colour)``.
"""
from __future__ import annotations

import math
from functools import lru_cache

import pygame

from src.application.play_preview import EnemyPreview
from src.domain.elements import Element, Reaction, reaction_summary
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui import glossary as gl
from src.presentation.ui.pixel_ui import outlined

Part = str | tuple[str, tuple[int, int, int]]

_BG = (22, 16, 28)
_TEXT = (236, 228, 214)
_PAD = 10
_ROW_H = 28
_ICON = {Element.FIRE: "fire", Element.WATER: "water", Element.EARTH: "earth", Element.AIR: "air"}


def element_icon(element: Element) -> str:
    return _ICON[element]


def element_ink(element: Element) -> tuple[int, int, int]:
    return gl.ELEMENT_COLOR[element.value]


def preview_rows(ep: EnemyPreview, keyword: str = "", *, compact: bool = False) -> list[list[Part]]:
    """The bubble's rows for one enemy (empty when the card changes nothing on it).

    ``compact`` (area cards: one bubble under every enemy): reaction icon + name only.
    """
    rows: list[list[Part]] = []
    if compact:
        for ev in ep.reactions[:2]:
            rows.append([f"@{gl.REACTION_ICON[ev.reaction]}",
                         (f"¡{ev.reaction.value.upper()}!", gl.REACTION_COLOR[ev.reaction])])
        if not ep.reactions and ep.after is not None and ep.after != ep.before:
            el, n = ep.after
            rows.append([f"@{_ICON[el]}", (f"{el.value} {n}", element_ink(el))])
        if rows and ep.hp_loss > 0:
            rows.append([(f"−{ep.hp_loss} de vida", gl.DAMAGE)])
        return rows
    for ev in ep.reactions[:2]:
        first, second = ev.first, ev.second
        row: list[Part] = []
        if first is not None and second is not None:
            had = ep.before[1] if ep.before and ep.before[0] is first else max(0, ev.stacks - 1)
            row += [f"@{_ICON[first]}", (str(had), element_ink(first)), ("+", _TEXT),
                    f"@{_ICON[second]}", (str(max(0, ev.stacks - had)), element_ink(second)), ("=", _TEXT)]
        row += [f"@{gl.REACTION_ICON[ev.reaction]}",
                (f"¡{ev.reaction.value.upper()}!", gl.REACTION_COLOR[ev.reaction])]
        rows.append(row)
        rows.append([(reaction_summary(ev.reaction, ev.stacks), _TEXT)])
    if not ep.reactions and ep.after is not None and ep.after != ep.before:
        el, n = ep.after
        if ep.before is not None and ep.before[0] is el:
            rows.append([f"@{_ICON[el]}", (f"{el.value} {ep.before[1]} → {n}", element_ink(el))])
        else:
            rows.append([f"@{_ICON[el]}", (f"+{n} de {el.value}", element_ink(el))])
    if keyword:
        rows.append([("@reaction"), (f"Reacción: {keyword}", gl.REACTION_INK)])
    if rows and ep.hp_loss > 0:
        rows.append([(f"−{ep.hp_loss} de vida" + ("  ¡muere!" if ep.killed else ""), gl.DAMAGE)])
    return rows


def _row_width(row: list[Part], font) -> int:
    w = 0
    for p in row:
        if isinstance(p, str):
            icon = ui_icon(p[1:], 2)
            w += (icon.get_width() if icon else 0) + 4
        else:
            w += font.size(p[0])[0] + 6
    return w


def draw_row(surface: pygame.Surface, row: list[Part], x: int, cy: int, fonts: FontRegistry,
             size: int = 16) -> int:
    """Draw one row left to right, vertically centred on ``cy``; returns the end x."""
    font = fonts.get(size)
    for p in row:
        if isinstance(p, str):
            icon = ui_icon(p[1:], 2)
            if icon is not None:
                surface.blit(icon, icon.get_rect(midleft=(x, cy)))
                x += icon.get_width() + 4
        else:
            label = outlined(font, p[0], p[1])
            surface.blit(label, label.get_rect(midleft=(x, cy)))
            x += label.get_width() + 6
    return x


def draw_preview_bubble(surface: pygame.Surface, anchor: tuple[int, int], rows: list[list[Part]],
                        fonts: FontRegistry, accent: tuple[int, int, int], t: float = 0.0,
                        bottom_limit: int | None = None) -> pygame.Rect | None:
    """Panel centred under ``anchor`` (x, top y) with a small pointer up. Kept on screen."""
    if not rows:
        return None
    font = fonts.get(16)
    w = max(_row_width(r, font) for r in rows) + 2 * _PAD
    h = len(rows) * _ROW_H + 2 * _PAD - 6
    sw, sh = surface.get_size()
    x = max(6, min(sw - w - 6, anchor[0] - w // 2))
    y = anchor[1] + 10
    if bottom_limit is not None and y + h > bottom_limit:
        y = max(70, bottom_limit - h)
    rect = pygame.Rect(x, y, w, h)
    pulse = 0.5 + 0.5 * math.sin(t * 4.0)
    rim = tuple(min(255, int(c * (0.8 + 0.2 * pulse))) for c in accent)
    pygame.draw.rect(surface, _BG, rect, border_radius=8)
    pygame.draw.rect(surface, rim, rect, 2, border_radius=8)
    px = max(rect.x + 12, min(rect.right - 12, anchor[0]))
    pygame.draw.polygon(surface, rim, [(px - 8, rect.y), (px + 8, rect.y), (px, rect.y - 9)])
    for k, row in enumerate(rows):
        draw_row(surface, row, rect.x + _PAD, rect.y + _PAD + k * _ROW_H + _ROW_H // 2 - 3, fonts)
    return rect


def draw_react_hint(surface: pygame.Surface, badge: pygame.Rect, reaction: Reaction, t: float) -> None:
    """A reaction would happen here: ring round the element badge + its icon bobbing beside it."""
    color = gl.REACTION_COLOR[reaction]
    pulse = 0.5 + 0.5 * math.sin(t * 6.0)
    pygame.draw.circle(surface, color, badge.center, badge.w // 2 + 3 + int(2 * pulse), 2)
    icon = ui_icon(gl.REACTION_ICON[reaction], 2)
    if icon is not None:
        bob = int(3 * math.sin(t * 5.0))
        surface.blit(icon, icon.get_rect(midleft=(badge.right + 4, badge.centery - 18 + bob)))


@lru_cache(maxsize=64)
def _floor_glow(color: tuple[int, int, int], w: int, h: int, level: int) -> pygame.Surface:
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    steps = 8
    for k in range(steps, 0, -1):
        a = int((6 + level * 2) * (steps - k + 1) / steps * 2.2)
        rw, rh = w * k / steps, h * k / steps
        pygame.draw.ellipse(surf, (*color, min(255, a)), ((w - rw) / 2, (h - rh) / 2, rw, rh))
    return surf


def draw_element_floor(surface: pygame.Surface, feet: tuple[int, int], color: tuple[int, int, int],
                       t: float, width: int = 150, strong: bool = False) -> None:
    """Soft glow on the floor under an enemy (additive), pulsing; ``strong`` when it would react."""
    level = int(4 + 3 * (0.5 + 0.5 * math.sin(t * 2.6))) + (6 if strong else 0)
    glow = _floor_glow(color, width, max(18, width // 4), level)
    surface.blit(glow, glow.get_rect(center=feet), special_flags=pygame.BLEND_RGBA_ADD)
