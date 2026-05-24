from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class IntentType(Enum):
    ATTACK = auto()
    BLOCK = auto()
    BUFF = auto()
    DEBUFF = auto()
    UNKNOWN = auto()


@dataclass
class Intent:
    intent_type: IntentType
    value: int = 0


@dataclass
class StatusEffect:
    name: str
    stacks: int
    is_buff: bool


@dataclass
class Enemy:
    id: str
    name: str
    max_hp: int
    current_hp: int
    block: int = 0
    intent: Intent = field(default_factory=lambda: Intent(IntentType.UNKNOWN))
    status_effects: list[StatusEffect] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def hp_ratio(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0.0


@dataclass
class Player:
    name: str
    max_hp: int
    current_hp: int
    block: int = 0
    dexterity: int = 0    # bonus block added to every block card played
    attack_bonus: int = 0  # bonus damage added to every attack card played
    luck: int = 0          # extra cards drawn per turn (1 per 5 luck)
    status_effects: list[StatusEffect] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def hp_ratio(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0.0
