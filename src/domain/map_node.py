from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class RoomType(Enum):
    COMBAT   = auto()
    TREASURE = auto()
    SHOP     = auto()
    EVENT    = auto()
    BOSS     = auto()


@dataclass
class MapNode:
    id: str
    room_type: RoomType
    row: int
    col: int
    connections: list[str] = field(default_factory=list)
    visited: bool = False
    available: bool = False
