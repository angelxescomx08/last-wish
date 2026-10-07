"""Gachapón rules: two kinds of pull, their tier odds and their rising prices.

The machine sells random relics. Every pull, of either kind, makes the next one
more expensive for the rest of the run (``Run.gacha_pulls``), so relics can
never be bought without limit:

    price(kind, pulls) = base(kind) × PRICE_GROWTH ** pulls   (rounded to 5)

* **Tirada normal** — the usual relic odds (``rarity.BASE_RARITY_WEIGHT``:
  50 / 28 / 14 / 6 / 2 %), bent by luck like any relic drop.
* **Tirada estelar** — costs more and never gives a Común: base weights
  0 / 40 / 34 / 18 / 8 %, also bent by luck, and twice the golden chance.

Tiers without relics left in the pool drop out and the rest share their weight,
so a pull never "misses". Pure domain code: no pygame, no I/O.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence, TypeVar

from src.domain.rarity import LUCK_TIER_STEP, Rarity

T = TypeVar("T")


class PullKind(Enum):
    NORMAL = "normal"
    STELLAR = "stellar"


@dataclass(frozen=True)
class PullDef:
    kind: PullKind
    name: str                              # Spanish button label
    base_price: int
    weights: dict[Rarity, float]           # base tier weights (0 luck)
    chroma_boost: float                    # multiplies the golden chance
    note: str                              # Spanish one-liner under the button


PRICE_GROWTH: float = 1.5                  # each pull (any kind) costs ×1.5 more afterwards

PULLS: dict[PullKind, PullDef] = {
    PullKind.NORMAL: PullDef(
        PullKind.NORMAL, "Tirada normal", 80,
        {Rarity.COMMON: 50.0, Rarity.UNCOMMON: 28.0, Rarity.RARE: 14.0,
         Rarity.EPIC: 6.0, Rarity.LEGENDARY: 2.0},
        1.0, "Probabilidades de siempre."),
    PullKind.STELLAR: PullDef(
        PullKind.STELLAR, "Tirada estelar", 190,
        {Rarity.COMMON: 0.0, Rarity.UNCOMMON: 40.0, Rarity.RARE: 34.0,
         Rarity.EPIC: 18.0, Rarity.LEGENDARY: 8.0},
        2.0, "Nunca Común · doble de dorada."),
}


def pull_price(kind: PullKind, pulls_done: int) -> int:
    """Price of the next ``kind`` pull after ``pulls_done`` pulls this run (multiple of 5)."""
    raw = PULLS[kind].base_price * PRICE_GROWTH ** max(0, pulls_done)
    return max(5, int(round(raw / 5.0)) * 5)


def tier_weight(kind: PullKind, rarity: Rarity, luck: int = 0) -> float:
    """Weight of a tier for this pull kind; luck lifts higher tiers like any relic drop."""
    base = PULLS[kind].weights.get(rarity, 0.0)
    return base * (1.0 + LUCK_TIER_STEP * max(0, luck) * (rarity.value - 1))


def pull_odds(kind: PullKind, luck: int = 0,
              tiers: Sequence[Rarity] | None = None) -> dict[Rarity, float]:
    """Probability of each tier (sums to 1 over ``tiers`` that have weight; all tiers by default)."""
    tiers = list(tiers) if tiers is not None else list(Rarity)
    weights = {t: tier_weight(kind, t, luck) for t in tiers}
    total = sum(weights.values())
    if total <= 0:                          # e.g. stellar pull with only Común relics left
        weights = {t: 1.0 for t in tiers}
        total = float(len(tiers)) or 1.0
    return {t: w / total for t, w in weights.items()}


def roll_pull(items: Sequence[T], kind: PullKind, rng: random.Random, *,
              rarity_of: Callable[[T], Rarity], luck: int = 0) -> T | None:
    """One item: a tier by this pull's odds (only tiers present in ``items``), then an item of it."""
    if not items:
        return None
    present = sorted({rarity_of(i) for i in items}, key=lambda r: r.value)
    odds = pull_odds(kind, luck, present)
    tier = rng.choices(present, weights=[odds[t] for t in present], k=1)[0]
    return rng.choice([i for i in items if rarity_of(i) is tier])
