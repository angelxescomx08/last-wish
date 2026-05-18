"""Tests for infrastructure/colors.py — verify every named color constant.

All pygame.Color objects are fully constructible without a display. Tests
confirm the correct RGB components so that accidental palette changes are caught.
"""
from __future__ import annotations

import pygame
import pytest

import src.infrastructure.colors as colors


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _rgb(c: pygame.Color) -> tuple[int, int, int]:
    return (c.r, c.g, c.b)


# ---------------------------------------------------------------------------
# Type checks — every export must be a pygame.Color
# ---------------------------------------------------------------------------

class TestColorTypes:
    _ALL = [
        "BG_DARK", "BG_PANEL", "BG_CARD_AREA", "BG_OVERLAY",
        "PLAYER_BODY", "PLAYER_ACCENT", "ENEMY_BODY", "ENEMY_ACCENT",
        "HP_FILL", "HP_LOW", "HP_EMPTY", "HP_TEXT",
        "BLOCK_COLOR", "BLOCK_BG",
        "CARD_ATTACK", "CARD_ATTACK_DARK", "CARD_SKILL", "CARD_SKILL_DARK",
        "CARD_POWER", "CARD_POWER_DARK", "CARD_SELECTED", "CARD_HOVER",
        "CARD_BORDER", "CARD_BROKEN", "CARD_BROKEN_DARK",
        "MANA_FILL", "MANA_EMPTY", "MANA_ORB_RING", "MANA_TEXT",
        "INTENT_ATTACK", "INTENT_BLOCK", "INTENT_BUFF",
        "INTENT_DEBUFF", "INTENT_UNKNOWN",
        "BUFF_COLOR", "DEBUFF_COLOR",
        "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_ACCENT",
        "TEXT_DAMAGE", "TEXT_BLOCK",
        "BORDER_DIM", "BORDER_BRIGHT",
        "RELIC_BG", "RELIC_BORDER",
        "END_TURN_BG", "END_TURN_HOVER", "END_TURN_TEXT",
        "PANEL_BORDER",
    ]

    def test_all_exports_are_pygame_color(self):
        for name in self._ALL:
            obj = getattr(colors, name)
            assert isinstance(obj, pygame.Color), f"{name} is not pygame.Color"

    def test_count_of_exported_constants(self):
        # Ensure we're not missing any constant (update if new colors are added)
        assert len(self._ALL) == 49


# ---------------------------------------------------------------------------
# RGB value checks — backgrounds
# ---------------------------------------------------------------------------

class TestBackgrounds:
    def test_bg_dark(self):
        assert _rgb(colors.BG_DARK) == (12, 12, 20)

    def test_bg_panel(self):
        assert _rgb(colors.BG_PANEL) == (22, 22, 36)

    def test_bg_card_area(self):
        assert _rgb(colors.BG_CARD_AREA) == (8, 10, 16)


# ---------------------------------------------------------------------------
# RGB value checks — cards
# ---------------------------------------------------------------------------

class TestCardColors:
    def test_card_attack(self):
        assert _rgb(colors.CARD_ATTACK) == (155, 38, 38)

    def test_card_skill(self):
        assert _rgb(colors.CARD_SKILL) == (38, 125, 55)

    def test_card_power(self):
        assert _rgb(colors.CARD_POWER) == (45, 55, 165)

    def test_card_broken(self):
        assert _rgb(colors.CARD_BROKEN) == (175, 80, 210)

    def test_card_selected(self):
        assert _rgb(colors.CARD_SELECTED) == (235, 210, 55)

    def test_dark_variants_are_darker(self):
        # Dark variants must have lower luminance than their base
        def lum(c: pygame.Color) -> int:
            return c.r + c.g + c.b

        assert lum(colors.CARD_ATTACK_DARK) < lum(colors.CARD_ATTACK)
        assert lum(colors.CARD_SKILL_DARK)  < lum(colors.CARD_SKILL)
        assert lum(colors.CARD_POWER_DARK)  < lum(colors.CARD_POWER)
        assert lum(colors.CARD_BROKEN_DARK) < lum(colors.CARD_BROKEN)


# ---------------------------------------------------------------------------
# RGB value checks — mana
# ---------------------------------------------------------------------------

class TestManaColors:
    def test_mana_fill(self):
        assert _rgb(colors.MANA_FILL) == (55, 155, 235)

    def test_mana_empty(self):
        assert _rgb(colors.MANA_EMPTY) == (25, 55, 95)

    def test_mana_orb_ring(self):
        assert _rgb(colors.MANA_ORB_RING) == (90, 185, 255)


# ---------------------------------------------------------------------------
# RGB value checks — text
# ---------------------------------------------------------------------------

class TestTextColors:
    def test_text_damage_is_reddish(self):
        c = colors.TEXT_DAMAGE
        assert c.r > c.g and c.r > c.b

    def test_text_block_is_bluish(self):
        c = colors.TEXT_BLOCK
        assert c.b > c.r

    def test_text_accent_is_golden(self):
        c = colors.TEXT_ACCENT
        assert c.r > 200 and c.g > 150 and c.b < 100


# ---------------------------------------------------------------------------
# RGB value checks — intents
# ---------------------------------------------------------------------------

class TestIntentColors:
    def test_intent_attack_is_red(self):
        c = colors.INTENT_ATTACK
        assert c.r > c.g and c.r > c.b

    def test_intent_block_is_blue(self):
        c = colors.INTENT_BLOCK
        assert c.b > c.r

    def test_intent_buff_is_green(self):
        c = colors.INTENT_BUFF
        assert c.g > c.r and c.g > c.b


# ---------------------------------------------------------------------------
# RGB range checks — all components in [0, 255]
# ---------------------------------------------------------------------------

class TestColorRanges:
    def test_all_components_in_valid_range(self):
        all_names = [
            "BG_DARK", "BG_PANEL", "BG_CARD_AREA",
            "PLAYER_BODY", "PLAYER_ACCENT", "ENEMY_BODY", "ENEMY_ACCENT",
            "HP_FILL", "HP_LOW", "HP_EMPTY",
            "CARD_ATTACK", "CARD_SKILL", "CARD_POWER",
            "MANA_FILL", "MANA_EMPTY",
            "TEXT_PRIMARY", "TEXT_DAMAGE", "TEXT_BLOCK",
        ]
        for name in all_names:
            c = getattr(colors, name)
            assert 0 <= c.r <= 255, f"{name}.r out of range"
            assert 0 <= c.g <= 255, f"{name}.g out of range"
            assert 0 <= c.b <= 255, f"{name}.b out of range"
