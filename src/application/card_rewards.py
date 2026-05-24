"""Card reward and pack-opening logic.

pick_reward_cards  — 3 random cards offered after combat.
pick_pack_cards    — 5 random cards from a theme's pool (for pack opening).
"""
from __future__ import annotations

import random

from src.domain.card import Card
from src.domain.card_pool import PackTheme, card_factories_for_theme
from src.domain.run import Run

_REWARD_PRIME: int = 3_141_592_653


def _reward_seed(run: Run, room_id: str) -> int:
    h = hash(room_id) & 0xFFFF_FFFF
    return (run.seed * _REWARD_PRIME + run.floor * 1_999 + h) & 0xFFFF_FFFF_FFFF_FFFF


def pick_reward_cards(run: Run, room_id: str, count: int = 3) -> list[Card]:
    """Return `count` distinct card choices for a combat reward."""
    rng = random.Random(_reward_seed(run, room_id))
    # Pick from all themes combined
    all_factories = []
    for theme in PackTheme:
        all_factories.extend(card_factories_for_theme(theme))
    chosen = rng.sample(all_factories, min(count, len(all_factories)))
    return [factory() for factory in chosen]


def pick_pack_cards(run: Run, theme: PackTheme, count: int = 5) -> list[Card]:
    """Return `count` distinct cards from the given theme (pack opening)."""
    rng      = random.Random(_reward_seed(run, f"pack_{theme.value}_{run.floor}"))
    pool     = card_factories_for_theme(theme)
    chosen   = rng.sample(pool, min(count, len(pool)))
    return [factory() for factory in chosen]
