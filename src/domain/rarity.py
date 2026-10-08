"""Rarity tiers shared by cards and relics, and how luck bends the odds.

Cards and relics use the **same** five tiers (``Rarity``), so a "rare" relic
and a "rare" card mean the same thing. ``CardRarity`` in ``card.py`` is an
alias of this enum.

Luck (``CharacterStats.luck``) does two things, both here:

* ``rarity_weight``: every point of luck multiplies a tier's base weight by
  ``1 + LUCK_TIER_STEP * luck * (tier - 1)``, so higher tiers grow faster and
  Common never changes. Used by ``weighted_sample`` to pick relics.
* ``luck_chroma_multiplier``: chroma (golden) drop chances are multiplied by
  ``1 + LUCK_CHROMA_STEP * luck`` (see ``chroma.roll_chroma``).

Pure domain code: no pygame, no I/O.
"""
from __future__ import annotations

import random
from enum import Enum
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")


class Rarity(Enum):
    COMMON    = 1   # Común
    UNCOMMON  = 2   # Poco común
    RARE      = 3   # Rara
    EPIC      = 4   # Épica
    LEGENDARY = 5   # Legendaria


RARITY_LABEL: dict[Rarity, str] = {
    Rarity.COMMON:    "Común",
    Rarity.UNCOMMON:  "Poco común",
    Rarity.RARE:      "Rara",
    Rarity.EPIC:      "Épica",
    Rarity.LEGENDARY: "Legendaria",
}

# Base weight of each tier with 0 luck (50 / 28 / 14 / 6 / 2 %).
BASE_RARITY_WEIGHT: dict[Rarity, float] = {
    Rarity.COMMON:    50.0,
    Rarity.UNCOMMON:  28.0,
    Rarity.RARE:      14.0,
    Rarity.EPIC:       6.0,
    Rarity.LEGENDARY:  2.0,
}

LUCK_TIER_STEP: float = 0.10     # per luck point, per tier above Common
LUCK_CHROMA_STEP: float = 0.10   # per luck point: +10 % of the base chroma chance


def rarity_label(rarity: Rarity) -> str:
    return RARITY_LABEL[rarity]


def rarity_weight(rarity: Rarity, luck: int = 0) -> float:
    """Weight of ``rarity`` for a given luck (negative luck counts as 0)."""
    return BASE_RARITY_WEIGHT[rarity] * (1.0 + LUCK_TIER_STEP * max(0, luck) * (rarity.value - 1))


def rarity_odds(luck: int = 0, tiers: Sequence[Rarity] | None = None) -> dict[Rarity, float]:
    """Probability of each tier (summing to 1) among ``tiers`` (default: all)."""
    tiers = list(tiers) if tiers is not None else list(Rarity)
    weights = {t: rarity_weight(t, luck) for t in tiers}
    total = sum(weights.values())
    return {t: (w / total if total > 0 else 0.0) for t, w in weights.items()}


# "Carta de la suerte": packs and card rewards may add extra cards thanks to luck.
LUCKY_CARD_LUCK: int = 100       # luck for a sure first lucky card (chance = luck / 100)


def lucky_card_chances(luck: int) -> tuple[float, float]:
    """Chance of a first and of a second lucky extra card (the second needs luck above 100)."""
    luck = max(0, luck)
    first = min(1.0, luck / LUCKY_CARD_LUCK)
    second = min(1.0, max(0, luck - LUCKY_CARD_LUCK) / (2 * LUCKY_CARD_LUCK))
    return first, second


def lucky_card_count(luck: int, rng: random.Random) -> int:
    """How many lucky extra cards a pack or a reward gets (0, 1 or 2; two rng calls)."""
    first, second = lucky_card_chances(luck)
    a, b = rng.random(), rng.random()
    if a >= first:
        return 0
    return 2 if b < second else 1


def luck_chroma_multiplier(luck: int = 0) -> float:
    """Factor applied to every chroma drop chance (1.0 with 0 luck)."""
    return 1.0 + LUCK_CHROMA_STEP * max(0, luck)


def weighted_sample(
    items: Sequence[T],
    count: int,
    rng: random.Random,
    *,
    rarity_of: Callable[[T], Rarity],
    luck: int = 0,
) -> list[T]:
    """Pick up to ``count`` distinct items: first a tier (luck-weighted), then an item of it.

    Only tiers that still have items take part, so an empty tier never wastes a
    pick. Deterministic for a given ``rng`` state.
    """
    remaining = list(items)
    chosen: list[T] = []
    while remaining and len(chosen) < count:
        tiers = sorted({rarity_of(i) for i in remaining}, key=lambda r: r.value)
        weights = [rarity_weight(t, luck) for t in tiers]
        tier = rng.choices(tiers, weights=weights, k=1)[0]
        options = [i for i in remaining if rarity_of(i) is tier]
        pick = rng.choice(options)
        remaining.remove(pick)
        chosen.append(pick)
    return chosen
