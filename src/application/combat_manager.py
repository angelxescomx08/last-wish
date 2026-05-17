from __future__ import annotations

from src.domain.card import Card, CardEffect, CardModifier, CardType, ModifierTag
from src.domain.combat import CombatState
from src.domain.entities import Enemy, Intent, IntentType, Player, StatusEffect
from src.domain.mana import Mana
from src.domain.numbers import BigValue
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic


# ---------------------------------------------------------------------------
# Card factories
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
# Sample state — showcases all UI elements
# ---------------------------------------------------------------------------

def create_sample_combat() -> CombatState:
    relics: list[Relic] = [
        Relic("r1", "Amuleto de Combate",  "Ganas 1 maná extra al inicio del combate"),
        Relic("r2", "Tótem Roto",          "+1 carta al robar cada turno"),
        Relic("r3", "Orbe de Fuego",       "Tus ataques hacen 2 de daño extra"),
        Relic("r4", "Escudo Espectral",    "Al recibir daño fatal, sobrevives con 1 HP"),
    ]

    player = Player(
        name="Viajero",
        max_hp=80,
        current_hp=65,
        block=5,
        status_effects=[
            StatusEffect("Fuerza", 2, is_buff=True),
        ],
    )

    enemies: list[Enemy] = [
        Enemy(
            id="e1", name="Cultista",
            max_hp=60, current_hp=45, block=0,
            intent=Intent(IntentType.ATTACK, 12),
            status_effects=[StatusEffect("Vulnerable", 2, is_buff=False)],
        ),
        Enemy(
            id="e2", name="Guardián",
            max_hp=40, current_hp=40, block=8,
            intent=Intent(IntentType.BLOCK, 8),
        ),
        Enemy(
            id="e3", name="Brujo",
            max_hp=35, current_hp=20, block=0,
            intent=Intent(IntentType.BUFF, 0),
            status_effects=[StatusEffect("Ritual", 1, is_buff=True)],
        ),
    ]

    # Build a hand that shows all card types and modifiers
    broken_card = _attack("slash_broken", "Tajo", 1, 9)
    broken_card.is_broken = True

    stacked_card = _attack("strike_stacked", "Golpe", 1, 6)
    stacked_card.stacked_effects.append(
        CardEffect("Chroma Fuego", damage=BigValue(4).add_multiplier(2))
    )
    stacked_card.modifiers.append(CardModifier(ModifierTag.CHROMA, stacks=1))

    hand_cards: list[Card] = [
        _attack("s1", "Golpe",       1, 6),
        _attack("s2", "Golpe",       1, 6),
        _skill( "d1", "Defender",    1, 5),
        _attack("bash","Embate",     2, 8),
        _skill( "d2", "Defender",    1, 5),
        _power( "fx", "Flexibilidad",0),
        stacked_card,
        broken_card,
    ]

    draw_cards  = [_attack(f"dr{i}", "Golpe",   1, 6) for i in range(10)]
    discard_cards = [_skill(f"dc{i}", "Defender", 1, 5) for i in range(3)]

    return CombatState(
        player=player,
        enemies=enemies,
        hand=Hand(cards=hand_cards),
        draw_pile=DrawPile(cards=draw_cards),
        discard_pile=DiscardPile(cards=discard_cards),
        mana=Mana(current=3, maximum=3),
        relics=relics,
        turn=1,
    )
