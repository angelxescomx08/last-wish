"""Main menu scene.

Options (top to bottom):
  • Jugar / Continuar  — start or resume a run
  • Ajustes            — settings (not yet implemented; shown grayed out)
  • Salir              — quit the application

Navigation: arrow keys + Enter, or mouse hover + click.

Look (same kit as the run screens): the baked dungeon room with its torches, rain
and embers behind a dark vignette, the three heroes idling on the floor, a gilded
title with a slow glow, and the options as pixel-art buttons in an iron panel
(gold = selected, bronze = the rest) with an icon each and key caps for the
controls. The menu fades in on open.
The requested_action attribute is set when the player confirms a choice.
SceneManager must reset it to None after consuming it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

import math

from src.infrastructure import colors
from src.infrastructure.audio import SoundPlayer
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader
from src.presentation.fx.bursts import soft_glow
from src.presentation.ui.dungeon_backdrop import DungeonBackdrop
from src.presentation.ui.pixel_ui import draw_button, draw_keycap, draw_panel, draw_ribbon, outlined


class MenuAction(Enum):
    PLAY     = auto()
    SETTINGS = auto()
    DEV      = auto()   # "Pruebas" tuning screen
    EXIT     = auto()


@dataclass
class _Option:
    label:   str
    action:  MenuAction
    enabled: bool = True


# ---------------------------------------------------------------------------
# Layout constants (virtual 1280×720 canvas)
# ---------------------------------------------------------------------------

_BG_COLOR        = pygame.Color(14, 20, 14)
_TITLE_Y: int    = 150
_SUBTITLE_Y: int = 222
_OPTIONS_Y: int  = 340   # top option centre-y
_OPTION_GAP: int = 62    # vertical distance between option centres
_NAV_HINT_Y: int = 694
_BUTTON_W: int   = 330
_BUTTON_H: int   = 48
_FADE_IN: float  = 0.6
_ICONS = {"PLAY": "attack_2", "SETTINGS": "gear", "DEV": "ritual", "EXIT": "unplayable"}
# The three heroes stand on the floor of the room (name, x, feet y, size).
_HEROES = (("La Pícara", 150, 640, 192), ("La Guerrera", 300, 650, 192), ("El Mago", 1080, 650, 192))


class MainMenuScene:
    """Full main menu with keyboard and mouse navigation."""

    _TITLE    = "Último Deseo"
    _SUBTITLE = "Un juego de cartas"
    _NAV_HINT = "↑ ↓ para navegar  |  ENTER para confirmar"

    def __init__(self, fonts: FontRegistry, *, has_active_game: bool = False, sound: SoundPlayer | None = None) -> None:
        self._sound = sound if sound is not None else SoundPlayer()
        self._fonts          = fonts
        self._options        = self._build_options(has_active_game)
        self._selected_index = 0
        self._option_rects:  list[pygame.Rect] = []
        self.requested_action: MenuAction | None = None
        self._t = 0.0
        self._backdrop: DungeonBackdrop | None = None
        self._sprites: SpriteLoader | None = None
        self._mouse: tuple[int, int] = (-1, -1)
        self._pressed = False

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.requested_action is not None:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self._move_selection(-1)
            elif event.key == pygame.K_DOWN:
                self._move_selection(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._confirm_selection()
        elif event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._pressed = True
            self._handle_click(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pressed = False

    def update(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1))
        self._t += dt
        if self._backdrop is not None:
            self._backdrop.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        cx = surface.get_width() // 2
        self._draw_room(surface)
        self._draw_heroes(surface)

        # Title: warm glow behind, gilded outlined letters, ribbon subtitle
        pulse = 0.5 + 0.5 * math.sin(self._t * 1.4)
        glow = soft_glow((255, 170, 70), int(260 + 30 * pulse))
        surface.blit(glow, glow.get_rect(center=(cx, _TITLE_Y)), special_flags=pygame.BLEND_RGB_ADD)
        shadow = outlined(self._fonts.get(76), self._TITLE, (40, 20, 10), (40, 20, 10))
        surface.blit(shadow, shadow.get_rect(center=(cx + 4, _TITLE_Y + 5)))
        title = outlined(self._fonts.get(76), self._TITLE, (252, 214, 112), (36, 18, 8))
        surface.blit(title, title.get_rect(center=(cx, _TITLE_Y)))
        draw_ribbon(surface, (cx, _SUBTITLE_Y), self._SUBTITLE.upper(), self._fonts, size=18)

        n = len(self._options)
        panel = pygame.Rect(0, 0, _BUTTON_W + 70, (n - 1) * _OPTION_GAP + _BUTTON_H + 56)
        panel.center = (cx, _OPTIONS_Y + (n - 1) * _OPTION_GAP // 2)
        draw_panel(surface, panel)
        self._option_rects = []
        for i, opt in enumerate(self._options):
            oy = _OPTIONS_Y + i * _OPTION_GAP
            rect = self._draw_option(surface, opt, cx, oy, selected=(i == self._selected_index))
            self._option_rects.append(rect)

        x = cx - 170
        for key, text in (("↑↓", "navegar"), ("Enter", "confirmar"), ("Clic", "elegir")):
            cap = draw_keycap(surface, (x, _NAV_HINT_Y), key, self._fonts)
            label = outlined(self._fonts.get(14), text, (214, 204, 186))
            surface.blit(label, label.get_rect(midleft=(cap.right + 6, _NAV_HINT_Y)))
            x = cap.right + 6 + label.get_width() + 34

        if self._t < _FADE_IN:                          # fade in from black on open
            veil = pygame.Surface(surface.get_size())
            veil.set_alpha(int(255 * (1 - self._t / _FADE_IN)))
            surface.blit(veil, (0, 0))

    def _draw_room(self, surface: pygame.Surface) -> None:
        if self._backdrop is None:
            self._backdrop = DungeonBackdrop(seed=3)
        self._backdrop.draw(surface)
        shade = _vignette(surface.get_size())
        surface.blit(shade, (0, 0))

    def _draw_heroes(self, surface: pygame.Surface) -> None:
        if self._sprites is None:
            self._sprites = SpriteLoader()
        for k, (name, x, feet, size) in enumerate(_HEROES):
            sprite = self._sprites.get_player_sprite(name, size=size, elapsed=self._t + k * 0.37)
            if sprite is None:
                continue
            if x > surface.get_width() // 2:
                sprite = pygame.transform.flip(sprite, True, False)     # face the centre
            shadow = pygame.Surface((110, 20), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 120), shadow.get_rect())
            surface.blit(shadow, shadow.get_rect(center=(x, feet - 4)))
            surface.blit(sprite, sprite.get_rect(midbottom=(x, feet + 20)))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_options(self, has_active_game: bool) -> list[_Option]:
        play_label = "Continuar" if has_active_game else "Jugar"
        return [
            _Option(play_label, MenuAction.PLAY),
            _Option("Ajustes",  MenuAction.SETTINGS),
            _Option("Pruebas",  MenuAction.DEV),
            _Option("Salir",    MenuAction.EXIT),
        ]

    def _draw_option(
        self,
        surface: pygame.Surface,
        opt: _Option,
        cx: int,
        cy: int,
        *,
        selected: bool,
    ) -> pygame.Rect:
        rect = pygame.Rect(0, 0, _BUTTON_W, _BUTTON_H)
        rect.center = (cx, cy)
        if not opt.enabled:
            state = "off"
        elif selected:
            state = "press" if self._pressed and rect.collidepoint(self._mouse) else "hover"
        else:
            state = "idle"
        glow = (0.35 + 0.25 * math.sin(self._t * 4.0)) if selected and opt.enabled else 0.0
        draw_button(surface, rect, opt.label, self._fonts, style="gold" if selected else "bronze",
                    state=state, icon=_ICONS.get(opt.action.name), t=self._t, glow=glow,
                    size=26 if selected else 22)
        if selected and opt.enabled:                    # pointing arrows at both sides
            bob = int(math.sin(self._t * 5.0) * 3)
            for side, sign in ((rect.left - 18, 1), (rect.right + 18, -1)):
                tip = (side + sign * 8 + sign * bob, cy)
                pygame.draw.polygon(surface, (252, 214, 112),
                                    [tip, (tip[0] - sign * 12, cy - 9), (tip[0] - sign * 12, cy + 9)])
                pygame.draw.polygon(surface, (40, 20, 10),
                                    [tip, (tip[0] - sign * 12, cy - 9), (tip[0] - sign * 12, cy + 9)], 2)
        return rect

    def _move_selection(self, delta: int) -> None:
        previous = self._selected_index
        n = len(self._options)
        for _ in range(n):
            self._selected_index = (self._selected_index + delta) % n
            if self._options[self._selected_index].enabled:
                if self._selected_index != previous:
                    self._sound.play_nav()
                return

    def _confirm_selection(self) -> None:
        opt = self._options[self._selected_index]
        if opt.enabled and self.requested_action is None:
            self.requested_action = opt.action
            self._sound.play_confirm()

    def _update_hover(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos) and self._options[i].enabled:
                if self._selected_index != i:
                    self._sound.play_nav()
                self._selected_index = i
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos) and self._options[i].enabled:
                self._selected_index = i
                self._confirm_selection()
                return


_VIGNETTE: dict = {}


def _vignette(size: tuple[int, int]) -> pygame.Surface:
    """Darkens the room towards the edges (smooth radial falloff, cached)."""
    shade = _VIGNETTE.get(size)
    if shade is None:
        w, h = size
        small = pygame.Surface((64, 36), pygame.SRCALPHA)
        for y in range(36):
            for x in range(64):
                d = math.hypot((x + 0.5) / 32 - 1, ((y + 0.5) / 18 - 0.9) * 1.1)
                a = int(min(210, 40 + 150 * max(0.0, d - 0.35) ** 1.5))
                small.set_at((x, y), (6, 4, 12, a))
        shade = pygame.transform.smoothscale(small, (w, h))
        _VIGNETTE[size] = shade
    return shade
