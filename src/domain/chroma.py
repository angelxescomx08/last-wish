"""Chromas — special finishes for cards and relics (golden, and more later).

A chroma is data + rules looked up in ``CHROMA_DEFS``, so a new kind is one
enum member and one ``ChromaDef``; nothing else has to learn about it:

* ``effect_multiplier``: a card is **cast that many times** when played (its
  printed stats stay normal; each cast is complete — damage with bonuses,
  block, draw, mana, on_play, combo). Relics multiply their numeric effects
  (bonuses, heals, charges). Packs let you keep that many cards. Golden = x2.
* ``card_note`` / ``relic_note`` are the Spanish lines shown in tooltips.
* ``card_drop_chance`` / ``relic_drop_chance`` / ``pack_drop_chance`` drive
  ``roll_chroma`` (overridable from the Pruebas screen, ``domain/tuning.py``);
  the hero's luck multiplies them (``rarity.luck_chroma_multiplier``).
* On a pack the multiplier is the number of cards you keep (golden: pick 2).
* ``on_card_played`` is an optional hook for chromas that will "do weird
  things": it runs after the card fully resolves with ``(state, card)``.

Visual styles live in ``src/presentation/fx/chroma_fx.py`` (keyed by Chroma).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable

from src.domain.rarity import luck_chroma_multiplier

if TYPE_CHECKING:
    from src.domain.card import Card
    from src.domain.combat import CombatState


class Chroma(Enum):
    GOLDEN = "golden"


@dataclass(frozen=True)
class ChromaDef:
    chroma: Chroma
    name: str                      # adjective shown in titles, e.g. "Dorada"
    card_note: str                 # tooltip line for cards
    relic_note: str                # tooltip line for relics
    short_note: str                # compact line for small tiles
    pack_note: str = ""            # line for a pack with this chroma
    name_masc: str = ""            # masculine adjective ("Dorado") for packs
    effect_multiplier: int = 1
    card_drop_chance: float = 0.0  # chance a generated card gets this chroma
    relic_drop_chance: float = 0.0
    pack_drop_chance: float = 0.0
    on_card_played: Callable[["CombatState", "Card"], None] | None = None


CHROMA_DEFS: dict[Chroma, ChromaDef] = {
    Chroma.GOLDEN: ChromaDef(
        chroma=Chroma.GOLDEN,
        name="Dorada",
        card_note="Dorada: al jugarla se lanza 2 veces (su efecto completo x2).",
        relic_note="Dorada: por ser dorada, sus efectos son x2.",
        short_note="Dorada: efectos x2",
        pack_note="Dorado: eliges 2 cartas (x2).",
        name_masc="Dorado",
        effect_multiplier=2,
        card_drop_chance=0.05,
        relic_drop_chance=0.08,
        pack_drop_chance=0.06,
    ),
}


def chroma_def(chroma: Chroma) -> ChromaDef:
    return CHROMA_DEFS[chroma]


def effect_multiplier(chroma: Chroma | None) -> int:
    """How many times stronger the effects are (1 without chroma)."""
    return 1 if chroma is None else CHROMA_DEFS[chroma].effect_multiplier


def chroma_title(name: str, chroma: Chroma | None, *, masculine: bool = False) -> str:
    """Display title: ``"Golpe · Dorada"`` / ``"Sobre de Acero · Dorado"`` (unchanged without chroma)."""
    if chroma is None:
        return name
    d = CHROMA_DEFS[chroma]
    return f"{name} · {d.name_masc if masculine and d.name_masc else d.name}"


def roll_chroma(
    rng: random.Random, *, for_relic: bool = False, kind: str | None = None, luck: int = 0,
) -> Chroma | None:
    """Draw at most one chroma (one rng call). ``kind``: "card" (default), "relic" or "pack".

    Chances come from ``tuning.chroma_chance`` (Pruebas overrides or the definition)
    and are multiplied by ``rarity.luck_chroma_multiplier(luck)`` (capped at 100 %).
    """
    from src.domain.tuning import chroma_chance   # local: tuning imports this module
    kind = kind or ("relic" if for_relic else "card")
    boost = luck_chroma_multiplier(luck)
    roll = rng.random()
    acc = 0.0
    for chroma in CHROMA_DEFS:
        acc += min(1.0, chroma_chance(chroma, kind) * boost)
        if roll < acc:
            return chroma
    return None
