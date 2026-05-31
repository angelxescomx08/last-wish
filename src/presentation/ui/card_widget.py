"""Card widget — layered sprite card renderer.

Layer order (back to front):
  1. Card frame          Alternate (1/2/3) — full background by card type
  2. Portrait tint       coloured oval matching card type
  3. Portrait frame      minion (4) — oval border, transparent centre
  4. Name banner         minion (6) — ribbon overlapping portrait top
  5. Mana gem            minion (7) — protrudes above card top
  6. Ability box         minion (2) — skill plate below portrait
  7. Rarity gem          _Rarity/rarity (N) — centred below portrait
  8. Stat hexagons       minion (8) — red=ATK left, green=DEF right
  9. Type plate          minion (3) — centred between hexagons
 10. Text overlays       mana cost, name, effect, ATK, DEF, type label
"""
from __future__ import annotations

import pygame

from src.domain.card import Card, CardRarity, CardType
from src.domain.numbers import BigValue
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.sprite_loader import SpriteLoader

# ---------------------------------------------------------------------------
# Card dimensions  (ratio 0.676 ≈ portrait card)
# ---------------------------------------------------------------------------

CARD_W: int = 100
CARD_H: int = 148

# Mana gem: protrudes this many pixels above the card rect top
_MANA_OVERHANG: int = 14

# Layer geometry (y in card-local coordinates, origin = card rect top-left)
_BANNER_Y: int   = 2     # name ribbon top
_BANNER_H: int   = 22    # name ribbon height

