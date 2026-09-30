from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

from src.domain.chroma import Chroma, effect_multiplier
from src.domain.keywords import Keyword
from src.domain.numbers import BigValue
from src.domain.rarity import Rarity

if TYPE_CHECKING:
    from src.domain.combat import CombatState


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()


class CardClass(Enum):
    """Who may find a card. Values match ``CharacterId`` values.

    NEUTRAL cards are available to every class; the others only to their own
    class, unless a relic mixes class pools (see ``relic_effects``).
    """
    NEUTRAL = "neutral"
    WARRIOR = "warrior"
    MAGE    = "mage"
    ROGUE   = "rogue"


# Cards and relics share the same five tiers (see ``src/domain/rarity.py``).
CardRarity = Rarity


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

    on_play: optional callable that receives the full CombatState after
    damage/block/mana have been applied.  Use it for any effect that
    cannot be expressed as a plain damage/block value: AoE, status
    application, deck-reading, conditional damage, etc.

    needs_target: set True when on_play requires a target enemy but the
    card deals no base damage (which would otherwise force targeting).

    hits_all_enemies: set True when on_play affects every enemy (area
    effects). It changes no rule; the UI uses it to show every enemy as the
    card's target instead of the hero.

    combo: optional extra layer (keyword COMBO) that also resolves when
    another card was already played this turn.

    text: optional Spanish description of what on_play does (shown for combo
    layers, e.g. "aplica 3 de Veneno más").
    """
    name: str
    damage: BigValue = field(default_factory=lambda: BigValue(0))
    block: BigValue = field(default_factory=lambda: BigValue(0))
    draw: int = 0
    mana_gain: int = 0
    needs_target: bool = False
    hits_all_enemies: bool = False
    on_play: Callable[[CombatState], None] | None = None
    combo: CardEffect | None = None
    text: str = ""


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
    card_class: CardClass = CardClass.NEUTRAL
    chroma: Chroma | None = None      # special finish (golden = every effect x2)

    def __post_init__(self) -> None:
        if self.rarity is None:
            self.rarity = CardRarity.COMMON

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all_effects(self) -> list[CardEffect]:
        return [self.base_effect, *self.stacked_effects]

    def combo_effects(self) -> list[CardEffect]:
        """Combo layers of the chain (keyword COMBO)."""
        return [fx.combo for fx in self.all_effects() if fx.combo is not None]

    def active_effects(self, combo: bool = False) -> list[CardEffect]:
        """Effects that resolve: the chain, plus its combo layers when combo is on."""
        return self.all_effects() + (self.combo_effects() if combo else [])

    def keywords(self) -> frozenset[Keyword]:
        return frozenset({Keyword.COMBO}) if self.combo_effects() else frozenset()

    def effect_multiplier(self) -> int:
        """Chroma multiplier (1 = normal, golden = 2)."""
        return effect_multiplier(self.chroma)

    def casts(self) -> int:
        """How many times the card resolves when played (golden: cast twice).

        Stats stay as printed; the chroma repeats the whole card instead.
        """
        return self.effect_multiplier()

    def total_damage(self, combo: bool = False) -> int:
        total = BigValue(0)
        for fx in self.active_effects(combo):
            total = total.add_flat(fx.damage.resolve())
        return total.resolve()

    def total_block(self, combo: bool = False) -> int:
        total = BigValue(0)
        for fx in self.active_effects(combo):
            total = total.add_flat(fx.block.resolve())
        return total.resolve()

    def total_draw(self, combo: bool = False) -> int:
        return sum(fx.draw for fx in self.active_effects(combo))

    def total_mana_gain(self, combo: bool = False) -> int:
        return sum(fx.mana_gain for fx in self.active_effects(combo))

    def effect_count(self) -> int:
        return len(self.stacked_effects)

    def has_modifier(self, tag: ModifierTag) -> bool:
        return any(m.tag == tag for m in self.modifiers)

    def modifier_stacks(self, tag: ModifierTag) -> int:
        for m in self.modifiers:
            if m.tag == tag:
                return m.stacks
        return 0
