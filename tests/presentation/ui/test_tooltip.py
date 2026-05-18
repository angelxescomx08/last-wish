"""Tests for presentation/ui/tooltip.py — content generators only.

The content generators (card_tooltip, relic_tooltip, enemy_tooltip,
player_tooltip, pile_tooltip, mana_tooltip) return plain TooltipContent
objects with no pygame calls. draw_tooltip() requires a Surface and is
covered by integration tests outside this file.
"""
from __future__ import annotations

import pytest

from src.domain.card import Card, CardEffect, CardModifier, CardType, ModifierTag
from src.domain.entities import Enemy, Intent, IntentType, Player, StatusEffect
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.relic import Relic, RelicTag
from src.presentation.ui.tooltip import (
    TooltipContent,
    card_tooltip,
    enemy_tooltip,
    mana_tooltip,
    pile_tooltip,
    player_tooltip,
    relic_tooltip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attack(damage: int, cost: int = 1, name: str = "Golpe") -> Card:
    return Card(
        id="t", name=name, card_type=CardType.ATTACK, cost=cost,
        base_effect=CardEffect(name, damage=BigValue(damage)),
    )


def _skill(block: int, draw: int = 0) -> Card:
    return Card(
        id="t", name="Defender", card_type=CardType.SKILL, cost=1,
        base_effect=CardEffect("Defender", block=BigValue(block), draw=draw),
    )


def _power() -> Card:
    return Card(
        id="t", name="Poder", card_type=CardType.POWER, cost=0,
        base_effect=CardEffect("Poder"),
    )


def _enemy(hp: int = 50, block: int = 0, intent: Intent | None = None) -> Enemy:
    return Enemy(
        id="e", name="Cultista", max_hp=50, current_hp=hp, block=block,
        intent=intent or Intent(IntentType.ATTACK, 10),
    )


def _player(hp: int = 80, block: int = 0) -> Player:
    return Player(name="Viajero", max_hp=80, current_hp=hp, block=block)


# ---------------------------------------------------------------------------
# TooltipContent dataclass
# ---------------------------------------------------------------------------

class TestTooltipContent:
    def test_stores_title_and_lines(self):
        tc = TooltipContent(title="Hola", lines=["línea 1", "línea 2"])
        assert tc.title == "Hola"
        assert tc.lines == ["línea 1", "línea 2"]

    def test_default_lines_empty(self):
        tc = TooltipContent(title="T")
        assert tc.lines == []


# ---------------------------------------------------------------------------
# card_tooltip()
# ---------------------------------------------------------------------------

class TestCardTooltip:
    def test_title_is_card_name(self):
        tt = card_tooltip(_attack(6))
        assert tt.title == "Golpe"

    def test_title_includes_rota_when_broken(self):
        card = _attack(6)
        card.is_broken = True
        assert "(Rota)" in card_tooltip(card).title

    def test_attack_shows_damage_line(self):
        tt = card_tooltip(_attack(6))
        combined = "\n".join(tt.lines)
        assert "daño" in combined

    def test_skill_shows_block_line(self):
        tt = card_tooltip(_skill(5))
        combined = "\n".join(tt.lines)
        assert "bloqueo" in combined

    def test_power_shows_special_effect_line(self):
        tt = card_tooltip(_power())
        combined = "\n".join(tt.lines)
        assert "efecto" in combined.lower() or "poder" in combined.lower()

    def test_cost_shown_in_lines(self):
        tt = card_tooltip(_attack(6, cost=2))
        combined = "\n".join(tt.lines)
        assert "2" in combined and "maná" in combined

    def test_draw_shown_when_nonzero(self):
        tt = card_tooltip(_skill(5, draw=2))
        combined = "\n".join(tt.lines)
        assert "2" in combined and "carta" in combined

    def test_stacked_effects_section_shown(self):
        card = _attack(6)
        card.stacked_effects.append(CardEffect("Fuego", damage=BigValue(4)))
        tt = card_tooltip(card)
        combined = "\n".join(tt.lines)
        assert "apilado" in combined.lower()

    def test_modifier_shown(self):
        card = _attack(6)
        card.modifiers.append(CardModifier(ModifierTag.CHROMA, stacks=1))
        combined = "\n".join(card_tooltip(card).lines)
        assert "Chroma" in combined

    def test_broken_hint_shown(self):
        card = _attack(6)
        card.is_broken = True
        combined = "\n".join(card_tooltip(card).lines)
        assert "ROTA" in combined or "fusionarse" in combined

    def test_bonus_damage_zero_no_orb_line(self):
        tt = card_tooltip(_attack(6), bonus_damage=0)
        combined = "\n".join(tt.lines)
        assert "Orbe" not in combined

    def test_bonus_damage_shows_orb_line(self):
        tt = card_tooltip(_attack(6), bonus_damage=2)
        combined = "\n".join(tt.lines)
        assert "Orbe de Fuego" in combined

    def test_bonus_damage_adds_to_displayed_value(self):
        tt = card_tooltip(_attack(6), bonus_damage=2)
        combined = "\n".join(tt.lines)
        assert "8" in combined  # 6 + 2

    def test_large_bonus_damage(self):
        tt = card_tooltip(_attack(10**9), bonus_damage=10**9)
        combined = "\n".join(tt.lines)
        assert "Orbe de Fuego" in combined

    def test_returns_tooltip_content(self):
        assert isinstance(card_tooltip(_attack(6)), TooltipContent)


# ---------------------------------------------------------------------------
# relic_tooltip()
# ---------------------------------------------------------------------------

class TestRelicTooltip:
    def test_title_is_relic_name(self):
        r = Relic("r", "Orbe de Fuego", "Daño extra", tag=RelicTag.FIRE_ORB)
        assert relic_tooltip(r).title == "Orbe de Fuego"

    def test_description_in_lines(self):
        r = Relic("r", "N", "Daño extra", tag=RelicTag.FIRE_ORB)
        assert "Daño extra" in relic_tooltip(r).lines

    def test_active_shows_activo(self):
        r = Relic("r", "N", "D", is_active=True)
        combined = "\n".join(relic_tooltip(r).lines)
        assert "Activo" in combined

    def test_inactive_shows_agotado(self):
        r = Relic("r", "N", "D", is_active=False)
        combined = "\n".join(relic_tooltip(r).lines)
        assert "Agotado" in combined

    def test_returns_tooltip_content(self):
        r = Relic("r", "N", "D")
        assert isinstance(relic_tooltip(r), TooltipContent)


# ---------------------------------------------------------------------------
# enemy_tooltip()
# ---------------------------------------------------------------------------

class TestEnemyTooltip:
    def test_title_is_enemy_name(self):
        assert enemy_tooltip(_enemy()).title == "Cultista"

    def test_hp_shown(self):
        combined = "\n".join(enemy_tooltip(_enemy(hp=30)).lines)
        assert "30" in combined

    def test_block_shown_when_nonzero(self):
        combined = "\n".join(enemy_tooltip(_enemy(block=8)).lines)
        assert "8" in combined and "Bloqueo" in combined

    def test_block_not_shown_when_zero(self):
        combined = "\n".join(enemy_tooltip(_enemy(block=0)).lines)
        assert "Bloqueo" not in combined

    def test_attack_intent_shown(self):
        e = _enemy(intent=Intent(IntentType.ATTACK, 12))
        combined = "\n".join(enemy_tooltip(e).lines)
        assert "12" in combined

    def test_block_intent_shown(self):
        e = _enemy(intent=Intent(IntentType.BLOCK, 8))
        combined = "\n".join(enemy_tooltip(e).lines)
        assert "8" in combined

    def test_buff_intent_shown(self):
        e = _enemy(intent=Intent(IntentType.BUFF, 0))
        combined = "\n".join(enemy_tooltip(e).lines)
        assert "fortalec" in combined.lower()

    def test_status_effects_shown(self):
        e = _enemy()
        e.status_effects = [StatusEffect("Vulnerable", 2, is_buff=False)]
        combined = "\n".join(enemy_tooltip(e).lines)
        assert "Vulnerable" in combined

    def test_returns_tooltip_content(self):
        assert isinstance(enemy_tooltip(_enemy()), TooltipContent)


# ---------------------------------------------------------------------------
# player_tooltip()
# ---------------------------------------------------------------------------

class TestPlayerTooltip:
    def test_title_is_player_name(self):
        assert player_tooltip(_player()).title == "Viajero"

    def test_hp_shown(self):
        combined = "\n".join(player_tooltip(_player(hp=65)).lines)
        assert "65" in combined

    def test_block_shown_when_nonzero(self):
        combined = "\n".join(player_tooltip(_player(block=5)).lines)
        assert "5" in combined and "Bloqueo" in combined

    def test_no_block_message_when_zero(self):
        combined = "\n".join(player_tooltip(_player(block=0)).lines)
        assert "bloqueo" in combined.lower()

    def test_status_effects_shown(self):
        p = _player()
        p.status_effects = [StatusEffect("Fuerza", 3, is_buff=True)]
        combined = "\n".join(player_tooltip(p).lines)
        assert "Fuerza" in combined

    def test_returns_tooltip_content(self):
        assert isinstance(player_tooltip(_player()), TooltipContent)


# ---------------------------------------------------------------------------
# pile_tooltip()
# ---------------------------------------------------------------------------

class TestPileTooltip:
    def test_draw_pile_title(self):
        tt = pile_tooltip("ROBO", 10, is_draw=True)
        assert "Robo" in tt.title

    def test_discard_pile_title(self):
        tt = pile_tooltip("DESCARTE", 3, is_draw=False)
        assert "Descarte" in tt.title

    def test_draw_count_shown(self):
        combined = "\n".join(pile_tooltip("ROBO", 7, is_draw=True).lines)
        assert "7" in combined

    def test_discard_count_shown(self):
        combined = "\n".join(pile_tooltip("DESCARTE", 4, is_draw=False).lines)
        assert "4" in combined

    def test_zero_count(self):
        combined = "\n".join(pile_tooltip("ROBO", 0, is_draw=True).lines)
        assert "0" in combined

    def test_returns_tooltip_content(self):
        assert isinstance(pile_tooltip("ROBO", 5, is_draw=True), TooltipContent)


# ---------------------------------------------------------------------------
# mana_tooltip()
# ---------------------------------------------------------------------------

class TestManaTooltip:
    def test_title_contains_mana(self):
        assert "Maná" in mana_tooltip(Mana(current=3, maximum=3)).title

    def test_current_and_max_shown(self):
        combined = "\n".join(mana_tooltip(Mana(current=2, maximum=4)).lines)
        assert "2" in combined and "4" in combined

    def test_zero_mana(self):
        combined = "\n".join(mana_tooltip(Mana(current=0, maximum=3)).lines)
        assert "0" in combined

    def test_returns_tooltip_content(self):
        assert isinstance(mana_tooltip(Mana(current=3, maximum=3)), TooltipContent)
