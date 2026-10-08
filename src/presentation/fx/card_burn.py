"""Card burn: a removed card burns away in pixel blocks, from the bottom up, with a glowing edge.

``CardBurn(face, seed)`` cuts the card into ``CELL``-px blocks, each with a burn threshold
(lower blocks first, plus noise so the edge is ragged). ``frame(progress)`` returns the card
with the burnt blocks gone and the blocks about to go painted as embers (white-hot → orange →
dark red). ``edge_points(progress)`` gives where embers should fly from. Pure pygame surfaces,
no particles of its own (the scene owns those).
"""
from __future__ import annotations

import random

import pygame

CELL = 6                      # block size in screen px
EDGE = 0.09                   # how far ahead of the burn the glowing edge reaches
BURN_SECONDS = 1.6            # full burn
EMBER = ((255, 250, 220), (255, 200, 90), (240, 120, 30), (150, 40, 20))


class CardBurn:
    def __init__(self, face: pygame.Surface, seed: int = 0) -> None:
        self.face = face
        w, h = face.get_size()
        rng = random.Random(seed)
        self.cols, self.rows = max(1, -(-w // CELL)), max(1, -(-h // CELL))
        # bottom rows burn first; noise makes the front ragged
        self.threshold = [[0.72 * (1.0 - (r + 0.5) / self.rows) + 0.28 * rng.random()
                           for c in range(self.cols)] for r in range(self.rows)]

    def burnt(self, row: int, col: int, progress: float) -> bool:
        return self.threshold[row][col] < progress

    def frame(self, progress: float) -> pygame.Surface:
        """The card at ``progress`` (0 = whole, ≥ 1 + EDGE = gone)."""
        out = self.face.copy()
        if progress <= 0:
            return out
        for r in range(self.rows):
            for c in range(self.cols):
                t = self.threshold[r][c]
                if t < progress:
                    out.fill((0, 0, 0, 0), (c * CELL, r * CELL, CELL, CELL))
                elif t < progress + EDGE:
                    k = (t - progress) / EDGE              # 0 = about to go (hottest)
                    color = EMBER[min(len(EMBER) - 1, int(k * len(EMBER)))]
                    out.fill((*color, 255), (c * CELL, r * CELL, CELL, CELL))
        return out

    def edge_points(self, progress: float, limit: int = 12) -> list[tuple[int, int]]:
        """Centres (in card px) of glowing blocks, for ember particles."""
        pts = [(c * CELL + CELL // 2, r * CELL + CELL // 2)
               for r in range(self.rows) for c in range(self.cols)
               if progress <= self.threshold[r][c] < progress + EDGE * 0.5]
        if len(pts) > limit:
            step = len(pts) / limit
            pts = [pts[int(i * step)] for i in range(limit)]
        return pts

    def gone(self, progress: float) -> bool:
        return progress >= 1.0 + EDGE
