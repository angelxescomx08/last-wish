from __future__ import annotations

import pygame

from src.domain.mana import Mana
from src.domain.pile import DiscardPile, DrawPile
from src.domain.relic import Relic
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader

RELIC_SZ: int       = 48
_RELIC_GAP: int     = 5
_RELIC_ICON_SZ: int = 36   # sprite size inside the 48×48 box (6 px inset each side)
_PILE_W: int = 56
_PILE_H: int = 76


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
    """Draw the relic bar and return each relic's bounding Rect."""
    rects: list[pygame.Rect] = []
    for i, relic in enumerate(relics):
        rect = pygame.Rect(x, y, RELIC_SZ, RELIC_SZ)
        rects.append(rect)

        hovered = i == hovered_index
        bg      = colors.TEXT_ACCENT if hovered else colors.RELIC_BG
        border  = colors.TEXT_PRIMARY if hovered else colors.RELIC_BORDER
        pygame.draw.rect(surface, bg, rect, border_radius=6)
        pygame.draw.rect(surface, border, rect, 2 if hovered else 1, border_radius=6)

        icon = sprites.get_relic_sprite(relic.name, size=_RELIC_ICON_SZ) if sprites else None

        if icon is not None:
            surface.blit(icon, icon.get_rect(center=rect.center))
            # Dim exhausted relics with a translucent overlay
            if not relic.is_active:
                dim = pygame.Surface((RELIC_SZ, RELIC_SZ), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 170))
                surface.blit(dim, rect.topleft)
        else:
            # Fallback: text abbreviation when no sprite available
            abbr_col  = colors.BG_DARK if hovered else colors.TEXT_ACCENT
            abbr_surf = fonts.get(10).render(relic.name[:5], True, abbr_col)
            surface.blit(abbr_surf, abbr_surf.get_rect(centerx=rect.centerx, centery=rect.centery - 4))

            sub_col  = colors.BG_DARK if hovered else colors.TEXT_SECONDARY
            sub_surf = fonts.get(7).render(relic.name[5:10], True, sub_col)
            surface.blit(sub_surf, sub_surf.get_rect(centerx=rect.centerx, centery=rect.centery + 9))

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
) -> None:
    radius = 40
    # Outer ring segments to show current / max visually
    for i in range(mana.maximum):
        filled = i < mana.current
        seg_col = colors.MANA_FILL if filled else colors.MANA_EMPTY
        seg_rect = pygame.Rect(cx - radius + 2 + i * (radius * 2 - 4) // mana.maximum,
                               cy - radius + 2,
                               (radius * 2 - 4) // mana.maximum - 2,
                               6)
        pygame.draw.rect(surface, seg_col, seg_rect, border_radius=3)

    pygame.draw.circle(surface, colors.MANA_EMPTY, (cx, cy), radius)
    pygame.draw.circle(surface, colors.MANA_ORB_RING, (cx, cy), radius, 2)

    value_font = fonts.get(28)
    value_surf = value_font.render(str(mana.current), True, colors.MANA_TEXT)
    surface.blit(value_surf, value_surf.get_rect(centerx=cx, centery=cy - 4))

    label_font = fonts.get(9)
    label_surf = label_font.render(f"/{mana.maximum} MANÁ", True, colors.TEXT_SECONDARY)
    surface.blit(label_surf, label_surf.get_rect(centerx=cx, centery=cy + 18))


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
) -> pygame.Rect:
    rect = pygame.Rect(x, y, _PILE_W, _PILE_H)
    bg   = pygame.Color(25, 30, 45) if pile_type == "ROBO" else pygame.Color(35, 20, 20)
    border = pygame.Color(60, 80, 120) if pile_type == "ROBO" else pygame.Color(100, 50, 50)

    pygame.draw.rect(surface, bg, rect, border_radius=5)
    pygame.draw.rect(surface, border, rect, 1, border_radius=5)

    count_font = fonts.get(22)
    count_surf = count_font.render(str(count), True, colors.TEXT_PRIMARY)
    surface.blit(count_surf, count_surf.get_rect(centerx=rect.centerx, centery=rect.centery - 5))

    label_font = fonts.get(8)
    label_surf = label_font.render(pile_type, True, colors.TEXT_SECONDARY)
    surface.blit(label_surf, label_surf.get_rect(centerx=rect.centerx, bottom=rect.bottom - 3))

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
) -> pygame.Rect:
    rect = pygame.Rect(x, y, w, h)
    bg   = colors.END_TURN_HOVER if hovered else colors.END_TURN_BG
    pygame.draw.rect(surface, bg, rect, border_radius=6)
    pygame.draw.rect(surface, colors.TEXT_ACCENT, rect, 1, border_radius=6)

    btn_font = fonts.get(16)
    btn_surf = btn_font.render("TERMINAR TURNO", True, colors.END_TURN_TEXT)
    surface.blit(btn_surf, btn_surf.get_rect(center=rect.center))

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
) -> None:
    turn_font = fonts.get(14)
    turn_surf = turn_font.render(f"TURNO  {turn}", True, colors.TEXT_SECONDARY)
    surface.blit(turn_surf, turn_surf.get_rect(centerx=cx, centery=cy))
