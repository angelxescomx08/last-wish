"""Factories that build CombatState objects.

create_combat_for_character — standalone combat (testing / sample run, no relics).
create_combat_from_run      — combat inside a full run (uses run deck and relics).
"""
from __future__ import annotations

from src.application.end_turn import draw_opening_hand
from src.domain.card import Card, CardEffect, CardModifier, CardType, ModifierTag
from src.domain.card_pool import starter_deck
from src.domain.character import Character
from src.domain.combat import CombatState
from src.domain.entities import Enemy, Intent, IntentType, Player
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic
from src.domain.run import Run


# ---------------------------------------------------------------------------
# Internal card factories (kept for backwards-compat / combat_manager)
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
# Standalone combat (no relics) — dev / testing
# ---------------------------------------------------------------------------

def create_combat_for_character(character: Character) -> CombatState:
    """Return a fresh CombatState for the given character with no starting relics."""
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
        relics=[],
        turn=1,
    )

    draw_opening_hand(state)
    return state


# ---------------------------------------------------------------------------
# Run-backed combat — used during actual gameplay
# ---------------------------------------------------------------------------

def create_combat_from_run(run: Run, enemies: list[Enemy]) -> CombatState:
    """Build a CombatState for the next room in the given run.

    Player stats are derived from character stats (HP carried over from run).
    Relics and deck come from the run.  Enemy list is supplied by run_manager.
    """
    from src.application import relic_effects  # local import to avoid cycle

    base_max_hp = run.character.stats.max_hp + relic_effects.max_hp_bonus(run.relics)
    player = Player(
        name=run.character.name,
        max_hp=base_max_hp,
        current_hp=min(run.player_current_hp, base_max_hp),
        dexterity=run.character.stats.dexterity,
        attack_bonus=run.character.stats.damage,
        luck=run.character.stats.luck,
    )

    mana = Mana(
        current=run.character.stats.max_mana,
        maximum=run.character.stats.max_mana,
    )

    import copy
    deck_copy = [copy.copy(card) for card in run.deck]

    state = CombatState(
        player=player,
        enemies=enemies,
        hand=Hand(cards=[]),
        draw_pile=DrawPile(cards=deck_copy),
        discard_pile=DiscardPile(cards=[]),
        mana=mana,
        relics=list(run.relics),
        turn=1,
    )

    draw_opening_hand(state)
    return state
