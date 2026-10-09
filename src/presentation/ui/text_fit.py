"""Make text fit a box: word-wrap to a width, or shorten a single line with "…".

Every label drawn inside a panel, button or plate should go through one of these, so a
longer text (or a wider font) never spills out of its frame.
"""
from __future__ import annotations

import pygame

ELLIPSIS = "…"


def wrap(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    """``text`` split into lines no wider than ``max_w`` px (a single over-long word is cut)."""
    max_w = max(1, int(max_w))
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split(" "):
            trial = f"{line} {word}" if line else word
            if font.size(trial)[0] <= max_w:
                line = trial
                continue
            if line:
                lines.append(line)
            line = word if font.size(word)[0] <= max_w else fit(font, word, max_w)
        lines.append(line)
    return lines


def fit(font: pygame.font.Font, text: str, max_w: int) -> str:
    """``text`` unchanged if it fits in ``max_w`` px, else cut and ended with "…"."""
    text = str(text)
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + ELLIPSIS)[0] > max_w:
        text = text[:-1]
    return text.rstrip() + ELLIPSIS if text else ""


def render_wrapped(font: pygame.font.Font, text: str, max_w: int, color, *,
                   max_lines: int | None = None) -> list[pygame.Surface]:
    """Rendered lines of ``wrap``; with ``max_lines`` the last kept line ends with "…"."""
    lines = wrap(font, text, max_w)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit(font, lines[-1] + ELLIPSIS, max_w)
    return [font.render(line, True, color) for line in lines]
