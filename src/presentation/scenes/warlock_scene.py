"""El Brujo — map room where you upgrade cards of your deck for gold.

The deck is shown in a scrollable grid (``CollectionViewer``) with each card's
upgrade price. "Ver mejoras" switches the whole grid to the upgraded versions,
and hovering a card shows what its upgrade changes. Clicking a card opens a
confirmation panel with the card now and after the upgrade; "Mejorar" pays and
upgrades it (``application.warlock``).
You may upgrade as many cards as your gold allows; "Salir" leaves the room.

Public flag consumed by SceneManager:
  cleared: bool — True when the player leaves.
"""
from __future__ import annotations

import pygame

from src.application.warlock import buy_upgrade, can_buy_upgrade, upgrade_price
from src.domain.card import Card
from src.domain.card_upgrade import can_upgrade, describe_upgrade, upgraded_preview
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card
from src.presentation.ui.collection_viewer import CollectionViewer
from src.presentation.ui.tooltip import TooltipContent, card_tooltip

_ACCENT = pygame.Color(80, 210, 170)          # Brujo green
_GOLD = pygame.Color(235, 195, 70)
_TOO_EXPENSIVE = pygame.Color(220, 90, 80)
_PANEL = pygame.Rect(290, 110, 700, 500)
_BTN_W, _BTN_H = 200, 44


class _UpgradeGrid(CollectionViewer):
    """The deck with prices; a left click on a card sets ``clicked`` to its index."""

    close_label = 'Salir'
    footer_text = 'Las cartas normales se pueden mejorar una sola vez'
    hint_text = 'Haz clic en una carta para mejorarla  ·  Rueda / ↑ ↓ para desplazarte'
    close_on_outside_click = False

    def __init__(self, run: Run, fonts: FontRegistry) -> None:
        self._run = run
        super().__init__('El Brujo', run.deck, fonts, 'cartas')
        self.clicked: int | None = None
        self.show_upgraded = False           # "Ver mejoras": draw every card as it would be upgraded
        self.toggle_rect = pygame.Rect(self._close_rect.x - 220, self._close_rect.y, 208,
                                       self._close_rect.h)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.toggle_rect.collidepoint(event.pos):
            self.show_upgraded = not self.show_upgraded
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_v:
            self.show_upgraded = not self.show_upgraded
            return
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self._viewport.collidepoint(event.pos)):
            for i, rect in self._item_rects.items():
                if rect.collidepoint(event.pos):
                    self.clicked = i
                    return
        super().handle_event(event)

    def _draw_item(self, surface, item: Card, rect) -> None:
        if not can_upgrade(item):
            text, color = 'Ya mejorada', colors.TEXT_SECONDARY
        else:
            affordable = self._run.gold >= upgrade_price(item)
            text = f'{upgrade_price(item)} de oro'
            color = _GOLD if affordable else _TOO_EXPENSIVE
        label = self._fonts.get(15).render(text, True, color)
        surface.blit(label, label.get_rect(centerx=rect.centerx, centery=rect.y + 24))
        shown = upgraded_preview(item) if self.show_upgraded and can_upgrade(item) else item
        draw_card(surface, shown, rect.x + 20, rect.y + 44, self._fonts)
        if not can_buy_upgrade(self._run, item):
            dim = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 130))
            surface.blit(dim, (rect.x + 20, rect.y + 44))

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        on = self.show_upgraded
        pygame.draw.rect(surface, pygame.Color(30, 110, 85) if on else colors.BG_DARK, self.toggle_rect,
                         border_radius=6)
        pygame.draw.rect(surface, _ACCENT if on else colors.PANEL_BORDER, self.toggle_rect, 1, border_radius=6)
        label = self._fonts.get(15).render(f"Ver mejoras (V): {'Sí' if on else 'No'}", True,
                                           colors.TEXT_PRIMARY)
        surface.blit(label, label.get_rect(center=self.toggle_rect.center))

    def _tooltip(self, item):
        tip = card_tooltip(upgraded_preview(item) if self.show_upgraded and can_upgrade(item) else item)
        if can_upgrade(item):
            extra = [f"Al mejorarla: {describe_upgrade(item)}",
                     f"Precio: {upgrade_price(item)} de oro"]
        else:
            extra = ["Ya está mejorada al máximo."]
        return TooltipContent(title=tip.title, lines=[*extra, "", *tip.lines], icon=tip.icon,
                              subtitle=tip.subtitle, panels=tip.panels)


