"""Card widget — layered sprite card renderer.

Layer order (back to front):
  1. Card frame          Alternate (1/2/3) — full background by card type
  2. Portrait tint       coloured ellipse matching card type
  3. Portrait frame      minion (4) — oval border, transparent centre
  4. Name banner         minion (6) — ribbon overlapping portrait top
  5. Mana gem            minion (7) — protrudes above card top
  6. Ability box         minion (2) — skill plate below portrait
  7. Rarity gem          _Rarity/rarity (N) — centred, straddles portrait and ability
  8. Stat hexagons       minion (8) — red=ATK left, green=DEF right
  9. Text overlays       mana cost, name (truncated), ability lines, ATK, DEF
"""
from __future__ import annotations

import pygame

from src.domain.card import Card, CardRarity, CardType
from src.domain.numbers import BigValue
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader

# ---------------------------------------------------------------------------
# Card dimensions  — large enough for all text to be legible
# ---------------------------------------------------------------------------

CARD_W: int = 140
CARD_H: int = 194

# Mana gem protrudes this many pixels above card rect top
_MANA_OVERHANG: int = 20

# ---------------------------------------------------------------------------
# Layer geometry  (y in card-local coordinates, origin = card rect top-left)
# Follows the ~40-45% portrait distribution requested.
# ---------------------------------------------------------------------------

_BANNER_Y: int   = 0
_BANNER_H: int   = 22          # 11% of card

_PORTRAIT_Y: int = 22
_PORTRAIT_H: int = 84          # 43% of card — dominant element
_PORTRAIT_W: int = 118         # 84% of card width (11 px margin each side)

# Rarity gem straddles portrait bottom and ability top
_GEM_SZ: int    = 24
_GEM_Y: int     = _PORTRAIT_Y + _PORTRAIT_H - 8    # overlaps portrait 8 px

# Ability box tight under gem
_ABILITY_Y: int = _GEM_Y + _GEM_SZ - 8             # overlaps gem 8 px
_ABILITY_H: int = 52           # 27% of card — tall enough for 3 text lines

# Stats hexagons: bottom-anchored, no type plate between them
_STATS_H: int   = 28
_STATS_Y: int   = CARD_H - _STATS_H               # = 166

# Horizontal centres for ATK / DEF inside the hexagon sprite
_ATK_CX: int = 22              # near left edge (inside red hex)
_DEF_CX: int = 118             # near right edge (inside green hex)

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
# Palette
# ---------------------------------------------------------------------------

_RARITY_COLOR: dict[CardRarity, pygame.Color] = {
    CardRarity.COMMON:    pygame.Color(160, 160, 160),
    CardRarity.UNCOMMON:  pygame.Color(60,  180, 80),
    CardRarity.RARE:      pygame.Color(60,  120, 220),
    CardRarity.EPIC:      pygame.Color(160, 60,  220),
    CardRarity.LEGENDARY: pygame.Color(230, 160, 20),
}

_TYPE_TINT: dict[CardType, pygame.Color] = {
    CardType.ATTACK: pygame.Color(140, 35,  35),
    CardType.SKILL:  pygame.Color(30,  80,  170),
    CardType.POWER:  pygame.Color(90,  30,  150),
}

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _fit(text: str, font: pygame.font.Font, max_w: int) -> str:
    """Truncate text with '…' so it fits within max_w pixels."""
    if font.size(text)[0] <= max_w:
        return text
    while len(text) > 1 and font.size(text + "…")[0] > max_w:
        text = text[:-1]
    return text + "…"


