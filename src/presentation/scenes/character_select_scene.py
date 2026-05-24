"""Character selection scene.

Displays three character panels side-by-side with stats and a visual bar
for each attribute. The player navigates with arrow keys or mouse and
confirms with Enter.

Public flags consumed by SceneManager:
  confirmed   → True when player confirms a character (SceneManager resets it)
  back_to_menu→ True when player presses ESC (SceneManager resets it)

selected_character is always valid while the scene is alive.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from src.domain.character import ALL_CHARACTERS, Character, CharacterStats
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

# ---------------------------------------------------------------------------
# Layout (virtual 1280×720 canvas)
# ---------------------------------------------------------------------------

_BG_COLOR          = pygame.Color(14, 20, 14)
_TITLE_Y: int      = 50
_PANEL_W: int      = 278
_PANEL_H: int      = 420
_PANEL_GAP: int    = 26
_PANELS_TOP: int   = 110

_PANELS_LEFT: int  = (1280 - 3 * _PANEL_W - 2 * _PANEL_GAP) // 2
_HINT_Y: int       = 692

_BAR_W: int        = _PANEL_W - 28  # bar width inside the panel
_BAR_H: int        = 5
_CORNER: int       = 7


# ---------------------------------------------------------------------------
# Stat display configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _StatRow:
    label:     str
    attr:      str          # attribute name on CharacterStats
    bar_color: pygame.Color


_STAT_ROWS: list[_StatRow] = [
    _StatRow("Daño",     "damage",    colors.TEXT_DAMAGE),
    _StatRow("Vida",     "max_hp",    colors.HP_FILL),
    _StatRow("Suerte",   "luck",      colors.TEXT_ACCENT),
    _StatRow("Maná",     "max_mana",  colors.MANA_FILL),
    _StatRow("Destreza", "dexterity", colors.BLOCK_COLOR),
]

# Pre-compute per-stat maximum across all characters for bar scaling
_STAT_MAXES: dict[str, int] = {
    row.attr: max(getattr(c.stats, row.attr) for c in ALL_CHARACTERS)
    for row in _STAT_ROWS
}


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class CharacterSelectScene:
    """Interactive character selection screen with stat panels."""

    _TITLE    = "SELECCIÓN DE PERSONAJE"
    _NAV_HINT = "← → para navegar  |  ENTER para confirmar  |  ESC para volver"

    def __init__(self, fonts: FontRegistry) -> None:
        self._fonts          = fonts
        self._selected_index = 0
        self._panel_rects:   list[pygame.Rect] = []
        self.confirmed       = False
        self.back_to_menu    = False

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self._move_selection(-1)
            elif event.key == pygame.K_RIGHT:
                self._move_selection(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirmed = True
            elif event.key == pygame.K_ESCAPE:
                self.back_to_menu = True
        elif event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG_COLOR)
        cx = surface.get_width() // 2

        title_surf = self._fonts.get(30).render(self._TITLE, True, colors.TEXT_ACCENT)
        surface.blit(title_surf, title_surf.get_rect(centerx=cx, centery=_TITLE_Y))

        self._panel_rects = []
        for i, character in enumerate(ALL_CHARACTERS):
            px = _PANELS_LEFT + i * (_PANEL_W + _PANEL_GAP)
            rect = self._draw_panel(surface, character, px, _PANELS_TOP,
                                    selected=(i == self._selected_index))
            self._panel_rects.append(rect)

        hint_surf = self._fonts.get(13).render(self._NAV_HINT, True, colors.TEXT_SECONDARY)
        surface.blit(hint_surf, hint_surf.get_rect(centerx=cx, centery=_HINT_Y))

    # ------------------------------------------------------------------
    # Public accessor
    # ------------------------------------------------------------------

    @property
    def selected_character(self) -> Character:
        return ALL_CHARACTERS[self._selected_index]

    # ------------------------------------------------------------------
    # Panel drawing
    # ------------------------------------------------------------------

    def _draw_panel(
        self,
        surface: pygame.Surface,
        character: Character,
        x: int,
        y: int,
        *,
        selected: bool,
    ) -> pygame.Rect:
        rect = pygame.Rect(x, y, _PANEL_W, _PANEL_H)

        # Background
        pygame.draw.rect(surface, colors.BG_PANEL, rect, border_radius=_CORNER)

        # Border — gold when selected, subtle otherwise
        border_col = colors.TEXT_ACCENT if selected else colors.PANEL_BORDER
        border_w   = 2 if selected else 1
        pygame.draw.rect(surface, border_col, rect, border_w, border_radius=_CORNER)

        cx = x + _PANEL_W // 2

        # Character name
        name_surf = self._fonts.get(22).render(character.name, True, colors.TEXT_ACCENT if selected else colors.TEXT_PRIMARY)
        surface.blit(name_surf, name_surf.get_rect(centerx=cx, centery=y + 28))

        # Separator
        pygame.draw.line(surface, colors.PANEL_BORDER,
                         (x + 12, y + 50), (x + _PANEL_W - 12, y + 50))

        # Description (single line, truncated to fit)
        desc_surf = self._fonts.get(11).render(character.description, True, colors.TEXT_SECONDARY)
        surface.blit(desc_surf, desc_surf.get_rect(centerx=cx, centery=y + 68))

        # Stats header
        stats_label = self._fonts.get(9).render("ESTADÍSTICAS", True, colors.TEXT_SECONDARY)
        surface.blit(stats_label, (x + 14, y + 90))

        # Stat rows
        stat_y = y + 110
        for row in _STAT_ROWS:
            self._draw_stat_row(surface, row, getattr(character.stats, row.attr),
                                x + 14, stat_y)
            stat_y += 52

        # Selection indicator at bottom
        if selected:
            sel_surf = self._fonts.get(12).render("SELECCIONADO", True, colors.TEXT_ACCENT)
            surface.blit(sel_surf, sel_surf.get_rect(centerx=cx, centery=y + _PANEL_H - 18))

        return rect

    def _draw_stat_row(
        self,
        surface: pygame.Surface,
        row: _StatRow,
        value: int,
        x: int,
        y: int,
    ) -> None:
        # Label (left) + value (right)
        label_surf = self._fonts.get(11).render(row.label + ":", True, colors.TEXT_PRIMARY)
        surface.blit(label_surf, (x, y))

        val_surf = self._fonts.get(11).render(str(value), True, row.bar_color)
        surface.blit(val_surf, (x + _BAR_W - val_surf.get_width(), y))

        # Bar track
        bar_y = y + 17
        track_rect = pygame.Rect(x, bar_y, _BAR_W, _BAR_H)
        pygame.draw.rect(surface, colors.BG_DARK, track_rect, border_radius=2)

        # Filled portion
        max_val = _STAT_MAXES.get(row.attr, 1) or 1
        fill_w  = max(2, int(_BAR_W * value / max_val))
        fill_rect = pygame.Rect(x, bar_y, fill_w, _BAR_H)
        pygame.draw.rect(surface, row.bar_color, fill_rect, border_radius=2)

    # ------------------------------------------------------------------
    # Input helpers
    # ------------------------------------------------------------------

    def _move_selection(self, delta: int) -> None:
        n = len(ALL_CHARACTERS)
        self._selected_index = (self._selected_index + delta) % n

    def _update_hover(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._panel_rects):
            if rect.collidepoint(pos):
                self._selected_index = i
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._panel_rects):
            if rect.collidepoint(pos):
                if self._selected_index == i:
                    self.confirmed = True
                else:
                    self._selected_index = i
                return
