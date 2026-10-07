"""Rich text: card-game style colour coding for rule text (tooltips and card faces).

The same sentence reads faster when its key parts stand out the same way
everywhere (the convention of Slay the Spire, Hearthstone, Monster Train…):

* "12 de daño" → red, "8 de escudo" / "bloqueo" → blue, "+1 de maná" → light blue,
* "3 de Veneno" / "Veneno" → green,
* every glossary term (statuses, Combo, Agotar…) → gold,
* the rest stays in the base colour.

``spans(text, base)`` splits a sentence into ``(text, colour)`` runs;
``render_lines(text, font, max_w, base)`` word-wraps it into ready surfaces
(cached), ``render_line`` draws a single line without wrapping.
"""
from __future__ import annotations

import re
from functools import lru_cache

import pygame

from src.presentation.ui import glossary as gl

Color = tuple[int, int, int]

_NUM = r"[+\-−]?\d[\d.,]*(?:[KMBTQE](?=\s))?"
_RULES: list[tuple[re.Pattern, Color]] = [
    (re.compile(_NUM + r"(?:\s*[x×]\s*\d+)?\s+(?:de\s+)?daño(?:\s+más)?"), gl.DAMAGE),
    (re.compile(r"daño"), gl.DAMAGE),
    (re.compile(_NUM + r"\s+(?:puntos\s+)?(?:de\s+)?(?:escudo|bloqueo)"), gl.BLOCK),
    (re.compile(r"\b(?:escudo|bloqueo|Bloqueo|Escudo)\b"), gl.BLOCK),
    (re.compile(_NUM + r"\s+de\s+maná"), gl.MANA),
    (re.compile(_NUM + r"\s+de\s+vida"), gl.DAMAGE),
    (re.compile(_NUM + r"\s+de\s+Veneno"), gl.POISON_INK),
]


def spans(text: str, base: Color) -> list[tuple[str, Color]]:
    """``text`` split into coloured runs (first matching rule wins on overlaps)."""
    colors: list[Color | None] = [None] * len(text)
    for pattern, color in _RULES + gl.highlight_words():
        for m in pattern.finditer(text):
            a, b = m.span()
            if any(colors[i] is not None for i in range(a, b)):
                continue
            for i in range(a, b):
                colors[i] = color
    out: list[tuple[str, Color]] = []
    for ch, c in zip(text, colors):
        col = c or base
        if out and out[-1][1] == col:
            out[-1] = (out[-1][0] + ch, col)
        else:
            out.append((ch, col))
    return out


def _word_runs(text: str, base: Color) -> list[list[tuple[str, Color]]]:
    """Words (split on spaces) as lists of coloured pieces."""
    words: list[list[tuple[str, Color]]] = [[]]
    for piece, col in spans(text, base):
        parts = piece.split(" ")
        for k, part in enumerate(parts):
            if k > 0:
                words.append([])
            if part:
                words[-1].append((part, col))
    return [w for w in words if w]


def _render_word(font: pygame.font.Font, pieces: list[tuple[str, Color]], shadow: bool) -> pygame.Surface:
    surfs = [font.render(t, True, c) for t, c in pieces]
    w = sum(s.get_width() for s in surfs)
    h = font.get_height()
    out = pygame.Surface((w + (1 if shadow else 0), h + (1 if shadow else 0)), pygame.SRCALPHA)
    x = 0
    for (t, _), s in zip(pieces, surfs):
        if shadow:
            out.blit(font.render(t, True, (8, 6, 12)), (x + 1, 1))
        out.blit(s, (x, 0))
        x += s.get_width()
    return out


def _join(words: list[pygame.Surface], space: int, height: int) -> pygame.Surface:
    w = sum(s.get_width() for s in words) + space * max(0, len(words) - 1)
    out = pygame.Surface((max(1, w), height), pygame.SRCALPHA)
    x = 0
    for s in words:
        out.blit(s, (x, 0))
        x += s.get_width() + space
    return out


@lru_cache(maxsize=1024)
def _cached_lines(text: str, font: pygame.font.Font, max_w: int, base: Color,
                  shadow: bool) -> tuple[pygame.Surface, ...]:
    space = font.size(" ")[0]
    height = font.get_height() + (1 if shadow else 0)
    lines: list[pygame.Surface] = []
    current: list[pygame.Surface] = []
    width = 0
    for pieces in _word_runs(text, base):
        surf = _render_word(font, pieces, shadow)
        extra = surf.get_width() + (space if current else 0)
        if current and width + extra > max_w:
            lines.append(_join(current, space, height))
            current, width = [], 0
            extra = surf.get_width()
        current.append(surf)
        width += extra
    if current:
        lines.append(_join(current, space, height))
    return tuple(lines) or (pygame.Surface((1, height), pygame.SRCALPHA),)


def render_lines(text: str, font: pygame.font.Font, max_w: int, base: Color = gl.BODY, *,
                 shadow: bool = False) -> list[pygame.Surface]:
    """``text`` word-wrapped to ``max_w`` px, one surface per line, colour-coded."""
    return list(_cached_lines(text, font, max(8, max_w), tuple(base[:3]), shadow))


def render_line(text: str, font: pygame.font.Font, base: Color = gl.BODY, *,
                shadow: bool = False) -> pygame.Surface:
    """One colour-coded line, never wrapped."""
    return _cached_lines(text, font, 1 << 20, tuple(base[:3]), shadow)[0]

