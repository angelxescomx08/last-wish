"""Inspect panel: everything about one character, in a scrollable window.

Card games keep the hover light and put the full text one step away (Slay the Spire
shows one short box per power next to the creature; Hearthstone / Legends of Runeterra
open a zoomed view on right click or hold). Last Wish does the same: hovering an enemy
shows ``tooltip.enemy_quick_tooltip``; **right click or a long press** opens this panel
with the whole ``TooltipContent`` (identity, intent in detail, every status with its full
rule, the glossary of every term mentioned).

* Sections: the main lines, then one block per panel (icon, title, tag, lines). Lines may
  start with ``[[icon]]``; lines starting with two spaces are dim notes.
* Scroll: mouse wheel, drag (touch), ↑/↓ keys, the arrows; a thin bar shows where you are.
* Close: Esc, right click, click outside, the "Cerrar" button.
* Performance: the content is rendered once into one tall surface; a frame is one blit of
  the visible slice (good for phones).
"""
from __future__ import annotations

import re

import pygame

from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui import glossary as gl
from src.presentation.ui import rich_text
from src.presentation.ui.pixel_ui import button_state, draw_button, draw_panel, outlined
from src.presentation.ui.tooltip import TooltipContent

PANEL = pygame.Rect(240, 60, 800, 600)
_PAD = 22
_HEADER_H = 92
_FOOTER_H = 52
_ICON = re.compile(r"^\[\[(\w+)\]\]\s*")
_DRAG = 6
_STEP = 48


def _render_line(line: str, fonts: FontRegistry, width: int) -> list[pygame.Surface]:
    """One rule line (optionally "[[icon]]…"), wrapped and colour-coded; dim when indented."""
    icon = None
    m = _ICON.match(line)
    if m:
        icon = ui_icon(m.group(1), 2)
        line = line[m.end():]
    dim = line.startswith("  ")
    font = fonts.get(16)
    indent = (icon.get_width() + 6) if icon is not None else (14 if dim else 0)
    rows = rich_text.render_lines(line.strip(), font, width - indent, gl.DIM if dim else gl.BODY)
    if not rows:
        return []
    h = sum(r.get_height() for r in rows)
    out = pygame.Surface((width, max(h, icon.get_height() if icon is not None else 0)), pygame.SRCALPHA)
    if icon is not None:
        out.blit(icon, (0, 0))
    y = 0
    for r in rows:
        out.blit(r, (indent, y))
        y += r.get_height()
    return [out]


