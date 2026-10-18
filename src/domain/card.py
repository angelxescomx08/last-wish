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
    from src.domain.elements import Element


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    STATUS = auto()   # junk added by enemies (Espora, Moho…); only lives for one combat


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

    singular: optional extra layer (keyword SINGULAR) that also resolves when
    the deck the combat started with has no repeated cards.

    void: optional extra layer (keyword VOID, "Vacío") that also resolves when
    paying the card's cost leaves the mana at exactly 0.

    spoil: optional extra layer (keyword SPOIL, "Despojo") that also resolves
    when a card was discarded by an effect earlier this turn.

    reaction: optional extra layer (keyword REACTION, "Reacción") that also
    resolves when playing the card causes an elemental reaction.

    fury: optional extra layer (keyword FURY, "Furia") that also resolves when
    the hero already lost HP this turn.

    endure: optional extra layer (keyword ENDURE, "Aguante") that also resolves
    when the hero has block when the card is played.

    element / element_stacks / element_all: Mage elements (``domain/elements.py``).
    The layer puts ``element_stacks`` of ``element`` on the target enemy (or on
    every enemy with ``element_all``) right after its damage, before ``on_play``.

    on_turn_start: for POWER cards, runs at the start of each of your turns while
    the power is in play (golden: twice).

    text: Spanish description of what on_play does, shown on the card face and in
    its tooltip (for keyword layers, shown after "Combo:" etc.).

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
    singular: CardEffect | None = None
    void: CardEffect | None = None
    spoil: CardEffect | None = None
    reaction: CardEffect | None = None
    fury: CardEffect | None = None
    endure: CardEffect | None = None
    element: Element | None = None
    element_stacks: int = 0
    element_all: bool = False
    element_hint: tuple = ()          # elements an on_play talks about (card-face badges only)
    on_turn_start: Callable[[CombatState], None] | None = None
    text: str = ""


