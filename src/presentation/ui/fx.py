"""Visual effects layer — hit flashes and floating damage/block numbers."""
from __future__ import annotations

import pygame


class _HitFlash:
    def __init__(self, rect: pygame.Rect, color: tuple[int, int, int], lifetime: float = 0.25,
                 delay: float = 0.0) -> None:
        self._rect     = rect.copy()
        self._color    = color
        self._lifetime = lifetime
        self._age      = -max(0.0, delay)     # negative age = waiting to appear

    def update(self, dt: float) -> bool:
        self._age += dt
        return self._age < self._lifetime

    def draw(self, surface: pygame.Surface) -> None:
        if self._age < 0:
            return
        alpha   = int(170 * max(0.0, 1 - self._age / self._lifetime))
        overlay = pygame.Surface(self._rect.size, pygame.SRCALPHA)
        overlay.fill((*self._color, alpha))
        surface.blit(overlay, self._rect.topleft)


class _FloatingNumber:
    _RISE = 42.0  # px / second upward

    def __init__(
        self,
        x: float, y: float,
        text: str,
        color: tuple[int, int, int],
        font: pygame.font.Font,
        lifetime: float = 0.8,
        delay: float = 0.0,
    ) -> None:
        self._x        = x
        self._y        = y
        self._text     = text
        self._color    = color
        self._font     = font
        self._lifetime = lifetime
        self._age      = -max(0.0, delay)     # negative age = waiting to appear

    def update(self, dt: float) -> bool:
        self._age += dt
        if self._age > 0:
            self._y -= self._RISE * dt
        return self._age < self._lifetime

    def draw(self, surface: pygame.Surface) -> None:
        if self._age < 0:
            return
        alpha = int(255 * max(0.0, 1 - self._age / self._lifetime))
        surf  = self._font.render(self._text, True, self._color)
        surf.set_alpha(alpha)
        surface.blit(surf, surf.get_rect(centerx=int(self._x), centery=int(self._y)))


class FxLayer:
    """Manages all active visual effects for a combat scene."""

    def __init__(self, font: pygame.font.Font) -> None:
        self._font:    pygame.font.Font = font
        self._effects: list[_HitFlash | _FloatingNumber] = []

    # ------------------------------------------------------------------
    # Spawn helpers
    # ------------------------------------------------------------------

    def add_hit_flash(self, rect: pygame.Rect, damage: int, *, dx: float = 0.0,
                      delay: float = 0.0, flash: bool = True) -> None:
        """Red flash + "-N"; ``dx``/``delay`` separate repeated hits (golden cards cast twice).

        ``flash=False`` shows only the number (animated sprites bake their own hit flash).
        """
        if flash:
            self._effects.append(_HitFlash(rect, (220, 40, 40), delay=delay))
        self._effects.append(_FloatingNumber(
            rect.centerx + dx, rect.top + 20,
            f"-{damage}", (255, 90, 90), self._font, delay=delay,
        ))

    def add_block_flash(self, rect: pygame.Rect, amount: int, *, flash: bool = True) -> None:
        if flash:
            self._effects.append(_HitFlash(rect, (60, 140, 255), lifetime=0.30))
        self._effects.append(_FloatingNumber(
            rect.centerx, rect.top + 20,
            f"+{amount} BLQ", (100, 190, 255), self._font,
        ))

    def add_text(self, x: float, y: float, text: str, color: tuple[int, int, int],
                 lifetime: float = 1.0) -> None:
        """Floating label, e.g. "¡COMBO!" over the hero."""
        self._effects.append(_FloatingNumber(x, y, text, color, self._font, lifetime=lifetime))

    def add_death_flash(self, rect: pygame.Rect, *, delay: float = 0.0) -> None:
        self._effects.append(_HitFlash(rect, (255, 255, 255), lifetime=0.40, delay=delay))

    # ------------------------------------------------------------------
    # Frame hooks
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._effects = [e for e in self._effects if e.update(dt)]

    def draw(self, surface: pygame.Surface) -> None:
        for e in self._effects:
            e.draw(surface)
