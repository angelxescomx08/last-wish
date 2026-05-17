from __future__ import annotations

import pygame

from src.domain.card import Card
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card

_COLS: int     = 10
_GAP_X: int    = 8
_GAP_Y: int    = 22
_PANEL_MARGIN  = 20


class PileViewer:
    """Full-screen modal overlay that lists every card in a pile."""

    def __init__(self, title: str, cards: list[Card], fonts: FontRegistry) -> None:
        self._title  = title
        self._cards  = cards
        self._fonts  = fonts
        self._panel: pygame.Rect | None = None
        self.dismissed: bool = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.dismissed = True
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._panel and not self._panel.collidepoint(event.pos):
                self.dismissed = True

    def draw(self, surface: pygame.Surface) -> None:
        # Dim the scene behind the panel
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 195))
        surface.blit(dim, (0, 0))

        panel = pygame.Rect(70, 55, 1140, 610)
        self._panel = panel

        pygame.draw.rect(surface, colors.BG_PANEL, panel, border_radius=10)
        pygame.draw.rect(surface, colors.BORDER_BRIGHT, panel, 2, border_radius=10)

        # Header
        title_surf = self._fonts.get(20).render(self._title, True, colors.TEXT_ACCENT)
        surface.blit(title_surf, (panel.x + _PANEL_MARGIN, panel.y + 14))

        count_surf = self._fonts.get(13).render(
            f"{len(self._cards)} cartas", True, colors.TEXT_SECONDARY
        )
        surface.blit(count_surf, (panel.x + _PANEL_MARGIN, panel.y + 38))

        hint_surf = self._fonts.get(11).render(
            "ESC  ·  clic fuera  →  cerrar", True, colors.TEXT_SECONDARY
        )
        surface.blit(hint_surf, (panel.right - hint_surf.get_width() - 16, panel.y + 18))

        # Divider
        pygame.draw.line(surface, colors.PANEL_BORDER,
                         (panel.x + 10, panel.y + 56), (panel.right - 10, panel.y + 56))

        # Empty state
        if not self._cards:
            empty_surf = self._fonts.get(20).render("La pila está vacía", True, colors.TEXT_SECONDARY)
            surface.blit(empty_surf, empty_surf.get_rect(center=panel.center))
            return

        # Cards grid — clip to panel area
        surface.set_clip(pygame.Rect(panel.x, panel.y + 58, panel.width, panel.height - 68))

        start_x = panel.x + _PANEL_MARGIN
        start_y = panel.y + 64
        for i, card in enumerate(self._cards):
            row = i // _COLS
            col = i % _COLS
            cx  = start_x + col * (CARD_W + _GAP_X)
            cy  = start_y + row * (CARD_H + _GAP_Y)
            if cy + CARD_H <= panel.bottom - 12:
                draw_card(surface, card, cx, cy, self._fonts)

        surface.set_clip(None)