@dataclass(frozen=True)
class CardUpgrade:
    """What one upgrade level changes on a card (see ``domain/card_upgrade.py``).

    Numbers are deltas applied to the card's base effect each time it is upgraded
    (``cost`` is usually negative: cheaper). ``on_play`` / ``text`` replace the base
    effect's callback and its Spanish description when set ("algo del texto").
    ``description`` is the Spanish summary shown by the Brujo; empty = generated.
    """
    cost: int = 0
    damage: int = 0
    block: int = 0
    draw: int = 0
    mana_gain: int = 0
    on_play: Callable[[CombatState], None] | None = None
    text: str = ""
    description: str = ""


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
    card_class: CardClass = CardClass.NEUTRAL
    chroma: Chroma | None = None      # special finish (golden = every effect x2)
    # Upgrades (Brujo): times upgraded, the cap (None = unlimited) and an optional
    # custom upgrade; without one, ``card_upgrade.default_upgrade`` decides.
    upgrade_level: int = 0
    max_upgrades: int | None = 1
    upgrade: CardUpgrade | None = None
    base_name: str = ""               # name before "+" suffixes (set post-init)
    # Played automatically (free) the moment it is drawn, then removed from the combat.
    play_on_draw: bool = False
    # Offered as a "Carta de la suerte" (extra card a pack/reward got thanks to luck; display only).
    lucky_drop: bool = False
    # Cartas Marcadas: always in the opening hand (put on top of the draw pile at combat start).
    innate: bool = False
    # Status-card rules (cards enemies put in your deck, see ``domain/status_cards.py``):
    unplayable: bool = False          # "Injugable": cannot be played
    exhaust: bool = False             # "Agotar": leaves the combat after being played
    ethereal: bool = False            # "Etérea": leaves the combat if still in hand at end of turn
    on_draw: Callable[[CombatState], None] | None = None              # when it reaches the hand
    on_turn_end_in_hand: Callable[[CombatState], None] | None = None  # still in hand at end of turn

    def __post_init__(self) -> None:
        if self.rarity is None:
            self.rarity = CardRarity.COMMON
        if not self.base_name:
            self.base_name = self.name

    @property
    def is_upgraded(self) -> bool:
        return self.upgrade_level > 0

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all_effects(self) -> list[CardEffect]:
        return [self.base_effect, *self.stacked_effects]

    def combo_effects(self) -> list[CardEffect]:
        """Combo layers of the chain (keyword COMBO)."""
        return [fx.combo for fx in self.all_effects() if fx.combo is not None]

    def singular_effects(self) -> list[CardEffect]:
        """Singular layers of the chain (keyword SINGULAR)."""
        return [fx.singular for fx in self.all_effects() if fx.singular is not None]

    def void_effects(self) -> list[CardEffect]:
        """Vacío layers of the chain (keyword VOID)."""
        return [fx.void for fx in self.all_effects() if fx.void is not None]

    def spoil_effects(self) -> list[CardEffect]:
        """Despojo layers of the chain (keyword SPOIL)."""
        return [fx.spoil for fx in self.all_effects() if fx.spoil is not None]

    def reaction_effects(self) -> list[CardEffect]:
        """Reacción layers of the chain (keyword REACTION)."""
        return [fx.reaction for fx in self.all_effects() if fx.reaction is not None]

    def fury_effects(self) -> list[CardEffect]:
        """Furia layers of the chain (keyword FURY)."""
        return [fx.fury for fx in self.all_effects() if fx.fury is not None]

    def endure_effects(self) -> list[CardEffect]:
        """Aguante layers of the chain (keyword ENDURE)."""
        return [fx.endure for fx in self.all_effects() if fx.endure is not None]

    def active_effects(self, combo: bool = False, singular: bool = False,
                       void: bool = False, spoil: bool = False,
                       reaction: bool = False, fury: bool = False,
                       endure: bool = False) -> list[CardEffect]:
        """Effects that resolve: the chain, plus its keyword layers that are on."""
        return (self.all_effects()
                + (self.combo_effects() if combo else [])
                + (self.singular_effects() if singular else [])
                + (self.void_effects() if void else [])
                + (self.spoil_effects() if spoil else [])
                + (self.reaction_effects() if reaction else [])
                + (self.fury_effects() if fury else [])
                + (self.endure_effects() if endure else []))

    def keywords(self) -> frozenset[Keyword]:
        out = set()
        if self.combo_effects():
            out.add(Keyword.COMBO)
        if self.singular_effects():
            out.add(Keyword.SINGULAR)
        if self.void_effects():
            out.add(Keyword.VOID)
        if self.spoil_effects():
            out.add(Keyword.SPOIL)
        if self.reaction_effects():
            out.add(Keyword.REACTION)
        if self.fury_effects():
            out.add(Keyword.FURY)
        if self.endure_effects():
            out.add(Keyword.ENDURE)
        return frozenset(out)

    def effect_multiplier(self) -> int:
        """Chroma multiplier (1 = normal, golden = 2)."""
        return effect_multiplier(self.chroma)

    def casts(self) -> int:
        """How many times the card resolves when played (golden: cast twice).

        Stats stay as printed; the chroma repeats the whole card instead.
        """
        return self.effect_multiplier()

    def total_damage(self, combo: bool = False, singular: bool = False, void: bool = False,
                     spoil: bool = False, reaction: bool = False, fury: bool = False,
                     endure: bool = False) -> int:
        total = BigValue(0)
        for fx in self.active_effects(combo, singular, void, spoil, reaction, fury, endure):
            total = total.add_flat(fx.damage.resolve())
        return total.resolve()

    def total_block(self, combo: bool = False, singular: bool = False, void: bool = False,
                    spoil: bool = False, reaction: bool = False, fury: bool = False,
                    endure: bool = False) -> int:
        total = BigValue(0)
        for fx in self.active_effects(combo, singular, void, spoil, reaction, fury, endure):
            total = total.add_flat(fx.block.resolve())
        return total.resolve()

    def total_draw(self, combo: bool = False, singular: bool = False, void: bool = False,
                   spoil: bool = False, reaction: bool = False, fury: bool = False,
                   endure: bool = False) -> int:
        return sum(fx.draw for fx in self.active_effects(combo, singular, void, spoil, reaction,
                                                         fury, endure))

    def total_mana_gain(self, combo: bool = False, singular: bool = False, void: bool = False,
                        spoil: bool = False, reaction: bool = False, fury: bool = False,
                        endure: bool = False) -> int:
        return sum(fx.mana_gain for fx in self.active_effects(combo, singular, void, spoil, reaction,
                                                              fury, endure))

    def element_badges(self) -> list:
        """Elements this card applies or uses (chain + keyword layers), in order, no repeats."""
        layers = (self.all_effects() + self.combo_effects() + self.singular_effects()
                  + self.void_effects() + self.spoil_effects() + self.reaction_effects()
                  + self.fury_effects() + self.endure_effects())
        out: list = []
        for fx in layers:
            for el in ((fx.element,) if fx.element is not None and fx.element_stacks > 0 else ()) + tuple(fx.element_hint):
                if el not in out:
                    out.append(el)
        return out

    def effect_count(self) -> int:
        return len(self.stacked_effects)

    def has_modifier(self, tag: ModifierTag) -> bool:
        return any(m.tag == tag for m in self.modifiers)

    def modifier_stacks(self, tag: ModifierTag) -> int:
        for m in self.modifiers:
            if m.tag == tag:
                return m.stacks
        return 0
