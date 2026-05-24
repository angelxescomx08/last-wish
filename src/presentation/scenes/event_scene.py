"""Event room scene — a simple event that awards gold.

Public flag consumed by SceneManager:
  cleared: bool — True when the player clicks "Recoger".
"""
from __future__ import annotations

import pygame

from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

_BG = pygame.Color(10, 10, 20)

_EVENTS: list[tuple[str, str]] = [
    ("Monedas Dispersas",
     "Encuentras monedas dispersadas por el suelo.\n¡Alguien debió pasar aquí con prisa!"),
    ("Cofre Olvidado",
     "Hay un pequeño cofre medio enterrado entre las piedras.\nNo tiene cerradura. ¡Qué suerte!"),
    ("Mercader Caído",
     "Un mercader caído ha perdido su bolsa de monedas.\nParece que ya no la necesita."),
    ("Trampa Fallida",
     "Una trampa dispara unas monedas al aire.\nAlgún ingeniero tuvo un día malo."),
]


def _event_text(room_id: str) -> tuple[str, str]:
    h = hash(room_id) & 0xFFFF_FFFF
    return _EVENTS[h % len(_EVENTS)]


class EventScene:
    """Mysterious event: narrative text + gold reward."""

    def __init__(self, run: Run, gold: int, room_id: str, fonts: FontRegistry) -> None:
        self._run        = run
        self._gold       = gold
        self._fonts      = fonts
        title, body      = _event_text(room_id)
        self._title      = title
        self._body_lines = body.split("\n")
        self._btn_rect:  pygame.Rect | None = None

        self.cleared: bool = False

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._btn_rect and self._btn_rect.collidepoint(event.pos):
                self.cleared = True

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        cx = surface.get_width() // 2

        # Title
        t = self._fonts.get(24).render("Evento Misterioso", True, pygame.Color(140, 80, 200))
        surface.blit(t, t.get_rect(centerx=cx, centery=80))

        # Event title
        et = self._fonts.get(18).render(self._title, True, colors.TEXT_ACCENT)
        surface.blit(et, et.get_rect(centerx=cx, centery=140))

        # Event body
        cy = 190
        for line in self._body_lines:
            ls = self._fonts.get(14).render(line, True, colors.TEXT_PRIMARY)
            surface.blit(ls, ls.get_rect(centerx=cx, centery=cy))
            cy += 26

        # Gold reward
        gr = self._fonts.get(18).render(
            f"Recompensa: +{self._gold} de oro", True, pygame.Color(220, 190, 50)
        )
        surface.blit(gr, gr.get_rect(centerx=cx, centery=300))

        # Button
        btn_surf = self._fonts.get(15).render("Recoger", True, colors.TEXT_PRIMARY)
        btn_rect = btn_surf.get_rect(centerx=cx, centery=380)
        self._btn_rect = pygame.Rect(
            btn_rect.x - 20, btn_rect.y - 8,
            btn_rect.width + 40, btn_rect.height + 16,
        )
        pygame.draw.rect(surface, pygame.Color(50, 120, 50), self._btn_rect, border_radius=6)
        pygame.draw.rect(surface, pygame.Color(60, 160, 60), self._btn_rect, 2, border_radius=6)
        surface.blit(btn_surf, btn_rect)
