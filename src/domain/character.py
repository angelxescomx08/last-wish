"""Character definitions with base stats for the character-selection screen.

Each Character carries a frozen CharacterStats record that maps directly
to fields on the Player entity once a combat begins.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CharacterId(Enum):
    WARRIOR = "warrior"
    MAGE    = "mage"
    ROGUE   = "rogue"


@dataclass(frozen=True)
class CharacterStats:
    damage:    int  # flat bonus added to every attack card played
    max_hp:    int  # starting and maximum health
    luck:      int  # extra cards drawn per turn (1 per 5 luck)
    max_mana:  int  # starting and maximum mana
    dexterity: int  # flat bonus added to every block card played


@dataclass(frozen=True)
class Character:
    id:          CharacterId
    name:        str  # Spanish display name
    description: str  # Spanish one-line description shown on the selection screen
    stats:       CharacterStats


ALL_CHARACTERS: list[Character] = [
    Character(
        id=CharacterId.WARRIOR,
        name="El Guerrero",
        description="Luchador resistente que prefiere la defensa.",
        stats=CharacterStats(damage=4, max_hp=100, luck=2, max_mana=2, dexterity=4),
    ),
    Character(
        id=CharacterId.MAGE,
        name="El Mago",
        description="Maestro de los arcanos con gran poder ofensivo.",
        stats=CharacterStats(damage=8, max_hp=60, luck=5, max_mana=4, dexterity=1),
    ),
    Character(
        id=CharacterId.ROGUE,
        name="El Pícaro",
        description="Ágil y astuto, con la suerte de su lado.",
        stats=CharacterStats(damage=6, max_hp=70, luck=8, max_mana=3, dexterity=2),
    ),
]
