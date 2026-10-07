"""Gachapón use cases: prices for this run, and one pull that pays, rolls and gives a relic.

* ``gacha_price(run, kind)``: ``domain.gacha.pull_price`` for the pulls already made this
  run (``Run.gacha_pulls``), then the shop discount (Máscara del Ladrón).
* ``pull(run, kind)``: checks the gold, pays, bumps ``Run.gacha_pulls`` (so every price
  rises), rolls a relic from the hero's relic pool (``run_manager._relic_pool``: neutral +
  own class, not owned yet; duplicates only once the pool is empty) with the pull's
  tier odds and luck and rolls its chroma (stellar: double golden chance). Seeded by
  the run seed and the pull number, so a run replays the same capsules.
* The hero then decides: ``accept(run, result)`` adds the relic
  (``run_manager.acquire_relic``: max HP, Espejo Singular…); ``decline(result)``
  throws it away. The gold is spent either way and the price still rises.

No pygame here.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from src.application.run_manager import _relic_pool, acquire_relic, run_luck, shop_price
from src.domain.chroma import roll_chroma
from src.domain.gacha import PULLS, PullKind, pull_odds, pull_price, roll_pull
from src.domain.rarity import Rarity
from src.domain.relic import Relic
from src.domain.run import Run

_GACHA_PRIME = 0x9E3779B1


@dataclass
class PullResult:
    success: bool
    message: str = ""
    relic: Relic | None = None
    kind: PullKind = PullKind.NORMAL
    price: int = 0
    duplicate: bool = False            # the pool was exhausted: an owned relic came again
    settled: bool = False              # accepted or declined already
    accepted: bool = False

    @property
    def rarity(self) -> Rarity | None:
        return self.relic.rarity if self.relic is not None else None


def gacha_price(run: Run, kind: PullKind) -> int:
    """Gold the next ``kind`` pull costs in this run (rises with every pull, any kind)."""
    return shop_price(run, pull_price(kind, run.gacha_pulls))


def can_pull(run: Run, kind: PullKind) -> bool:
    return run.gold >= gacha_price(run, kind)


def gacha_odds(run: Run, kind: PullKind) -> dict[Rarity, float]:
    """Tier odds shown on the machine for this hero (luck included, every tier)."""
    return pull_odds(kind, run_luck(run))


def _rng(run: Run) -> random.Random:
    return random.Random((run.seed * _GACHA_PRIME + 7919 * (run.gacha_pulls + 1)) & 0xFFFF_FFFF_FFFF)


def pull(run: Run, kind: PullKind, rng: random.Random | None = None) -> PullResult:
    """Pay and pull one capsule. Fails (nothing changes) when the hero cannot afford it."""
    price = gacha_price(run, kind)
    if run.gold < price:
        return PullResult(False, "¡No tienes oro suficiente!", kind=kind, price=price)
    rng = rng or _rng(run)
    owned = {r.tag for r in run.relics}
    pool = _relic_pool(run)
    luck = run_luck(run)
    relic = roll_pull(pool, kind, rng, rarity_of=lambda r: r.rarity, luck=luck)
    if relic is None:
        return PullResult(False, "La máquina está vacía.", kind=kind, price=price)
    run.gold -= price
    run.gacha_pulls += 1
    relic.chroma = roll_chroma(rng, for_relic=True,
                               luck=int(luck * PULLS[kind].chroma_boost + 10 * (PULLS[kind].chroma_boost - 1)))
    duplicate = relic.tag in owned and relic.tag is not None
    return PullResult(True, f"¡{relic.name}!", relic=relic, kind=kind, price=price, duplicate=duplicate)


def accept(run: Run, result: PullResult) -> bool:
    """Keep the pulled relic (once). Returns True when it was added now."""
    if not result.success or result.relic is None or result.settled:
        return False
    acquire_relic(run, result.relic)
    result.settled = result.accepted = True
    return True


def decline(result: PullResult) -> bool:
    """Throw the pulled relic away (the gold is not returned). True when it was declined now."""
    if not result.success or result.relic is None or result.settled:
        return False
    result.settled = True
    result.accepted = False
    return True
