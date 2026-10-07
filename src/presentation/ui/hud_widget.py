"""Combat HUD widgets, drawn with the pixel-art kit (``pixel_ui``): relic slots, mana
orb, card piles, End Turn button and the turn ribbon. Each falls back to plain shapes
when the kit is missing."""
from __future__ import annotations

import math

import pygame

from src.domain.mana import Mana
from src.domain.relic import Relic
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader
from src.infrastructure.ui_kit import kit_piece, kit_slice
from src.presentation.fx import chroma_fx
from src.presentation.ui.card_widget import RARITY_COLOR
from src.presentation.ui.pixel_ui import ManaOrb, draw_button, draw_ribbon, outlined

RELIC_SZ: int       = 48
_RELIC_GAP: int     = 5
_RELIC_ICON_SZ: int = 36   # sprite size inside the 48×48 box (6 px inset each side)
PILE_W: int = 108
PILE_H: int = 88
_PILE_W, _PILE_H = PILE_W, PILE_H     # old names


# ---------------------------------------------------------------------------
# Relics bar (top of screen)
# ---------------------------------------------------------------------------

def draw_relics(
    surface: pygame.Surface,
    relics: list[Relic],
    x: int,
    y: int,
    fonts: FontRegistry,
    *,
    hovered_index: int | None = None,
    sprites: SpriteLoader | None = None,
) -> list[pygame.Rect]:
    """Draw the relic slots (iron frames, rarity-coloured rim) and return each relic's Rect."""
    rects: list[pygame.Rect] = []
    for i, relic in enumerate(relics):
        rect = pygame.Rect(x, y, RELIC_SZ, RELIC_SZ)
        rects.append(rect)
        hovered = i == hovered_index
        shown = rect.move(0, -2) if hovered else rect
        frame = kit_slice("panel", RELIC_SZ, RELIC_SZ)
        if frame is not None:
            surface.blit(frame, shown.topleft)
        else:
            pygame.draw.rect(surface, colors.RELIC_BG, shown, border_radius=6)
        rim = RARITY_COLOR.get(relic.rarity, colors.RELIC_BORDER)
        pygame.draw.rect(surface, colors.TEXT_PRIMARY if hovered else rim, shown.inflate(-6, -6), 1,
                         border_radius=3)

        icon = sprites.get_relic_sprite(relic.name, size=_RELIC_ICON_SZ) if sprites else None
        if icon is not None:
            surface.blit(icon, icon.get_rect(center=shown.center))
            if not relic.is_active:                     # dim exhausted relics
                dim = pygame.Surface((RELIC_SZ - 8, RELIC_SZ - 8), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 170))
                surface.blit(dim, shown.inflate(-8, -8).topleft)
        else:
            abbr = outlined(fonts.get(10), relic.name[:5], colors.TEXT_ACCENT)
            surface.blit(abbr, abbr.get_rect(centerx=shown.centerx, centery=shown.centery - 4))
            sub = outlined(fonts.get(8), relic.name[5:10], colors.TEXT_SECONDARY)
            surface.blit(sub, sub.get_rect(centerx=shown.centerx, centery=shown.centery + 8))

        if relic.chroma is not None:
            chroma_fx.draw_chroma_box(surface, shown, relic.chroma, chroma_fx.now(), radius=6)
        x += RELIC_SZ + _RELIC_GAP
    return rects


# ---------------------------------------------------------------------------
# Mana orb (bottom-left)
# ---------------------------------------------------------------------------

def draw_mana(
    surface: pygame.Surface,
    mana: Mana,
    cx: int,
    cy: int,
    fonts: FontRegistry,
    orb: ManaOrb | None = None,
) -> pygame.Rect:
    """The animated mana orb (``orb`` keeps its effects between frames; a still one otherwise)."""
    if orb is None:
        orb = ManaOrb()
        orb.update(0.0, mana)
    return orb.draw(surface, (cx, cy), fonts, mana)


# ---------------------------------------------------------------------------
# Card piles (draw + discard)
# ---------------------------------------------------------------------------

def draw_pile_widget(
    surface: pygame.Surface,
    pile_type: str,   # "ROBO" or "DESCARTE"
    count: int,
    x: int,
    y: int,
    fonts: FontRegistry,
    *,
    hovered: bool = False,
    t: float = 0.0,
) -> pygame.Rect:
    """A stack of card backs (blue = draw, red = discard) with the count and the pile's name."""
    rect = pygame.Rect(x, y, PILE_W, PILE_H)
    lift = -3 if hovered else 0
    draw = pile_type == "ROBO"
    sprite = kit_piece("pile_empty" if count == 0 else "pile_draw" if draw else "pile_discard")
    if sprite is not None:
        pos = sprite.get_rect(midtop=(rect.centerx, rect.y + lift))
        if hovered:                                     # lit up while the pointer is on it
            sprite = sprite.copy()
            sprite.fill((40, 34, 20, 0), special_flags=pygame.BLEND_RGBA_ADD)
        surface.blit(sprite, pos)
        badge_c = (pos.right - 8, pos.bottom - 10)
    else:
        bg = pygame.Color(25, 30, 45) if draw else pygame.Color(35, 20, 20)
        pygame.draw.rect(surface, bg, rect, border_radius=5)
        badge_c = (rect.right - 14, rect.bottom - 16)
    ring = (90, 140, 230) if draw else (220, 90, 80)
    pygame.draw.circle(surface, (12, 8, 16), badge_c, 17)
    pygame.draw.circle(surface, ring, badge_c, 17, 2)
    num = outlined(fonts.get(19), str(count), (255, 255, 255))
    surface.blit(num, num.get_rect(center=badge_c))
    label = outlined(fonts.get(12), pile_type.title() if not hovered else f"{pile_type.title()} · Ver",
                     (230, 220, 200))
    surface.blit(label, label.get_rect(midtop=(rect.centerx - 10, rect.bottom - 6)))
    return rect


# ---------------------------------------------------------------------------
# End turn button
# ---------------------------------------------------------------------------

def draw_end_turn_button(
    surface: pygame.Surface,
    x: int,
    y: int,
    w: int,
    h: int,
    fonts: FontRegistry,
    *,
    hovered: bool = False,
    pressed: bool = False,
    enabled: bool = True,
    ready: bool = False,
    t: float = 0.0,
) -> pygame.Rect:
    """Big gold button with an hourglass and the E key.

    ``ready`` (nothing left to play) makes it pulse; ``enabled=False`` greys it out
    as "Turno enemigo" while the enemies act.
    """
    rect = pygame.Rect(x, y, w, h)
    state = "off" if not enabled else ("press" if pressed and hovered else "hover" if hovered else "idle")
    glow = (0.55 + 0.45 * math.sin(t * 5.0)) if ready and enabled else 0.0
    draw_button(surface, rect, "TERMINAR TURNO" if enabled else "TURNO ENEMIGO", fonts,
                style="gold", state=state, icon="hourglass", key="E" if enabled else None,
                t=t, glow=glow, size=14)
    return rect


# ---------------------------------------------------------------------------
# Turn counter
# ---------------------------------------------------------------------------

def draw_turn_counter(
    surface: pygame.Surface,
    turn: int,
    cx: int,
    cy: int,
    fonts: FontRegistry,
) -> pygame.Rect:
    return draw_ribbon(surface, (cx, cy), f"TURNO {turn}", fonts, size=16)
