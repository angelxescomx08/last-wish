from __future__ import annotations

import pygame

from src.domain.card import Card, CardType, ModifierTag
from src.domain.numbers import BigValue
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

CARD_W: int = 70
CARD_H: int = 100
_COST_R: int = 11
_HEADER_H: int = 20
_CORNER: int = 5

_TYPE_LABEL: dict[CardType, str] = {
    CardType.ATTACK: "ATK",
    CardType.SKILL:  "HAB",
    CardType.POWER:  "POD",
}

_MOD_COLORS: dict[ModifierTag, pygame.Color] = {
    ModifierTag.CHROMA:      pygame.Color(255, 100, 50),
    ModifierTag.TRANSPARENT: pygame.Color(150, 200, 255),
    ModifierTag.ETHEREAL:    pygame.Color(180, 130, 255),
    ModifierTag.ECHO:        pygame.Color(80,  230, 180),
}


def _type_palette(card_type: CardType) -> tuple[pygame.Color, pygame.Color]:
    match card_type:
        case CardType.ATTACK: return colors.CARD_ATTACK,  colors.CARD_ATTACK_DARK
        case CardType.SKILL:  return colors.CARD_SKILL,   colors.CARD_SKILL_DARK
        case CardType.POWER:  return colors.CARD_POWER,   colors.CARD_POWER_DARK


def draw_card(
    surface: pygame.Surface,
    card: Card,
    x: int,
    y: int,
    fonts: FontRegistry,
    *,
    selected: bool = False,
    hovered: bool = False,
    affordable: bool = True,
    bonus_damage: int = 0,
    bonus_block: int = 0,
) -> pygame.Rect:
    """Draw a card rectangle and return its bounding Rect."""
    lift = -20 if (selected or hovered) else 0
    rect = pygame.Rect(x, y + lift, CARD_W, CARD_H)

    body_col, dark_col = _type_palette(card.card_type)
    if card.is_broken:
        body_col, dark_col = colors.CARD_BROKEN, colors.CARD_BROKEN_DARK

    # Dim unaffordable cards
    if not affordable:
        r, g, b = dark_col.r // 2, dark_col.g // 2, dark_col.b // 2
        dark_col = pygame.Color(r, g, b)
        r2, g2, b2 = body_col.r // 2, body_col.g // 2, body_col.b // 2
        body_col = pygame.Color(r2, g2, b2)

    border_col   = colors.CARD_SELECTED if selected else (colors.CARD_HOVER if hovered else colors.CARD_BORDER)
    border_width = 2 if (selected or card.is_broken) else 1

    # Card body
    pygame.draw.rect(surface, dark_col, rect, border_radius=_CORNER)
    pygame.draw.rect(surface, border_col, rect, border_width, border_radius=_CORNER)

    # Header strip
    header = pygame.Rect(rect.x + 1, rect.y + 1, CARD_W - 2, _HEADER_H)
    pygame.draw.rect(surface, body_col, header,
                     border_top_left_radius=_CORNER, border_top_right_radius=_CORNER)

    # Card name (truncated, shifted right of cost orb)
    name_font = fonts.get(9)
    short_name = card.name[:8]
    name_surf = name_font.render(short_name, True, colors.TEXT_PRIMARY)
    surface.blit(name_surf, name_surf.get_rect(centerx=rect.x + CARD_W // 2 + 7,
                                               centery=rect.y + _HEADER_H // 2))

    # Central value: damage or block (damage shows the final effective value)
    val_font  = fonts.get(22)
    dmg = card.total_damage()
    blk = card.total_block()
    if dmg > 0:
        effective = dmg + bonus_damage
        v_surf = val_font.render(BigValue.format_int(effective), True, colors.TEXT_DAMAGE)
        surface.blit(v_surf, v_surf.get_rect(centerx=rect.centerx, centery=rect.centery + 8))
    elif blk > 0:
        effective_blk = blk + bonus_block
        v_surf = val_font.render(BigValue.format_int(effective_blk), True, colors.TEXT_BLOCK)
        surface.blit(v_surf, v_surf.get_rect(centerx=rect.centerx, centery=rect.centery + 8))

    # Card type label (bottom-right)
    type_font = fonts.get(8)
    type_surf = type_font.render(_TYPE_LABEL[card.card_type], True, colors.TEXT_SECONDARY)
    surface.blit(type_surf, (rect.right - type_surf.get_width() - 3, rect.bottom - 12))

    # Stacked effects badge (bottom-left)
    if card.effect_count() > 0:
        fx_font = fonts.get(8)
        fx_surf = fx_font.render(f"+{card.effect_count()}fx", True, colors.TEXT_ACCENT)
        surface.blit(fx_surf, (rect.x + 3, rect.bottom - 12))

    # Modifier dots (above type label)
    dot_x = rect.x + 4
    for mod in card.modifiers:
        dot_col = _MOD_COLORS.get(mod.tag, colors.TEXT_ACCENT)
        pygame.draw.circle(surface, dot_col, (dot_x, rect.bottom - 18), 3)
        dot_x += 8

    # Broken diagonal stripe
    if card.is_broken:
        pygame.draw.line(surface, colors.CARD_BROKEN,
                         (rect.x + 4, rect.y + 26), (rect.right - 4, rect.bottom - 14), 1)

    # Cost orb (top-left, over header) — red when unaffordable
    orb = (rect.x + _COST_R, rect.y + _COST_R)
    orb_fill = colors.MANA_FILL if affordable else pygame.Color(160, 30, 30)
    orb_ring = colors.MANA_ORB_RING if affordable else pygame.Color(220, 60, 60)
    pygame.draw.circle(surface, orb_fill, orb, _COST_R)
    pygame.draw.circle(surface, orb_ring, orb, _COST_R, 1)
    cost_font = fonts.get(13)
    cost_surf = cost_font.render(str(card.cost), True, colors.TEXT_PRIMARY)
    surface.blit(cost_surf, cost_surf.get_rect(center=orb))

    return rect
