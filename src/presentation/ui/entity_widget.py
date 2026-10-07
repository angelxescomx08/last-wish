"""Enemies and the hero on the battlefield: HP bar, block, status badges and intents.

Readability rules (from card games such as Slay the Spire):

* **Intent** = one big icon + one number. The sword grows with the damage, a
  multi-attack reads "4×3", and small icons after it say what else the move
  does (block, buff, debuff, junk cards). When the attacks coming this turn
  would kill the hero the intent glows red with a skull.
* **Statuses** = their icon with the stack count in the corner (hover for the rule).
* **Block** = a blue shield with its number on the HP bar, which turns blue-rimmed.
* **Incoming damage** blinks on the hero's HP bar (the HP the coming attacks take).

``hitboxes`` (optional dict) is filled with ``"intent"`` → rect and
``"statuses"`` → ``[(StatusEffect, rect)]`` so the scene can show the right tooltip.
"""
from __future__ import annotations

import math

import pygame

from src.domain.entities import Enemy, Intent, IntentType, Player, StatusEffect
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry
from src.infrastructure.ui_icons import ui_icon
from src.presentation.ui.glossary import status_icon
from src.presentation.ui.tooltip import intent_icon

_CORNER: int = 6
_HP_H: int   = 13


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _outlined(font: pygame.font.Font, text: str, color, outline=(12, 8, 14)) -> pygame.Surface:
    base = font.render(text, True, color)
    edge = font.render(text, True, outline)
    out = pygame.Surface((base.get_width() + 2, base.get_height() + 2), pygame.SRCALPHA)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2), (0, 0), (2, 2), (0, 2), (2, 0)):
        out.blit(edge, (dx, dy))
    out.blit(base, (1, 1))
    return out


def _draw_hp_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    current: int,
    maximum: int,
    fonts: FontRegistry,
    *,
    block: int = 0,
    preview_loss: int = 0,
    t: float = 0.0,
) -> None:
    """HP bar. ``block`` > 0 rims it blue; ``preview_loss`` blinks the HP the coming attacks take."""
    fill_ratio = max(0.0, min(1.0, current / maximum)) if maximum > 0 else 0.0
    fill_col   = colors.HP_LOW if fill_ratio < 0.35 else colors.HP_FILL

    pygame.draw.rect(surface, colors.HP_EMPTY, rect, border_radius=3)
    if fill_ratio > 0:
        fill_rect = pygame.Rect(rect.x, rect.y, int(rect.width * fill_ratio), rect.height)
        pygame.draw.rect(surface, fill_col, fill_rect, border_radius=3)
        loss = min(current, max(0, preview_loss))
        if loss > 0 and maximum > 0:                   # the part the coming attacks will take
            after = int(rect.width * (current - loss) / maximum)
            seg = pygame.Rect(rect.x + after, rect.y, max(2, fill_rect.width - after), rect.height)
            k = 0.5 + 0.5 * math.sin(t * 6.0)
            pygame.draw.rect(surface, (int(160 + 90 * k), int(36 + 50 * k), int(40 + 40 * k)), seg)
            hatch = pygame.Surface(seg.size, pygame.SRCALPHA)
            for sx in range(-seg.h, seg.w, 5):         # diagonal hatching
                pygame.draw.line(hatch, (255, 214, 200, 150), (sx, seg.h), (sx + seg.h, 0))
            surface.blit(hatch, seg.topleft)
    rim = colors.BLOCK_COLOR if block > 0 else colors.BORDER_DIM
    pygame.draw.rect(surface, rim, rect, 2 if block > 0 else 1, border_radius=3)

    hp_surf = _outlined(fonts.get(11), f"{current}/{maximum}", colors.HP_TEXT)
    surface.blit(hp_surf, hp_surf.get_rect(center=rect.center))


def _draw_block_badge(
    surface: pygame.Surface,
    cx: int,
    cy: int,
    block: int,
    fonts: FontRegistry,
) -> pygame.Rect | None:
    """Blue shield with the block number (sits on the left end of the HP bar)."""
    if block <= 0:
        return None
    icon = ui_icon("block", 2)
    font = fonts.get(13)
    if icon is None:
        radius = 14
        pygame.draw.circle(surface, colors.BLOCK_BG, (cx, cy), radius)
        pygame.draw.circle(surface, colors.BLOCK_COLOR, (cx, cy), radius, 2)
        bs = font.render(str(block), True, colors.BLOCK_COLOR)
        surface.blit(bs, bs.get_rect(center=(cx, cy)))
        return pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
    rect = icon.get_rect(center=(cx, cy))
    surface.blit(icon, rect)
    bs = _outlined(font, str(block), (240, 248, 255), (10, 26, 60))
    surface.blit(bs, bs.get_rect(center=(cx, cy - 1)))
    return rect


