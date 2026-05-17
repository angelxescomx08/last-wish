from __future__ import annotations

import pygame


class FontRegistry:
    """Loads and caches pygame SysFont instances by size."""

    def __init__(self) -> None:
        self._cache: dict[int, pygame.font.Font] = {}

    def get(self, size: int) -> pygame.font.Font:
        if size not in self._cache:
            self._cache[size] = pygame.font.SysFont("segoeuisemibold,arialnarrow,serif", size)
        return self._cache[size]
