"""Treasure room scene.

Shows the offered relics (one, or more with Llave Maestra). The player picks one
(click its box; with a single relic it is already picked) and takes it, or skips.

Public flags consumed by SceneManager:
  cleared: bool               — True when the player has decided.
  took_relic: bool            — True if the player took a relic.
  chosen_relic: Relic | None  — the relic taken (None when skipped).
"""
from __future__ import annotations

import pygame

from src.domain.chroma import chroma_def, chroma_title
from src.domain.relic import Relic
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx import chroma_fx
from src.presentation.ui.card_widget import _wrap
from src.presentation.ui.tooltip import draw_tooltip, relic_tooltip

_BG = pygame.Color(14, 10, 6)
_GOLD = pygame.Color(210, 170, 30)
_PICKED = pygame.Color(255, 225, 120)

_BTN_W: int = 160
_BTN_H: int = 40
_BOX_H: int = 220
_GAP: int = 30


def box_width(count: int) -> int:
    """Width of each relic box: one big box, or narrower boxes side by side."""
    return 400 if count <= 1 else (300 if count == 2 else 260)


class TreasureScene:
    """Treasure room: show the relics, let the player take one or skip."""

    def __init__(self, run: Run, relics: Relic | list[Relic], fonts: FontRegistry, *,
                 sound: SoundPlayer | None = None) -> None:
        self._sound = sound if sound is not None else SoundPlayer()
        self._run         = run
        self._relics: list[Relic] = [relics] if isinstance(relics, Relic) else list(relics)
        self._fonts       = fonts
        self._selected    = 0
        self._take_rect:  pygame.Rect | None = None
        self._skip_rect:  pygame.Rect | None = None
        self._relic_rects: list[pygame.Rect] = []
        self._mouse:      tuple[int, int] = (0, 0)

        self.cleared:      bool = False
        self.took_relic:   bool = False
        self.chosen_relic: Relic | None = None

    @property
    def _relic(self) -> Relic:
        """The relic currently picked (kept for callers of the one-relic version)."""
        return self._relics[self._selected]

    @property
    def _relic_rect(self) -> pygame.Rect | None:
        return self._relic_rects[self._selected] if self._relic_rects else None

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

        t = self._fonts.get(26).render("Sala del Tesoro", True, _GOLD)
        surface.blit(t, t.get_rect(centerx=cx, centery=70))
        if len(self._relics) > 1:
            hint = self._fonts.get(14).render("Elige una reliquia", True, colors.TEXT_SECONDARY)
            surface.blit(hint, hint.get_rect(centerx=cx, centery=104))

        n = len(self._relics)
        w = box_width(n)
        x0 = cx - (n * w + (n - 1) * _GAP) // 2
        self._relic_rects = []
        for i, relic in enumerate(self._relics):
            box = pygame.Rect(x0 + i * (w + _GAP), 130, w, _BOX_H)
            self._relic_rects.append(box)
            self._draw_relic(surface, relic, box, picked=(n > 1 and i == self._selected))

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

        for relic, box in zip(self._relics, self._relic_rects):
            if box.collidepoint(self._mouse):
                draw_tooltip(surface, relic_tooltip(relic), self._mouse, self._fonts)
                break

    def _draw_relic(self, surface: pygame.Surface, relic: Relic, box: pygame.Rect, *,
                    picked: bool) -> None:
        pygame.draw.rect(surface, colors.BG_PANEL, box, border_radius=8)
        pygame.draw.rect(surface, _PICKED if picked else _GOLD, box, 3 if picked else 2, border_radius=8)

        name_surf = self._fonts.get(18).render(chroma_title(relic.name, relic.chroma), True,
                                               pygame.Color(220, 190, 60))
        surface.blit(name_surf, name_surf.get_rect(centerx=box.centerx, centery=box.y + 60))

        font = self._fonts.get(13)
        y = box.y + 100
        for line in _wrap(relic.description, font, box.w - 30)[:4]:
            s = font.render(line, True, colors.TEXT_PRIMARY)
            surface.blit(s, s.get_rect(centerx=box.centerx, top=y))
            y += font.get_linesize()
        if relic.chroma is not None:
            note = font.render(chroma_def(relic.chroma).relic_note, True,
                               chroma_fx.style(relic.chroma).main)
            surface.blit(note, note.get_rect(centerx=box.centerx, centery=box.bottom - 25))
            chroma_fx.draw_chroma_box(surface, box, relic.chroma, chroma_fx.now(), radius=8)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self.cleared:
            return
        for i, box in enumerate(self._relic_rects):
            if box.collidepoint(pos):
                if i != self._selected:
                    self._selected = i
                    self._sound.play_nav()
                return
        if self._take_rect and self._take_rect.collidepoint(pos):
            self._sound.play_reward()
            self.took_relic = True
            self.chosen_relic = self._relic
            self.cleared    = True
        elif self._skip_rect and self._skip_rect.collidepoint(pos):
            self._sound.play_cancel()
            self.took_relic = False
            self.chosen_relic = None
            self.cleared    = True
