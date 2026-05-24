"""Factory that builds a fresh CombatState from a selected Character.

All characters start at full health; enemies also begin at full HP so
every run is fair regardless of the chosen character.
"""
from __future__ import annotations

from src.application.end_turn import draw_opening_hand
from src.domain.card import Card, CardEffect, CardModifier, CardType, ModifierTag
from src.domain.character import Character
from src.domain.combat import CombatState
from src.domain.entities import Enemy, Intent, IntentType, Player
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic, RelicTag


# ---------------------------------------------------------------------------
# Internal card factories (mirrors combat_manager for consistency)
# ---------------------------------------------------------------------------

def _attack(id: str, name: str, cost: int, damage: int) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.ATTACK, cost=cost,
        base_effect=CardEffect(name=name, damage=BigValue(damage)),
    )


def _skill(id: str, name: str, cost: int, block: int, draw: int = 0) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.SKILL, cost=cost,
        base_effect=CardEffect(name=name, block=BigValue(block), draw=draw),
    )


def _power(id: str, name: str, cost: int) -> Card:
    return Card(
        id=id, name=name, card_type=CardType.POWER, cost=cost,
        base_effect=CardEffect(name=name),
    )


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def create_combat_for_character(character: Character) -> CombatState:
    """Return a fresh CombatState for the given character with all entities at full HP."""
    player = Player(
        name=character.name,
        max_hp=character.stats.max_hp,
        current_hp=character.stats.max_hp,
        dexterity=character.stats.dexterity,
        attack_bonus=character.stats.damage,
        luck=character.stats.luck,
    )

    mana = Mana(
        current=character.stats.max_mana,
        maximum=character.stats.max_mana,
    )

    enemies: list[Enemy] = [
        Enemy(
            id="e1", name="Cultista",
            max_hp=60, current_hp=60,
            intent=Intent(IntentType.ATTACK, 12),
        ),
        Enemy(
            id="e2", name="Guardián",
            max_hp=40, current_hp=40,
            intent=Intent(IntentType.BLOCK, 8),
        ),
        Enemy(
            id="e3", name="Brujo",
            max_hp=35, current_hp=35,
            intent=Intent(IntentType.BUFF, 0),
        ),
    ]

    relics: list[Relic] = [
        Relic("r1", "Amuleto de Combate",
              "Ganas 1 maná extra al inicio del combate.",
              tag=RelicTag.COMBAT_AMULET),
        Relic("r2", "Tótem Roto",
              "Robas 1 carta adicional al inicio de cada turno.",
              tag=RelicTag.BROKEN_TOTEM),
        Relic("r3", "Orbe de Fuego",
              "Tus ataques infligen 2 de daño extra.",
              tag=RelicTag.FIRE_ORB),
        Relic("r4", "Escudo Espectral",
              "Al recibir daño fatal, sobrevives con 1 HP.",
              tag=RelicTag.SPECTRAL_SHIELD),
    ]

    stacked_card = _attack("strike_stacked", "Golpe", 1, 6)
    stacked_card.stacked_effects.append(
        CardEffect("Chroma Fuego", damage=BigValue(4).add_multiplier(2))
    )
    stacked_card.modifiers.append(CardModifier(ModifierTag.CHROMA, stacks=1))

    all_cards: list[Card] = [
        _attack("s1",   "Golpe",        1, 6),
        _attack("s2",   "Golpe",        1, 6),
        _skill( "d1",   "Defender",     1, 5),
        _attack("bash", "Embate",       2, 8),
        _skill( "d2",   "Defender",     1, 5),
        _power( "fx",   "Flexibilidad", 0),
        stacked_card,
        *[_attack(f"dr{i}", "Golpe", 1, 6) for i in range(10)],
    ]

    state = CombatState(
        player=player,
        enemies=enemies,
        hand=Hand(cards=[]),
        draw_pile=DrawPile(cards=all_cards),
        discard_pile=DiscardPile(cards=[]),
        mana=mana,
        relics=relics,
        turn=1,
    )

    draw_opening_hand(state)
    return state
