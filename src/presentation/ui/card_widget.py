"""Card widget — rarity frames from assets/cards-v2 with dynamic content.

Layers (back to front), following the asset pack's guide:
  1. Illustration, clipped to the frame's transparent window, over a backdrop
     tinted by card type (attack red, skill blue, power violet).
  2. Dark discs under the mana and stat circles (their centres are see-through).
  3. Rarity frame (COMMON … LEGENDARY) — chosen by ``card.rarity``, never by type.
  4. Text from the card's data: mana cost, name, effect lines, attack / block.
  5. Interaction: lift + rarity-coloured outline on hover/selection, dimming when
     the card is unaffordable, a slash for broken cards.

Performance: layers 1–4 are rendered once into a cached surface keyed by every
value they show (cost, name, effective damage/block, rarity, affordability…).
When a relic changes the damage or a card's cost changes, the key changes and
the card is redrawn once; otherwise drawing a card is a single blit.
"""
from __future__ import annotations

from collections import OrderedDict

import pygame

from src.domain.card import Card, CardRarity, CardType
from src.domain.chroma import chroma_def
from src.domain.keywords import combo_text
from src.domain.numbers import BigValue
from src.infrastructure import colors
from src.infrastructure.card_assets import card_frame, card_illustration, card_layout
from src.infrastructure.fonts import FontRegistry
from src.presentation.fx import chroma_fx

# ---------------------------------------------------------------------------
# Card dimensions (frame aspect ratio ≈ 0.72)
# ---------------------------------------------------------------------------

CARD_W: int = 140
CARD_H: int = 194

_FALLBACK_ZONES = {
    "art": {"x0": 0.14, "y0": 0.16, "x1": 0.86, "y1": 0.54},
    "mana": {"cx": 0.137, "cy": 0.097, "r": 0.058},
    "name": {"x0": 0.285, "y0": 0.080, "x1": 0.850, "y1": 0.146},
    "text": {"x0": 0.150, "y0": 0.590, "x1": 0.850, "y1": 0.835},
    "attack": {"cx": 0.131, "cy": 0.889, "r": 0.056},
    "block": {"cx": 0.870, "cy": 0.889, "r": 0.056},
}

_RARITY_COLOR: dict[CardRarity, pygame.Color] = {
    CardRarity.COMMON:    pygame.Color(170, 160, 150),
    CardRarity.UNCOMMON:  pygame.Color(80, 200, 110),
    CardRarity.RARE:      pygame.Color(80, 150, 240),
    CardRarity.EPIC:      pygame.Color(180, 90, 240),
    CardRarity.LEGENDARY: pygame.Color(245, 175, 40),
}

_TYPE_BACKDROP: dict[CardType, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    CardType.ATTACK: ((70, 18, 22), (150, 44, 40)),
    CardType.SKILL:  ((16, 30, 66), (44, 90, 150)),
    CardType.POWER:  ((40, 16, 64), (110, 56, 160)),
}

_INK_DARK = (34, 24, 18)            # name on the parchment plate
_INK_LIGHT = (236, 230, 214)        # effect text on the dark panel
_MANA_INK = (200, 230, 255)
_ATK_INK = (255, 150, 120)
_DEF_INK = (150, 210, 255)
_BONUS_INK = (140, 240, 140)
_HOLE = (18, 16, 24)
KEYWORD_READY_GLOW = (70, 225, 170)   # aura on cards whose Combo is ready

_CACHE_MAX = 256
_cache: "OrderedDict[tuple, pygame.Surface]" = OrderedDict()


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


