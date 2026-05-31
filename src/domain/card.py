from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from src.domain.numbers import BigValue


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()


class CardRarity(Enum):
    COMMON    = 1   # Común     — starter / basic pool
    UNCOMMON  = 2   # Poco Común — low-cost pack cards
    RARE      = 3   # Raro       — mid-cost pack cards
    EPIC      = 4   # Épico      — high-cost pack cards
    LEGENDARY = 5   # Legendario — EPICO pack cards


class ModifierTag(Enum):
    """Stackable modifiers that alter how a card resolves.

    Exact mechanical effects are TBD — tracked here so the effect chain
    is never thrown away and can be interpreted at resolution time.
    """
    CHROMA = auto()       # Shifts damage element / type
    TRANSPARENT = auto()  # Bypasses enemy block
    ETHEREAL = auto()     # Exhausted instead of discarded after play
    ECHO = auto()         # Triggers the effect an additional time


@dataclass
class CardModifier:
    tag: ModifierTag
    stacks: int = 1


@dataclass
class CardEffect:
    """One layer in a card's effect chain.

    Cards accumulate effects via stacking / breaking-and-merging.
    Each effect contributes independently to the resolved totals.
    """
    name: str
    damage: BigValue = field(default_factory=lambda: BigValue(0))
    block: BigValue = field(default_factory=lambda: BigValue(0))
    draw: int = 0
    mana_gain: int = 0


@dataclass
class Card:
    """A playing card with a stackable effect chain and modifier list.

    Stacking: additional CardEffects are appended to stacked_effects.
    Breaking: is_broken=True flags the card as a merge candidate.
              Two broken cards can fuse — their effect chains concatenate
              into a new card that inherits both parents' history.
    Chromas / transparencies are stored as CardModifiers and interpreted
    at resolution time so no information is ever discarded.
    """

    id: str
    name: str
    card_type: CardType
    cost: int
    base_effect: CardEffect
    rarity: CardRarity = field(default=None)  # set post-init; None → COMMON fallback
    stacked_effects: list[CardEffect] = field(default_factory=list)
    modifiers: list[CardModifier] = field(default_factory=list)
    is_broken: bool = False
    is_upgraded: bool = False

    def __post_init__(self) -> None:
        if self.rarity is None:
            self.rarity = CardRarity.COMMON

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all_effects(self) -> list[CardEffect]:
        return [self.base_effect, *self.stacked_effects]

    def total_damage(self) -> int:
        total = BigValue(0)
        for fx in self.all_effects():
            total = total.add_flat(fx.damage.resolve())
        return total.resolve()

    def total_block(self) -> int:
        total = BigValue(0)
        for fx in self.all_effects():
            total = total.add_flat(fx.block.resolve())
        return total.resolve()

    def effect_count(self) -> int:
        return len(self.stacked_effects)

    def has_modifier(self, tag: ModifierTag) -> bool:
        return any(m.tag == tag for m in self.modifiers)

    def modifier_stacks(self, tag: ModifierTag) -> int:
        for m in self.modifiers:
            if m.tag == tag:
                return m.stacks
        return 0
