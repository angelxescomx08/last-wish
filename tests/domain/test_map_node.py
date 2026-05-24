"""Tests for MapNode dataclass and RoomType enum.

Covers enum membership, MapNode field defaults, and mutation of visited,
available, and connections.  No pygame dependency.
"""
from __future__ import annotations

from src.domain.map_node import MapNode, RoomType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(
    id: str = "n1",
    room_type: RoomType = RoomType.COMBAT,
    row: int = 0,
    col: int = 0,
    **kwargs,
) -> MapNode:
    return MapNode(id=id, room_type=room_type, row=row, col=col, **kwargs)


# ---------------------------------------------------------------------------
# RoomType enum
# ---------------------------------------------------------------------------

class TestRoomTypeEnum:
    def test_combat_exists(self):
        assert RoomType.COMBAT in RoomType

    def test_treasure_exists(self):
        assert RoomType.TREASURE in RoomType

    def test_shop_exists(self):
        assert RoomType.SHOP in RoomType

    def test_event_exists(self):
        assert RoomType.EVENT in RoomType

    def test_boss_exists(self):
        assert RoomType.BOSS in RoomType

    def test_exactly_five_variants(self):
        assert len(list(RoomType)) == 5

    def test_all_unique_values(self):
        values = [t.value for t in RoomType]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# MapNode — field defaults
# ---------------------------------------------------------------------------

class TestMapNodeDefaults:
    def test_connections_defaults_to_empty_list(self):
        node = _node()
        assert node.connections == []

    def test_visited_defaults_to_false(self):
        node = _node()
        assert node.visited is False

    def test_available_defaults_to_false(self):
        node = _node()
        assert node.available is False

    def test_id_stored(self):
        node = _node(id="abc")
        assert node.id == "abc"

    def test_room_type_stored(self):
        node = _node(room_type=RoomType.BOSS)
        assert node.room_type == RoomType.BOSS

    def test_row_stored(self):
        node = _node(row=3)
        assert node.row == 3

    def test_col_stored(self):
        node = _node(col=2)
        assert node.col == 2


# ---------------------------------------------------------------------------
# MapNode — each RoomType can be assigned
# ---------------------------------------------------------------------------

class TestMapNodeRoomType:
    def test_combat_type(self):
        assert _node(room_type=RoomType.COMBAT).room_type == RoomType.COMBAT

    def test_treasure_type(self):
        assert _node(room_type=RoomType.TREASURE).room_type == RoomType.TREASURE

    def test_shop_type(self):
        assert _node(room_type=RoomType.SHOP).room_type == RoomType.SHOP

    def test_event_type(self):
        assert _node(room_type=RoomType.EVENT).room_type == RoomType.EVENT

    def test_boss_type(self):
        assert _node(room_type=RoomType.BOSS).room_type == RoomType.BOSS


# ---------------------------------------------------------------------------
# MapNode — mutations
# ---------------------------------------------------------------------------

class TestMapNodeMutations:
    def test_set_visited_true(self):
        node = _node()
        node.visited = True
        assert node.visited is True

    def test_set_available_true(self):
        node = _node()
        node.available = True
        assert node.available is True

    def test_append_to_connections(self):
        node = _node()
        node.connections.append("n2")
        assert "n2" in node.connections

    def test_multiple_connections(self):
        node = _node()
        node.connections.append("n2")
        node.connections.append("n3")
        assert len(node.connections) == 2

    def test_connections_initial_explicit(self):
        node = _node(connections=["x", "y"])
        assert node.connections == ["x", "y"]

    def test_visited_false_then_true(self):
        node = _node(visited=False)
        node.visited = True
        assert node.visited is True

    def test_available_false_then_true(self):
        node = _node(available=False)
        node.available = True
        assert node.available is True

    def test_independent_connections_per_instance(self):
        a = _node(id="a")
        b = _node(id="b")
        a.connections.append("c")
        assert b.connections == []
