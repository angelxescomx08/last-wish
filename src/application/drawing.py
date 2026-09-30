"""Drawing cards during combat (shared by turn start and card effects).

``draw_one`` reshuffles the discard pile into the draw pile when it runs out.
A card with ``play_on_draw`` is not added to the hand: it resolves for free the
moment it is drawn (each cast of its on_play effects) and leaves the combat.
"""
from __future__ import annotations

import random

from src.domain.card import Card
from src.domain.combat import CombatState


def draw_one(state: CombatState) -> Card | None:
    """Draw the top card. Returns it, or None if nothing could be drawn."""
    if state.draw_pile.count == 0:
        if state.discard_pile.count == 0:
            return None
        state.draw_pile.cards = list(state.discard_pile.cards)
        random.shuffle(state.draw_pile.cards)
        state.discard_pile.cards.clear()
    if state.draw_pile.count == 0 or state.hand.is_full:
        return None
    card = state.draw_pile.cards.pop()
    if card.play_on_draw:
        _play_on_draw(state, card)
    else:
        state.hand.cards.append(card)
    return card


def draw_cards(state: CombatState, count: int) -> None:
    for _ in range(max(0, count)):
        if draw_one(state) is None:
            break


def _play_on_draw(state: CombatState, card: Card) -> None:
    for _ in range(card.casts()):
        for fx in card.all_effects():
            if fx.on_play is not None:
                fx.on_play(state)
