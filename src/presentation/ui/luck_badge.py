"""Luck badge: a small kit plate that shows how the hero's luck is helping right now.

"[trébol] Suerte 108 ▲  ·  Rara o mejor 61 % · dorada 87 %" — green (with ▲) when
relics such as the Trébol de Siete Hojas raise luck above the character's own, so
the player can see that their luck improves packs, rewards, relics and the gachapón.
Drawn in the shop, the pack opening, the card reward and the gachapón.
"""
from __future__ import annotations

import pygame

from src.application.luck import LuckReport
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui.pixel_ui import draw_panel, outlined

LUCKY = (140, 240, 120)
PLAIN = (236, 226, 204)
DIM = (188, 180, 164)


def luck_line(report: LuckReport) -> tuple[str, str]:
    """(title, detail) texts of the badge."""
    arrow = " ▲" if report.bonus > 0 else ""
    title = f"Suerte {report.luck}{arrow}"
    detail = (f"Rara o mejor {report.rare_or_better():.0%} · dorada {report.golden['card']:.0%}"
              f" · carta extra {report.extra_card:.0%}")
    return title, detail


def draw_luck_badge(surface: pygame.Surface, anchor: str, pos: tuple[int, int], report: LuckReport,
                    fonts: FontRegistry) -> pygame.Rect:
    """Draw the badge with its ``anchor`` ("center", "topleft", "bottomleft"…) at ``pos``."""
    title, detail = luck_line(report)
    t = outlined(fonts.get(15), title, LUCKY if report.bonus > 0 else PLAIN)
    d = outlined(fonts.get(12), detail, DIM)
    icon = ui_icon("clover", 2)
    icon_w = icon.get_width() + 6 if icon else 0
    w = icon_w + max(t.get_width(), d.get_width()) + 34
    rect = pygame.Rect(0, 0, w, 50)
    setattr(rect, anchor, pos)
    draw_panel(surface, rect)
    x = rect.x + 14
    if icon is not None:
        surface.blit(icon, icon.get_rect(midleft=(x, rect.centery)))
        x += icon_w
    surface.blit(t, (x, rect.y + 7))
    surface.blit(d, (x, rect.y + 27))
    return rect
