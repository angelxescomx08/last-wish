"""Shop scene — buys thematic card packs.

Shows four packs with their name, description, and cost.
The player clicks one they can afford to open it (→ PackOpeningScene).
The selected_pack flag is consumed by SceneManager.

Public flags:
  selected_pack: PackTheme | None — set when player clicks an affordable pack.
  cleared: bool                   — True when player clicks "Salir".
"""
from __future__ import annotations

import pygame

from src.domain.card_pool import ALL_PACKS, PackDef, PackTheme
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

_BG      = pygame.Color(10, 14, 18)
_PACK_W  = 260
_PACK_H  = 160
_PACK_GAP = 20


class ShopScene:
    """Shop: four pack tiles + exit button."""

    def __init__(self, run: Run, fonts: FontRegistry) -> None:
        self._run          = run
        self._fonts        = fonts
        self._pack_rects:  list[pygame.Rect] = []
        self._hovered:     int | None = None
        self._exit_rect:   pygame.Rect | None = None

        self.selected_pack: PackTheme | None = None
        self.cleared:       bool = False

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2

        # Title
        t = self._fonts.get(26).render("Tienda del Viajero", True, colors.TEXT_ACCENT)
        surface.blit(t, t.get_rect(centerx=cx, centery=50))

        # Gold
        g = self._fonts.get(14).render(
            f"Oro disponible: {self._run.gold}", True, pygame.Color(220, 190, 50)
        )
        surface.blit(g, g.get_rect(centerx=cx, centery=88))

        # Pack tiles — 2×2 grid centred
        cols    = 2
        total_w = cols * _PACK_W + (cols - 1) * _PACK_GAP
        start_x = cx - total_w // 2
        start_y = 120

        self._pack_rects = []
        for idx, pack in enumerate(ALL_PACKS):
            row  = idx // cols
            col  = idx % cols
            px   = start_x + col * (_PACK_W + _PACK_GAP)
            py   = start_y + row * (_PACK_H + _PACK_GAP)
            rect = pygame.Rect(px, py, _PACK_W, _PACK_H)
            self._pack_rects.append(rect)
            self._draw_pack_tile(surface, pack, rect, idx)

        # Exit
        es = self._fonts.get(14).render("Salir", True, colors.TEXT_SECONDARY)
        er = es.get_rect(centerx=cx, centery=500)
        self._exit_rect = pygame.Rect(er.x - 16, er.y - 8, er.width + 32, er.height + 16)
        pygame.draw.rect(surface, colors.BG_PANEL,     self._exit_rect, border_radius=6)
        pygame.draw.rect(surface, colors.PANEL_BORDER, self._exit_rect, 1, border_radius=6)
        surface.blit(es, er)

    def _draw_pack_tile(
        self,
        surface: pygame.Surface,
        pack: PackDef,
        rect: pygame.Rect,
        idx: int,
    ) -> None:
        can_afford = self._run.gold >= pack.cost
        hovered    = self._hovered == idx

        bg_col   = pygame.Color(30, 40, 55)      if can_afford else pygame.Color(28, 28, 35)
        border_c = colors.TEXT_ACCENT             if hovered and can_afford else \
                   pygame.Color(80, 120, 160)     if can_afford else \
                   pygame.Color(50, 50, 60)

        pygame.draw.rect(surface, bg_col,   rect, border_radius=8)
        pygame.draw.rect(surface, border_c, rect, 2, border_radius=8)

        cx = rect.centerx
        ns = self._fonts.get(15).render(
            pack.name, True, colors.TEXT_ACCENT if can_afford else pygame.Color(80, 80, 80)
        )
        surface.blit(ns, ns.get_rect(centerx=cx, centery=rect.top + 30))

        ds = self._fonts.get(11).render(
            pack.description, True, colors.TEXT_SECONDARY if can_afford else pygame.Color(60, 60, 60)
        )
        surface.blit(ds, ds.get_rect(centerx=cx, centery=rect.top + 70))

        cost_col = pygame.Color(220, 190, 50) if can_afford else pygame.Color(150, 80, 80)
        cs = self._fonts.get(14).render(f"{pack.cost} oro", True, cost_col)
        surface.blit(cs, cs.get_rect(centerx=cx, centery=rect.top + 110))

        if not can_afford:
            na = self._fonts.get(10).render("Sin fondos", True, pygame.Color(150, 80, 80))
            surface.blit(na, na.get_rect(centerx=cx, centery=rect.top + 140))

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self._hovered = None
        for i, rect in enumerate(self._pack_rects):
            if rect.collidepoint(pos):
                self._hovered = i
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._pack_rects):
            if rect.collidepoint(pos):
                pack = ALL_PACKS[i]
                if self._run.gold >= pack.cost:
                    self._run.gold  -= pack.cost
                    self.selected_pack = pack.theme
                return
        if self._exit_rect and self._exit_rect.collidepoint(pos):
            self.cleared = True
