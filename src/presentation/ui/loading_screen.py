"""Asset-independent pixel UI shown before startup decoding begins."""
from __future__ import annotations

import pygame

from src.infrastructure.colors import TEXT_ACCENT, TEXT_PRIMARY, TEXT_SECONDARY
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.viewport import Viewport


class LoadingScreen:
    """Draw startup feedback using only fonts and primitive pixel shapes."""

    def __init__(self, fonts: FontRegistry) -> None:
        self._fonts = fonts
        self._title = fonts.get(64).render("ÚLTIMO DESEO", False, TEXT_ACCENT)
        self._subtitle = fonts.get(18).render("PREPARANDO LA AVENTURA", False, TEXT_PRIMARY)
        self._hint = fonts.get(16).render("La mazmorra te espera...", False, TEXT_SECONDARY)

    def draw(self, surface: pygame.Surface, label: str, progress: float) -> None:
        progress = max(0.0, min(1.0, progress))
        surface.fill((12, 14, 24))
        for row, y in enumerate(range(0, 720, 48)):
            for x in range(-80, 1280, 160):
                brick = pygame.Rect(x + (80 if row % 2 else 0), y, 158, 46)
                pygame.draw.rect(surface, (18, 21, 33), brick, 1)
        panel = pygame.Rect(300, 206, 680, 308)
        pygame.draw.rect(surface, (8, 10, 18), panel.move(6, 8))
        pygame.draw.rect(surface, (22, 24, 38), panel)
        pygame.draw.rect(surface, (94, 76, 46), panel, 2)
        pygame.draw.rect(surface, (45, 44, 54), panel.inflate(-12, -12), 2)
        for x, y in (panel.topleft, panel.topright, panel.bottomleft, panel.bottomright):
            pygame.draw.rect(surface, TEXT_ACCENT, (x - 3, y - 3, 6, 6))
        surface.blit(self._title, self._title.get_rect(center=(640, 278)))
        surface.blit(self._subtitle, self._subtitle.get_rect(center=(640, 331)))
        stage = self._fonts.get(18).render(label, False, TEXT_SECONDARY)
        surface.blit(stage, stage.get_rect(center=(640, 375)))
        bar = pygame.Rect(410, 400, 460, 24)
        pygame.draw.rect(surface, (6, 10, 18), bar)
        fill = bar.inflate(-8, -8)
        fill.w = round(fill.w * progress)
        if fill.w:
            pygame.draw.rect(surface, TEXT_ACCENT, fill)
            pygame.draw.rect(surface, (245, 216, 139), (fill.x, fill.y, fill.w, 3))
        pygame.draw.rect(surface, (115, 105, 85), bar, 2)
        percent = self._fonts.get(16).render(f"{round(progress * 100)} %", False, TEXT_PRIMARY)
        surface.blit(percent, percent.get_rect(center=(640, 455)))
        surface.blit(self._hint, self._hint.get_rect(center=(640, 550)))

    def present(self, screen: pygame.Surface, viewport: Viewport,
                label: str, progress: float) -> bool:
        """Service window events and present one completed loading step."""
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                return False
        width, height = screen.get_size()
        viewport.resize(max(1, width), max(1, height))
        self.draw(viewport.surface, label, progress)
        viewport.present(screen)
        pygame.display.flip()
        return True
