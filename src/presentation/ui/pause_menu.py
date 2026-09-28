"""Run pause overlay: keyboard/mouse navigation and explicit abandonment."""
from enum import Enum, auto
import pygame
from src.infrastructure.fonts import FontRegistry

PAUSE_BUTTON = pygame.Rect(232, 16, 140, 36)


class PauseAction(Enum):
    RESUME = auto()
    ABANDON = auto()


class PauseMenu:
    def __init__(self, fonts: FontRegistry):
        self.fonts = fonts
        self.confirming = False
        self.selected = 0
        self.action = None
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
        pygame.draw.rect(surface, (22, 27, 38), panel)
        pygame.draw.rect(surface, (175, 139, 72), panel, 2)
        self._text(surface, '¿Abandonar la partida?' if self.confirming else 'Partida en pausa', 34, (640, 242))
        self._text(surface, 'Perderás el progreso de esta partida.' if self.confirming else 'La partida se detiene hasta que vuelvas.', 19, (640, 296))
        labels = ('Cancelar', 'Abandonar y volver al menú') if self.confirming else ('Reanudar', 'Abandonar partida…')
        for i, (rect, label) in enumerate(zip(self.buttons, labels)):
            pygame.draw.rect(surface, (62, 53, 40) if i == self.selected else (32, 39, 53), rect)
            pygame.draw.rect(surface, (222, 181, 101) if i == self.selected else (88, 97, 111), rect, 2)
            self._text(surface, label, 23, rect.center)
        self._text(surface, '↑ ↓ seleccionar  ·  Enter aceptar  ·  Esc volver', 16, (640, 510))

    def _text(self, surface, text, size, center):
        rendered = self.fonts.get(size).render(text, True, (237, 227, 207))
        surface.blit(rendered, rendered.get_rect(center=center))


def draw_pause_button(surface, fonts):
    pygame.draw.rect(surface, (25, 31, 43), PAUSE_BUTTON)
    pygame.draw.rect(surface, (163, 137, 85), PAUSE_BUTTON, 1)
    text = fonts.get(18).render('Pausa · Esc', True, (237, 227, 207))
    surface.blit(text, text.get_rect(center=PAUSE_BUTTON.center))
