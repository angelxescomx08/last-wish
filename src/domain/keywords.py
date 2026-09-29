"""Card keywords (Hearthstone style): named rules shared by many cards.

A keyword is data in ``KEYWORD_DEFS`` (name + rule text for tooltips); the rule
itself lives where it resolves. Add a keyword = enum member + definition +
its rule. Current keywords:

* COMBO — an extra effect layer (``CardEffect.combo``) that also resolves when
  you already played another card this turn (``CombatState.cards_played_this_turn``).
  Rogue cards only (see ``card_pool``).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.card import Card


class Keyword(Enum):
    COMBO = "combo"


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
}


def keyword_def(keyword: Keyword) -> KeywordDef:
    return KEYWORD_DEFS[keyword]


def combo_text(card: "Card") -> str:
    """Spanish summary of a card's combo layers as printed: "+5 de daño, roba 1"."""
    parts: list[str] = []
    for fx in card.combo_effects():
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
