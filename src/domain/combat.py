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
    turn: int = 1
    selected_card_index: int | None = None
    targeted_enemy_index: int | None = None
