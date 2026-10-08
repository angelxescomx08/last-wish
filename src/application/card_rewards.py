"""Card reward and pack-opening logic, filtered by class.

A run may only find NEUTRAL cards and cards of its own class, plus the class
pools unlocked by relics (``Relic.card_classes``) — see ``allowed_card_classes``.

pick_reward_cards  — 3 random cards offered after combat (all themes).
pick_pack_cards    — 5 random cards from a theme's pool (for pack opening).

**Cartas de la suerte:** after the normal picks, luck may add up to two extra
cards (``rarity.lucky_card_count``: chance luck/100, a second one above 100 luck —
so the Trébol de Siete Hojas makes one certain). They come from every allowed
card of any theme, Rara or better when there is one, are rolled with the same
luck, get their own golden roll and carry ``Card.lucky_drop`` so screens can mark
them. They use their own rng, so the normal picks never change.

Both pick a rarity tier first (weights in ``domain/rarity.py``, bent by luck),
then a card of that tier, so higher tiers get likelier with more luck.
"""
from __future__ import annotations

import random
import zlib

from src.application import relic_effects
from src.domain.card import Card, CardClass
from src.domain.chroma import roll_chroma
from src.domain.rarity import Rarity, lucky_card_count, weighted_sample
from src.domain.card_pool import (
    PackTheme,
    card_factories_for_classes,
    card_factories_for_theme,
    class_for_character,
)
from src.domain.run import Run
from src.domain.tuning import TUNING

_REWARD_PRIME: int = 3_141_592_653
_CHROMA_SALT: int = 0x5EED_C0DE
_LUCKY_SALT: int = 0x7_C10_FE11


def _reward_seed(run: Run, room_id: str) -> int:
    h = zlib.crc32(room_id.encode("utf-8"))       # stable across runs (str hash is salted)
    return (run.seed * _REWARD_PRIME + run.floor * 1_999 + h) & 0xFFFF_FFFF_FFFF_FFFF


def _with_chromas(cards: list[Card], seed: int, luck: int = 0) -> list[Card]:
    """Each generated card may get a chroma (5 % golden, boosted by luck); own rng, so card picks are unchanged."""
    rng = random.Random(seed ^ _CHROMA_SALT)
    for card in cards:
        card.chroma = roll_chroma(rng, luck=luck)
    return cards


def _luck(run: Run) -> int:
    from src.application.run_manager import run_luck   # local: keeps module load order simple
    return run_luck(run)


def _pick(pool, count: int, rng: random.Random, luck: int):
    """Distinct card factories, tier first (luck-weighted, ``rarity.weighted_sample``)."""
    return weighted_sample(pool, count, rng, rarity_of=lambda f: f.rarity, luck=luck)


def allowed_card_classes(run: Run) -> frozenset[CardClass]:
    """Neutral + the run's class + every class pool mixed in by its relics (or all, from Pruebas)."""
    if TUNING.all_class_cards:
        return frozenset(CardClass)
    own = class_for_character(run.character.id)
    return frozenset({CardClass.NEUTRAL, own}) | relic_effects.unlocked_card_classes(run.relics)


def pick_reward_cards(run: Run, room_id: str, count: int = 3) -> list[Card]:
    """Return `count` distinct card choices for a combat reward."""
    seed = _reward_seed(run, room_id)
    rng = random.Random(seed)
    pool = card_factories_for_classes(allowed_card_classes(run))
    chosen = _pick(pool, count, rng, _luck(run))
    cards = _with_chromas([factory() for factory in chosen], seed, _luck(run))
    return cards + lucky_cards(run, seed, {c.id for c in cards})


def pick_pack_cards(run: Run, theme: PackTheme, count: int = 5) -> list[Card]:
    """Return `count` distinct cards from the given theme (pack opening).

    If the theme has fewer allowed cards than ``count`` the pack is topped up
    with allowed cards from other themes, so it is never short.
    """
    seed    = _reward_seed(run, f"pack_{theme.value}_{run.floor}")
    rng     = random.Random(seed)
    allowed = allowed_card_classes(run)
    pool    = card_factories_for_theme(theme, allowed)
    chosen  = _pick(pool, count, rng, _luck(run))
    if len(chosen) < count:
        extra = [f for f in card_factories_for_classes(allowed) if f.theme is not theme]
        chosen += _pick(extra, count - len(chosen), rng, _luck(run))
    cards = _with_chromas([factory() for factory in chosen], seed, _luck(run))
    return cards + lucky_cards(run, seed, {c.id for c in cards})


def lucky_cards(run: Run, seed: int, exclude: set[str]) -> list[Card]:
    """The "Cartas de la suerte" luck adds to a pack or a reward (usually none)."""
    luck = _luck(run)
    rng = random.Random(seed ^ _LUCKY_SALT)
    n = lucky_card_count(luck, rng)
    if n == 0:
        return []
    pool = [f for f in card_factories_for_classes(allowed_card_classes(run)) if f.card_id not in exclude]
    rare = [f for f in pool if f.rarity.value >= Rarity.RARE.value]
    chosen = _pick(rare if len(rare) >= n else pool, n, rng, luck)
    cards = _with_chromas([factory() for factory in chosen], seed ^ _LUCKY_SALT, luck)
    for card in cards:
        card.lucky_drop = True
    return cards
