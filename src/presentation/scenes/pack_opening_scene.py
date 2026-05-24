"""Pack opening scene — shows 5 cards from a pack, player picks 1.

Public flag consumed by SceneManager:
  cleared:      bool        — True when player picks or skips.
  chosen_card:  Card | None — the chosen card.
"""
from __future__ import annotations

import pygame

from src.domain.card import Card
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card
from src.presentation.ui.tooltip import card_tooltip, draw_tooltip

_BG  = pygame.Color(8, 12, 20)
_GAP = 20


class PackOpeningScene:
    """Show 5 pack cards; player selects one to keep."""

    def __init__(
        self,
        cards: list[Card],
        pack_name: str,
        fonts: FontRegistry,
    ) -> None:
        self._cards      = cards
        self._pack_name  = pack_name
        self._fonts      = fonts
        self._card_rects: list[pygame.Rect] = []
        self._hovered:    int | None = None
        self._skip_rect:  pygame.Rect | None = None
        self._mouse:      tuple[int, int] = (0, 0)

        self.cleared:     bool = False
        self.chosen_card: Card | None = None

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2

        # Title
        t = self._fonts.get(24).render(f"Abriendo: {self._pack_name}", True, colors.TEXT_ACCENT)
        surface.blit(t, t.get_rect(centerx=cx, centery=50))

        sub = self._fonts.get(13).render(
            "Elige una carta para añadir a tu mazo:", True, colors.TEXT_PRIMARY
        )
        surface.blit(sub, sub.get_rect(centerx=cx, centery=90))

        # Cards — centered row
        n       = len(self._cards)
        total_w = n * CARD_W + max(0, n - 1) * _GAP
        start_x = cx - total_w // 2
        card_y  = 120
        self._card_rects = []
        for i, card in enumerate(self._cards):
            rect = draw_card(
                surface, card, start_x + i * (CARD_W + _GAP), card_y, self._fonts,
                hovered=(self._hovered == i),
            )
            self._card_rects.append(rect)

        # Skip
        ss = self._fonts.get(14).render("Omitir", True, colors.TEXT_SECONDARY)
        sr = ss.get_rect(centerx=cx, centery=card_y + CARD_H + 40)
        self._skip_rect = pygame.Rect(sr.x - 10, sr.y - 6, sr.width + 20, sr.height + 12)
        pygame.draw.rect(surface, colors.BG_PANEL,     self._skip_rect, border_radius=5)
        pygame.draw.rect(surface, colors.PANEL_BORDER, self._skip_rect, 1, border_radius=5)
        surface.blit(ss, sr)

        # Tooltip
        if self._hovered is not None and self._hovered < len(self._cards):
            tip = card_tooltip(self._cards[self._hovered])
            draw_tooltip(surface, tip, self._mouse, self._fonts)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self._hovered = None
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos):
                self._hovered = i
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos):
                self.chosen_card = self._cards[i]
                self.cleared     = True
                return
        if self._skip_rect and self._skip_rect.collidepoint(pos):
            self.chosen_card = None
            self.cleared     = True
