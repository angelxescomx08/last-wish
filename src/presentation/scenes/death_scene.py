"""Death screen scene.

Shown when the player's HP reaches 0. Presents two options:
  • Nueva Partida     — go back to character selection for a fresh run
  • Menú Principal   — return to the main menu

Navigation: arrow keys + Enter, or mouse hover + click.
requested_action is set when the player confirms. SceneManager resets it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

# ---------------------------------------------------------------------------
# Layout (virtual 1280×720 canvas)
# ---------------------------------------------------------------------------

_BG_COLOR          = pygame.Color(8, 5, 10)
_TITLE_Y: int      = 220
_SUBTITLE_Y: int   = 290
_OPTIONS_Y: int    = 390
_OPTION_GAP: int   = 60
_HINT_Y: int       = 692


class DeathAction(Enum):
    NEW_GAME  = auto()
    MAIN_MENU = auto()


@dataclass
class _Option:
    label:  str
    action: DeathAction


class DeathScene:
    """Screen shown when the player dies."""

    _TITLE    = "HAS MUERTO"
    _NAV_HINT = "↑ ↓ para navegar  |  ENTER para confirmar"

    def __init__(self, fonts: FontRegistry, turn_reached: int) -> None:
        self._fonts          = fonts
        self._turn_reached   = turn_reached
        self._selected_index = 0
        self._option_rects:  list[pygame.Rect] = []
        self._options: list[_Option] = [
            _Option("Nueva Partida",   DeathAction.NEW_GAME),
            _Option("Menú Principal",  DeathAction.MAIN_MENU),
        ]
        self.requested_action: DeathAction | None = None

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self._move_selection(-1)
            elif event.key == pygame.K_DOWN:
                self._move_selection(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._confirm_selection()
        elif event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG_COLOR)
        cx = surface.get_width() // 2

        title_surf = self._fonts.get(72).render(self._TITLE, True, pygame.Color(210, 40, 40))
        surface.blit(title_surf, title_surf.get_rect(centerx=cx, centery=_TITLE_Y))

        sub_text  = f"Llegaste al turno {self._turn_reached}"
        sub_surf  = self._fonts.get(24).render(sub_text, True, colors.TEXT_PRIMARY)
        surface.blit(sub_surf, sub_surf.get_rect(centerx=cx, centery=_SUBTITLE_Y))

        self._option_rects = []
        for i, opt in enumerate(self._options):
            oy   = _OPTIONS_Y + i * _OPTION_GAP
            rect = self._draw_option(surface, opt, cx, oy, selected=(i == self._selected_index))
            self._option_rects.append(rect)

        hint_surf = self._fonts.get(13).render(self._NAV_HINT, True, colors.TEXT_SECONDARY)
        surface.blit(hint_surf, hint_surf.get_rect(centerx=cx, centery=_HINT_Y))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _draw_option(
        self,
        surface: pygame.Surface,
        opt: _Option,
        cx: int,
        cy: int,
        *,
        selected: bool,
    ) -> pygame.Rect:
        color     = colors.TEXT_ACCENT if selected else colors.TEXT_PRIMARY
        font_size = 38 if selected else 30
        text_surf = self._fonts.get(font_size).render(opt.label, True, color)
        rect      = text_surf.get_rect(centerx=cx, centery=cy)
        surface.blit(text_surf, rect)

        if selected:
            arrow_surf = self._fonts.get(font_size).render(">", True, colors.TEXT_ACCENT)
            surface.blit(arrow_surf, (rect.left - arrow_surf.get_width() - 14, rect.top))

        return rect

    def _move_selection(self, delta: int) -> None:
        n = len(self._options)
        self._selected_index = (self._selected_index + delta) % n

    def _confirm_selection(self) -> None:
        self.requested_action = self._options[self._selected_index].action

    def _update_hover(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos):
                self._selected_index = i
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos):
                self._selected_index = i
                self._confirm_selection()
                return
