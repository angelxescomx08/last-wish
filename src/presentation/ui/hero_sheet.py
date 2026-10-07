"""Hero sheet overlay ("Héroe", key C): the hero's stats drawn so they read at a glance.

Left: the animated hero in a lit frame, name, description, a big HP bar and (in
combat) the current statuses. Right: one row per stat — icon, name, big number, a
bar split into **base** (stat colour) and **bonus** (green; red when negative), the
sources under the bar ("Base 6 · Orbe de Fuego +2") and one sentence of what the
number does. Bottom: gold, floor, deck (with a bar per card type), relics and turn.

Opening animation: the panel rises in, the bars fill one after another and spark
when full. Esc / C / the X / a click outside closes it (``closed``).
Data comes from ``application.hero_stats.hero_sheet`` (no rules here).
"""
from __future__ import annotations

import math

import pygame

from src.application.hero_stats import HeroSheet, HeroStat
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader
from src.infrastructure.ui_icons import ui_icon
from src.presentation.fx.bursts import GLOW, BurstParticles
from src.presentation.ui import rich_text
from src.presentation.ui.glossary import status_icon
from src.presentation.ui.pixel_ui import draw_button, draw_keycap, draw_panel, draw_ribbon, outlined

PANEL = pygame.Rect(100, 46, 1080, 630)
CLOSE = pygame.Rect(PANEL.right - 58, PANEL.y + 14, 40, 36)
PORTRAIT = pygame.Rect(PANEL.x + 34, PANEL.y + 70, 300, 268)
ROW_X = PANEL.x + 372
ROW_Y = PANEL.y + 72
ROW_H = 63
BAR_X = ROW_X + 300
BAR_W = 340
BAR_H = 14

STAT_COLOR = {
    "hp": (226, 62, 62), "mana": (70, 140, 240), "attack": (240, 112, 70), "dexterity": (80, 190, 230),
    "luck": (110, 210, 90), "draw": (236, 190, 70), "hand": (180, 120, 236),
}
BONUS = (130, 245, 120)
MALUS = (255, 90, 80)
GOLD = (246, 204, 92)
DIM = (178, 170, 156)
OPEN_TIME = 0.25
FILL_TIME = 0.55
FILL_STAGGER = 0.08


