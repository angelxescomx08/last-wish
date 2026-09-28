"""Tests for presentation/ui/card_widget.py.

draw_card() renders directly onto a pygame.Surface. All tests here
require a real pygame display context (headless rendering via an off-screen
Surface). The session fixture in conftest.py initialises pygame so
Surface creation works without an open window.
"""
from __future__ import annotations

import pygame
import pytest

from src.domain.card import Card, CardEffect, CardType
from src.domain.numbers import BigValue
from src.presentation.ui.card_widget import CARD_H, CARD_W, draw_card
from src.infrastructure.fonts import FontRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _surface() -> pygame.Surface:
    return pygame.Surface((400, 300))


def _fonts() -> FontRegistry:
    return FontRegistry()


def _attack(damage: int = 6) -> Card:
    return Card(
        id="t", name="Golpe", card_type=CardType.ATTACK, cost=1,
        base_effect=CardEffect("Golpe", damage=BigValue(damage)),
    )


def _skill(block: int = 5) -> Card:
    return Card(
        id="t", name="Defender", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect("Defender", block=BigValue(block)),
    )


def _power() -> Card:
    return Card(
        id="t", name="Poder", card_type=CardType.POWER, cost=0,
        base_effect=CardEffect("Poder"),
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestCardWidgetConstants:
    def test_card_width_positive(self):
        assert CARD_W > 0

    def test_card_height_positive(self):
        assert CARD_H > 0

    def test_card_taller_than_wide(self):
        assert CARD_H > CARD_W


# ---------------------------------------------------------------------------
# draw_card() — return value
# ---------------------------------------------------------------------------

class TestDrawCardReturn:
    def test_returns_rect(self):
        rect = draw_card(_surface(), _attack(), 10, 10, _fonts())
        assert isinstance(rect, pygame.Rect)

    def test_rect_width_matches_card_w(self):
        rect = draw_card(_surface(), _attack(), 10, 10, _fonts())
        assert rect.width == CARD_W

    def test_rect_height_matches_card_h(self):
        rect = draw_card(_surface(), _attack(), 10, 10, _fonts())
        assert rect.height == CARD_H

    def test_rect_x_matches_requested(self):
        rect = draw_card(_surface(), _attack(), 50, 100, _fonts())
        assert rect.x == 50

    def test_rect_y_matches_when_not_hovered(self):
        rect = draw_card(_surface(), _attack(), 50, 100, _fonts())
        assert rect.y == 100

    def test_hovered_rect_y_lifted(self):
        base = draw_card(_surface(), _attack(), 50, 100, _fonts())
        hovered = draw_card(_surface(), _attack(), 50, 100, _fonts(), hovered=True)
        assert hovered.y < base.y

    def test_selected_rect_y_lifted(self):
        base = draw_card(_surface(), _attack(), 50, 100, _fonts())
        selected = draw_card(_surface(), _attack(), 50, 100, _fonts(), selected=True)
        assert selected.y < base.y


# ---------------------------------------------------------------------------
# draw_card() — does not crash for any card type
# ---------------------------------------------------------------------------

class TestDrawCardSmoke:
    def test_attack_card(self):
        draw_card(_surface(), _attack(), 0, 0, _fonts())

    def test_skill_card(self):
        draw_card(_surface(), _skill(), 0, 0, _fonts())

    def test_power_card(self):
        draw_card(_surface(), _power(), 0, 0, _fonts())

    def test_broken_card(self):
        card = _attack()
        card.is_broken = True
        draw_card(_surface(), card, 0, 0, _fonts())

    def test_unaffordable_card(self):
        draw_card(_surface(), _attack(), 0, 0, _fonts(), affordable=False)

    def test_bonus_damage_zero(self):
        draw_card(_surface(), _attack(), 0, 0, _fonts(), bonus_damage=0)

    def test_bonus_damage_nonzero(self):
        draw_card(_surface(), _attack(), 0, 0, _fonts(), bonus_damage=2)

    def test_large_bonus_damage(self):
        draw_card(_surface(), _attack(10**9), 0, 0, _fonts(), bonus_damage=10**9)


# ---------------------------------------------------------------------------
# cards-v2 frames: dynamic content, rarity frames, caching
# ---------------------------------------------------------------------------

from src.domain.card import CardRarity  # noqa: E402
from src.presentation.ui.card_widget import _ability_lines, render_card_surface  # noqa: E402


def _bytes(surface):
    return pygame.image.tobytes(surface, "RGBA")


class TestDynamicContent:
    def test_effect_text_uses_effective_damage(self):
        assert _ability_lines(_attack(6), damage=8)[0] == "Inflige 8 de daño."

    def test_effect_text_formats_huge_values(self):
        assert _ability_lines(_attack(), damage=2 * 10**9)[0] == "Inflige 2.0B de daño."

    def test_block_text(self):
        assert _ability_lines(_skill(5), block=5) == ["Gana 5 de escudo."]

    def test_power_text(self):
        assert _ability_lines(_power()) == ["Poder permanente."]

    def test_surface_is_cached_for_the_same_state(self):
        fonts = _fonts()
        assert render_card_surface(_attack(), fonts) is render_card_surface(_attack(), fonts)

    def test_bonus_damage_redraws_the_card(self):
        fonts = _fonts()
        assert _bytes(render_card_surface(_attack(), fonts)) != _bytes(render_card_surface(_attack(), fonts, bonus_damage=2))

    def test_cost_change_redraws_the_card(self):
        fonts = _fonts()
        cheap, pricey = _attack(), _attack()
        pricey.cost = 3
        assert _bytes(render_card_surface(cheap, fonts)) != _bytes(render_card_surface(pricey, fonts))

    def test_rarity_changes_the_frame(self):
        fonts = _fonts()
        common, legendary = _attack(), _attack()
        legendary.rarity = CardRarity.LEGENDARY
        assert _bytes(render_card_surface(common, fonts)) != _bytes(render_card_surface(legendary, fonts))

    def test_unaffordable_card_is_darker(self):
        fonts = _fonts()
        lit = render_card_surface(_attack(), fonts)
        dim = render_card_surface(_attack(), fonts, affordable=False)
        pt = (CARD_W // 2, CARD_H * 3 // 10)
        assert sum(dim.get_at(pt)[:3]) < sum(lit.get_at(pt)[:3])

    def test_card_surface_has_card_size(self):
        assert render_card_surface(_skill(), _fonts()).get_size() == (CARD_W, CARD_H)

    def test_stress_many_states_keep_cache_bounded(self):
        from src.presentation.ui import card_widget
        fonts = _fonts()
        for bonus in range(400):
            render_card_surface(_attack(), fonts, bonus_damage=bonus)
        assert len(card_widget._cache) <= card_widget._CACHE_MAX
