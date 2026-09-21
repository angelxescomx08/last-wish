"""Scrollable collection modal shared by cards and relics."""
from __future__ import annotations

import pygame
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.tooltip import draw_tooltip


class CollectionViewer:
    tile_width = 180
    tile_height = 254

    def __init__(self, title: str, items: list, fonts: FontRegistry, noun: str) -> None:
        self._title, self._items, self._fonts, self._noun = title, items, fonts, noun
        self._panel = pygame.Rect(50, 30, 1180, 660)
        self._viewport = pygame.Rect(78, 124, 1100, 520)
        self._close_rect = pygame.Rect(1108, 48, 96, 34)
        self._track = pygame.Rect(1190, 124, 12, 520)
        self._scroll_y = 0
        self._drag_offset: int | None = None
        self._mouse = (-1, -1)
        self._item_rects: dict[int, pygame.Rect] = {}
        self._visible_indices: list[int] = []
        self._columns = max(1, self._viewport.width // self.tile_width)
        rows = (len(items) + self._columns - 1) // self._columns
        self._content_height = rows * self.tile_height
        self._max_scroll = max(0, self._content_height - self._viewport.height)
        self.dismissed = False

    @property
    def _thumb(self) -> pygame.Rect:
        height = max(32, int(self._track.height * self._viewport.height / max(self._content_height, 1)))
        height = min(height, self._track.height)
        travel = self._track.height - height
        top = self._track.top + round(travel * self._scroll_y / max(self._max_scroll, 1))
        return pygame.Rect(self._track.x, top, self._track.width, height)

    def _scroll_to(self, value: int) -> None:
        self._scroll_y = max(0, min(self._max_scroll, value))
        self._item_rects.clear()  # never show stale tooltips after scrolling

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.dismissed = True
            targets = {pygame.K_HOME: 0, pygame.K_END: self._max_scroll,
                       pygame.K_UP: self._scroll_y - 60, pygame.K_DOWN: self._scroll_y + 60,
                       pygame.K_PAGEUP: self._scroll_y - self._viewport.height,
                       pygame.K_PAGEDOWN: self._scroll_y + self._viewport.height}
            if event.key in targets:
                self._scroll_to(targets[event.key])
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_to(self._scroll_y - event.y * 60)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button in (4, 5):
                self._scroll_to(self._scroll_y + (-60 if event.button == 4 else 60))
            elif event.button == 1:
                if self._close_rect.collidepoint(event.pos) or not self._panel.collidepoint(event.pos):
                    self.dismissed = True
                elif self._max_scroll and self._track.collidepoint(event.pos):
                    if self._thumb.collidepoint(event.pos):
                        self._drag_offset = event.pos[1] - self._thumb.top
                    else:
                        direction = -1 if event.pos[1] < self._thumb.top else 1
                        self._scroll_to(self._scroll_y + direction * self._viewport.height)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_offset = None
        elif event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            if self._drag_offset is not None:
                travel = self._track.height - self._thumb.height
                offset = event.pos[1] - self._track.top - self._drag_offset
                self._scroll_to(round(offset * self._max_scroll / max(travel, 1)))

    def draw(self, surface: pygame.Surface) -> None:
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 190))
        surface.blit(dim, (0, 0))
        pygame.draw.rect(surface, colors.BG_PANEL, self._panel, border_radius=12)
        pygame.draw.rect(surface, colors.BORDER_BRIGHT, self._panel, 1, border_radius=12)
        title = self._fonts.get(24).render(f'{self._title}  ·  {len(self._items)} {self._noun}', True, colors.TEXT_ACCENT)
        surface.blit(title, (78, 48))
        hint = self._fonts.get(13).render('Pasa el cursor para ver detalles  ·  Rueda / ↑ ↓ / Re Pág / Av Pág', True, colors.TEXT_SECONDARY)
        surface.blit(hint, (78, 90))
        pygame.draw.rect(surface, colors.BG_DARK, self._close_rect, border_radius=6)
        label = self._fonts.get(15).render('Cerrar ×', True, colors.TEXT_PRIMARY)
        surface.blit(label, label.get_rect(center=self._close_rect.center))
        self._visible_indices = []
        self._item_rects = {}
        previous_clip = surface.get_clip()
        try:
            surface.set_clip(previous_clip.clip(self._viewport))
            gap = (self._viewport.width - self._columns * self.tile_width) // max(self._columns - 1, 1)
            for i, item in enumerate(self._items):
                rect = pygame.Rect(self._viewport.x + (i % self._columns) * (self.tile_width + gap),
                                   self._viewport.y + (i // self._columns) * self.tile_height - self._scroll_y,
                                   self.tile_width, self.tile_height)
                if not rect.colliderect(self._viewport):
                    continue
                self._visible_indices.append(i)
                self._item_rects[i] = rect
                self._draw_item(surface, item, rect)
            if not self._items:
                empty = self._fonts.get(22).render('No hay objetos en esta colección', True, colors.TEXT_SECONDARY)
                surface.blit(empty, empty.get_rect(center=self._viewport.center))
        finally:
            surface.set_clip(previous_clip)
        if self._max_scroll:
            pygame.draw.rect(surface, colors.BG_DARK, self._track, border_radius=6)
            pygame.draw.rect(surface, colors.TEXT_SECONDARY, self._thumb, border_radius=6)
        footer = self._fonts.get(12).render('ESC o clic fuera para cerrar', True, colors.TEXT_SECONDARY)
        surface.blit(footer, footer.get_rect(center=(640, 668)))
        if self._viewport.collidepoint(self._mouse) and self._drag_offset is None:
            for i, rect in self._item_rects.items():
                if rect.collidepoint(self._mouse):
                    draw_tooltip(surface, self._tooltip(self._items[i]), self._mouse, self._fonts)
                    break

    def _draw_item(self, surface, item, rect) -> None:
        raise NotImplementedError

    def _tooltip(self, item):
        raise NotImplementedError
