"""Card reward and pack-opening logic, filtered by class.

A run may only find NEUTRAL cards and cards of its own class, plus the class
pools unlocked by relics (``Relic.card_classes``) — see ``allowed_card_classes``.

pick_reward_cards  — 3 random cards offered after combat (all themes).
pick_pack_cards    — 5 random cards from a theme's pool (for pack opening).
"""
from __future__ import annotations

import random

from src.application import relic_effects
from src.domain.card import Card, CardClass
from src.domain.card_pool import (
    PackTheme,
    card_factories_for_classes,
    card_factories_for_theme,
    class_for_character,
)
from src.domain.run import Run

_REWARD_PRIME: int = 3_141_592_653


def _reward_seed(run: Run, room_id: str) -> int:
    h = hash(room_id) & 0xFFFF_FFFF
    return (run.seed * _REWARD_PRIME + run.floor * 1_999 + h) & 0xFFFF_FFFF_FFFF_FFFF


def allowed_card_classes(run: Run) -> frozenset[CardClass]:
    """Neutral + the run's class + every class pool mixed in by its relics."""
    own = class_for_character(run.character.id)
    return frozenset({CardClass.NEUTRAL, own}) | relic_effects.unlocked_card_classes(run.relics)


def pick_reward_cards(run: Run, room_id: str, count: int = 3) -> list[Card]:
    """Return `count` distinct card choices for a combat reward."""
    rng = random.Random(_reward_seed(run, room_id))
    pool = card_factories_for_classes(allowed_card_classes(run))
    chosen = rng.sample(pool, min(count, len(pool)))
    return [factory() for factory in chosen]


def pick_pack_cards(run: Run, theme: PackTheme, count: int = 5) -> list[Card]:
    """Return `count` distinct cards from the given theme (pack opening).

    If the theme has fewer allowed cards than ``count`` the pack is topped up
    with allowed cards from other themes, so it is never short.
    """
    rng     = random.Random(_reward_seed(run, f"pack_{theme.value}_{run.floor}"))
    allowed = allowed_card_classes(run)
    pool    = card_factories_for_theme(theme, allowed)
    chosen  = rng.sample(pool, min(count, len(pool)))
    if len(chosen) < count:
        extra = [f for f in card_factories_for_classes(allowed) if f.theme is not theme]
        chosen += rng.sample(extra, min(count - len(chosen), len(extra)))
    return [factory() for factory in chosen]
