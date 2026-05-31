from __future__ import annotations

import pygame

from src.domain.card import Card, CardRarity, CardType, ModifierTag
from src.domain.numbers import BigValue
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader

# ---------------------------------------------------------------------------
# Card dimensions  (maintained at ~0.72 aspect ratio matching the frame art)
# ---------------------------------------------------------------------------

CARD_W: int = 90
CARD_H: int = 124

# Layer Y positions within the card (all in card-local coordinates)
_MANA_Y:  int = 0    # minion(7) top decoration
_MANA_H:  int = 27
_TITLE_Y: int = 24   # minion(6) title decoration  (slight overlap with mana)
_TITLE_H: int = 22
_DESC_Y:  int = 78   # minion(2) description box
_DESC_H:  int = 28
_STAT_Y:  int = 106  # minion(8) ATK/DEF hexagons
_STAT_H:  int = 18
_GEM_SZ:  int = 14   # rarity gem size

# Text centre-Y positions
_MANA_CY:  int = _MANA_Y  + _MANA_H  // 2
_TITLE_CY: int = _TITLE_Y + _TITLE_H // 2
_DESC_CY:  int = _DESC_Y  + _DESC_H  // 2
_ATK_CX:   int = CARD_W // 4           # red (left) hexagon centre-x
_DEF_CX:   int = CARD_W * 3 // 4      # green (right) hexagon centre-x
_STAT_CY:  int = _STAT_Y  + _STAT_H  // 2

# Fallback border palette (used when frame sprites are absent)
_CORNER: int = 5

# ---------------------------------------------------------------------------
# Lazy module-level sprite loader
# ---------------------------------------------------------------------------

_sprites: SpriteLoader | None = None


def _sp() -> SpriteLoader:
    global _sprites
    if _sprites is None:
        _sprites = SpriteLoader()
    return _sprites


# ---------------------------------------------------------------------------
# Rarity colours (fallback dots / tints)
# ---------------------------------------------------------------------------