def render_content(content: TooltipContent, fonts: FontRegistry, width: int) -> pygame.Surface:
    """The whole content as one tall surface (sections stacked)."""
    parts: list[tuple[pygame.Surface, int]] = []       # (surface, gap after)
    for line in content.lines:
        for s in _render_line(line, fonts, width):
            parts.append((s, 4))
    for panel in content.panels:
        head = pygame.Surface((width, 32), pygame.SRCALPHA)
        pygame.draw.line(head, (*panel.color, 255), (0, 2), (width, 2), 1)
        x = 0
        icon = ui_icon(panel.icon, 2) if panel.icon else None
        if icon is not None:
            head.blit(icon, (0, 6))
            x = icon.get_width() + 8
        title = outlined(fonts.get(16), panel.title, panel.color)
        head.blit(title, (x, 6 + (28 - title.get_height()) // 2))
        if panel.tag:
            tag = outlined(fonts.get(8), panel.tag, gl.DIM)
            head.blit(tag, (width - tag.get_width(), 14))
        parts.append((head, 2))
        for line in panel.lines:
            for s in _render_line(line, fonts, width):
                parts.append((s, 3))
        parts.append((pygame.Surface((1, 8), pygame.SRCALPHA), 0))
    total = sum(s.get_height() + g for s, g in parts) or 1
    surf = pygame.Surface((width, total), pygame.SRCALPHA)
    y = 0
    for s, g in parts:
        surf.blit(s, (0, y))
        y += s.get_height() + g
    return surf


class InspectOverlay:
    """Modal, scrollable view of one ``TooltipContent`` (``portrait``: optional picture)."""

    def __init__(self, content: TooltipContent, fonts: FontRegistry,
                 portrait: pygame.Surface | None = None) -> None:
        self.content = content
        self._fonts = fonts
        self.dismissed = False
        self.view = pygame.Rect(PANEL.x + _PAD, PANEL.y + _HEADER_H, PANEL.w - 2 * _PAD - 14,
                                PANEL.h - _HEADER_H - _FOOTER_H)
        self.body = render_content(content, fonts, self.view.w)
        self.offset = 0.0
        self.target = 0.0
        self.close_rect = pygame.Rect(PANEL.right - 150, PANEL.bottom - 46, 130, 36)
        self._portrait = portrait
        self._mouse = (0, 0)
        self._down = False
        self._press: tuple[int, float] | None = None
        self._dragging = False

    @property
    def max_offset(self) -> int:
        return max(0, self.body.get_height() - self.view.h)

    def _clamp(self, v: float) -> float:
        return max(0.0, min(float(self.max_offset), v))

    def scroll(self, px: float) -> None:
        self.target = self._clamp(self.target + px)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            if self._press is not None:
                y0, off0 = self._press
                if self._dragging or abs(event.pos[1] - y0) >= _DRAG:
                    self._dragging = True
                    self.target = self.offset = self._clamp(off0 - (event.pos[1] - y0))
        elif event.type == pygame.MOUSEWHEEL:
            self.scroll(-event.y * _STEP)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
            self.scroll(_STEP if event.button == 5 else -_STEP)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.dismissed = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._down = True
            if self.close_rect.collidepoint(event.pos) or not PANEL.collidepoint(event.pos):
                self.dismissed = True
            elif self.view.collidepoint(event.pos):
                self._press, self._dragging = (event.pos[1], self.offset), False
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._down = False
            if self._press is not None and not self._dragging:
                if self._arrow_up().collidepoint(event.pos):
                    self.scroll(-3 * _STEP)
                elif self._arrow_down().collidepoint(event.pos):
                    self.scroll(3 * _STEP)
            self._press, self._dragging = None, False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_i):
                self.dismissed = True
            elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_PAGEDOWN):
                self.scroll(_STEP if event.key != pygame.K_PAGEDOWN else self.view.h - _STEP)
            elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_PAGEUP):
                self.scroll(-_STEP if event.key != pygame.K_PAGEUP else -(self.view.h - _STEP))

    def update(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1))
        self.offset += (self.target - self.offset) * min(1.0, dt * 14)
        if abs(self.target - self.offset) < 0.5:
            self.offset = self.target

    def _arrow_up(self) -> pygame.Rect:
        return pygame.Rect(self.view.right - 30, self.view.y, 30, 24)

    def _arrow_down(self) -> pygame.Rect:
        return pygame.Rect(self.view.right - 30, self.view.bottom - 24, 30, 24)

    def draw(self, surface: pygame.Surface) -> None:
        fonts = self._fonts
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((6, 4, 10, 190))
        surface.blit(shade, (0, 0))
        draw_panel(surface, PANEL)
        # header: portrait, name, subtitle
        x = PANEL.x + _PAD
        if self._portrait is not None:
            pw, ph = self._portrait.get_size()
            k = min(64 / max(1, pw), 64 / max(1, ph))
            pic = pygame.transform.scale(self._portrait, (max(1, int(pw * k)), max(1, int(ph * k))))
            surface.blit(pic, pic.get_rect(midleft=(x, PANEL.y + 46)))
            x += 76
        title = outlined(fonts.get(32), self.content.title, (246, 204, 92))
        surface.blit(title, (x, PANEL.y + 18))
        sub = " · ".join(p for p in (self.content.subtitle, self.content.tag) if p)
        if sub:
            surface.blit(outlined(fonts.get(16), sub, gl.DIM), (x, PANEL.y + 56))
        pygame.draw.line(surface, (110, 96, 70), (PANEL.x + _PAD, self.view.y - 6),
                         (PANEL.right - _PAD, self.view.y - 6), 1)
        # body: the visible slice of the pre-rendered content
        off = int(round(self.offset))
        h = min(self.view.h, self.body.get_height() - off)
        if h > 0:
            surface.blit(self.body, self.view.topleft, pygame.Rect(0, off, self.view.w, h))
        # scrollbar + arrows when it overflows
        if self.max_offset > 0:
            track = pygame.Rect(self.view.right + 6, self.view.y, 6, self.view.h)
            pygame.draw.rect(surface, (40, 34, 50), track, border_radius=3)
            knob_h = max(30, int(track.h * self.view.h / self.body.get_height()))
            knob_y = track.y + int((track.h - knob_h) * (self.offset / self.max_offset))
            pygame.draw.rect(surface, (246, 204, 92), (track.x, knob_y, track.w, knob_h), border_radius=3)
            for rect, up, show in ((self._arrow_up(), True, self.offset > 0.5),
                                   (self._arrow_down(), False, self.offset < self.max_offset - 0.5)):
                if show:
                    cx, cy = rect.center
                    pygame.draw.rect(surface, (14, 10, 18), rect, border_radius=5)
                    pts = [(cx - 8, cy + 4), (cx + 8, cy + 4), (cx, cy - 5)] if up else \
                          [(cx - 8, cy - 4), (cx + 8, cy - 4), (cx, cy + 5)]
                    pygame.draw.polygon(surface, (246, 204, 92), pts)
            hint = outlined(fonts.get(8), "Rueda / arrastrar / ↑↓ para desplazar", gl.DIM)
            surface.blit(hint, (PANEL.x + _PAD, PANEL.bottom - 34))
        draw_button(surface, self.close_rect, "Cerrar", fonts, key="Esc",
                    state=button_state(self.close_rect, self._mouse, self._down), size=14)
