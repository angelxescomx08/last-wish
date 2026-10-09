"""Post-combat reward scene.

Shows gold earned and three card choices.  The player picks one to add to their
deck, then continues back to the map. After an elite, a ``relic`` is shown too (it is
the elite's drop, always obtained; the manager adds it when the scene clears) and the
cards were rolled with a little more luck (``elites.ELITE_CARD_LUCK``).

Public flag consumed by SceneManager:
  cleared: bool  — True when the player has finished choosing.
  chosen_card: Card | None — the card the player picked (None if skipped).
"""
from __future__ import annotations

import pygame

from src.application.card_preview import run_card_bonus
from src.application.luck import luck_report
from src.presentation.fx import card_fx
from src.presentation.ui.luck_badge import draw_luck_badge
from src.domain.card import Card
from src.domain.chroma import chroma_title
from src.domain.relic import Relic
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card
from src.presentation.fx import chroma_fx
from src.presentation.ui.text_fit import fit
from src.presentation.ui.tooltip import TooltipContent, card_tooltip, draw_tooltip, relic_tooltip

_BG  = pygame.Color(12, 18, 12)
_GAP = 30
_RELIC_W, _RELIC_H = 600, 70           # elite drop panel
_RELIC_GOLD = pygame.Color(220, 190, 60)


class CombatRewardScene:
    """Victory reward: gold display + 3 card choices."""

    def __init__(
        self,
        run: Run,
        gold_earned: int,
        cards: list[Card],
        fonts: FontRegistry,
        *,
        sound: SoundPlayer | None = None,
        relic: Relic | None = None,
    ) -> None:
        self._sound = sound if sound is not None else SoundPlayer()
        self._run          = run
        self._bonus        = run_card_bonus(run)     # same numbers as in the hand
        self._gold_earned  = gold_earned
        self._interest     = getattr(run, "last_interest", 0)   # Interés Compuesto
        self._cards        = cards
        self._fonts        = fonts
        self._card_rects:  list[pygame.Rect] = []
        self._hovered:     int | None = None
        self._skip_rect:   pygame.Rect | None = None
        self._mouse:       tuple[int, int] = (0, 0)
        self._t = 0.0
        self.relic: Relic | None = relic       # elite drop (shown; obtained when the scene clears)
        self._relic_rect: pygame.Rect | None = None

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
        self._t += max(0.0, min(dt, 0.1))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2

        # Title
        t = self._fonts.get(28).render("¡VICTORIA!", True, colors.TEXT_ACCENT)
        surface.blit(t, t.get_rect(centerx=cx, centery=60))

        # Gold
        g = self._fonts.get(18).render(
            f"Oro obtenido: +{self._gold_earned}" + (f"  (+{self._interest} de interés)" if self._interest else ""), True, pygame.Color(220, 190, 50)
        )
        surface.blit(g, g.get_rect(centerx=cx, centery=108))

        prompt_y, card_y = 148, 190
        if self.relic is not None:
            self._draw_relic(surface, cx)
            prompt_y, card_y = 228, 266
        h = self._fonts.get(14).render(
            "Elige una carta para añadir a tu mazo:", True, colors.TEXT_PRIMARY
        )
        surface.blit(h, h.get_rect(centerx=cx, centery=prompt_y))
        if self.relic is not None:
            note = self._fonts.get(11).render(
                "Cartas de élite: algo más de probabilidad de ser raras", True, colors.TEXT_SECONDARY)
            surface.blit(note, note.get_rect(centerx=cx, centery=prompt_y + 18))
            card_y += 8

        # Cards
        n         = len(self._cards)
        total_w   = n * CARD_W + max(0, n - 1) * _GAP
        start_x   = cx - total_w // 2
        self._card_rects = []
        for i, card in enumerate(self._cards):
            cx_card = start_x + i * (CARD_W + _GAP)
            dmg, blk = self._bonus.for_card(card)
            if card.lucky_drop:                        # luck added this card
                card_fx.draw_lucky_back(surface, pygame.Rect(cx_card, card_y - (20 if self._hovered == i else 0),
                                                             CARD_W, CARD_H), self._t)
            rect    = draw_card(
                surface, card, cx_card, card_y, self._fonts,
                hovered=(self._hovered == i), bonus_damage=dmg, bonus_block=blk,
            )
            if card.lucky_drop:
                card_fx.draw_lucky_front(surface, rect, self._t, self._fonts)
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

        draw_luck_badge(surface, "bottomleft", (16, 704), luck_report(self._run), self._fonts)

        # Tooltip
        if self.relic is not None and self._relic_rect and self._relic_rect.collidepoint(self._mouse):
            draw_tooltip(surface, relic_tooltip(self.relic), self._mouse, self._fonts)
        elif self._hovered is not None and self._hovered < len(self._cards):
            dmg, blk = self._bonus.for_card(self._cards[self._hovered])
            tip = card_tooltip(self._cards[self._hovered], bonus_damage=dmg, bonus_block=blk)
            draw_tooltip(surface, tip, self._mouse, self._fonts)

    def _draw_relic(self, surface: pygame.Surface, cx: int) -> None:
        """Elite drop: "Reliquia obtenida" panel with the relic's name and rule text."""
        relic = self.relic
        box = pygame.Rect(cx - _RELIC_W // 2, 136, _RELIC_W, _RELIC_H)
        self._relic_rect = box
        pygame.draw.rect(surface, colors.BG_PANEL, box, border_radius=8)
        pygame.draw.rect(surface, _RELIC_GOLD, box, 2, border_radius=8)
        head = self._fonts.get(11).render("RELIQUIA OBTENIDA", True, colors.TEXT_SECONDARY)
        surface.blit(head, head.get_rect(centerx=box.centerx, top=box.y + 6))
        name_font = self._fonts.get(16)
        name = fit(name_font, chroma_title(relic.name, relic.chroma), box.w - 24)
        ns = name_font.render(name, True, _RELIC_GOLD)
        surface.blit(ns, ns.get_rect(centerx=box.centerx, top=box.y + 20))
        desc_font = self._fonts.get(13)
        ds = desc_font.render(fit(desc_font, relic.description, box.w - 24), True, colors.TEXT_PRIMARY)
        surface.blit(ds, ds.get_rect(centerx=box.centerx, top=box.y + 44))
        if relic.chroma is not None:
            chroma_fx.draw_chroma_box(surface, box, relic.chroma, chroma_fx.now(), radius=8)

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        previous = self._hovered
        self._hovered = None
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos):
                self._hovered = i
                if i != previous:
                    self._sound.play_nav()
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self.cleared:
            return
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos):
                self._sound.play_reward()
                self.chosen_card = self._cards[i]
                self.cleared     = True
                return
        if self._skip_rect and self._skip_rect.collidepoint(pos):
            self._sound.play_cancel()
            self.chosen_card = None
            self.cleared     = True
