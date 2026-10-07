"""Status cards: junk that enemies put into the hero's deck during a combat.

They are never part of the run deck — ``create_combat_from_run`` copies the deck
into the piles, and these cards are added to those piles only — so they vanish
when the combat ends.

* **Espora** (La Reina Micélida): costs 1 and is exhausted when played (pay mana to
  get rid of it); if it is still in your hand at the end of your turn you get 3 Veneno.
* **Moho** (La Reina Micélida): unplayable; drawing it drains 1 mana; it fades at the
  end of the turn (ethereal), so each Moho is a one-time tax.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from src.domain.card import Card, CardEffect, CardType
from src.domain.entities import POISON, add_status

if TYPE_CHECKING:
    from src.domain.combat import CombatState

SPORE_ID = "status_espora"
MOLD_ID = "status_moho"
SPORE_POISON = 3        # Veneno taken when an Espora is still in hand at the end of the turn
MOLD_MANA_DRAIN = 1     # mana lost when a Moho is drawn


def _spore_poison(state: CombatState) -> None:
    add_status(state.player.status_effects, POISON, SPORE_POISON, is_buff=False)


def _mold_drain(state: CombatState) -> None:
    state.mana.spend(MOLD_MANA_DRAIN)


def spore() -> Card:
    return Card(
        id=SPORE_ID, name="Espora", card_type=CardType.STATUS, cost=1,
        base_effect=CardEffect(
            name="Espora",
            text=f"Agotar. Si sigue en tu mano al final del turno, recibes {SPORE_POISON} de Veneno"),
        exhaust=True, on_turn_end_in_hand=_spore_poison, max_upgrades=0,
    )


def mold() -> Card:
    return Card(
        id=MOLD_ID, name="Moho", card_type=CardType.STATUS, cost=0,
        base_effect=CardEffect(
            name="Moho",
            text=f"Injugable. Al robarla pierdes {MOLD_MANA_DRAIN} de maná. Se desvanece al final del turno"),
        unplayable=True, ethereal=True, on_draw=_mold_drain, max_upgrades=0,
    )


STATUS_CARD_FACTORIES: dict[str, Callable[[], Card]] = {
    SPORE_ID: spore,
    MOLD_ID: mold,
}


def make_status_card(card_id: str) -> Card | None:
    factory = STATUS_CARD_FACTORIES.get(card_id)
    return factory() if factory else None
