"""Test/tuning knobs ("Pruebas" screen): probabilities and cheats, in one place.

``TUNING`` is the live instance read by the rules. Defaults reproduce normal
play exactly, so tests and a fresh install behave as before. The Pruebas
screen edits it and ``src/infrastructure/dev_settings.py`` saves it to
``dev_settings.json``.

Chroma drop chances are generic: ``chroma_chances["golden:card"]`` overrides
``ChromaDef.card_drop_chance`` (kinds: card, relic, pack). A missing key means
"use the definition". New chromas show up on the screen automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields

from src.domain.chroma import CHROMA_DEFS, Chroma

CHROMA_KINDS: tuple[str, ...] = ("card", "relic", "pack")
STARTING_GOLD: int = 2000


@dataclass
class Tuning:
    chroma_chances: dict[str, float] = field(default_factory=dict)
    all_class_cards: bool = False     # rewards/packs ignore classes (every class pool)
    starting_gold: int = STARTING_GOLD
    gold_multiplier: float = 1.0      # combat and event gold
    invincible: bool = False          # enemy attacks never lower the hero's HP
    extra_mana: int = 0               # added to max mana at combat start
    extra_draw: int = 0               # extra cards drawn each turn
    extra_max_hp: int = 0
    extra_luck: int = 0               # hero stats (Pruebas "Stats del héroe")
    extra_damage: int = 0
    extra_dexterity: int = 0
    forced_boss: int = 0              # floor-1 boss: 0 = by seed, 1.. = index in FLOOR1_BOSSES
    forced_encounter: int = 0         # combat rooms: 0 = random, 1.. = enemy_roster.ENCOUNTERS index
    boss_rooms: bool = False          # every combat room is the floor's boss (to test bosses)
    gacha_rooms: bool = False         # every combat room opens the gachapón (to test it)

    def reset(self) -> None:
        default = Tuning()
        for f in fields(self):
            setattr(self, f.name, getattr(default, f.name))


TUNING = Tuning()


def hero_luck(base_luck: int) -> int:
    """Character luck plus the Pruebas bonus (never negative)."""
    return max(0, base_luck + TUNING.extra_luck)


def chroma_key(chroma: Chroma, kind: str) -> str:
    return f"{chroma.value}:{kind}"


def default_chroma_chance(chroma: Chroma, kind: str) -> float:
    d = CHROMA_DEFS[chroma]
    return {"card": d.card_drop_chance, "relic": d.relic_drop_chance, "pack": d.pack_drop_chance}[kind]


def chroma_chance(chroma: Chroma, kind: str) -> float:
    """Current drop chance (tuning override or the chroma's definition), clamped to 0..1."""
    value = TUNING.chroma_chances.get(chroma_key(chroma, kind))
    if value is None:
        value = default_chroma_chance(chroma, kind)
    return max(0.0, min(1.0, float(value)))
