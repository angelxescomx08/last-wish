"""Run pause overlay, the pause / hero buttons and their placement.

The two run buttons are pixel-art kit buttons with a picture and their key:
``[⚙ Esc]`` opens the pause menu, ``[⛑ C]`` the hero sheet. Hovering one shows
its name under it. ``pause_button_rect(scene)`` decides where they go (a scene
with a busy top bar declares its own ``pause_button_rect``); the hero button
sits right after it (``stats_button_rect``).
"""
import math
from enum import Enum, auto

import pygame

from src.infrastructure.fonts import FontRegistry
from src.presentation.ui.pixel_ui import draw_button, draw_keycap, draw_panel, draw_ribbon, outlined

PAUSE_BUTTON = pygame.Rect(232, 16, 64, 36)
_STATS_GAP = 6


class PauseAction(Enum):
    RESUME = auto()
    ABANDON = auto()


class PauseMenu:
    def __init__(self, fonts: FontRegistry):
        self.fonts = fonts
        self.confirming = False
        self.selected = 0
        self.action = None
        self.t = 0.0
        self.buttons = [pygame.Rect(425, 348, 430, 52), pygame.Rect(425, 420, 430, 52)]

    def handle_event(self, event):
        if self.action is not None:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.confirming:
                    self.confirming = False
                    self.selected = 0
                else:
                    self.action = PauseAction.RESUME
            elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_TAB):
                self.selected = 1 - self.selected
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and not getattr(event, 'repeat', False):
                self._activate()
        elif event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.buttons):
                if rect.collidepoint(event.pos):
                    self.selected = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.buttons):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    self._activate()
                    break

    def update(self, dt: float) -> None:
        self.t += max(0.0, min(dt, 0.1))

    def _activate(self):
        if self.selected == 0:
            if self.confirming:
                self.confirming = False
            else:
                self.action = PauseAction.RESUME
        elif self.confirming:
            self.action = PauseAction.ABANDON
        else:
            self.confirming = True
            self.selected = 0

    def draw(self, surface):
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((5, 8, 16, 205))
        surface.blit(veil, (0, 0))
        panel = pygame.Rect(350, 190, 580, 350)
        draw_panel(surface, panel)
        draw_ribbon(surface, (panel.centerx, panel.y + 6), 'PAUSA', self.fonts, size=17)
        self._text(surface, '¿Abandonar la partida?' if self.confirming else 'Partida en pausa', 34, (640, 248))
        self._text(surface, 'Perderás el progreso de esta partida.' if self.confirming
                   else 'La partida se detiene hasta que vuelvas.', 19, (640, 298), (200, 190, 170))
        labels = ('Cancelar', 'Abandonar y volver al menú') if self.confirming else ('Reanudar', 'Abandonar partida…')
        icons = (None, None) if self.confirming else ('hourglass', 'unplayable')
        for i, (rect, label) in enumerate(zip(self.buttons, labels)):
            danger = i == 1
            style = 'bronze' if danger else 'gold'
            draw_button(surface, rect, label, self.fonts, style=style, icon=icons[i],
                        state='hover' if i == self.selected else 'idle', t=self.t, size=22,
                        glow=(0.4 + 0.3 * math.sin(self.t * 4)) if i == self.selected and not danger else 0.0)
        x = 640 - 150
        for key, text in (('↑↓', 'seleccionar'), ('Enter', 'aceptar'), ('Esc', 'volver')):
            cap = draw_keycap(surface, (x, 512), key, self.fonts)
            label = outlined(self.fonts.get(14), text, (200, 190, 170))
            surface.blit(label, label.get_rect(midleft=(cap.right + 5, 512)))
            x = cap.right + 5 + label.get_width() + 26

    def _text(self, surface, text, size, center, color=(237, 227, 207)):
        rendered = outlined(self.fonts.get(size), text, color)
        surface.blit(rendered, rendered.get_rect(center=center))


def pause_button_rect(scene) -> pygame.Rect | None:
    """Where the pause button goes for ``scene``, or None while it shows an overlay.

    A scene whose top bar is busy (combat relics) declares its own
    ``pause_button_rect``; the others use ``PAUSE_BUTTON``. The button is hidden
    while a collection overlay is open so it never covers the overlay's title
    (Escape still closes the overlay first).
    """
    if getattr(scene, '_overlay', None) is not None:
        return None
    rect = getattr(scene, 'pause_button_rect', None)
    return rect if isinstance(rect, pygame.Rect) else PAUSE_BUTTON


def stats_button_rect(scene) -> pygame.Rect | None:
    """The hero-sheet button: right after the pause button (same size), or None when hidden."""
    pause = pause_button_rect(scene)
    if pause is None:
        return None
    return pygame.Rect(pause.right + _STATS_GAP, pause.y, pause.w, pause.h)


def _state(rect: pygame.Rect, mouse, pressed: bool) -> str:
    if rect.collidepoint(mouse):
        return 'press' if pressed else 'hover'
    return 'idle'


def _hover_label(surface, fonts, rect: pygame.Rect, text: str) -> None:
    label = outlined(fonts.get(13), text, (250, 236, 206))
    box = label.get_rect(midtop=(rect.centerx, rect.bottom + 6)).inflate(12, 6)
    box.clamp_ip(surface.get_rect())
    pygame.draw.rect(surface, (14, 10, 18), box, border_radius=4)
    pygame.draw.rect(surface, (176, 140, 72), box, 1, border_radius=4)
    surface.blit(label, label.get_rect(center=box.center))


def draw_pause_button(surface, fonts, rect: pygame.Rect = PAUSE_BUTTON, *, mouse=(-1, -1),
                      pressed: bool = False, t: float = 0.0):
    draw_button(surface, rect, '', fonts, icon='gear', key='Esc', state=_state(rect, mouse, pressed), t=t)
    if rect.collidepoint(mouse):
        _hover_label(surface, fonts, rect, 'Pausa')


def draw_stats_button(surface, fonts, rect: pygame.Rect, *, mouse=(-1, -1), pressed: bool = False,
                      t: float = 0.0):
    draw_button(surface, rect, '', fonts, icon='helmet', key='C', state=_state(rect, mouse, pressed), t=t)
    if rect.collidepoint(mouse):
        _hover_label(surface, fonts, rect, 'Héroe y estadísticas')