def _wrap(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    """Word-wrap text into lines that fit max_w. Truncates with '…' only if a single word doesn't fit."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if font.size(candidate)[0] <= max_w:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word if font.size(word)[0] <= max_w else _fit(word, font, max_w)
    if current:
        lines.append(current)
    return lines or [""]


def _ability_lines(card: Card, damage: int = 0, block: int = 0, combo: bool = False) -> list[str]:
    """Spanish effect lines built from the card's data (effective values).

    ``combo``: the card's Combo is ready, so its numbers already include the combo
    layer and the keyword line says so.
    """
    lines: list[str] = []
    draw = card.total_draw(combo)
    mana = card.total_mana_gain(combo)
    if card.card_type == CardType.ATTACK and damage > 0:
        lines.append(f"Inflige {BigValue.format_int(damage)} de daño.")
    if block > 0:
        lines.append(f"Gana {BigValue.format_int(block)} de escudo.")
    if draw > 0:
        lines.append(f"Roba {draw} carta{'s' if draw > 1 else ''}.")
    if mana > 0:
        lines.append(f"+{mana} de maná.")
    if card.card_type == CardType.POWER:
        lines.append("Poder permanente.")
    if card.combo_effects():
        lines.append("¡Combo activo!" if combo else f"Combo: {combo_text(card)}.")
    return lines[:4]


def _outlined(font: pygame.font.Font, text: str, color, outline=(10, 8, 12)) -> pygame.Surface:
    base = font.render(text, True, color)
    edge = font.render(text, True, outline)
    out = pygame.Surface((base.get_width() + 2, base.get_height() + 2), pygame.SRCALPHA)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(edge, (dx, dy))
    out.blit(base, (1, 1))
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _zones(rarity: str) -> dict:
    layout = card_layout()
    if not layout:
        return _FALLBACK_ZONES
    z = dict(layout["zones"])
    frame = layout["frames"].get(rarity)
    z["art"] = frame["art"] if frame else _FALLBACK_ZONES["art"]
    return z


def _rect(z: dict, w: int, h: int) -> pygame.Rect:
    return pygame.Rect(round(z["x0"] * w), round(z["y0"] * h),
                       round((z["x1"] - z["x0"]) * w), round((z["y1"] - z["y0"]) * h))


def _circle(z: dict, w: int, h: int) -> tuple[tuple[int, int], int]:
    return (round(z["cx"] * w), round(z["cy"] * h)), max(2, round(z["r"] * w))


def _backdrop(card_type: CardType, size: tuple[int, int]) -> pygame.Surface:
    dark, light = _TYPE_BACKDROP.get(card_type, ((30, 30, 40), (70, 70, 90)))
    w, h = size
    surf = pygame.Surface(size)
    bands = 6
    for i in range(bands):                       # banded vertical gradient, pixel-art style
        t = i / (bands - 1)
        col = tuple(round(d + (l - d) * (1 - abs(t - 0.45) * 1.6)) for d, l in zip(dark, light))
        y0 = round(i * h / bands)
        surf.fill(col, (0, y0, w, round((i + 1) * h / bands) - y0))
    return surf


def render_card_surface(card: Card, fonts: FontRegistry, *, w: int = CARD_W, h: int = CARD_H,
                        affordable: bool = True, bonus_damage: int = 0,
                        bonus_block: int = 0, combo: bool = False) -> pygame.Surface:
    """Compose the static part of a card (cached by every value it displays).

    ``combo``: its Combo is ready — numbers include the combo layer (shown in green).
    """
    combo = combo and bool(card.combo_effects())
    raw_damage, raw_block = card.total_damage(combo), card.total_block(combo)
    damage = raw_damage + bonus_damage if raw_damage > 0 else 0
    block = raw_block + bonus_block if raw_block > 0 else 0
    combo_dmg = combo and raw_damage > card.total_damage()
    combo_blk = combo and raw_block > card.total_block()
    rarity = (card.rarity or CardRarity.COMMON).name
    key = (card.id, card.name, card.card_type, rarity, card.cost, damage, block, bonus_damage > 0 or combo_dmg,
           bonus_block > 0 or combo_blk, tuple(_ability_lines(card, damage, block, combo)), affordable,
           card.is_broken, card.chroma, w, h, id(fonts))
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached

    z = _zones(rarity)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)

    # 1. illustration window
    art_rect = _rect(z["art"], w, h).inflate(4, 4)
    surf.blit(_backdrop(card.card_type, art_rect.size), art_rect.topleft)
    art = card_illustration(card.id, card.card_type.name, art_rect.w, art_rect.h)
    if art is not None:
        surf.blit(art, art.get_rect(center=art_rect.center))

    # 2. dark discs behind see-through circles
    for name in ("mana", "attack", "block"):
        c, r = _circle(z[name], w, h)
        pygame.draw.circle(surf, _HOLE, c, r + 1)

    # 3. rarity frame
    frame = card_frame(rarity, w, h)
    if frame is not None and card.chroma is not None:
        frame = chroma_fx.gild_frame(frame, card.chroma)
    if frame is not None:
        surf.blit(frame, (0, 0))
    else:
        pygame.draw.rect(surf, _RARITY_COLOR.get(card.rarity, colors.CARD_BORDER), surf.get_rect(), 3,
                         border_radius=8)

    # 4. text
    c, r = _circle(z["mana"], w, h)
    mana_col = _MANA_INK if affordable else (235, 80, 80)
    cost = _outlined(fonts.get(max(10, round(r * 2.1))), str(card.cost), mana_col)
    surf.blit(cost, cost.get_rect(center=c))

    name_rect = _rect(z["name"], w, h)
    size = max(8, round(name_rect.h * 0.78))
    name_font = fonts.get(size)
    while size > 7 and name_font.size(card.name)[0] > name_rect.w - 4:   # shrink before truncating
        size -= 1
        name_font = fonts.get(size)
    name_s = name_font.render(_fit(card.name, name_font, name_rect.w - 4), True, _INK_DARK)
    surf.blit(name_s, name_s.get_rect(center=name_rect.center))

    text_rect = _rect(z["text"], w, h)
    if card.chroma is not None:   # chroma name plate at the foot of the text panel, e.g. "DORADA"
        st = chroma_fx.style(card.chroma)
        casts = card.casts()
        label = chroma_def(card.chroma).name.upper() + (f"  x{casts}" if casts > 1 else "")
        plate = _outlined(fonts.get(max(7, round(h * 0.048))), label, st.bright, outline=st.dark)
        surf.blit(plate, plate.get_rect(centerx=text_rect.centerx, bottom=text_rect.bottom))
        text_rect = pygame.Rect(text_rect.x, text_rect.y, text_rect.w, max(1, text_rect.h - plate.get_height()))
    lines = _ability_lines(card, damage, block, combo)
    if lines:
        font = fonts.get(max(8, round(h * 0.052)))
        wrapped: list[str] = []
        for raw in lines:
            wrapped.extend(_wrap(raw, font, text_rect.w))
        line_h = font.get_linesize()
        max_lines = max(1, text_rect.h // line_h)
        if len(wrapped) > max_lines:
            wrapped = wrapped[:max_lines]
            wrapped[-1] = _fit(wrapped[-1] + "…", font, text_rect.w)
        y = text_rect.centery - len(wrapped) * line_h // 2
        for line in wrapped:
            s = font.render(line, True, _INK_LIGHT)
            surf.blit(s, s.get_rect(centerx=text_rect.centerx, top=y))
            y += line_h

    for zone, value, ink, boosted in (("attack", damage, _ATK_INK, bonus_damage > 0 or combo_dmg),
                                      ("block", block, _DEF_INK, bonus_block > 0 or combo_blk)):
        if value > 0:
            c, r = _circle(z[zone], w, h)
            txt = BigValue.format_int(value)
            size = max(8, round(r * (2.0 if len(txt) <= 2 else 1.5 if len(txt) == 3 else 1.2)))
            s = _outlined(fonts.get(size), txt, _BONUS_INK if boosted else ink)
            surf.blit(s, s.get_rect(center=c))

    if not affordable:
        surf.fill((150, 150, 150, 255), special_flags=pygame.BLEND_RGBA_MULT)

    if card.is_broken:   # baked in, so it tilts with the card
        pygame.draw.line(surf, colors.CARD_BROKEN, (0, 0), (w - 1, h - 1), 2)

    _cache[key] = surf
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return surf


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
    combo: bool = False,
) -> pygame.Rect:
    """Draw a card and return its bounding Rect (lifted when hovered or selected)."""
    lift = -20 if (selected or hovered) else 0
    rect = pygame.Rect(x, y + lift, CARD_W, CARD_H)
    body = render_card_surface(card, fonts, affordable=affordable,
                               bonus_damage=bonus_damage, bonus_block=bonus_block, combo=combo)
    if combo and card.combo_effects():
        chroma_fx.draw_silhouette_aura(surface, body, rect.center, KEYWORD_READY_GLOW, chroma_fx.now(),
                                       key=(CARD_W, CARD_H, card.rarity), speed=4.0)
    if card.chroma is not None:
        t = chroma_fx.now()
        chroma_fx.draw_card_aura(surface, body, rect.center, card.chroma, t,
                                 key=(CARD_W, CARD_H, card.rarity))
        body = chroma_fx.animate_card_face(body, card.chroma, t)
    surface.blit(body, rect.topleft)
    if card.chroma is not None:
        chroma_fx.draw_motes(surface, rect, card.chroma, chroma_fx.now())

    if selected or hovered:
        glow = _RARITY_COLOR.get(card.rarity, colors.CARD_HOVER)
        col = colors.CARD_SELECTED if selected else glow
        pygame.draw.rect(surface, col, rect.inflate(4, 4), 2, border_radius=10)

    return rect


# ---------------------------------------------------------------------------
# Free placement (hand fan, held card, aiming) — scaled and rotated, cached
# ---------------------------------------------------------------------------

_SCALE_STEP = 0.05
_ROT_MAX = 96
_rot_cache: OrderedDict = OrderedDict()


def quantize_scale(scale: float) -> float:
    """Scales snap to 5 % steps so a hover tween reuses a handful of renders."""
    return max(_SCALE_STEP, round(scale / _SCALE_STEP) * _SCALE_STEP)


def card_size(scale: float) -> tuple[int, int]:
    q = quantize_scale(scale)
    return round(CARD_W * q), round(CARD_H * q)


def draw_card_at(
    surface: pygame.Surface,
    card: Card,
    center: tuple[float, float],
    fonts: FontRegistry,
    *,
    scale: float = 1.0,
    angle: float = 0.0,
    affordable: bool = True,
    bonus_damage: int = 0,
    bonus_block: int = 0,
    outline: tuple[int, int, int] | None = None,
    combo: bool = False,
) -> pygame.Rect:
    """Draw a card centred on ``center``; returns its (unrotated) rect.

    The face is re-rendered at the quantised size (crisp text, never an
    upscaled bitmap). A tilt of a whole degree or more is rotated once and
    cached; ``outline`` draws a highlight (only on untilted cards).
    A broken card's slash is part of the cached face.
    """
    w, h = card_size(scale)
    body = render_card_surface(card, fonts, w=w, h=h, affordable=affordable,
                               bonus_damage=bonus_damage, bonus_block=bonus_block, combo=combo)
    tilt = int(round(angle))
    if combo and card.combo_effects():   # keyword ready: pulsing aura hugging the card
        chroma_fx.draw_silhouette_aura(surface, body, (round(center[0]), round(center[1])), KEYWORD_READY_GLOW,
                                       chroma_fx.now(), key=(w, h, card.rarity), angle=tilt, speed=4.0)
    if card.chroma is not None:
        # Animated each frame, so it bypasses the rotation cache.
        t = chroma_fx.now()
        chroma_fx.draw_card_aura(surface, body, (round(center[0]), round(center[1])), card.chroma, t,
                                 key=(w, h, card.rarity), angle=tilt)
        body = chroma_fx.animate_card_face(body, card.chroma, t, base_w=CARD_W)
        if tilt:
            body = pygame.transform.rotozoom(body, tilt, 1.0)
        surface.blit(body, body.get_rect(center=(round(center[0]), round(center[1]))))
        chroma_fx.draw_motes(surface, pygame.Rect(round(center[0]) - w // 2, round(center[1]) - h // 2, w, h),
                             card.chroma, t, scale=w / CARD_W)
    elif tilt:
        key = (body, tilt)
        rotated = _rot_cache.get(key)
        if rotated is None:
            rotated = pygame.transform.rotozoom(body, tilt, 1.0)
            _rot_cache[key] = rotated
            if len(_rot_cache) > _ROT_MAX:
                _rot_cache.popitem(last=False)
        else:
            _rot_cache.move_to_end(key)
        surface.blit(rotated, rotated.get_rect(center=(round(center[0]), round(center[1]))))
    else:
        surface.blit(body, body.get_rect(center=(round(center[0]), round(center[1]))))
    rect = pygame.Rect(round(center[0]) - w // 2, round(center[1]) - h // 2, w, h)
    if outline is not None and not tilt:
        pygame.draw.rect(surface, outline, rect.inflate(6, 6), 3, border_radius=12)
    return rect
