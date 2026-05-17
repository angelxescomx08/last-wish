from __future__ import annotations

import pygame

VIRTUAL_W: int = 1280
VIRTUAL_H: int = 720


class Viewport:
    """Maps a fixed 1280×720 virtual canvas to any actual screen size.

    All game rendering targets `viewport.surface` (virtual coords).
    Mouse events are re-mapped to virtual coords via `transform_event`.
    The virtual surface is then smoothly scaled to fill the real display
    with letterbox/pillarbox bars as needed — works on any resolution or
    aspect ratio (phones in landscape, tablets, widescreen desktops, etc).
    """

    def __init__(self, actual_w: int, actual_h: int) -> None:
        self.surface: pygame.Surface = pygame.Surface((VIRTUAL_W, VIRTUAL_H))
        self._update(actual_w, actual_h)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resize(self, actual_w: int, actual_h: int) -> None:
        self._update(actual_w, actual_h)

    def to_virtual(self, actual_pos: tuple[int, int]) -> tuple[int, int]:
        """Convert an actual-screen pixel position to virtual canvas coords."""
        if self._scale <= 0:
            return actual_pos
        vx = (actual_pos[0] - self._off_x) / self._scale
        vy = (actual_pos[1] - self._off_y) / self._scale
        return (int(vx), int(vy))

    def transform_event(self, event: pygame.event.Event) -> pygame.event.Event:
        """Return a copy of a mouse event with `.pos` in virtual coordinates."""
        _MOUSE_TYPES = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)
        if event.type not in _MOUSE_TYPES:
            return event
        attrs = dict(event.__dict__)
        attrs["pos"] = self.to_virtual(event.pos)
        if "rel" in attrs and self._scale > 0:
            rx, ry = event.rel
            attrs["rel"] = (rx / self._scale, ry / self._scale)
        return pygame.event.Event(event.type, attrs)

    def present(self, screen: pygame.Surface) -> None:
        """Scale the virtual surface and blit it onto the real display."""
        screen.fill((0, 0, 0))
        scaled = pygame.transform.smoothscale(
            self.surface, (self._dest_w, self._dest_h)
        )
        screen.blit(scaled, (self._off_x, self._off_y))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update(self, actual_w: int, actual_h: int) -> None:
        sx = actual_w / VIRTUAL_W
        sy = actual_h / VIRTUAL_H
        self._scale  = min(sx, sy)
        self._dest_w = int(VIRTUAL_W * self._scale)
        self._dest_h = int(VIRTUAL_H * self._scale)
        self._off_x  = (actual_w - self._dest_w) // 2
        self._off_y  = (actual_h - self._dest_h) // 2
