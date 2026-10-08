"""The numbers a card shows outside the hand: printed value + the hero's stats.

In combat a card shows its *effective* damage and block (printed + the hero's Ataque
and Orbe de Fuego / Destreza). Every other place a card can be seen — rewards, pack
openings, El Brujo, the deck and pile viewers — must show the same numbers, otherwise
a card looks weaker when you pick it than once it is in your hand.

* ``run_card_bonus(run)`` — bonuses from the character, Pruebas and relics.
* ``combat_card_bonus(state)`` — live combat bonuses (cards may have raised them).
* ``CardBonus.for_card(card)`` — ``(bonus_damage, bonus_block)`` for that card (a card
  with no damage gets no damage bonus, same rule as the combat hand).

Per-turn extras (Combo scarf, Afilar's next-damage bonus) are only shown in the hand.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.application import relic_effects
from src.domain.card import Card
from src.domain.combat import CombatState
from src.domain.run import Run
from src.domain.tuning import TUNING


@dataclass(frozen=True)
class CardBonus:
    attack: int = 0
    block: int = 0

    def for_card(self, card: Card) -> tuple[int, int]:
        return (self.attack if card.total_damage() > 0 else 0,
                self.block if card.total_block() > 0 else 0)


NO_BONUS = CardBonus()


def run_card_bonus(run: Run | None) -> CardBonus:
    if run is None:
        return NO_BONUS
    stats = run.character.stats
    return CardBonus(
        attack=stats.damage + TUNING.extra_damage + relic_effects.extra_attack_damage(run.relics),
        block=stats.dexterity + TUNING.extra_dexterity,
    )


def combat_card_bonus(state: CombatState) -> CardBonus:
    return CardBonus(
        attack=state.player.attack_bonus + relic_effects.extra_attack_damage(state.relics),
        block=state.player.dexterity,
    )
