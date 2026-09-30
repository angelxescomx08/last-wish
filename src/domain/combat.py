from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.card import Card
from src.domain.entities import Enemy, Player
from src.domain.mana import Mana
from src.domain.pile import DiscardPile, DrawPile, Hand
from src.domain.relic import Relic


@dataclass
class CombatState:
    player: Player
    enemies: list[Enemy]
    hand: Hand
    draw_pile: DrawPile
    discard_pile: DiscardPile
    mana: Mana
    relics: list[Relic] = field(default_factory=list)
    active_powers: list[Card] = field(default_factory=list)
    turn: int = 1
    selected_card_index: int | None = None
    targeted_enemy_index: int | None = None
    cards_played_this_turn: int = 0   # resets each player turn; > 0 turns Combo on
    singular_deck: bool = False       # keyword SINGULAR: the starting deck had no repeated cards
    # Cost modifiers (see ``card_cost``)
    next_card_discount: int = 0       # "la siguiente carta cuesta 1 menos" (this turn only)
    first_card_discount: int = 0      # power: the first card of each turn costs less (whole combat)
    next_damage_bonus: int = 0        # "la siguiente carta inflige +6" (next damaging card, this turn)
    combo_always: bool = False        # power: Combo resolves without playing a card first

    @property
    def combo_active(self) -> bool:
        """Keyword COMBO: another card was already played this turn (or a power says always)."""
        return self.cards_played_this_turn > 0 or self.combo_always

    def card_cost(self, card) -> int:
        """Mana ``card`` costs right now, after discounts (never below 0)."""
        discount = self.next_card_discount
        if self.cards_played_this_turn == 0:
            discount += self.first_card_discount
        return max(0, card.cost - discount)

    def void_ready(self, card) -> bool:
        """Keyword VOID would resolve if ``card`` were played now (it spends the last mana)."""
        from src.domain.keywords import void_triggers   # local: keywords is a leaf module
        return bool(card.void_effects()) and void_triggers(self.card_cost(card), self.mana.current)

    def singular_ready(self, card) -> bool:
        """Keyword SINGULAR would resolve for ``card`` in this combat."""
        return self.singular_deck and bool(card.singular_effects())
