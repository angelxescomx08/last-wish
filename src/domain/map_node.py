from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class RoomType(Enum):
    COMBAT   = auto()
    TREASURE = auto()
    SHOP     = auto()
    EVENT    = auto()
    BOSS     = auto()
    WARLOCK  = auto()   # El Brujo: upgrade cards for gold (one per floor)
    GACHA    = auto()   # Gachapón: random relics for rising prices (one per floor, if room)


@dataclass
class MapNode:
    id: str
    room_type: RoomType
    row: int
    col: int
    connections: list[str] = field(default_factory=list)
    visited: bool = False
    available: bool = False
