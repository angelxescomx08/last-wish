"""Main menu scene.

Options (top to bottom):
  • Jugar / Continuar  — start or resume a run
  • Ajustes            — settings (not yet implemented; shown grayed out)
  • Salir              — quit the application

Navigation: arrow keys + Enter, or mouse hover + click.
The requested_action attribute is set when the player confirms a choice.
SceneManager must reset it to None after consuming it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry


class MenuAction(Enum):
    PLAY     = auto()
    SETTINGS = auto()
    EXIT     = auto()


@dataclass
class _Option:
    label:   str
    action:  MenuAction
    enabled: bool = True


# ---------------------------------------------------------------------------
# Layout constants (virtual 1280×720 canvas)
# ---------------------------------------------------------------------------

_BG_COLOR        = pygame.Color(14, 20, 14)
_TITLE_Y: int    = 220
_SUBTITLE_Y: int = 310
_OPTIONS_Y: int  = 420   # top option centre-y
_OPTION_GAP: int = 60    # vertical distance between option centres
_NAV_HINT_Y: int = 690


class MainMenuScene:
    """Full main menu with keyboard and mouse navigation."""

    _TITLE    = "Último Deseo"
    _SUBTITLE = "Un juego de cartas"
    _NAV_HINT = "↑ ↓ para navegar  |  ENTER para confirmar"

    def __init__(self, fonts: FontRegistry, *, has_active_game: bool = False) -> None:
        self._fonts          = fonts
        self._options        = self._build_options(has_active_game)
        self._selected_index = 0
        self._option_rects:  list[pygame.Rect] = []
        self.requested_action: MenuAction | None = None

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

        title_surf = self._fonts.get(68).render(self._TITLE, True, colors.TEXT_ACCENT)
        surface.blit(title_surf, title_surf.get_rect(centerx=cx, centery=_TITLE_Y))

        sub_surf = self._fonts.get(28).render(self._SUBTITLE, True, colors.TEXT_PRIMARY)
        surface.blit(sub_surf, sub_surf.get_rect(centerx=cx, centery=_SUBTITLE_Y))

        self._option_rects = []
        for i, opt in enumerate(self._options):
            oy = _OPTIONS_Y + i * _OPTION_GAP
            rect = self._draw_option(surface, opt, cx, oy, selected=(i == self._selected_index))
            self._option_rects.append(rect)

        hint_surf = self._fonts.get(13).render(self._NAV_HINT, True, colors.TEXT_SECONDARY)
        surface.blit(hint_surf, hint_surf.get_rect(centerx=cx, centery=_NAV_HINT_Y))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_options(self, has_active_game: bool) -> list[_Option]:
        play_label = "Continuar" if has_active_game else "Jugar"
        return [
            _Option(play_label, MenuAction.PLAY),
            _Option("Ajustes",  MenuAction.SETTINGS, enabled=False),
            _Option("Salir",    MenuAction.EXIT),
        ]

    def _draw_option(
        self,
        surface: pygame.Surface,
        opt: _Option,
        cx: int,
        cy: int,
        *,
        selected: bool,
    ) -> pygame.Rect:
        if not opt.enabled:
            color = pygame.Color(80, 80, 80)
        elif selected:
            color = colors.TEXT_ACCENT
        else:
            color = colors.TEXT_PRIMARY

        font_size = 38 if selected else 30
        text_surf = self._fonts.get(font_size).render(opt.label, True, color)
        rect = text_surf.get_rect(centerx=cx, centery=cy)
        surface.blit(text_surf, rect)

        if selected and opt.enabled:
            arrow_surf = self._fonts.get(font_size).render(">", True, colors.TEXT_ACCENT)
            surface.blit(arrow_surf, (rect.left - arrow_surf.get_width() - 14, rect.top))

        return rect

    def _move_selection(self, delta: int) -> None:
        n = len(self._options)
        for _ in range(n):
            self._selected_index = (self._selected_index + delta) % n
            if self._options[self._selected_index].enabled:
                return

    def _confirm_selection(self) -> None:
        opt = self._options[self._selected_index]
        if opt.enabled:
            self.requested_action = opt.action

    def _update_hover(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos) and self._options[i].enabled:
                self._selected_index = i
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos) and self._options[i].enabled:
                self._selected_index = i
                self._confirm_selection()
                return