class WarlockScene:
    """Upgrade cards for gold. Escape opens the pause menu (or closes the confirmation)."""

    pause_button_rect = pygame.Rect(78, 652, 64, 36)
    gold_hud_pos = ("bottomright", (1268, 708))   # the top right holds the viewer's close button

    def __init__(self, run: Run, fonts: FontRegistry, *, sound: SoundPlayer | None = None) -> None:
        self._run = run
        self._fonts = fonts
        self._sound = sound if sound is not None else SoundPlayer()
        self._grid = _UpgradeGrid(run, fonts)
        self._selected: int | None = None
        self._confirm_rect: pygame.Rect | None = None
        self._cancel_rect: pygame.Rect | None = None
        self._message = ''
        self._message_ok = True
        self.cleared = False

    @property
    def _overlay(self) -> int | None:
        """The confirmation panel counts as an overlay: Escape closes it, pause button hides."""
        return self._selected

    @property
    def selected_index(self) -> int | None:
        return self._selected

    # ------------------------------------------------------------------ actions

    def select(self, index: int) -> None:
        """Open the confirmation panel for ``run.deck[index]`` (if it can still be upgraded)."""
        if not 0 <= index < len(self._run.deck):
            return
        card = self._run.deck[index]
        if not can_upgrade(card):
            self._say(f'{card.name} ya no se puede mejorar', ok=False)
            self._sound.play_error()
            return
        self._selected = index
        self._grid._mouse = (-1, -1)            # no stale tooltip under the panel
        self._sound.play_confirm()

    def confirm(self) -> bool:
        """Pay and upgrade the selected card. Returns True if it was upgraded."""
        if self._selected is None:
            return False
        card = self._run.deck[self._selected]
        old_name = card.name
        if buy_upgrade(self._run, self._selected):
            self._say(f'{old_name} → {card.name}')
            self._sound.play_purchase()
            self._selected = None
            return True
        self._say('No tienes suficiente oro', ok=False)
        self._sound.play_error()
        return False

    def cancel(self) -> None:
        if self._selected is not None:
            self._selected = None
            self._sound.play_cancel()

    def _say(self, text: str, *, ok: bool = True) -> None:
        self._message, self._message_ok = text, ok

    # ------------------------------------------------------------------ protocol

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.cleared:
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
        pass

    def draw(self, surface: pygame.Surface) -> None:
        self._grid._title = 'El Brujo'
        self._grid.draw(surface)
        if self._message:
            msg = self._fonts.get(15).render(self._message, True,
                                             _ACCENT if self._message_ok else _TOO_EXPENSIVE)
            surface.blit(msg, msg.get_rect(midright=(1100, 104)))
        if self._selected is not None:
            self._draw_confirm(surface, self._run.deck[self._selected])

    def _draw_confirm(self, surface: pygame.Surface, card: Card) -> None:
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surface.blit(dim, (0, 0))
        pygame.draw.rect(surface, colors.BG_PANEL, _PANEL, border_radius=12)
        pygame.draw.rect(surface, _ACCENT, _PANEL, 2, border_radius=12)
        cx = _PANEL.centerx
        title = self._fonts.get(24).render('Mejorar carta', True, _ACCENT)
        surface.blit(title, title.get_rect(centerx=cx, top=_PANEL.top + 18))

        preview = upgraded_preview(card)
        top = _PANEL.top + 70
        draw_card(surface, card, cx - 60 - CARD_W, top, self._fonts)
        draw_card(surface, preview, cx + 60, top, self._fonts)
        arrow = self._fonts.get(40).render('→', True, _ACCENT)
        surface.blit(arrow, arrow.get_rect(center=(cx, top + CARD_H // 2)))

        y = top + CARD_H + 22
        desc = self._fonts.get(16).render(f'Mejora: {describe_upgrade(card)}', True, colors.TEXT_PRIMARY)
        surface.blit(desc, desc.get_rect(centerx=cx, top=y))
        price = upgrade_price(card)
        affordable = self._run.gold >= price
        cost = self._fonts.get(15).render(f'Precio: {price} de oro  ·  Tienes: {self._run.gold}', True,
                                          _GOLD if affordable else _TOO_EXPENSIVE)
        surface.blit(cost, cost.get_rect(centerx=cx, top=y + 28))

        by = _PANEL.bottom - _BTN_H - 22
        self._confirm_rect = pygame.Rect(cx - _BTN_W - 12, by, _BTN_W, _BTN_H)
        self._cancel_rect = pygame.Rect(cx + 12, by, _BTN_W, _BTN_H)
        fill = pygame.Color(30, 110, 85) if affordable else pygame.Color(50, 50, 55)
        pygame.draw.rect(surface, fill, self._confirm_rect, border_radius=6)
        pygame.draw.rect(surface, _ACCENT if affordable else colors.PANEL_BORDER, self._confirm_rect, 2,
                         border_radius=6)
        pygame.draw.rect(surface, colors.BG_DARK, self._cancel_rect, border_radius=6)
        pygame.draw.rect(surface, colors.PANEL_BORDER, self._cancel_rect, 1, border_radius=6)
        ok = self._fonts.get(16).render(f'Mejorar ({price})', True,
                                        colors.TEXT_PRIMARY if affordable else colors.TEXT_SECONDARY)
        no = self._fonts.get(16).render('Cancelar', True, colors.TEXT_SECONDARY)
        surface.blit(ok, ok.get_rect(center=self._confirm_rect.center))
        surface.blit(no, no.get_rect(center=self._cancel_rect.center))
