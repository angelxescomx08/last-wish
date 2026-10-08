"""Luck report: what the hero's luck does to every drop, compared with no luck bonus.

Luck (``run_manager.run_luck``: character + Pruebas + relics such as the Trébol de
Siete Hojas) already bends **every** random reward of a run: card tiers in rewards
and packs, relic tiers (treasure, shop, boss, gachapón), and the golden chance of
cards, relics, packs and gachapón capsules. ``luck_report(run)`` gathers those odds
twice — with the hero's real luck and with the character's own luck (no relics) —
so screens can show the player how much their luck is helping right now.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.application import relic_effects
from src.application.hero_stats import StatSource
from src.application.run_manager import run_luck
from src.domain.chroma import CHROMA_DEFS
from src.domain.gacha import PullKind, pull_odds
from src.domain.rarity import Rarity, luck_chroma_multiplier, lucky_card_chances, rarity_odds
from src.domain.relic import Relic
from src.domain.run import Run
from src.domain.tuning import chroma_chance, hero_luck

KINDS = ("card", "relic", "pack")


def golden_chance(kind: str, luck: int) -> float:
    """Chance that one card / relic / pack comes out with a chroma (golden), 0..1."""
    boost = luck_chroma_multiplier(luck)
    return min(1.0, sum(min(1.0, chroma_chance(c, kind) * boost) for c in CHROMA_DEFS))


def at_least(odds: dict[Rarity, float], tier: Rarity) -> float:
    """Probability of ``tier`` or better."""
    return sum(p for r, p in odds.items() if r.value >= tier.value)


@dataclass(frozen=True)
class LuckReport:
    luck: int                                  # the hero's luck now
    base: int                                  # the character's own luck (no relics)
    sources: tuple[StatSource, ...] = ()       # relics adding luck
    tiers: dict[Rarity, float] = field(default_factory=dict)        # card/relic tier odds now
    base_tiers: dict[Rarity, float] = field(default_factory=dict)
    golden: dict[str, float] = field(default_factory=dict)          # per KINDS
    base_golden: dict[str, float] = field(default_factory=dict)

    @property
    def bonus(self) -> int:
        return self.luck - self.base

    def rare_or_better(self, *, base: bool = False) -> float:
        return at_least(self.base_tiers if base else self.tiers, Rarity.RARE)

    def gacha(self, kind: PullKind, *, base: bool = False) -> dict[Rarity, float]:
        return pull_odds(kind, self.base if base else self.luck)

    @property
    def extra_card(self) -> float:
        """Chance that a pack or a card reward gets a "Carta de la suerte"."""
        return lucky_card_chances(self.luck)[0]

    @property
    def second_extra_card(self) -> float:
        return lucky_card_chances(self.luck)[1]

    def summary(self) -> str:
        """One line for shops and packs: "Suerte 108: Rara o mejor 61 % · dorada 87 %"."""
        return (f"Suerte {self.luck}: Rara o mejor {self.rare_or_better():.0%} · "
                f"dorada {self.golden['card']:.0%}")


def luck_report(run: Run) -> LuckReport:
    luck = run_luck(run)
    base = hero_luck(run.character.stats.luck)
    sources = tuple(StatSource(r.name, relic_effects.luck_bonus([r])) for r in run.relics
                    if relic_effects.luck_bonus([r]))
    return LuckReport(
        luck=luck, base=base, sources=sources,
        tiers=rarity_odds(luck), base_tiers=rarity_odds(base),
        golden={k: golden_chance(k, luck) for k in KINDS},
        base_golden={k: golden_chance(k, base) for k in KINDS},
    )


def relic_luck(relics: list[Relic]) -> int:
    return relic_effects.luck_bonus(relics)
