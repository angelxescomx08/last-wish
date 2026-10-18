"""Deck choices asked by relics when you get them (``Run.pending_choices``). No pygame.

* ``"remove"`` (Tijeras del Sastre): the chosen cards leave the deck for good; the deck
  never drops below ``purge.MIN_DECK``.
* ``"innate"`` (Cartas Marcadas): the chosen cards get ``Card.innate`` — every combat they
  are put on top of the draw pile, so they start in your hand.
"""
from __future__ import annotations

from src.application.purge import MIN_DECK
from src.domain.run import Run


def choice_limit(run: Run, kind: str, count: int) -> int:
    """How many cards may be chosen (never more than the deck allows)."""
    if kind == "remove":
        return max(0, min(count, len(run.deck) - MIN_DECK))
    return max(0, min(count, len(run.deck)))


def apply_choice(run: Run, kind: str, indices: list[int]) -> int:
    """Apply a choice; invalid or repeated indices are ignored. Returns the cards affected."""
    valid = sorted({i for i in indices if 0 <= i < len(run.deck)})
    valid = valid[:choice_limit(run, kind, len(valid))]
    if kind == "remove":
        for i in reversed(valid):
            run.deck.pop(i)
    elif kind == "innate":
        for i in valid:
            run.deck[i].innate = True
    return len(valid)


def next_choice(run: Run) -> tuple[str, int] | None:
    """Take the next pending choice (None when there is none)."""
    return run.pending_choices.pop(0) if run.pending_choices else None