def _ability_lines(card: Card) -> list[str]:
    """Up to 3 lines describing the card's active effects."""
    lines: list[str] = []
    draw  = sum(fx.draw for fx in card.all_effects())
    mana  = sum(fx.mana_gain for fx in card.all_effects())

    if card.card_type == CardType.ATTACK and card.total_damage() > 0:
        lines.append("Inflige daño al enemigo")
    if card.total_block() > 0:
        lines.append("Gana escudo")
    if draw > 0:
        lines.append(f"Roba {draw} carta{'s' if draw > 1 else ''}")
    if mana > 0:
        lines.append(f"+{mana} maná")
    if card.card_type == CardType.POWER:
        lines.append("Poder permanente")
    return lines[:3]


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
    """Draw a layered sprite card and return its bounding Rect."""
    lift = -20 if (selected or hovered) else 0
    rect = pygame.Rect(x, y + lift, CARD_W, CARD_H)
    sp   = _sp()
    rx, ry = rect.x, rect.y

    # Portrait centred x
    px = rx + (CARD_W - _PORTRAIT_W) // 2

    # Optional dim overlay for unaffordable cards
    dim_alpha = 110 if not affordable else 0

    def _blit(surf: pygame.Surface | None, bx: int, by: int) -> None:
        if surf is None:
            return
        if dim_alpha:
            s    = surf.copy()
            dark = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            dark.fill((0, 0, 0, dim_alpha))
            s.blit(dark, (0, 0))
            surface.blit(s, (bx, by))
        else:
            surface.blit(surf, (bx, by))

    # ------------------------------------------------------------------
    # 1. Card frame  (Alternate 1/2/3)
    # ------------------------------------------------------------------
    frame = sp.get_card_frame(card.card_type.name, CARD_W, CARD_H)
    _blit(frame, rx, ry)
    if frame is None:
        tint = _TYPE_TINT.get(card.card_type, colors.BG_PANEL)
        pygame.draw.rect(surface, tint, rect, border_radius=8)
        pygame.draw.rect(surface, colors.CARD_BORDER, rect, 1, border_radius=8)

    # ------------------------------------------------------------------
    # 2. Portrait tint  (coloured ellipse inside oval frame)
    # ------------------------------------------------------------------
    tint_col  = _TYPE_TINT.get(card.card_type, colors.BG_PANEL)
    inset     = 8
    tint_rect = pygame.Rect(px + inset, ry + _PORTRAIT_Y + inset,
                            _PORTRAIT_W - inset * 2, _PORTRAIT_H - inset * 2)
    pygame.draw.ellipse(surface, tint_col, tint_rect)

    # ------------------------------------------------------------------
    # 3. Portrait oval frame  (minion 4, transparent centre)
    # ------------------------------------------------------------------
    portrait_frame = sp.get_card_component("portrait", _PORTRAIT_W, _PORTRAIT_H)
    _blit(portrait_frame, px, ry + _PORTRAIT_Y)

    # ------------------------------------------------------------------
    # 4. Name banner  (minion 6, full width)
    # ------------------------------------------------------------------
    banner = sp.get_card_component("banner", CARD_W, _BANNER_H)
    _blit(banner, rx, ry + _BANNER_Y)

    # ------------------------------------------------------------------
    # 5. Mana gem  (minion 7, protrudes above card top)
    # ------------------------------------------------------------------
    mana_w, mana_h = 52, 26
    mana_surf = sp.get_card_component("mana", mana_w, mana_h)
    mana_bx   = rx + (CARD_W - mana_w) // 2
    mana_by   = ry - _MANA_OVERHANG - mana_h // 2
    _blit(mana_surf, mana_bx, mana_by)

    # ------------------------------------------------------------------
    # 6. Ability box  (minion 2, full width)
    # ------------------------------------------------------------------
    ability = sp.get_card_component("ability", CARD_W, _ABILITY_H)
    _blit(ability, rx, ry + _ABILITY_Y)

    # ------------------------------------------------------------------
    # 7. Rarity gem  (centred, straddles portrait/ability boundary)
    # ------------------------------------------------------------------
    gem    = sp.get_rarity_badge(card.rarity.name, size=_GEM_SZ)
    gem_bx = rx + (CARD_W - _GEM_SZ) // 2
    gem_by = ry + _GEM_Y
    _blit(gem, gem_bx, gem_by)
    if gem is None:
        gem_col = _RARITY_COLOR.get(card.rarity, colors.TEXT_SECONDARY)
        pygame.draw.circle(surface, gem_col,
                           (rx + CARD_W // 2, ry + _GEM_Y + _GEM_SZ // 2), 8)

    # ------------------------------------------------------------------
    # 8. Stat hexagons  (minion 8, full width, no plate between them)
    # ------------------------------------------------------------------
    stats_surf = sp.get_card_component("stats", CARD_W, _STATS_H)
    _blit(stats_surf, rx, ry + _STATS_Y)

    # ------------------------------------------------------------------
    # 9. Text overlays
    # ------------------------------------------------------------------
    stat_cy = ry + _STATS_Y + _STATS_H // 2

    # — Mana cost (always visible, never truncated)
    mana_col = colors.TEXT_PRIMARY if affordable else pygame.Color(220, 60, 60)
    mc = fonts.get(17).render(str(card.cost), True, mana_col)
    surface.blit(mc, mc.get_rect(centerx=rx + CARD_W // 2,
                                  centery=mana_by + mana_h // 2))

    # — Card name (truncated with … if needed)
    name_col  = colors.TEXT_PRIMARY if affordable else pygame.Color(110, 110, 110)
    name_font = fonts.get(10)
    max_name  = CARD_W - 26               # leave room for mana orb on the left
    name_s    = name_font.render(_fit(card.name, name_font, max_name), True, name_col)
    surface.blit(name_s, name_s.get_rect(centerx=rx + CARD_W // 2,
                                          centery=ry + _BANNER_Y + _BANNER_H // 2))

    # — Ability lines (up to 3 lines inside ability box)
    lines = _ability_lines(card)
    if lines:
        eff_font  = fonts.get(9)
        max_text  = CARD_W - 14
        line_h    = eff_font.size("A")[1] + 2
        total_h   = len(lines) * line_h
        start_y   = ry + _ABILITY_Y + (_ABILITY_H - total_h) // 2
        for i, line in enumerate(lines):
            eff_s = eff_font.render(_fit(line, eff_font, max_text), True, colors.TEXT_SECONDARY)
            surface.blit(eff_s, eff_s.get_rect(centerx=rx + CARD_W // 2,
                                                 centery=start_y + i * line_h + line_h // 2))

    # — ATK  (left red hexagon, NEVER hidden or truncated)
    dmg     = card.total_damage()
    atk_val = BigValue.format_int(dmg + bonus_damage) if dmg > 0 else "—"
    atk_col = colors.TEXT_DAMAGE if dmg > 0 else pygame.Color(100, 60, 60)
    ats     = fonts.get(13).render(atk_val, True, atk_col)
    surface.blit(ats, ats.get_rect(centerx=rx + _ATK_CX, centery=stat_cy))

    # — DEF  (right green hexagon, NEVER hidden or truncated)
    blk     = card.total_block()
    def_val = BigValue.format_int(blk + bonus_block) if blk > 0 else "—"
    def_col = colors.TEXT_BLOCK if blk > 0 else pygame.Color(60, 100, 60)
    dfs     = fonts.get(13).render(def_val, True, def_col)
    surface.blit(dfs, dfs.get_rect(centerx=rx + _DEF_CX, centery=stat_cy))

    # ------------------------------------------------------------------
    # Selection / hover border  (drawn last so it's always on top)
    # ------------------------------------------------------------------
    if selected:
        pygame.draw.rect(surface, colors.CARD_SELECTED, rect, 2, border_radius=6)
    elif hovered:
        pygame.draw.rect(surface, colors.CARD_HOVER, rect, 2, border_radius=6)

    if card.is_broken:
        pygame.draw.line(surface, colors.CARD_BROKEN, rect.topleft, rect.bottomright, 1)

    return rect
