"""Boss reward scene — three internal phases after defeating the boss.

Phase 1 GOLD:    Show gold earned and auto-add to run, then "Abrir Sobre" button.
Phase 2 PACK:    Push PackOpeningScene (handled by SceneManager) and wait.
Phase 3 RELICS:  Show 3 relic choices; player picks one.
After phase 3:   SceneManager reads cleared=True → advances floor.

Public flags:
  cleared: bool            — True when all three phases are done.
  open_pack_requested: bool— True when player clicks "Abrir Sobre" (SceneManager opens pack).
  chosen_relic: Relic | None — set after player picks a relic.
"""
from __future__ import annotations

from enum import Enum, auto

import pygame

from src.domain.relic import Relic
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.tooltip import draw_tooltip, relic_tooltip

_BG = pygame.Color(18, 6, 6)

_BTN_W = 200
_BTN_H = 42

_RELIC_BOX_W = 280
_RELIC_BOX_H = 140


class _Phase(Enum):
    GOLD   = auto()
    PACK   = auto()   # waiting for SceneManager to push/pop PackOpeningScene
    RELICS = auto()
    DONE   = auto()


class BossRewardScene:
    """Multi-phase boss reward screen."""

    def __init__(
        self,
        run: Run,
        gold_earned: int,
        relics: list[Relic],
        fonts: FontRegistry,
    ) -> None:
        self._run          = run
        self._gold_earned  = gold_earned
        self._relics       = relics
        self._fonts        = fonts
        self._phase        = _Phase.GOLD
        self._relic_rects: list[pygame.Rect] = []
        self._btn_rect:    pygame.Rect | None = None
        self._hovered_rel: int | None = None
        self._mouse:       tuple[int, int] = (0, 0)

        self.cleared:             bool = False
        self.open_pack_requested: bool = False
        self.chosen_relic:        Relic | None = None

    # ------------------------------------------------------------------
    # Called by SceneManager after PackOpeningScene is done
    # ------------------------------------------------------------------

    def pack_done(self) -> None:
        """Advance from PACK phase to RELICS phase."""
        self._phase = _Phase.RELICS

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            if self._phase == _Phase.RELICS:
                self._update_relic_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        if self._phase == _Phase.GOLD:
            self._draw_gold(surface)
        elif self._phase == _Phase.PACK:
            self._draw_waiting(surface)
        elif self._phase == _Phase.RELICS:
            self._draw_relics(surface)

    # ------------------------------------------------------------------
    # Phase drawing
    # ------------------------------------------------------------------

    def _draw_gold(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2

        t = self._fonts.get(30).render("¡JEFE DERROTADO!", True, pygame.Color(230, 50, 50))
        surface.blit(t, t.get_rect(centerx=cx, centery=80))

        g = self._fonts.get(20).render(
            f"Oro obtenido: +{self._gold_earned}", True, pygame.Color(220, 190, 50)
        )
        surface.blit(g, g.get_rect(centerx=cx, centery=150))

        info = self._fonts.get(14).render(
            "Abre el sobre épico para elegir una carta poderosa.",
            True, colors.TEXT_PRIMARY,
        )
        surface.blit(info, info.get_rect(centerx=cx, centery=220))

        bs = self._fonts.get(16).render("Abrir Sobre Épico", True, colors.TEXT_PRIMARY)
        br = bs.get_rect(centerx=cx, centery=310)
        self._btn_rect = pygame.Rect(br.x - 20, br.y - 10, br.width + 40, br.height + 20)
        pygame.draw.rect(surface, pygame.Color(100, 30, 30), self._btn_rect, border_radius=7)
        pygame.draw.rect(surface, pygame.Color(200, 60, 60), self._btn_rect, 2, border_radius=7)
        surface.blit(bs, br)

    def _draw_waiting(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2
        w = self._fonts.get(18).render("Abriendo sobre…", True, colors.TEXT_SECONDARY)
        surface.blit(w, w.get_rect(centerx=cx, centery=360))

    def _draw_relics(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2

        t = self._fonts.get(24).render("Elige una Reliquia", True, colors.TEXT_ACCENT)
        surface.blit(t, t.get_rect(centerx=cx, centery=60))

        n       = len(self._relics)
        total_w = n * _RELIC_BOX_W + max(0, n - 1) * 20
        start_x = cx - total_w // 2
        self._relic_rects = []

        for i, relic in enumerate(self._relics):
            rx   = start_x + i * (_RELIC_BOX_W + 20)
            ry   = 120
            rect = pygame.Rect(rx, ry, _RELIC_BOX_W, _RELIC_BOX_H)
            self._relic_rects.append(rect)

            border = colors.TEXT_ACCENT if self._hovered_rel == i else colors.PANEL_BORDER
            pygame.draw.rect(surface, colors.BG_PANEL, rect, border_radius=8)
            pygame.draw.rect(surface, border,          rect, 2, border_radius=8)

            ns = self._fonts.get(14).render(relic.name, True, pygame.Color(220, 190, 60))
            surface.blit(ns, ns.get_rect(centerx=rect.centerx, centery=rect.top + 35))

            ds = self._fonts.get(11).render(relic.description, True, colors.TEXT_SECONDARY)
            surface.blit(ds, ds.get_rect(centerx=rect.centerx, centery=rect.top + 90))

        # Tooltip
        if self._hovered_rel is not None and self._hovered_rel < len(self._relics):
            tip = relic_tooltip(self._relics[self._hovered_rel])
            draw_tooltip(surface, tip, self._mouse, self._fonts)

        hint = self._fonts.get(11).render(
            "Haz clic en una reliquia para tomarla", True, colors.TEXT_SECONDARY
        )
        surface.blit(hint, hint.get_rect(centerx=cx, centery=300))

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _update_relic_hover(self, pos: tuple[int, int]) -> None:
        self._hovered_rel = None
        for i, rect in enumerate(self._relic_rects):
            if rect.collidepoint(pos):
                self._hovered_rel = i
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self._phase == _Phase.GOLD:
            if self._btn_rect and self._btn_rect.collidepoint(pos):
                self._phase = _Phase.PACK
                self.open_pack_requested = True

        elif self._phase == _Phase.RELICS:
            for i, rect in enumerate(self._relic_rects):
                if rect.collidepoint(pos):
                    self.chosen_relic = self._relics[i]
                    self._phase       = _Phase.DONE
                    self.cleared      = True
                    return
