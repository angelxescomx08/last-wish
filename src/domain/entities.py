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


# Status "Veneno": loses its stacks in HP at the start of its turn, then 1 stack wears off.
POISON: str = "Veneno"
# Status "Marcado": every hit it takes deals its stacks as extra damage (cleared when your turn ends).
MARKED: str = "Marcado"

# Status "Débil": the one who has it deals 25 % less attack damage (rounded down).
WEAK: str = "Débil"
WEAK_FACTOR_NUM, WEAK_FACTOR_DEN = 3, 4


def weakened(amount: int, status_effects: list[StatusEffect]) -> int:
    """``amount`` reduced by Débil (x0.75, rounded down) when present."""
    if any(se.name == WEAK and se.stacks > 0 for se in status_effects):
        return amount * WEAK_FACTOR_NUM // WEAK_FACTOR_DEN
    return amount


def add_status(status_effects: list[StatusEffect], name: str, stacks: int, *, is_buff: bool) -> None:
    """Add ``stacks`` to an existing status of that name, or append a new one."""
    for se in status_effects:
        if se.name == name:
            se.stacks += stacks
            return
    status_effects.append(StatusEffect(name, stacks, is_buff))


def tick_status(status_effects: list[StatusEffect], name: str) -> list[StatusEffect]:
    """One stack of ``name`` wears off; returns the list without exhausted statuses."""
    for se in status_effects:
        if se.name == name:
            se.stacks -= 1
    return [se for se in status_effects if se.stacks > 0]


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


def deal_damage(enemy: "Enemy", amount: int) -> int:
    """One hit on ``enemy``: Marcado adds its stacks, block absorbs first. Returns HP lost."""
    if amount <= 0 or not enemy.is_alive:
        return 0
    amount += sum(se.stacks for se in enemy.status_effects if se.name == MARKED)
    absorbed = min(enemy.block, amount)
    enemy.block -= absorbed
    lost = min(enemy.current_hp, amount - absorbed)
    enemy.current_hp -= lost
    return lost


def status_stacks(status_effects: list[StatusEffect], name: str) -> int:
    return sum(se.stacks for se in status_effects if se.name == name)


@dataclass
class Player:
    name: str
    max_hp: int
    current_hp: int
    block: int = 0
    dexterity: int = 0    # bonus block added to every block card played
    attack_bonus: int = 0  # bonus damage added to every attack card played
    luck: int = 0          # better odds of golden cards/relics and higher relic tiers
    status_effects: list[StatusEffect] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def hp_ratio(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0.0
