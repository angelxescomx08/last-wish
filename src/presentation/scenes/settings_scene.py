"""Settings scene.

Allows the player to toggle game preferences:
  • Mostrar FPS  — toggle the on-screen FPS counter

Navigation: arrow keys + Enter/Space to toggle; ESC or "Volver" to exit.
The cleared flag is set when the player leaves; SceneManager consumes it
and persists the preferences.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.preferences import UserPreferences

# ---------------------------------------------------------------------------
# Layout (virtual 1280×720 canvas)
# ---------------------------------------------------------------------------

_BG_COLOR      = pygame.Color(14, 20, 14)
_TITLE_Y: int  = 200
_ITEMS_Y: int  = 340
_ITEM_GAP: int = 72
_HINT_Y: int   = 690

_COLOR_ON  = pygame.Color(80,  200, 80)
_COLOR_OFF = pygame.Color(160, 70,  70)


class _ItemKind(Enum):
    TOGGLE = auto()
    BACK   = auto()


@dataclass
class _Item:
    label: str
    kind:  _ItemKind


class SettingsScene:
    """Settings screen with toggleable preferences."""

    _TITLE    = "Ajustes"
    _NAV_HINT = "↑ ↓ para navegar  |  ENTER para confirmar"

    def __init__(self, fonts: FontRegistry, prefs: UserPreferences) -> None:
        self._fonts  = fonts
        self._prefs  = prefs
        self._items: list[_Item] = [
            _Item("Mostrar FPS", _ItemKind.TOGGLE),
            _Item("Volver",      _ItemKind.BACK),
        ]
        self._selected     = 0
        self._item_rects:  list[pygame.Rect] = []
        self.cleared: bool = False

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self._selected = (self._selected - 1) % len(self._items)
            elif event.key == pygame.K_DOWN:
                self._selected = (self._selected + 1) % len(self._items)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._confirm()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                if self._items[self._selected].kind == _ItemKind.TOGGLE:
                    self._toggle_fps()
            elif event.key == pygame.K_ESCAPE:
                self.cleared = True
        elif event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG_COLOR)
        cx = surface.get_width() // 2

        title_surf = self._fonts.get(56).render(self._TITLE, True, colors.TEXT_ACCENT)
        surface.blit(title_surf, title_surf.get_rect(centerx=cx, centery=_TITLE_Y))

        self._item_rects = []
        for i, item in enumerate(self._items):
            iy   = _ITEMS_Y + i * _ITEM_GAP
            rect = self._draw_item(surface, item, cx, iy, selected=(i == self._selected))
            self._item_rects.append(rect)

        hint_surf = self._fonts.get(13).render(self._NAV_HINT, True, colors.TEXT_SECONDARY)
        surface.blit(hint_surf, hint_surf.get_rect(centerx=cx, centery=_HINT_Y))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _draw_item(
        self,
        surface: pygame.Surface,
        item: _Item,
        cx: int,
        cy: int,
        *,
        selected: bool,
    ) -> pygame.Rect:
        color     = colors.TEXT_ACCENT if selected else colors.TEXT_PRIMARY
        font_size = 38 if selected else 30
        font      = self._fonts.get(font_size)

        if item.kind == _ItemKind.TOGGLE:
            value_text  = "Activado" if self._prefs.show_fps else "Desactivado"
            value_color = _COLOR_ON if self._prefs.show_fps else _COLOR_OFF
            label_surf  = font.render(item.label, True, color)
            sep_surf    = font.render(":  ", True, color)
            value_surf  = font.render(value_text, True, value_color)

            total_w = (label_surf.get_width() + sep_surf.get_width()
                       + value_surf.get_width())
            x = cx - total_w // 2

            label_rect = label_surf.get_rect(left=x, centery=cy)
            sep_rect   = sep_surf.get_rect(left=label_rect.right, centery=cy)
            value_rect = value_surf.get_rect(left=sep_rect.right, centery=cy)

            surface.blit(label_surf, label_rect)
            surface.blit(sep_surf,   sep_rect)
            surface.blit(value_surf, value_rect)

            bounding = pygame.Rect(
                label_rect.left,
                min(label_rect.top, value_rect.top),
                total_w,
                max(label_rect.height, value_rect.height),
            )
        else:
            text_surf = font.render(item.label, True, color)
            bounding  = text_surf.get_rect(centerx=cx, centery=cy)
            surface.blit(text_surf, bounding)

        if selected:
            arrow_surf = font.render(">", True, colors.TEXT_ACCENT)
            surface.blit(
                arrow_surf,
                (bounding.left - arrow_surf.get_width() - 14,
                 bounding.centery - arrow_surf.get_height() // 2),
            )

        return bounding

    def _toggle_fps(self) -> None:
        self._prefs.show_fps = not self._prefs.show_fps

    def _confirm(self) -> None:
        item = self._items[self._selected]
        if item.kind == _ItemKind.TOGGLE:
            self._toggle_fps()
        else:
            self.cleared = True

    def _update_hover(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._item_rects):
            if rect.collidepoint(pos):
                self._selected = i
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._item_rects):
            if rect.collidepoint(pos):
                self._selected = i
                self._confirm()
                return
