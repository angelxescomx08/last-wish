from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.card import Card
from src.domain.character import Character
from src.domain.game_map import GameMap
from src.domain.relic import Relic


@dataclass
class Run:
    """Persistent state that survives across rooms and floors during a run."""
    character: Character
    seed: int
    floor: int = 1
    gold: int = 0
    player_max_hp: int = 0
    player_current_hp: int = 0
    deck: list[Card] = field(default_factory=list)
    relics: list[Relic] = field(default_factory=list)
    current_map: GameMap | None = None
    current_room_id: str | None = None

    def add_card(self, card: Card) -> None:
        self.deck.append(card)

    def add_relic(self, relic: Relic) -> None:
        self.relics.append(relic)

    def apply_combat_result(self, hp_after: int) -> None:
        """Persist player HP from a finished combat."""
        self.player_current_hp = max(1, hp_after)