_RARITY_COLOR: dict[CardRarity, pygame.Color] = {
    CardRarity.COMMON:    pygame.Color(160, 160, 160),
    CardRarity.UNCOMMON:  pygame.Color(60,  180, 80),
    CardRarity.RARE:      pygame.Color(60,  120, 220),
    CardRarity.EPIC:      pygame.Color(160, 60,  220),
    CardRarity.LEGENDARY: pygame.Color(230, 160, 20),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _type_fallback_palette(card_type: CardType) -> tuple[pygame.Color, pygame.Color]:
    match card_type:
        case CardType.ATTACK: return colors.CARD_ATTACK,  colors.CARD_ATTACK_DARK
        case CardType.SKILL:  return colors.CARD_SKILL,   colors.CARD_SKILL_DARK
        case CardType.POWER:  return colors.CARD_POWER,   colors.CARD_POWER_DARK


def _effect_line(card: Card) -> str:
    """Short description shown in the description box."""
    total_draw = sum(fx.draw for fx in card.all_effects())
    parts: list[str] = []
    if total_draw > 0:
        parts.append(f"Roba {total_draw}")
    if card.card_type == CardType.POWER:
        parts.append("Poder")
    return "  ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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
    """Draw a card using layered sprites and return its bounding Rect."""
    lift = -20 if (selected or hovered) else 0
    rect = pygame.Rect(x, y + lift, CARD_W, CARD_H)
    sp   = _sp()

    # ------------------------------------------------------------------
    # Layer 1: card frame (Alternate 1/2/3 by CardType)
    # ------------------------------------------------------------------
    frame = sp.get_card_frame(card.card_type.name, CARD_W, CARD_H)
    if frame is not None:
        if not affordable:
            dim = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            dim.blit(frame, (0, 0))
            dark = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 120))
            dim.blit(dark, (0, 0))
            surface.blit(dim, rect.topleft)
        else:
            surface.blit(frame, rect.topleft)
    else:
        # Fallback coloured rectangle
        body_col, dark_col = _type_fallback_palette(card.card_type)
        if not affordable:
            dark_col = pygame.Color(dark_col.r // 2, dark_col.g // 2, dark_col.b // 2)
        pygame.draw.rect(surface, dark_col, rect, border_radius=_CORNER)
        border_col = colors.CARD_SELECTED if selected else (
            colors.CARD_HOVER if hovered else colors.CARD_BORDER
        )
        pygame.draw.rect(surface, border_col, rect, 1, border_radius=_CORNER)

    # ------------------------------------------------------------------
    # Layer 2: mana top decoration  (minion 7)
    # ------------------------------------------------------------------
    mana_surf = sp.get_card_component("mana", CARD_W, _MANA_H)
    if mana_surf is not None:
        surface.blit(mana_surf, (rect.x, rect.y + _MANA_Y))

    # ------------------------------------------------------------------
    # Layer 3: title decoration  (minion 6)
    # ------------------------------------------------------------------
    title_surf = sp.get_card_component("title", CARD_W, _TITLE_H)
    if title_surf is not None:
        surface.blit(title_surf, (rect.x, rect.y + _TITLE_Y))

    # ------------------------------------------------------------------
    # Layer 4: description box  (minion 2)
    # ------------------------------------------------------------------
    desc_surf = sp.get_card_component("description", CARD_W, _DESC_H)
    if desc_surf is not None:
        surface.blit(desc_surf, (rect.x, rect.y + _DESC_Y))

    # ------------------------------------------------------------------
    # Layer 5: stat hexagons  (minion 8 — full width, red left | green right)
    # ------------------------------------------------------------------
    stats_surf = sp.get_card_component("stats", CARD_W, _STAT_H)
    if stats_surf is not None:
        surface.blit(stats_surf, (rect.x, rect.y + _STAT_Y))

    # ------------------------------------------------------------------
    # Text overlays
    # ------------------------------------------------------------------
    # Mana cost
    mana_font = fonts.get(13)
    mana_col  = colors.TEXT_PRIMARY if affordable else pygame.Color(160, 30, 30)
    mana_s    = mana_font.render(str(card.cost), True, mana_col)
    surface.blit(mana_s, mana_s.get_rect(centerx=rect.centerx, centery=rect.y + _MANA_CY))

    # Card name
    name_font = fonts.get(8)
    name_col  = colors.TEXT_PRIMARY if affordable else pygame.Color(100, 100, 100)
    short     = card.name[:10]
    name_s    = name_font.render(short, True, name_col)
    surface.blit(name_s, name_s.get_rect(centerx=rect.centerx, centery=rect.y + _TITLE_CY))

    # Effect description (draw, power)
    eff_line = _effect_line(card)
    if eff_line:
        eff_font = fonts.get(7)
        eff_s    = eff_font.render(eff_line, True, colors.TEXT_SECONDARY)
        surface.blit(eff_s, eff_s.get_rect(centerx=rect.centerx, centery=rect.y + _DESC_CY))

    # ATK value on left (red) hexagon
    dmg = card.total_damage()
    atk_font = fonts.get(11)
    if dmg > 0:
        atk_val = BigValue.format_int(dmg + bonus_damage)
        atk_col = colors.TEXT_DAMAGE
    else:
        atk_val = "—"
        atk_col = pygame.Color(90, 60, 60)
    atk_s = atk_font.render(atk_val, True, atk_col)
    surface.blit(atk_s, atk_s.get_rect(centerx=rect.x + _ATK_CX, centery=rect.y + _STAT_CY))

    # DEF value on right (green) hexagon
    blk = card.total_block()
    if blk > 0:
        def_val = BigValue.format_int(blk + bonus_block)
        def_col = colors.TEXT_BLOCK
    else:
        def_val = "—"
        def_col = pygame.Color(60, 90, 60)
    def_s = atk_font.render(def_val, True, def_col)
    surface.blit(def_s, def_s.get_rect(centerx=rect.x + _DEF_CX, centery=rect.y + _STAT_CY))

    # ------------------------------------------------------------------
    # Layer 6: rarity gem (bottom-right of description box)
    # ------------------------------------------------------------------
    gem = sp.get_rarity_badge(card.rarity.name, size=_GEM_SZ)
    if gem is not None:
        surface.blit(gem, (rect.right - _GEM_SZ - 2, rect.y + _DESC_Y + 1))
    else:
        gem_col = _RARITY_COLOR.get(card.rarity, colors.TEXT_SECONDARY)
        pygame.draw.circle(surface, gem_col, (rect.right - 6, rect.y + _DESC_Y + 6), 4)

    # ------------------------------------------------------------------
    # Broken diagonal stripe
    # ------------------------------------------------------------------
    if card.is_broken:
        pygame.draw.line(surface, colors.CARD_BROKEN,
                         rect.topleft, rect.bottomright, 1)

    # Selection / hover highlight border
    if selected or hovered:
        border_col = colors.CARD_SELECTED if selected else colors.CARD_HOVER
        pygame.draw.rect(surface, border_col, rect, 2, border_radius=_CORNER)

    return rect