_PORTRAIT_Y: int = 18    # oval frame top (overlaps banner bottom)
_PORTRAIT_H: int = 58    # oval frame height → ~40% of card
_PORTRAIT_W: int = 55    # oval frame width  (maintains 0.95 ratio)
_PORTRAIT_X: int = (_PORTRAIT_W // 2) * 0  # centred, see _px below

_GEM_SZ: int     = 16    # rarity gem size
_GEM_Y: int      = _PORTRAIT_Y + _PORTRAIT_H + 4   # below oval

_ABILITY_Y: int  = _GEM_Y + _GEM_SZ + 4            # ability box top
_ABILITY_H: int  = 34    # ability box height

_STATS_Y: int    = _ABILITY_Y + _ABILITY_H + 2      # hexagons top
_STATS_H: int    = 20    # hexagons height (fills to CARD_H)

_TYPE_H: int     = 16    # type-plate height (centred over stats row)

# Horizontal centres for ATK and DEF hexagons
_ATK_CX: int = 20        # left hexagon centre-x
_DEF_CX: int = 80        # right hexagon centre-x

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
# Rarity colours for fallback tints
# ---------------------------------------------------------------------------

_RARITY_COLOR: dict[CardRarity, pygame.Color] = {
    CardRarity.COMMON:    pygame.Color(160, 160, 160),
    CardRarity.UNCOMMON:  pygame.Color(60,  180, 80),
    CardRarity.RARE:      pygame.Color(60,  120, 220),
    CardRarity.EPIC:      pygame.Color(160, 60,  220),
    CardRarity.LEGENDARY: pygame.Color(230, 160, 20),
}

_TYPE_TINT: dict[CardType, pygame.Color] = {
    CardType.ATTACK: pygame.Color(160, 40,  40),
    CardType.SKILL:  pygame.Color(40,  90,  180),
    CardType.POWER:  pygame.Color(100, 40,  160),
}

_TYPE_LABEL: dict[CardType, str] = {
    CardType.ATTACK: "ataque",
    CardType.SKILL:  "habilidad",
    CardType.POWER:  "poder",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _effect_line(card: Card) -> str:
    total_draw = sum(fx.draw for fx in card.all_effects())
    parts: list[str] = []
    if total_draw > 0:
        parts.append(f"Roba {total_draw}")
    if card.card_type == CardType.POWER:
        parts.append("Poder permanente")
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
    """Draw a layered sprite card and return its bounding Rect."""
    lift = -20 if (selected or hovered) else 0
    rect  = pygame.Rect(x, y + lift, CARD_W, CARD_H)
    sp    = _sp()
    rx, ry = rect.x, rect.y   # shortcuts

    # Portrait centred x
    px = rx + (CARD_W - _PORTRAIT_W) // 2

    # Dim factor for unaffordable cards
    dim_alpha = 110 if not affordable else 0

    def _blit(surf: pygame.Surface | None, bx: int, by: int) -> None:
        if surf is None:
            return
        if dim_alpha:
            s = surf.copy()
            dark = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            dark.fill((0, 0, 0, dim_alpha))
            s.blit(dark, (0, 0))
            surface.blit(s, (bx, by))
        else:
            surface.blit(surf, (bx, by))

    # ------------------------------------------------------------------
    # Layer 1: card frame  (Alternate 1/2/3)
    # ------------------------------------------------------------------
    frame = sp.get_card_frame(card.card_type.name, CARD_W, CARD_H)
    _blit(frame, rx, ry)
    if frame is None:
        # Fallback coloured rectangle
        tint = _TYPE_TINT.get(card.card_type, colors.BG_PANEL)
        pygame.draw.rect(surface, tint, rect, border_radius=6)
        pygame.draw.rect(surface, colors.CARD_BORDER, rect, 1, border_radius=6)

    # ------------------------------------------------------------------
    # Layer 2: portrait tint (coloured ellipse inside the oval area)
    # ------------------------------------------------------------------
    tint_col = _TYPE_TINT.get(card.card_type, colors.BG_PANEL)
    tint_rect = pygame.Rect(px + 6, ry + _PORTRAIT_Y + 6,
                            _PORTRAIT_W - 12, _PORTRAIT_H - 12)
    pygame.draw.ellipse(surface, tint_col, tint_rect)

    # ------------------------------------------------------------------
    # Layer 3: portrait oval frame  (minion 4, transparent centre)
    # ------------------------------------------------------------------
    portrait_frame = sp.get_card_component("portrait", _PORTRAIT_W, _PORTRAIT_H)
    _blit(portrait_frame, px, ry + _PORTRAIT_Y)

    # ------------------------------------------------------------------
    # Layer 4: name banner  (minion 6)
    # ------------------------------------------------------------------
    banner = sp.get_card_component("banner", CARD_W, _BANNER_H)
    _blit(banner, rx, ry + _BANNER_Y)

    # ------------------------------------------------------------------
    # Layer 5: mana gem  (minion 7 — protrudes above card top)
    # ------------------------------------------------------------------
    mana_w, mana_h = 44, 22
    mana_surf = sp.get_card_component("mana", mana_w, mana_h)
    mana_bx   = rx + (CARD_W - mana_w) // 2
    mana_by   = ry - _MANA_OVERHANG - mana_h // 2
    _blit(mana_surf, mana_bx, mana_by)

    # ------------------------------------------------------------------
    # Layer 6: ability / skill box  (minion 2)
    # ------------------------------------------------------------------
    ability = sp.get_card_component("ability", CARD_W, _ABILITY_H)
    _blit(ability, rx, ry + _ABILITY_Y)

    # ------------------------------------------------------------------
    # Layer 7: rarity gem  (centred below portrait)
    # ------------------------------------------------------------------
    gem = sp.get_rarity_badge(card.rarity.name, size=_GEM_SZ)
    gem_bx = rx + (CARD_W - _GEM_SZ) // 2
    gem_by = ry + _GEM_Y
    _blit(gem, gem_bx, gem_by)
    if gem is None:
        gem_col = _RARITY_COLOR.get(card.rarity, colors.TEXT_SECONDARY)
        pygame.draw.circle(surface, gem_col, (rx + CARD_W // 2, ry + _GEM_Y + _GEM_SZ // 2), 6)

    # ------------------------------------------------------------------
    # Layer 8: stat hexagons  (minion 8 — full width)
    # ------------------------------------------------------------------
    stats_surf = sp.get_card_component("stats", CARD_W, _STATS_H)
    _blit(stats_surf, rx, ry + _STATS_Y)

    # ------------------------------------------------------------------
    # Layer 9: type plate  (minion 3 — centred between hexagons)
    # ------------------------------------------------------------------
    type_w = 42
    type_surf = sp.get_card_component("type_plate", type_w, _TYPE_H)
    _blit(type_surf, rx + (CARD_W - type_w) // 2, ry + _STATS_Y + (_STATS_H - _TYPE_H) // 2)

    # ------------------------------------------------------------------
    # Layer 10: text overlays
    # ------------------------------------------------------------------
    stat_cy = ry + _STATS_Y + _STATS_H // 2

    # Mana cost
    mana_col = colors.TEXT_PRIMARY if affordable else pygame.Color(200, 60, 60)
    mc = fonts.get(14).render(str(card.cost), True, mana_col)
    surface.blit(mc, mc.get_rect(centerx=rx + CARD_W // 2,
                                  centery=mana_by + mana_h // 2))

    # Card name
    name_col = colors.TEXT_PRIMARY if affordable else pygame.Color(110, 110, 110)
    ns = fonts.get(8).render(card.name[:11], True, name_col)
    surface.blit(ns, ns.get_rect(centerx=rx + CARD_W // 2,
                                  centery=ry + _BANNER_Y + _BANNER_H // 2))

    # Effect line in ability box
    eff = _effect_line(card)
    if eff:
        es = fonts.get(7).render(eff, True, colors.TEXT_SECONDARY)
        surface.blit(es, es.get_rect(centerx=rx + CARD_W // 2,
                                      centery=ry + _ABILITY_Y + _ABILITY_H // 2))

    # ATK (left, red hexagon)
    dmg = card.total_damage()
    atk_val = BigValue.format_int(dmg + bonus_damage) if dmg > 0 else "—"
    atk_col = colors.TEXT_DAMAGE if dmg > 0 else pygame.Color(80, 55, 55)
    ats = fonts.get(11).render(atk_val, True, atk_col)
    surface.blit(ats, ats.get_rect(centerx=rx + _ATK_CX, centery=stat_cy))

    # DEF (right, green hexagon)
    blk = card.total_block()
    def_val = BigValue.format_int(blk + bonus_block) if blk > 0 else "—"
    def_col = colors.TEXT_BLOCK if blk > 0 else pygame.Color(55, 80, 55)
    dfs = fonts.get(11).render(def_val, True, def_col)
    surface.blit(dfs, dfs.get_rect(centerx=rx + _DEF_CX, centery=stat_cy))

    # Type label (centred between hexagons)
    tl = fonts.get(7).render(_TYPE_LABEL[card.card_type], True, colors.TEXT_SECONDARY)
    surface.blit(tl, tl.get_rect(centerx=rx + CARD_W // 2, centery=stat_cy))

    # ------------------------------------------------------------------
    # Selection / hover border
    # ------------------------------------------------------------------
    if selected:
        pygame.draw.rect(surface, colors.CARD_SELECTED, rect, 2, border_radius=5)
    elif hovered:
        pygame.draw.rect(surface, colors.CARD_HOVER, rect, 2, border_radius=5)

    # Broken diagonal
    if card.is_broken:
        pygame.draw.line(surface, colors.CARD_BROKEN, rect.topleft, rect.bottomright, 1)

    return rect
