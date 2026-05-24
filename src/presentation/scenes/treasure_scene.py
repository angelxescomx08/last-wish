"""Treasure room scene.

Shows a single relic.  The player can take it (adds to run) or skip.

Public flag consumed by SceneManager:
  cleared: bool    — True when the player has decided.
  took_relic: bool — True if the player took the relic.
"""
from __future__ import annotations

import pygame

from src.domain.relic import Relic
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.tooltip import draw_tooltip, relic_tooltip

_BG = pygame.Color(14, 10, 6)

_BTN_W: int = 160
_BTN_H: int = 40


class TreasureScene:
    """Treasure room: show a relic, let player take or skip."""

    def __init__(self, run: Run, relic: Relic, fonts: FontRegistry) -> None:
        self._run         = run
        self._relic       = relic
        self._fonts       = fonts
        self._take_rect:  pygame.Rect | None = None
        self._skip_rect:  pygame.Rect | None = None
        self._relic_rect: pygame.Rect | None = None
        self._mouse:      tuple[int, int] = (0, 0)

        self.cleared:    bool = False
        self.took_relic: bool = False

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2

        # Title
        t = self._fonts.get(26).render("Sala del Tesoro", True, pygame.Color(210, 170, 30))
        surface.blit(t, t.get_rect(centerx=cx, centery=70))

        # Relic box
        box = pygame.Rect(cx - 200, 130, 400, 220)
        pygame.draw.rect(surface, colors.BG_PANEL, box, border_radius=8)
        pygame.draw.rect(surface, pygame.Color(210, 170, 30), box, 2, border_radius=8)
        self._relic_rect = box

        name_surf = self._fonts.get(18).render(
            self._relic.name, True, pygame.Color(220, 190, 60)
        )
        surface.blit(name_surf, name_surf.get_rect(centerx=cx, centery=220))

        desc_surf = self._fonts.get(13).render(
            self._relic.description, True, colors.TEXT_PRIMARY
        )
        surface.blit(desc_surf, desc_surf.get_rect(centerx=cx, centery=270))

        # Buttons
        btn_y = 390
        take_rect = pygame.Rect(cx - _BTN_W - 16, btn_y, _BTN_W, _BTN_H)
        skip_rect = pygame.Rect(cx + 16,           btn_y, _BTN_W, _BTN_H)
        self._take_rect = take_rect
        self._skip_rect = skip_rect

        pygame.draw.rect(surface, pygame.Color(50, 120, 50),   take_rect, border_radius=6)
        pygame.draw.rect(surface, pygame.Color(60, 150, 60),   take_rect, 2, border_radius=6)
        pygame.draw.rect(surface, colors.BG_PANEL,             skip_rect, border_radius=6)
        pygame.draw.rect(surface, colors.PANEL_BORDER,         skip_rect, 1, border_radius=6)

        ts = self._fonts.get(15).render("Tomar",  True, colors.TEXT_PRIMARY)
        ss = self._fonts.get(15).render("Omitir", True, colors.TEXT_SECONDARY)
        surface.blit(ts, ts.get_rect(center=take_rect.center))
        surface.blit(ss, ss.get_rect(center=skip_rect.center))

        # Tooltip on hover
        if self._relic_rect and self._relic_rect.collidepoint(self._mouse):
            tip = relic_tooltip(self._relic)
            draw_tooltip(surface, tip, self._mouse, self._fonts)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self._take_rect and self._take_rect.collidepoint(pos):
            self.took_relic = True
            self.cleared    = True
        elif self._skip_rect and self._skip_rect.collidepoint(pos):
            self.took_relic = False
            self.cleared    = True
