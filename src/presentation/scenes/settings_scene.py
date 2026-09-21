"""FPS and independent audio controls, applied live and saved on leaving."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.preferences import UserPreferences

_BG_COLOR = pygame.Color(14, 20, 14)
_TITLE_Y = 170
_ITEMS_Y = 290
_ITEM_GAP = 86
_HINT_Y = 676
_COLOR_ON = pygame.Color(80, 200, 80)
_COLOR_OFF = pygame.Color(160, 100, 100)
_VOLUME_STEP = 0.1


class _ItemKind(Enum):
    TOGGLE = auto()
    VOLUME = auto()
    BACK = auto()


@dataclass
class _Item:
    label: str
    kind: _ItemKind
    preference: str | None = None


class SettingsScene:
    """Keyboard and mouse settings with immediate audio feedback."""

    _TITLE = "Ajustes"
    _NAV_HINT = "↑ ↓ navegar  |  ← → volumen  |  ENTER confirmar  |  ESC volver"

    def __init__(
        self,
        fonts: FontRegistry,
        prefs: UserPreferences,
        *,
        sound: SoundPlayer | None = None,
    ) -> None:
        self._fonts = fonts
        self._prefs = prefs
        self._sound = sound if sound is not None else SoundPlayer()
        self._sound.set_volumes(prefs.sfx_volume, prefs.music_volume)
        self._items = [
            _Item("Mostrar FPS", _ItemKind.TOGGLE),
            _Item("Efectos de sonido", _ItemKind.VOLUME, "sfx_volume"),
            _Item("Música", _ItemKind.VOLUME, "music_volume"),
            _Item("Volver", _ItemKind.BACK),
        ]
        self._selected = 0
        self._item_rects: list[pygame.Rect] = []
        self._volume_buttons: dict[int, tuple[pygame.Rect, pygame.Rect]] = {}
        self.cleared = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._handle_key(event.key)
        elif event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def _handle_key(self, key: int) -> None:
        if key in (pygame.K_UP, pygame.K_DOWN):
            delta = -1 if key == pygame.K_UP else 1
            self._select((self._selected + delta) % len(self._items))
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._confirm()
        elif key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._adjust_selected(-_VOLUME_STEP if key == pygame.K_LEFT else _VOLUME_STEP)
        elif key == pygame.K_ESCAPE:
            self._leave()

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG_COLOR)
        cx = surface.get_width() // 2
        title = self._fonts.get(56).render(self._TITLE, True, colors.TEXT_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, _TITLE_Y)))
        self._item_rects = []
        self._volume_buttons = {}
        for index, item in enumerate(self._items):
            cy = _ITEMS_Y + index * _ITEM_GAP
            self._item_rects.append(self._draw_item(surface, item, index, cx, cy))
        hint = self._fonts.get(16).render(self._NAV_HINT, True, colors.TEXT_SECONDARY)
        surface.blit(hint, hint.get_rect(center=(cx, _HINT_Y)))

    def _draw_item(
        self, surface: pygame.Surface, item: _Item, index: int, cx: int, cy: int,
    ) -> pygame.Rect:
        selected = index == self._selected
        color = colors.TEXT_ACCENT if selected else colors.TEXT_PRIMARY
        row = pygame.Rect(cx - 340, cy - 33, 680, 66)
        if selected:
            pygame.draw.rect(surface, (25, 36, 26), row, border_radius=9)
            pygame.draw.rect(surface, (73, 87, 49), row, width=1, border_radius=9)
        if item.kind == _ItemKind.VOLUME:
            self._draw_volume(surface, item, index, row, color)
        else:
            text = item.label
            if item.kind == _ItemKind.TOGGLE:
                text += ":  " + ("Activado" if self._prefs.show_fps else "Desactivado")
            label = self._fonts.get(30).render(text, True, color)
            surface.blit(label, label.get_rect(center=row.center))
        return row

    def _draw_volume(
        self, surface: pygame.Surface, item: _Item, index: int,
        row: pygame.Rect, color: pygame.Color,
    ) -> None:
        volume = getattr(self._prefs, item.preference)
        label = self._fonts.get(28).render(item.label, True, color)
        surface.blit(label, label.get_rect(left=row.left + 22, centery=row.centery))
        minus = pygame.Rect(row.right - 266, row.top + 11, 44, 44)
        plus = pygame.Rect(row.right - 66, row.top + 11, 44, 44)
        self._volume_buttons[index] = (minus, plus)
        self._draw_volume_button(surface, minus, "−", color, enabled=volume > 0)
        self._draw_volume_button(surface, plus, "+", color, enabled=volume < 1)
        value = f"{volume:.0%}" if volume else "0% · mudo"
        value_color = _COLOR_ON if volume else _COLOR_OFF
        value_surf = self._fonts.get(23).render(value, True, value_color)
        surface.blit(value_surf, value_surf.get_rect(center=(row.right - 144, row.centery)))

    def _draw_volume_button(
        self, surface: pygame.Surface, rect: pygame.Rect, label: str,
        color: pygame.Color, *, enabled: bool,
    ) -> None:
        pygame.draw.rect(surface, (31, 44, 31), rect, border_radius=6)
        border = color if enabled else colors.TEXT_SECONDARY
        pygame.draw.rect(surface, border, rect, width=1, border_radius=6)
        text = self._fonts.get(30).render(label, True, border)
        surface.blit(text, text.get_rect(center=rect.center))

    def _select(self, index: int) -> None:
        if index != self._selected:
            self._selected = index
            self._sound.play_nav()

    def _toggle_fps(self) -> None:
        self._prefs.show_fps = not self._prefs.show_fps
        self._sound.play_confirm()

    def _adjust_selected(self, delta: float) -> None:
        item = self._items[self._selected]
        if item.kind == _ItemKind.TOGGLE:
            self._toggle_fps()
        elif item.kind == _ItemKind.VOLUME:
            current = getattr(self._prefs, item.preference)
            volume = max(0.0, min(1.0, round(current + delta, 2)))
            if volume == current:
                return
            setattr(self._prefs, item.preference, volume)
            self._sound.set_volumes(self._prefs.sfx_volume, self._prefs.music_volume)
            self._sound.play_confirm()

    def _confirm(self) -> None:
        if self._items[self._selected].kind == _ItemKind.BACK:
            self._leave()
        else:
            self._adjust_selected(_VOLUME_STEP)

    def _leave(self) -> None:
        self._sound.play_cancel()
        self.cleared = True

    def _update_hover(self, pos: tuple[int, int]) -> None:
        for index, rect in enumerate(self._item_rects):
            if rect.collidepoint(pos):
                self._select(index)
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for index, rect in enumerate(self._item_rects):
            if not rect.collidepoint(pos):
                continue
            self._selected = index
            if index in self._volume_buttons:
                minus, plus = self._volume_buttons[index]
                if minus.collidepoint(pos):
                    self._adjust_selected(-_VOLUME_STEP)
                elif plus.collidepoint(pos):
                    self._adjust_selected(_VOLUME_STEP)
            else:
                self._confirm()
            return
