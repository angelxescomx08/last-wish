"""Shop with three single-stock relics and three single-stock packs."""
from __future__ import annotations

import pygame

from src.presentation.ui.text_fit import fit
from src.application.run_manager import acquire_relic, pick_shop_stock, shop_price
from src.domain.card_pool import PackTheme
from src.domain.chroma import chroma_def, chroma_title
from src.domain.run import Run
from src.infrastructure.card_assets import pack_art
from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader
from src.presentation.fx import chroma_fx
from src.presentation.ui.card_widget import _wrap
from src.application.luck import luck_report
from src.presentation.ui.luck_badge import draw_luck_badge

_RELIC_COST = 150
_TILE_W = 330
_TILE_H = 190
_GAP = 24


class ShopScene:
    def __init__(self, run: Run, fonts: FontRegistry, *, sound: SoundPlayer | None = None) -> None:
        self._sound = sound if sound is not None else SoundPlayer()
        self._run = run
        self._fonts = fonts
        self._sprites = SpriteLoader()
        self._packs, self._relics = pick_shop_stock(run)
        self._sold_packs: set[int] = set()
        self._sold_relics: set[int] = set()
        self._pack_rects: list[pygame.Rect] = []
        self._relic_rects: list[pygame.Rect] = []
        self._hovered: tuple[str, int] | None = None
        self._exit_rect: pygame.Rect | None = None
        self.selected_pack: PackTheme | None = None
        self.selected_pack_chroma = None        # Chroma of the bought pack (golden: pick 2)
        self._gilded: dict = {}
        self.cleared = False
        self._feedback_text = ""
        self._feedback_time = 0.0
        self._feedback_color = colors.TEXT_ACCENT

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        self._feedback_time = max(0.0, self._feedback_time - dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(pygame.Color(10, 14, 18))
        cx = surface.get_width() // 2
        self._label(surface, 'Tienda del Viajero', (cx, 45), 26, colors.TEXT_ACCENT)
        start_x = cx - (3 * _TILE_W + 2 * _GAP) // 2
        self._relic_rects = []
        self._pack_rects = []
        for kind, items, sold, rects, top in (
            ('Reliquias', self._relics, self._sold_relics, self._relic_rects, 140),
            ('Sobres', self._packs, self._sold_packs, self._pack_rects, 385),
        ):
            self._label(surface, kind, (cx, top - 20), 16, colors.TEXT_SECONDARY)
            for i, item in enumerate(items):
                rect = pygame.Rect(start_x + i * (_TILE_W + _GAP), top, _TILE_W, _TILE_H)
                rects.append(rect)
                is_pack = kind == 'Sobres'
                cost = shop_price(self._run, item.cost if is_pack else _RELIC_COST)
                sprite = (pack_art(item.theme.value, 150) if is_pack
                          else self._sprites.get_relic_sprite(item.name, 64))
                if is_pack and item.chroma is not None and sprite is not None:
                    key = (item.theme, item.chroma)
                    if key not in self._gilded:
                        self._gilded[key] = chroma_fx.gild_frame(sprite, item.chroma)
                    sprite = chroma_fx.animate_card_face(self._gilded[key], item.chroma,
                                                         chroma_fx.now(), base_w=110)
                self._draw_tile(surface, item, cost, sprite, rect, i in sold,
                                self._hovered == (kind, i))
        if self._feedback_time > 0:
            self._label(surface, self._feedback_text, (cx, 601), 16, self._feedback_color)
        draw_luck_badge(surface, "bottomleft", (16, 704), luck_report(self._run), self._fonts)
        self._exit_rect = pygame.Rect(cx - 80, 625, 160, 42)
        pygame.draw.rect(surface, colors.BG_PANEL, self._exit_rect, border_radius=6)
        self._label(surface, 'Salir', self._exit_rect.center, 16, colors.TEXT_PRIMARY)

    def _label(self, surface, text, center, size, color):
        rendered = self._fonts.get(size).render(text, True, color)
        surface.blit(rendered, rendered.get_rect(center=center))

    def _draw_tile(self, surface, item, cost, sprite, rect, sold, hovered):
        available = not sold and self._run.gold >= cost
        border = colors.TEXT_ACCENT if hovered and available else colors.PANEL_BORDER
        pygame.draw.rect(surface, colors.BG_PANEL, rect, border_radius=8)
        pygame.draw.rect(surface, border, rect, 2, border_radius=8)
        if sprite is not None:
            art = sprite.copy()
            if sold:
                art.set_alpha(60)
            surface.blit(art, art.get_rect(center=(rect.x + 55, rect.y + 90)))
        color = colors.TEXT_SECONDARY if sold else colors.TEXT_PRIMARY
        text_x = rect.x + 215
        chroma = getattr(item, 'chroma', None)
        is_pack = hasattr(item, 'theme')
        self._label(surface, chroma_title(item.name, chroma, masculine=is_pack), (rect.centerx, rect.y + 25),
                    16, color)
        description = item.description
        if chroma is not None:
            note = chroma_def(chroma).pack_note if is_pack else chroma_def(chroma).short_note + '.'
            description += ' ' + note
            if not sold:
                chroma_fx.draw_chroma_box(surface, rect, chroma, chroma_fx.now(), radius=8)
        lines = _wrap(description, self._fonts.get(13), 205)
        room = max(1, (rect.bottom - 52 - (rect.y + 65)) // 19 + 1)
        if len(lines) > room:
            lines = lines[:room]
            lines[-1] = fit(self._fonts.get(13), lines[-1] + "…", 205)
        for i, line in enumerate(lines):
            self._label(surface, line, (text_x, rect.y + 65 + i * 19), 13, color)
        label = 'Agotado' if sold else f'{cost} oro'
        self._label(surface, label, (rect.centerx, rect.bottom - 40), 16,
                    colors.TEXT_SECONDARY if sold else colors.TEXT_ACCENT)
        if not sold and not available:
            self._label(surface, 'Sin fondos', (rect.centerx, rect.bottom - 18), 12,
                        pygame.Color(180, 90, 90))

    def _update_hover(self, pos: tuple[int, int]) -> None:
        previous = self._hovered
        self._hovered = None
        for kind, rects in (('Sobres', self._pack_rects), ('Reliquias', self._relic_rects)):
            for i, rect in enumerate(rects):
                if rect.collidepoint(pos):
                    self._hovered = (kind, i)
                    if self._hovered != previous:
                        self._sound.play_nav()
                    return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self.selected_pack is not None or self.cleared:
            return
        for i, rect in enumerate(self._pack_rects):
            if rect.collidepoint(pos):
                pack = self._packs[i]
                price = shop_price(self._run, pack.cost)
                if not self._purchase_allowed(i in self._sold_packs, price):
                    return
                self._run.gold -= price
                self._sold_packs.add(i)
                self.selected_pack = pack.theme
                self.selected_pack_chroma = pack.chroma
                self._sound.play_purchase()
                self._show_feedback(f"{pack.name} comprado")
                return
        for i, rect in enumerate(self._relic_rects):
            if rect.collidepoint(pos):
                price = shop_price(self._run, _RELIC_COST)
                if not self._purchase_allowed(i in self._sold_relics, price):
                    return
                self._run.gold -= price
                self._sold_relics.add(i)
                acquire_relic(self._run, self._relics[i])
                self._sound.play_purchase()
                self._show_feedback(f"{self._relics[i].name} obtenida")
                return
        if self._exit_rect and self._exit_rect.collidepoint(pos):
            self.cleared = True
            self._sound.play_cancel()

    def _show_feedback(self, text: str, *, error: bool = False) -> None:
        self._feedback_text = text
        self._feedback_time = 2.0
        self._feedback_color = pygame.Color(235, 130, 125) if error else colors.TEXT_ACCENT

    def _purchase_allowed(self, sold: bool, cost: int) -> bool:
        if sold:
            message = "Este objeto ya está agotado"
        elif self._run.gold < cost:
            message = f"Te faltan {cost - self._run.gold} de oro"
        else:
            return True
        self._show_feedback(message, error=True)
        self._sound.play_error()
        return False