class HeroSheetOverlay:
    def __init__(self, sheet: HeroSheet, fonts: FontRegistry, sprites: SpriteLoader | None = None) -> None:
        self.sheet = sheet
        self._fonts = fonts
        self._sprites = sprites or SpriteLoader()
        self.t = 0.0
        self.closed = False
        self._mouse = (-1, -1)
        self._sparked: set[str] = set()
        self._particles = BurstParticles(capacity=240, seed=9)

    # ------------------------------------------------------------ input

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_c):
            self.closed = True
        elif event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if CLOSE.collidepoint(event.pos) or not PANEL.collidepoint(event.pos):
                self.closed = True

    # ------------------------------------------------------------ timing

    def fill(self, index: int) -> float:
        """0..1 progress of stat row ``index``'s bar (they fill one after another)."""
        start = OPEN_TIME + index * FILL_STAGGER
        k = max(0.0, min(1.0, (self.t - start) / FILL_TIME))
        return 1 - (1 - k) ** 3

    def update(self, dt: float) -> None:
        dt = max(0.0, min(dt, 0.1))
        self.t += dt
        for i, stat in enumerate(self.sheet.stats):
            if stat.key not in self._sparked and self.fill(i) >= 1.0:
                self._sparked.add(stat.key)
                end = BAR_X + int(BAR_W * self._bar_total(stat))
                y = ROW_Y + i * ROW_H + 10 + BAR_H // 2
                self._particles.burst(end, y, 10, palette=[STAT_COLOR[stat.key], (255, 255, 255), BONUS],
                                      speed=(30, 120), life=(0.25, 0.5), size=(2, 3), style=GLOW)
        self._particles.update(dt)

    @staticmethod
    def _bar_total(stat: HeroStat) -> float:
        scale = max(stat.reference, stat.value, stat.base, 1)
        return min(1.0, max(stat.value, 0) / scale)

    # ------------------------------------------------------------ drawing

    def draw(self, surface: pygame.Surface) -> None:
        k = min(1.0, self.t / OPEN_TIME)
        ease = 1 - (1 - k) ** 3
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((4, 4, 10, int(200 * ease)))
        surface.blit(veil, (0, 0))
        dy = int((1 - ease) * 40)
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self._draw_content(layer)
        if ease < 1:
            layer.set_alpha(int(255 * ease))
        surface.blit(layer, (0, dy))
        self._particles.draw(surface, (0, dy))

    def _draw_content(self, surface: pygame.Surface) -> None:
        f = self._fonts
        draw_panel(surface, PANEL)
        draw_ribbon(surface, (PANEL.centerx, PANEL.y + 8), "HÉROE", f, size=17)
        state = "hover" if CLOSE.collidepoint(self._mouse) else "idle"
        draw_button(surface, CLOSE, "X", f, state=state, t=self.t, size=18)
        self._draw_portrait(surface)
        head = outlined(f.get(16), "ATRIBUTOS", GOLD)
        surface.blit(head, (ROW_X, PANEL.y + 40))
        hint = outlined(f.get(12), "verde = bonus de reliquias, cartas o Pruebas", DIM)
        surface.blit(hint, hint.get_rect(topright=(BAR_X + BAR_W, PANEL.y + 44)))
        for i, stat in enumerate(self.sheet.stats):
            self._draw_row(surface, i, stat)
        self._draw_tiles(surface)
        foot = outlined(f.get(12), "cerrar", DIM)
        x = PANEL.centerx - 50
        draw_keycap(surface, (x, PANEL.bottom - 16), "Esc", f)
        draw_keycap(surface, (x + 30, PANEL.bottom - 16), "C", f)
        surface.blit(foot, foot.get_rect(midleft=(x + 46, PANEL.bottom - 16)))

    def _draw_portrait(self, surface: pygame.Surface) -> None:
        f = self._fonts
        frame = PORTRAIT
        back = pygame.Surface(frame.size, pygame.SRCALPHA)
        back.fill((10, 8, 18, 255))
        pulse = 0.5 + 0.5 * math.sin(self.t * 1.6)
        for r in range(150, 10, -6):                      # warm light behind the hero
            a = int((26 + 10 * pulse) * (1 - r / 150))
            pygame.draw.circle(back, (255, 170, 80, a), (frame.w // 2, frame.h // 2 + 30), r)
        pygame.draw.ellipse(back, (0, 0, 0, 120), pygame.Rect(frame.w // 2 - 70, frame.h - 44, 140, 22))
        surface.blit(back, frame.topleft)
        sprite = self._sprites.get_player_sprite(self.sheet.name, size=192, elapsed=self.t, animation="idle")
        if sprite is not None:
            surface.blit(sprite, sprite.get_rect(midbottom=(frame.centerx, frame.bottom - 18)))
        pygame.draw.rect(surface, (120, 96, 60), frame, 2)
        y = frame.bottom + 10
        name = outlined(f.get(26), self.sheet.name, GOLD)
        surface.blit(name, name.get_rect(midtop=(frame.centerx, y)))
        y += name.get_height() + 2
        for line in rich_text.render_lines(self.sheet.title, f.get(13), frame.w, DIM):
            surface.blit(line, line.get_rect(midtop=(frame.centerx, y)))
            y += line.get_height()
        hp = self.sheet.stat("hp")
        y += 10
        self._draw_hp(surface, pygame.Rect(frame.x, y, frame.w, 26), hp)
        y += 38
        if self.sheet.statuses:
            label = outlined(f.get(13), "Estados ahora", GOLD)
            surface.blit(label, (frame.x, y))
            y += 20
            x = frame.x
            for name, stacks, is_buff in self.sheet.statuses[:6]:
                icon = ui_icon(status_icon(name, is_buff), 2)
                if icon is not None:
                    surface.blit(icon, (x, y))
                txt = outlined(f.get(12), f"{name} {stacks}", (160, 240, 160) if is_buff else (236, 170, 240))
                surface.blit(txt, (x + 30, y + 7))
                x += 30 + txt.get_width() + 12
                if x > frame.right - 60:
                    x, y = frame.x, y + 30

    def _draw_hp(self, surface: pygame.Surface, rect: pygame.Rect, hp: HeroStat) -> None:
        f = self._fonts
        fill = self.fill(0)
        current = hp.current if hp.current is not None else hp.value
        pygame.draw.rect(surface, (50, 14, 18), rect, border_radius=4)
        ratio = current / hp.value if hp.value > 0 else 0
        inner = pygame.Rect(rect.x, rect.y, int(rect.w * ratio * fill), rect.h)
        if inner.w > 0:
            pygame.draw.rect(surface, (200, 46, 52), inner, border_radius=4)
            pygame.draw.rect(surface, (250, 110, 100), (inner.x + 2, inner.y + 3, max(0, inner.w - 4), 4))
        pygame.draw.rect(surface, (14, 8, 12), rect, 2, border_radius=4)
        heart = ui_icon("heal", 2)
        if heart is not None:
            surface.blit(heart, heart.get_rect(center=(rect.x + 4, rect.centery)))
        txt = outlined(f.get(17), f"{current} / {hp.value}", (255, 240, 230))
        surface.blit(txt, txt.get_rect(center=rect.center))

    def _draw_row(self, surface: pygame.Surface, i: int, stat: HeroStat) -> None:
        f = self._fonts
        y = ROW_Y + i * ROW_H
        color = STAT_COLOR.get(stat.key, GOLD)
        if i % 2 == 0:
            band = pygame.Surface((BAR_X + BAR_W - ROW_X + 16, ROW_H - 4), pygame.SRCALPHA)
            band.fill((255, 255, 255, 8))
            surface.blit(band, (ROW_X - 8, y - 4))
        icon = ui_icon(stat.icon, 3) or ui_icon(stat.icon, 2)
        if icon is not None:
            surface.blit(icon, icon.get_rect(center=(ROW_X + 20, y + 18)))
        name = outlined(f.get(18), stat.name, color)
        surface.blit(name, (ROW_X + 48, y))
        value_txt = f"{stat.current} / {stat.value}" if stat.current is not None else str(stat.value)
        value = outlined(f.get(26), value_txt, (255, 255, 255))
        surface.blit(value, value.get_rect(topright=(BAR_X - 14, y - 4)))
        effect = rich_text.render_line(stat.effect, f.get(13), (226, 220, 206))
        if effect.get_width() > BAR_X + BAR_W - ROW_X - 48:
            effect = rich_text.render_lines(stat.effect, f.get(12), BAR_X + BAR_W - ROW_X - 48, (226, 220, 206))[0]
        surface.blit(effect, (ROW_X + 48, y + 30))
        self._draw_bar(surface, i, stat, color, y + 4)
        detail = outlined(f.get(11), stat.breakdown(), DIM)
        surface.blit(detail, detail.get_rect(topright=(BAR_X + BAR_W, y + 4 + BAR_H + 2)))

    def _draw_bar(self, surface: pygame.Surface, i: int, stat: HeroStat, color, y: int) -> None:
        rect = pygame.Rect(BAR_X, y, BAR_W, BAR_H)
        pygame.draw.rect(surface, (16, 12, 22), rect.inflate(4, 4), border_radius=3)
        pygame.draw.rect(surface, (34, 30, 44), rect, border_radius=2)
        scale = max(stat.reference, stat.value, stat.base, 1)
        fill = self.fill(i)
        base_w = int(BAR_W * min(stat.base, stat.value if stat.bonus < 0 else stat.base) / scale * fill)
        total_w = int(BAR_W * max(0, stat.value) / scale * fill)
        if stat.key == "hp" and stat.current is not None:
            base_w = int(BAR_W * min(stat.base, stat.current) / scale * fill)
            total_w = int(BAR_W * stat.current / scale * fill)
        if base_w > 0:
            pygame.draw.rect(surface, color, (rect.x, rect.y, base_w, rect.h), border_radius=2)
            light = tuple(min(255, c + 60) for c in color)
            pygame.draw.line(surface, light, (rect.x + 1, rect.y + 2), (rect.x + base_w - 2, rect.y + 2))
        if total_w > base_w:
            pygame.draw.rect(surface, BONUS, (rect.x + base_w, rect.y, total_w - base_w, rect.h))
            pygame.draw.line(surface, (220, 255, 210), (rect.x + base_w, rect.y + 2), (rect.x + total_w - 2, rect.y + 2))
        if stat.bonus < 0 and stat.key != "hp":
            lost_w = int(BAR_W * (stat.base - max(0, stat.value)) / scale * fill)
            pygame.draw.rect(surface, MALUS, (rect.x + total_w, rect.y, lost_w, rect.h), 1)
        if scale <= 12:                                    # pips for small numbers
            for k in range(1, scale):
                x = rect.x + int(BAR_W * k / scale)
                pygame.draw.line(surface, (12, 10, 16), (x, rect.y), (x, rect.bottom - 1))
        pygame.draw.rect(surface, (8, 6, 12), rect, 1, border_radius=2)

    def _draw_tiles(self, surface: pygame.Surface) -> None:
        f = self._fonts
        s = self.sheet
        tiles = [("coin", "Oro", str(s.gold)), ("tower", "Piso", str(s.floor)),
                 ("deck", "Mazo", f"{s.deck_size} cartas"), ("bag", "Reliquias", str(s.relic_count))]
        if s.turn is not None:
            tiles.append(("hourglass", "Turno", str(s.turn)))
        x0, y0 = ROW_X - 8, ROW_Y + 7 * ROW_H + 4
        w = (BAR_X + BAR_W - x0 - 8 * (len(tiles) - 1)) // len(tiles)
        for k, (icon_name, label, value) in enumerate(tiles):
            rect = pygame.Rect(x0 + k * (w + 8), y0, w, 60)
            draw_panel(surface, rect)
            icon = ui_icon(icon_name, 2)
            if icon is not None:
                surface.blit(icon, icon.get_rect(midleft=(rect.x + 12, rect.centery)))
            surface.blit(outlined(f.get(12), label, DIM), (rect.x + 46, rect.y + 11))
            surface.blit(outlined(f.get(18), value, (255, 255, 255)), (rect.x + 46, rect.y + 24))
            if label == "Mazo" and s.deck_size:
                bar = pygame.Rect(rect.x + 46, rect.bottom - 13, rect.w - 58, 5)
                colors = {"Ataques": (226, 70, 60), "Habilidades": (70, 140, 230), "Poderes": (190, 120, 240)}
                x = bar.x
                for kind, n in s.deck_by_type.items():
                    seg = round(bar.w * n / s.deck_size)
                    pygame.draw.rect(surface, colors.get(kind, (150, 150, 150)), (x, bar.y, seg, bar.h))
                    x += seg
                pygame.draw.rect(surface, (10, 8, 12), bar.inflate(2, 2), 1)
