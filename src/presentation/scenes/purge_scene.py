"""Altar de Purga — map room where you remove ONE card of your choice from the deck, for gold.

The deck is shown in a scrollable grid (``CollectionViewer``) with the price on top. Clicking
a card opens a confirmation panel ("Eliminar (precio)" / "Cancelar"). Confirming pays
(``application.purge``) and the card burns away on the altar (``fx/card_burn``) with embers;
then the room closes by itself — one card per altar. "Salir" leaves without removing anything.
When the card cannot be removed (not enough gold, deck at its minimum) the grid is dimmed and
says why.

Public flag consumed by SceneManager:
  cleared: bool — True when the player leaves (or after the burn).
"""
from __future__ import annotations

import math
import random

import pygame

from src.application.card_preview import run_card_bonus
from src.application.purge import can_purge, purge_block_reason, purge_card, purge_price
from src.domain.card import Card
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx.bursts import BurstParticles, soft_glow
from src.presentation.fx.card_burn import BURN_SECONDS, EMBER, CardBurn
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card, render_card_surface
from src.presentation.ui.collection_viewer import CollectionViewer
from src.presentation.ui.tooltip import TooltipContent, card_tooltip

_ACCENT = pygame.Color(240, 130, 50)          # altar fire
_GOLD = pygame.Color(235, 195, 70)
_BAD = pygame.Color(220, 90, 80)
_PANEL = pygame.Rect(390, 100, 500, 520)
_BTN_W, _BTN_H = 200, 44
_BURN_SCALE = 1.5                              # the card is shown bigger while it burns
_BURN_CENTER = (640, 330)
_AFTER_BURN = 0.7                              # s on the empty altar before the room closes


class _PurgeGrid(CollectionViewer):
    """The deck; a left click on a card sets ``clicked`` to its index."""

    close_label = 'Salir'
    hint_text = 'Haz clic en la carta que quieras eliminar  ·  Rueda / ↑ ↓ para desplazarte'
    close_on_outside_click = False

    def __init__(self, run: Run, fonts: FontRegistry) -> None:
        self._run = run
        super().__init__('Altar de Purga', run.deck, fonts, 'cartas')
        self.clicked: int | None = None

    @property
    def footer_text(self) -> str:  # type: ignore[override]
        return (f'Solo puedes eliminar una carta en este altar  ·  Precio: {purge_price(self._run)} de oro'
                '  ·  Siempre te queda al menos 1 carta')

    def handle_event(self, event: pygame.event.Event) -> None:
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self._viewport.collidepoint(event.pos)):
            for i, rect in self._item_rects.items():
                if rect.collidepoint(event.pos):
                    self.clicked = i
                    return
        super().handle_event(event)

    def _draw_item(self, surface, item: Card, rect) -> None:
        ok = can_purge(self._run)
        label = self._fonts.get(15).render(f'Eliminar · {purge_price(self._run)}', True, _GOLD if ok else _BAD)
        surface.blit(label, label.get_rect(centerx=rect.centerx, centery=rect.y + 24))
        dmg, blk = run_card_bonus(self._run).for_card(item)
        draw_card(surface, item, rect.x + 20, rect.y + 44, self._fonts, bonus_damage=dmg, bonus_block=blk)
        if not ok:
            dim = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 130))
            surface.blit(dim, (rect.x + 20, rect.y + 44))

    def _tooltip(self, item):
        dmg, blk = run_card_bonus(self._run).for_card(item)
        tip = card_tooltip(item, bonus_damage=dmg, bonus_block=blk)
        reason = purge_block_reason(self._run)
        extra = [reason] if reason else [f'Eliminar por {purge_price(self._run)} de oro (para siempre)']
        return TooltipContent(title=tip.title, lines=[*extra, "", *tip.lines], icon=tip.icon,
                              subtitle=tip.subtitle, panels=tip.panels)


