"""The Mage's cheat sheet: the four elements on a wheel and the six reactions between them.

Opened in combat with the "Elementos" button or the R key (``CombatScene``). Every
element sits on a corner of the diamond (Fuego top, Agua right, Aire bottom, Tierra
left); the icon of the reaction two elements make sits on the line that joins them.
On the right, one row per reaction (icon, elements, what it does) and, below, what
each element does on its own. Esc / R / click outside / "Cerrar" close it.
"""
from __future__ import annotations

import math

import pygame

from src.domain.elements import REACTIONS, Element, Reaction
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui import glossary as gl
from src.presentation.ui.element_preview import draw_row, element_icon, element_ink
from src.presentation.ui.pixel_ui import button_state, draw_button, draw_panel, draw_ribbon, outlined

PANEL = pygame.Rect(150, 70, 980, 580)
_CENTER = (PANEL.x + 230, PANEL.y + 300)
_R = 150
CORNERS: dict[Element, tuple[int, int]] = {
    Element.FIRE: (_CENTER[0], _CENTER[1] - _R),
    Element.WATER: (_CENTER[0] + _R, _CENTER[1]),
    Element.AIR: (_CENTER[0], _CENTER[1] + _R),
    Element.EARTH: (_CENTER[0] - _R, _CENTER[1]),
}
_SHORT: dict[Reaction, str] = {
    Reaction.STEAM: "doble de las acumulaciones como daño",
    Reaction.MAGMA: "le quita el escudo · Vulnerable 2",
    Reaction.WILDFIRE: "Fuego a todos los enemigos",
    Reaction.MUD: "triple de las acumulaciones en escudo",
    Reaction.FREEZE: "pierde su próxima acción",
    Reaction.SANDSTORM: "Débil 1 a todos los enemigos",
}
_TEXT = (236, 228, 214)
_ALONE: dict[Element, str] = {
    Element.FIRE: "pierde vida al final de su turno",
    Element.WATER: "sus golpes hacen menos daño",
    Element.EARTH: "recibe más daño por golpe",
    Element.AIR: "nada; sus reacciones van a todos",
}


def reaction_spot(pair: frozenset[Element]) -> tuple[int, int]:
    """Where a reaction's icon goes: middle of the edge, or off-centre on the two diagonals."""
    a, b = sorted(pair, key=lambda e: e.value)
    (ax, ay), (bx, by) = CORNERS[a], CORNERS[b]
    mx, my = (ax + bx) // 2, (ay + by) // 2
    if pair == frozenset({Element.FIRE, Element.AIR}):
        return (mx, my - 58)
    if pair == frozenset({Element.WATER, Element.EARTH}):
        return (mx + 58, my)
    return (mx, my)


class ElementWheelOverlay:
    def __init__(self, fonts: FontRegistry) -> None:
        self._fonts = fonts
        self._mouse = (0, 0)
        self._down = False
        self.dismissed = False
        self.close_rect = pygame.Rect(PANEL.right - 150, PANEL.bottom - 50, 130, 36)
        self._t = 0.0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            self._down = True
            if self.close_rect.collidepoint(event.pos) or not PANEL.collidepoint(event.pos) or event.button == 3:
                self.dismissed = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self._down = False
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_r, pygame.K_RETURN):
            self.dismissed = True

    def update(self, dt: float) -> None:
        self._t += max(0.0, dt)

    def draw(self, surface: pygame.Surface) -> None:
        fonts = self._fonts
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((6, 4, 10, 190))
        surface.blit(shade, (0, 0))
        draw_panel(surface, PANEL)
        draw_ribbon(surface, (PANEL.centerx, PANEL.y + 4), "Elementos y reacciones", fonts, size=16)

        # the wheel: edges, reaction icons, element corners
        for pair in REACTIONS:
            a, b = tuple(pair)
            pygame.draw.line(surface, (74, 66, 92), CORNERS[a], CORNERS[b], 3)
        for pair, reaction in REACTIONS.items():
            x, y = reaction_spot(pair)
            pygame.draw.circle(surface, (22, 16, 28), (x, y), 19)
            pygame.draw.circle(surface, gl.REACTION_COLOR[reaction], (x, y), 19, 2)
            icon = ui_icon(gl.REACTION_ICON[reaction], 2)
            if icon is not None:
                surface.blit(icon, icon.get_rect(center=(x, y)))
        for el, (x, y) in CORNERS.items():
            pulse = 0.5 + 0.5 * math.sin(self._t * 2.4 + list(Element).index(el))
            pygame.draw.circle(surface, (22, 16, 28), (x, y), 36)
            pygame.draw.circle(surface, element_ink(el), (x, y), 36, 2 + int(pulse))
            icon = ui_icon(element_icon(el), 4)
            if icon is not None:
                surface.blit(icon, icon.get_rect(center=(x, y)))
            name = outlined(fonts.get(16), el.value, element_ink(el))
            off = {Element.FIRE: (0, -52), Element.AIR: (0, 52), Element.WATER: (0, 50), Element.EARTH: (0, 50)}[el]
            surface.blit(name, name.get_rect(center=(x + off[0], y + off[1])))
        hint = outlined(fonts.get(14), "Dos elementos distintos en un enemigo = reacción", (176, 170, 160))
        surface.blit(hint, hint.get_rect(center=(_CENTER[0], PANEL.bottom - 34)))

        # reactions list
        x0, y = PANEL.x + 470, PANEL.y + 56
        head = outlined(fonts.get(16), "Reacciones (con la suma de acumulaciones)", (246, 204, 92))
        surface.blit(head, (x0, y)); y += 32
        for pair, reaction in REACTIONS.items():
            a, b = sorted(pair, key=lambda e: list(Element).index(e))
            draw_row(surface, [f"@{gl.REACTION_ICON[reaction]}", (reaction.value, gl.REACTION_COLOR[reaction]),
                               (" ", _TEXT), f"@{element_icon(a)}", ("+", _TEXT), f"@{element_icon(b)}"],
                     x0, y + 12, fonts)
            detail = outlined(fonts.get(14), _SHORT[reaction], _TEXT)
            surface.blit(detail, (x0 + 40, y + 28))
            y += 46
        # elements alone
        y += 10
        head = outlined(fonts.get(16), "Cada elemento solo", (246, 204, 92))
        surface.blit(head, (x0, y)); y += 24
        for el in Element:
            draw_row(surface, [f"@{element_icon(el)}", (el.value + ":", element_ink(el)), (_ALONE[el], _TEXT)],
                     x0, y + 10, fonts, size=14)
            y += 26

        draw_button(surface, self.close_rect, "Cerrar", fonts,
                    state=button_state(self.close_rect, self._mouse, self._down), key="R", size=14)
