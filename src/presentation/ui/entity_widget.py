from __future__ import annotations

import pygame

from src.domain.entities import Enemy, Intent, IntentType, Player, StatusEffect
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

_CORNER: int = 6
_HP_H: int   = 13
_STATUS_SZ   = 18


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _draw_hp_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    current: int,
    maximum: int,
    fonts: FontRegistry,
) -> None:
    fill_ratio = max(0.0, min(1.0, current / maximum)) if maximum > 0 else 0.0
    fill_col   = colors.HP_LOW if fill_ratio < 0.35 else colors.HP_FILL

    pygame.draw.rect(surface, colors.HP_EMPTY, rect, border_radius=3)
    if fill_ratio > 0:
        fill_rect = pygame.Rect(rect.x, rect.y, int(rect.width * fill_ratio), rect.height)
        pygame.draw.rect(surface, fill_col, fill_rect, border_radius=3)
    pygame.draw.rect(surface, colors.BORDER_DIM, rect, 1, border_radius=3)

    hp_font = fonts.get(10)
    hp_text = f"{current}/{maximum}"
    hp_surf = hp_font.render(hp_text, True, colors.HP_TEXT)
    surface.blit(hp_surf, hp_surf.get_rect(center=rect.center))


def _draw_block_badge(
    surface: pygame.Surface,
    cx: int,
    cy: int,
    block: int,
    fonts: FontRegistry,
) -> None:
    if block <= 0:
        return
    radius = 14
    pygame.draw.circle(surface, colors.BLOCK_BG, (cx, cy), radius)
    pygame.draw.circle(surface, colors.BLOCK_COLOR, (cx, cy), radius, 2)
    bf = fonts.get(12)
    bs = bf.render(str(block), True, colors.BLOCK_COLOR)
    surface.blit(bs, bs.get_rect(center=(cx, cy)))


def _draw_status_effects(
    surface: pygame.Surface,
    effects: list[StatusEffect],
    start_x: int,
    y: int,
    fonts: FontRegistry,
) -> None:
    x = start_x
    for fx in effects:
        col = colors.BUFF_COLOR if fx.is_buff else colors.DEBUFF_COLOR
        badge = pygame.Rect(x, y, _STATUS_SZ, _STATUS_SZ)
        pygame.draw.rect(surface, col, badge, border_radius=3)
        stacks_font = fonts.get(8)
        stacks_surf = stacks_font.render(str(fx.stacks), True, colors.TEXT_PRIMARY)
        surface.blit(stacks_surf, stacks_surf.get_rect(center=badge.center))
        label_font = fonts.get(7)
        label_surf = label_font.render(fx.name[:4], True, col)
        surface.blit(label_surf, (x, y + _STATUS_SZ + 1))
        x += _STATUS_SZ + 4


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


def _draw_intent(
    surface: pygame.Surface,
    intent: Intent,
    cx: int,
    cy: int,
    fonts: FontRegistry,
) -> None:
    col   = _INTENT_COLOR[intent.intent_type]
    label = _INTENT_LABEL[intent.intent_type]
    if intent.value > 0:
        label = f"{label} {intent.value}"

    w, h = 56, 22
    rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
    pygame.draw.rect(surface, colors.BG_PANEL, rect, border_radius=4)
    pygame.draw.rect(surface, col, rect, 1, border_radius=4)

    intent_font = fonts.get(10)
    intent_surf = intent_font.render(label, True, col)
    surface.blit(intent_surf, intent_surf.get_rect(center=rect.center))


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
) -> pygame.Rect:
    rect = pygame.Rect(x, y, ENEMY_W, ENEMY_H)

    # Defeated state — draw greyed-out silhouette and return
    if not enemy.is_alive:
        pygame.draw.rect(surface, pygame.Color(30, 25, 25), rect, border_radius=_CORNER)
        pygame.draw.rect(surface, pygame.Color(60, 50, 50), rect, 1, border_radius=_CORNER)
        dead_font = fonts.get(13)
        dead_surf = dead_font.render("DERROTADO", True, pygame.Color(100, 80, 80))
        surface.blit(dead_surf, dead_surf.get_rect(center=rect.center))
        return rect

    # Intent bubble above
    _draw_intent(surface, enemy.intent, rect.centerx, y - 30, fonts)

    # Name label
    name_font = fonts.get(11)
    name_surf = name_font.render(enemy.name, True, colors.TEXT_ACCENT)
    surface.blit(name_surf, name_surf.get_rect(centerx=rect.centerx, bottom=y - 4))

    # Body
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

    pygame.draw.rect(surface, body_col, rect, border_radius=_CORNER)
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

    # HP bar
    hp_rect = pygame.Rect(x, rect.bottom + 4, ENEMY_W, _HP_H)
    _draw_hp_bar(surface, hp_rect, enemy.current_hp, enemy.max_hp, fonts)

    # Block badge (bottom-right of body)
    _draw_block_badge(surface, rect.right - 16, rect.bottom - 16, enemy.block, fonts)

    # Status effects
    _draw_status_effects(surface, enemy.status_effects, x, rect.bottom + 20, fonts)

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
) -> pygame.Rect:
    rect = pygame.Rect(x, y, PLAYER_W, PLAYER_H)

    # Body
    pygame.draw.rect(surface, colors.PLAYER_BODY, rect, border_radius=_CORNER)
    pygame.draw.rect(surface, colors.PLAYER_ACCENT, rect, 2, border_radius=_CORNER)

    # Name
    nf = fonts.get(12)
    ns = nf.render(player.name, True, colors.TEXT_ACCENT)
    surface.blit(ns, ns.get_rect(centerx=rect.centerx, bottom=y - 4))

    # HP bar
    hp_rect = pygame.Rect(x, rect.bottom + 4, PLAYER_W, _HP_H + 2)
    _draw_hp_bar(surface, hp_rect, player.current_hp, player.max_hp, fonts)

    # Block badge
    _draw_block_badge(surface, rect.right - 18, rect.bottom - 18, player.block, fonts)

    # Status effects
    _draw_status_effects(surface, player.status_effects, x, rect.bottom + 22, fonts)

    return rect
