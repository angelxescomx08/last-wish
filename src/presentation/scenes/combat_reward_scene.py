"""Post-combat reward scene.

Shows gold earned and three card choices.  The player picks one to add to their
deck, then continues back to the map.

Public flag consumed by SceneManager:
  cleared: bool  — True when the player has finished choosing.
  chosen_card: Card | None — the card the player picked (None if skipped).
"""
from __future__ import annotations

import pygame

from src.domain.card import Card
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card
from src.presentation.ui.tooltip import TooltipContent, card_tooltip, draw_tooltip

_BG  = pygame.Color(12, 18, 12)
_GAP = 30


class CombatRewardScene:
    """Victory reward: gold display + 3 card choices."""

    def __init__(
        self,
        run: Run,
        gold_earned: int,
        cards: list[Card],
        fonts: FontRegistry,
    ) -> None:
        self._run          = run
        self._gold_earned  = gold_earned
        self._cards        = cards
        self._fonts        = fonts
        self._card_rects:  list[pygame.Rect] = []
        self._hovered:     int | None = None
        self._skip_rect:   pygame.Rect | None = None
        self._mouse:       tuple[int, int] = (0, 0)

        self.cleared:      bool = False
        self.chosen_card:  Card | None = None

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
        t = self._fonts.get(28).render("¡VICTORIA!", True, colors.TEXT_ACCENT)
        surface.blit(t, t.get_rect(centerx=cx, centery=60))

        # Gold
        g = self._fonts.get(18).render(
            f"Oro obtenido: +{self._gold_earned}", True, pygame.Color(220, 190, 50)
        )
        surface.blit(g, g.get_rect(centerx=cx, centery=108))

        h = self._fonts.get(14).render(
            "Elige una carta para añadir a tu mazo:", True, colors.TEXT_PRIMARY
        )
        surface.blit(h, h.get_rect(centerx=cx, centery=148))

        # Cards
        n         = len(self._cards)
        total_w   = n * CARD_W + max(0, n - 1) * _GAP
        start_x   = cx - total_w // 2
        card_y    = 190
        self._card_rects = []
        for i, card in enumerate(self._cards):
            cx_card = start_x + i * (CARD_W + _GAP)
            rect    = draw_card(
                surface, card, cx_card, card_y, self._fonts,
                hovered=(self._hovered == i),
            )
            self._card_rects.append(rect)

        # Skip button
        skip_surf  = self._fonts.get(14).render("Omitir", True, colors.TEXT_SECONDARY)
        skip_rect  = skip_surf.get_rect(centerx=cx, centery=card_y + CARD_H + 40)
        self._skip_rect = pygame.Rect(
            skip_rect.x - 10, skip_rect.y - 6,
            skip_rect.width + 20, skip_rect.height + 12,
        )
        pygame.draw.rect(surface, colors.BG_PANEL, self._skip_rect, border_radius=5)
        pygame.draw.rect(surface, colors.PANEL_BORDER, self._skip_rect, 1, border_radius=5)
        surface.blit(skip_surf, skip_rect)

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