STATUS_BADGE: int = 28        # icon size (14 px art ×2)
_STATUS_STEP: int = 31


def status_rects(effects: list[StatusEffect], start_x: int, y: int, max_w: int = 10_000) -> list[pygame.Rect]:
    """Where each status badge goes (rows wrap past ``max_w``)."""
    per_row = max(1, max_w // _STATUS_STEP)
    return [pygame.Rect(start_x + (i % per_row) * _STATUS_STEP, y + (i // per_row) * _STATUS_STEP,
                        STATUS_BADGE, STATUS_BADGE) for i in range(len(effects))]


def _draw_status_effects(
    surface: pygame.Surface,
    effects: list[StatusEffect],
    start_x: int,
    y: int,
    fonts: FontRegistry,
    max_w: int = 10_000,
) -> list[tuple[StatusEffect, pygame.Rect]]:
    """Status badges: the status icon with its stacks in the corner (hover one for its rule)."""
    out: list[tuple[StatusEffect, pygame.Rect]] = []
    stacks_font = fonts.get(13)
    for fx, badge in zip(effects, status_rects(effects, start_x, y, max_w)):
        icon = ui_icon(status_icon(fx.name, fx.is_buff), 2)
        if icon is not None:
            surface.blit(icon, badge.topleft)
        else:
            col = colors.BUFF_COLOR if fx.is_buff else colors.DEBUFF_COLOR
            pygame.draw.rect(surface, col, badge.inflate(-6, -6), border_radius=3)
        ink = (160, 245, 170) if fx.is_buff else (255, 240, 236)
        stacks = _outlined(stacks_font, str(fx.stacks), ink)
        surface.blit(stacks, stacks.get_rect(bottomright=(badge.right + 3, badge.bottom + 3)))
        out.append((fx, badge))
    return out


# ---------------------------------------------------------------------------
# Intent
# ---------------------------------------------------------------------------

_INTENT_LABEL: dict[IntentType, str] = {
    IntentType.ATTACK:  "ATQ",
    IntentType.BLOCK:   "BLQ",
    IntentType.BUFF:    "BUFF",
    IntentType.DEBUFF:  "DEB",
    IntentType.UNKNOWN: "???",
}

_INTENT_COLOR: dict[IntentType, pygame.Color] = {
    IntentType.ATTACK:  colors.INTENT_ATTACK,
    IntentType.BLOCK:   colors.INTENT_BLOCK,
    IntentType.BUFF:    colors.INTENT_BUFF,
    IntentType.DEBUFF:  colors.INTENT_DEBUFF,
    IntentType.UNKNOWN: colors.INTENT_UNKNOWN,
}


def intent_label(intent: Intent, damage: int | None = None) -> str:
    """Short text form: "ATQ 12", "ATQ 5x3", "BLQ 12 +CARTAS", "DEB", "BUFF +BLQ"…

    Used when the icon art is missing. ``damage``: per-hit damage after Fuerza /
    Débil / Vulnerable (ATTACK only).
    """
    label = _INTENT_LABEL[intent.intent_type]
    value = damage if (damage is not None and intent.intent_type == IntentType.ATTACK) else intent.value
    if value > 0:
        label = f"{label} {value}"
    if intent.is_multi_hit:
        label += f"x{intent.hits}"
    extras = []
    if intent.block > 0:
        extras.append("BLQ")
    if intent.debuffs and intent.intent_type != IntentType.DEBUFF:
        extras.append("DEB")
    if intent.cards:
        extras.append("CARTAS")
    if intent.buffs and intent.intent_type != IntentType.BUFF:
        extras.append("BUFF")
    return label + "".join(f" +{e}" for e in extras)


def intent_number(intent: Intent, damage: int | None = None) -> str:
    """The number printed next to the intent icon: "6", "4×3", block amount, or ""."""
    if intent.intent_type == IntentType.ATTACK:
        value = damage if damage is not None else intent.value
        return f"{value}×{intent.hits}" if intent.is_multi_hit else str(value)
    if intent.intent_type == IntentType.BLOCK and intent.value > 0:
        return str(intent.value)
    return ""


def intent_extras(intent: Intent) -> list[str]:
    """Small icons after the main one: block, buff, debuff, junk cards (what else the move does)."""
    extras: list[str] = []
    if intent.block > 0:
        extras.append("block")
    if intent.buffs and intent.intent_type != IntentType.BUFF:
        extras.append("status_buff")
    if intent.debuffs and intent.intent_type != IntentType.DEBUFF:
        extras.append("status_debuff")
    if intent.cards:
        extras.append("junk_card")
    return extras


def draw_intent(
    surface: pygame.Surface,
    intent: Intent,
    cx: int,
    bottom: int,
    fonts: FontRegistry,
    damage: int | None = None,
    *,
    lethal: bool = False,
    t: float = 0.0,
) -> pygame.Rect:
    """Draw the intent centred on ``cx`` with its bottom at ``bottom``. Returns its rect.

    ``lethal``: the attacks coming this turn kill the hero — the intent glows red.
    """
    main = ui_icon(intent_icon(intent, damage), 2)
    if main is None:                                   # no art: the old text bubble
        return _draw_intent_bubble(surface, intent, cx, bottom - 11, fonts, damage)
    number = intent_number(intent, damage)
    attack = intent.intent_type == IntentType.ATTACK
    ink = (255, 96, 84) if lethal else (255, 240, 226) if attack else (214, 236, 255)
    num_s = _outlined(fonts.get(21), number, ink) if number else None
    extras = [e for e in (ui_icon(name, 2) for name in intent_extras(intent)) if e is not None]
    width = main.get_width() + (num_s.get_width() if num_s else 0) + sum(e.get_width() for e in extras)
    height = main.get_height()
    bob = round(math.sin(t * 2.4) * 2)
    rect = pygame.Rect(cx - width // 2, bottom - height, width, height)

    shade = pygame.Surface((width + 18, 20), pygame.SRCALPHA)      # contrast under the icons
    pygame.draw.ellipse(shade, (6, 4, 10, 130), shade.get_rect())
    surface.blit(shade, shade.get_rect(center=(rect.centerx, rect.bottom - 7)))
    if lethal:
        k = 0.5 + 0.5 * math.sin(t * 7.0)
        size = main.get_width() + 34
        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        for r in range(size // 2, 4, -3):
            a = int((70 + 80 * k) * (1 - r / (size / 2)) ** 1.2)
            pygame.draw.circle(glow, (255, 40, 30, a), (size // 2, size // 2), r)
        surface.blit(glow, glow.get_rect(center=(rect.x + main.get_width() // 2, rect.centery + bob)))

    x = rect.x
    surface.blit(main, (x, rect.y + bob))
    x += main.get_width()
    if num_s is not None:
        surface.blit(num_s, num_s.get_rect(midleft=(x - 3, rect.bottom - 11)))
        x += num_s.get_width()
    for e in extras:
        surface.blit(e, e.get_rect(bottomleft=(x, rect.bottom)))
        x += e.get_width()
    if lethal:
        skull = ui_icon("lethal", 1)
        if skull is not None:
            surface.blit(skull, skull.get_rect(center=(rect.x + 2, rect.y + 3 + bob)))
    return rect


def _draw_intent_bubble(
    surface: pygame.Surface,
    intent: Intent,
    cx: int,
    cy: int,
    fonts: FontRegistry,
    damage: int | None = None,
) -> pygame.Rect:
    col   = _INTENT_COLOR[intent.intent_type]
    label = intent_label(intent, damage)
    intent_font = fonts.get(10)
    w, h = max(56, intent_font.size(label)[0] + 16), 22
    rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
    pygame.draw.rect(surface, colors.BG_PANEL, rect, border_radius=4)
    pygame.draw.rect(surface, col, rect, 1, border_radius=4)
    intent_surf = intent_font.render(label, True, col)
    surface.blit(intent_surf, intent_surf.get_rect(center=rect.center))
    return rect


# ---------------------------------------------------------------------------
# Enemy
# ---------------------------------------------------------------------------

ENEMY_W: int = 128
ENEMY_H: int = 150


def draw_enemy(
    surface: pygame.Surface,
    enemy: Enemy,
    x: int,
    y: int,
    fonts: FontRegistry,
    *,
    targeted: bool = False,
    highlighted: bool = False,
    sprite: pygame.Surface | None = None,
    framed: bool = True,
    size: tuple[int, int] | None = None,
    intent_damage: int | None = None,
    lethal: bool = False,
    t: float = 0.0,
    hitboxes: dict | None = None,
) -> pygame.Rect:
    """Draw one enemy. ``framed=False`` skips the body panel (animated sprites draw themselves).

    ``size``: body rect size (bosses use a bigger one); ``intent_damage``: per-hit damage
    shown on the intent (after Fuerza / Débil / Vulnerable); ``lethal``: the coming
    attacks kill the hero; ``hitboxes``: filled with the intent and status badge rects.
    """
    w, h = size or (ENEMY_W, ENEMY_H)
    rect = pygame.Rect(x, y, w, h)

    # Defeated state — draw greyed-out silhouette and return
    if not enemy.is_alive:
        pygame.draw.rect(surface, pygame.Color(30, 25, 25), rect, border_radius=_CORNER)
        pygame.draw.rect(surface, pygame.Color(60, 50, 50), rect, 1, border_radius=_CORNER)
        dead_font = fonts.get(13)
        dead_surf = dead_font.render("DERROTADO", True, pygame.Color(100, 80, 80))
        surface.blit(dead_surf, dead_surf.get_rect(center=rect.center))
        return rect

    # Name label, intent above it
    name_font = fonts.get(12)
    name_surf = _outlined(name_font, enemy.name, colors.TEXT_ACCENT)
    name_rect = name_surf.get_rect(centerx=rect.centerx, bottom=y - 2)
    surface.blit(name_surf, name_rect)
    intent_rect = draw_intent(surface, enemy.intent, rect.centerx, name_rect.top - 1, fonts,
                              intent_damage, lethal=lethal, t=t)

    # Body background
    if highlighted:
        body_col = pygame.Color(160, 70, 40)
        border   = pygame.Color(255, 160, 50)
        bw       = 2
    elif targeted:
        body_col = colors.ENEMY_ACCENT
        border   = pygame.Color(255, 220, 60)
        bw       = 2
    else:
        body_col = colors.ENEMY_BODY
        border   = colors.ENEMY_ACCENT
        bw       = 1

    if framed:
        pygame.draw.rect(surface, body_col, rect, border_radius=_CORNER)

    # Sprite centred inside body (drawn before border so border overlaps edges)
    if sprite is not None:
        surface.blit(sprite, sprite.get_rect(center=rect.center))

    if framed:
        pygame.draw.rect(surface, border, rect, bw, border_radius=_CORNER)

    # Targeting crosshair corners when highlighted
    if highlighted:
        sz = 8
        for cx, cy, dx, dy in [
            (rect.x, rect.y, 1, 1),
            (rect.right, rect.y, -1, 1),
            (rect.x, rect.bottom, 1, -1),
            (rect.right, rect.bottom, -1, -1),
        ]:
            pygame.draw.line(surface, border, (cx, cy), (cx + dx * sz, cy), 2)
            pygame.draw.line(surface, border, (cx, cy), (cx, cy + dy * sz), 2)

    # HP bar with the block shield on its left end
    hp_rect = pygame.Rect(x, rect.bottom + 4, w, _HP_H)
    _draw_hp_bar(surface, hp_rect, enemy.current_hp, enemy.max_hp, fonts, block=enemy.block)
    _draw_block_badge(surface, hp_rect.x, hp_rect.centery, enemy.block, fonts)

    # Status effects
    statuses = _draw_status_effects(surface, enemy.status_effects, x, rect.bottom + 21, fonts, max(w, 124))
    if hitboxes is not None:
        hitboxes["intent"] = intent_rect
        hitboxes["statuses"] = statuses
    return rect


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

PLAYER_W: int = 155
PLAYER_H: int = 195


def draw_player(
    surface: pygame.Surface,
    player: Player,
    x: int,
    y: int,
    fonts: FontRegistry,
    *,
    sprite: pygame.Surface | None = None,
    framed: bool = True,
    incoming_loss: int = 0,
    t: float = 0.0,
    hitboxes: dict | None = None,
) -> pygame.Rect:
    """Draw the hero. ``incoming_loss``: HP the enemies' coming attacks will take (blinks on the bar)."""
    rect = pygame.Rect(x, y, PLAYER_W, PLAYER_H)

    # Body background
    if framed:
        pygame.draw.rect(surface, colors.PLAYER_BODY, rect, border_radius=_CORNER)

    # Sprite centred inside body (drawn before border)
    if sprite is not None:
        surface.blit(sprite, sprite.get_rect(center=rect.center))

    if framed:
        pygame.draw.rect(surface, colors.PLAYER_ACCENT, rect, 2, border_radius=_CORNER)

    # Name
    ns = _outlined(fonts.get(12), player.name, colors.TEXT_ACCENT)
    surface.blit(ns, ns.get_rect(centerx=rect.centerx, bottom=y - 4))

    # HP bar (+ the damage coming this enemy turn) with the block shield on its left end
    hp_rect = pygame.Rect(x, rect.bottom + 4, PLAYER_W, _HP_H + 2)
    _draw_hp_bar(surface, hp_rect, player.current_hp, player.max_hp, fonts,
                 block=player.block, preview_loss=incoming_loss, t=t)
    _draw_block_badge(surface, hp_rect.x, hp_rect.centery, player.block, fonts)
    if incoming_loss > 0:                              # "-8" chip after the bar
        chip = _outlined(fonts.get(14), f"-{incoming_loss}", (255, 110, 96))
        surface.blit(chip, chip.get_rect(midleft=(hp_rect.right + 5, hp_rect.centery)))

    # Status effects
    statuses = _draw_status_effects(surface, player.status_effects, x, rect.bottom + 23, fonts, PLAYER_W + 40)
    if hitboxes is not None:
        hitboxes["statuses"] = statuses
    return rect