class PurgeScene:
    """Remove one card for gold. Escape opens the pause menu (or closes the confirmation)."""

    pause_button_rect = pygame.Rect(78, 652, 64, 36)
    gold_hud_pos = ("bottomright", (1268, 708))   # the top right holds the viewer's close button

    def __init__(self, run: Run, fonts: FontRegistry, *, sound: SoundPlayer | None = None) -> None:
        self._run = run
        self._fonts = fonts
        self._sound = sound if sound is not None else SoundPlayer()
        self._grid = _PurgeGrid(run, fonts)
        self._selected: int | None = None
        self._confirm_rect: pygame.Rect | None = None
        self._cancel_rect: pygame.Rect | None = None
        self._message = ''
        self._burn: CardBurn | None = None
        self._burn_t = 0.0
        self._burnt_name = ''
        self._particles = BurstParticles(500, seed=17)
        self._rng = random.Random(23)
        self.removed: Card | None = None
        self.cleared = False

    @property
    def _overlay(self) -> int | None:
        """The confirmation panel (or the burn) counts as an overlay: Escape closes it."""
        return self._selected if self._burn is None else -1

    @property
    def selected_index(self) -> int | None:
        return self._selected

    @property
    def burning(self) -> bool:
        return self._burn is not None

    # ------------------------------------------------------------------ actions

    def select(self, index: int) -> None:
        """Open the confirmation panel for ``run.deck[index]`` (if a card can be removed now)."""
        if self._burn is not None or not 0 <= index < len(self._run.deck):
            return
        reason = purge_block_reason(self._run)
        if reason:
            self._message = reason
            self._sound.play_error()
            return
        self._selected = index
        self._grid._mouse = (-1, -1)            # no stale tooltip under the panel
        self._sound.play_confirm()

    def confirm(self) -> bool:
        """Pay and remove the selected card; it starts burning. Returns True if removed."""
        if self._selected is None:
            return False
        card = self._run.deck[self._selected]
        dmg, blk = run_card_bonus(self._run).for_card(card)
        face = render_card_surface(card, self._fonts, bonus_damage=dmg, bonus_block=blk)
        removed = purge_card(self._run, self._selected)
        if removed is None:
            self._message = purge_block_reason(self._run) or 'No se pudo eliminar'
            self._sound.play_error()
            return False
        self.removed = removed
        self._selected = None
        big = pygame.transform.smoothscale(face, (round(CARD_W * _BURN_SCALE), round(CARD_H * _BURN_SCALE)))
        self._burn = CardBurn(big, seed=len(self._run.deck))
        self._burn_t = 0.0
        self._burnt_name = removed.name
        self._sound.play_purchase()
        self._sound.play_death()
        return True

    def cancel(self) -> None:
        if self._selected is not None:
            self._selected = None
            self._sound.play_cancel()

    def skip_burn(self) -> None:
        if self._burn is not None:
            self._burn_t = BURN_SECONDS + _AFTER_BURN

    # ------------------------------------------------------------------ protocol

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.cleared:
            return
        if self._burn is not None:                       # a click / key hurries the ceremony
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self.skip_burn()
            return
        if self._selected is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.cancel()
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.confirm()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._confirm_rect and self._confirm_rect.collidepoint(event.pos):
                    self.confirm()
                elif ((self._cancel_rect and self._cancel_rect.collidepoint(event.pos))
                      or not _PANEL.collidepoint(event.pos)):
                    self.cancel()
            return
        self._grid.handle_event(event)
        if self._grid.clicked is not None:
            index, self._grid.clicked = self._grid.clicked, None
            self.select(index)
        if self._grid.dismissed:
            self.cleared = True
            self._sound.play_cancel()

    def update(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1))
        self._particles.update(dt)
        if self._burn is None:
            return
        self._burn_t += dt
        progress = self._burn_t / BURN_SECONDS
        w, h = self._burn.face.get_size()
        x0, y0 = _BURN_CENTER[0] - w // 2, _BURN_CENTER[1] - h // 2
        for px, py in self._burn.edge_points(progress, limit=6):
            self._particles.emit(x0 + px, y0 + py, self._rng.uniform(-30, 30), self._rng.uniform(-160, -60),
                                 life=self._rng.uniform(0.5, 1.1), palette=EMBER,
                                 size=self._rng.uniform(1.5, 3.0), drag=1.2)
        if self._burn_t >= BURN_SECONDS + _AFTER_BURN:
            self._burn = None
            self.cleared = True

    def draw(self, surface: pygame.Surface) -> None:
        self._grid.draw(surface)
        if self._message:
            msg = self._fonts.get(15).render(self._message, True, _BAD)
            surface.blit(msg, msg.get_rect(midright=(1100, 104)))
        if self._selected is not None:
            self._draw_confirm(surface, self._run.deck[self._selected])
        if self._burn is not None:
            self._draw_burn(surface)
        self._particles.draw(surface)

    def _dim(self, surface: pygame.Surface, alpha: int) -> None:
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, alpha))
        surface.blit(dim, (0, 0))

    def _draw_confirm(self, surface: pygame.Surface, card: Card) -> None:
        self._dim(surface, 170)
        pygame.draw.rect(surface, colors.BG_PANEL, _PANEL, border_radius=12)
        pygame.draw.rect(surface, _ACCENT, _PANEL, 2, border_radius=12)
        cx = _PANEL.centerx
        title = self._fonts.get(24).render('Eliminar carta', True, _ACCENT)
        surface.blit(title, title.get_rect(centerx=cx, top=_PANEL.top + 18))
        top = _PANEL.top + 66
        dmg, blk = run_card_bonus(self._run).for_card(card)
        draw_card(surface, card, cx - CARD_W // 2, top, self._fonts, bonus_damage=dmg, bonus_block=blk)
        y = top + CARD_H + 20
        note = self._fonts.get(16).render('Sale de tu mazo para siempre.', True, colors.TEXT_PRIMARY)
        surface.blit(note, note.get_rect(centerx=cx, top=y))
        price = purge_price(self._run)
        cost = self._fonts.get(15).render(f'Precio: {price} de oro  ·  Tienes: {self._run.gold}', True, _GOLD)
        surface.blit(cost, cost.get_rect(centerx=cx, top=y + 28))
        left = self._fonts.get(13).render('Solo una carta por altar', True, colors.TEXT_SECONDARY)
        surface.blit(left, left.get_rect(centerx=cx, top=y + 52))
        by = _PANEL.bottom - _BTN_H - 22
        self._confirm_rect = pygame.Rect(cx - _BTN_W - 12, by, _BTN_W, _BTN_H)
        self._cancel_rect = pygame.Rect(cx + 12, by, _BTN_W, _BTN_H)
        pygame.draw.rect(surface, pygame.Color(120, 50, 20), self._confirm_rect, border_radius=6)
        pygame.draw.rect(surface, _ACCENT, self._confirm_rect, 2, border_radius=6)
        pygame.draw.rect(surface, colors.BG_DARK, self._cancel_rect, border_radius=6)
        pygame.draw.rect(surface, colors.PANEL_BORDER, self._cancel_rect, 1, border_radius=6)
        ok = self._fonts.get(16).render(f'Eliminar ({price})', True, colors.TEXT_PRIMARY)
        no = self._fonts.get(16).render('Cancelar', True, colors.TEXT_SECONDARY)
        surface.blit(ok, ok.get_rect(center=self._confirm_rect.center))
        surface.blit(no, no.get_rect(center=self._cancel_rect.center))

    def _draw_burn(self, surface: pygame.Surface) -> None:
        self._dim(surface, 190)
        progress = self._burn_t / BURN_SECONDS
        flicker = 0.5 + 0.5 * math.sin(self._burn_t * 23.0)
        heat = max(0.0, 1.0 - abs(progress - 0.5) * 1.6) * (0.75 + 0.25 * flicker)
        level = max(1, min(8, round(8 * heat)))         # quantised: a few cached glows
        glow = soft_glow((int(150 * level / 8), int(60 * level / 8), int(18 * level / 8)), 220)
        surface.blit(glow, glow.get_rect(center=_BURN_CENTER), special_flags=pygame.BLEND_RGB_ADD)
        if not self._burn.gone(progress):
            img = self._burn.frame(progress)
            surface.blit(img, img.get_rect(center=_BURN_CENTER))
        text = self._fonts.get(22).render(f'{self._burnt_name} se consume en el altar', True, _ACCENT)
        surface.blit(text, text.get_rect(centerx=640, top=_BURN_CENTER[1] + CARD_H * _BURN_SCALE / 2 + 24))
        hint = self._fonts.get(13).render('Clic para continuar', True, colors.TEXT_SECONDARY)
        surface.blit(hint, hint.get_rect(centerx=640, top=_BURN_CENTER[1] + CARD_H * _BURN_SCALE / 2 + 56))
