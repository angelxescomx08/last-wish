"""Altar de Purga: remove one card of your choice from the deck for gold (one altar per floor).

Each altar lets you remove **one** card per visit. The price grows with every card
removed this run (``Run.cards_removed``): ``PURGE_BASE + PURGE_STEP × removed``, and the
Máscara del Ladrón discounts it like any shop price. The deck never goes below
``MIN_DECK`` cards. No pygame.
"""
from __future__ import annotations

from src.application.run_manager import shop_price
from src.domain.card import Card
from src.domain.run import Run

PURGE_BASE = 75
PURGE_STEP = 25
MIN_DECK = 1                  # you always keep at least one card


def purge_price(run: Run) -> int:
    """What removing a card costs now (rises 25 per card already removed this run)."""
    return shop_price(run, PURGE_BASE + PURGE_STEP * max(0, run.cards_removed))


def purge_block_reason(run: Run) -> str:
    """Spanish reason why no card can be removed now, or "" when it is possible."""
    if len(run.deck) <= MIN_DECK:
        return "Es tu última carta: tu mazo no puede quedarse vacío"
    if run.gold < purge_price(run):
        return "No tienes suficiente oro"
    return ""


def can_purge(run: Run) -> bool:
    return purge_block_reason(run) == ""


def purge_card(run: Run, index: int) -> Card | None:
    """Pay and remove ``run.deck[index]``. Returns the removed card, or None (nothing changes)."""
    if not 0 <= index < len(run.deck) or not can_purge(run):
        return None
    run.gold -= purge_price(run)
    run.cards_removed += 1
    return run.deck.pop(index)
