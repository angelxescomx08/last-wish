"""Card keywords (Hearthstone style): named rules shared by many cards.

A keyword is data in ``KEYWORD_DEFS`` (name + rule text for tooltips); the rule
itself lives where it resolves. Add a keyword = enum member + definition +
its rule. Current keywords:

* COMBO — an extra effect layer (``CardEffect.combo``) that also resolves when
  you already played another card this turn (``CombatState.cards_played_this_turn``).
  Rogue cards only (see ``card_pool``).
* SINGULAR — an extra effect layer (``CardEffect.singular``) that also resolves
  when the deck you started the combat with has no repeated cards (same card id),
  see ``deck_is_singular`` and ``CombatState.singular_deck`` (fixed for the combat).
* VOID ("Vacío") — an extra effect layer (``CardEffect.void``) that also resolves
  when paying the card's cost leaves your mana at exactly 0 (the card must cost at
  least 1). Mage cards only (see ``card_pool``).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from src.domain.card import Card


class Keyword(Enum):
    COMBO = "combo"
    SINGULAR = "singular"
    VOID = "void"


@dataclass(frozen=True)
class KeywordDef:
    keyword: Keyword
    name: str      # "Combo"
    rule: str      # tooltip explanation


KEYWORD_DEFS: dict[Keyword, KeywordDef] = {
    Keyword.COMBO: KeywordDef(
        Keyword.COMBO, "Combo",
        "Combo: efecto extra si ya jugaste otra carta este turno.",
    ),
    Keyword.SINGULAR: KeywordDef(
        Keyword.SINGULAR, "Singular",
        "Singular: efecto extra si tu mazo inicial no tiene cartas repetidas.",
    ),
    Keyword.VOID: KeywordDef(
        Keyword.VOID, "Vacío",
        "Vacío: efecto extra si al jugarla te quedas con 0 de maná.",
    ),
}


def keyword_def(keyword: Keyword) -> KeywordDef:
    return KEYWORD_DEFS[keyword]


def deck_is_singular(cards: Iterable["Card"]) -> bool:
    """True when no two cards share an id (golden or not, a copy is a repeat). Empty deck: True."""
    ids = [c.id for c in cards]
    return len(ids) == len(set(ids))


def combo_text(card: "Card") -> str:
    """Spanish summary of a card's combo layers as printed: "+5 de daño, roba 1"."""
    return layer_text(card.combo_effects())


def singular_text(card: "Card") -> str:
    """Spanish summary of a card's Singular layers as printed."""
    return layer_text(card.singular_effects())


def void_text(card: "Card") -> str:
    """Spanish summary of a card's Vacío layers as printed."""
    return layer_text(card.void_effects())


def void_triggers(cost: int, mana_before: int) -> bool:
    """Keyword VOID: paying ``cost`` leaves exactly 0 mana (a free card never triggers it)."""
    return cost > 0 and mana_before - cost == 0


def layer_text(effects) -> str:
    """Spanish summary of keyword layers: "+5 de daño, roba 1"."""
    parts: list[str] = []
    for fx in effects:
        dmg, blk = fx.damage.resolve(), fx.block.resolve()
        if dmg:
            parts.append(f"+{dmg} de daño")
        if blk:
            parts.append(f"+{blk} de escudo")
        if fx.draw:
            parts.append(f"roba {fx.draw}")
        if fx.mana_gain:
            parts.append(f"+{fx.mana_gain} de maná")
        if fx.text:
            parts.append(fx.text)
    return ", ".join(parts) or "efecto extra"
