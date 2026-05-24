"""Tests for GameMap dataclass.

Covers field storage, available_nodes(), and mark_visited() including edge
cases: non-existent node id, nodes with no connections.  No pygame dependency.
"""
from __future__ import annotations

from src.domain.game_map import GameMap
from src.domain.map_node import MapNode, RoomType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(id: str, row: int, col: int, *, room_type: RoomType = RoomType.COMBAT,
          available: bool = False, visited: bool = False,
          connections: list[str] | None = None) -> MapNode:
    return MapNode(
        id=id,
        room_type=room_type,
        row=row,
        col=col,
        available=available,
        visited=visited,
        connections=connections if connections is not None else [],
    )


def _two_node_map() -> GameMap:
    """Simple map: node A (row 0, available) connects to node B (row 1, not available)."""
    a = _node("A", row=0, col=0, available=True, connections=["B"])
    b = _node("B", row=1, col=0, available=False)
    return GameMap(
        floor=1,
        nodes={"A": a, "B": b},
        boss_id="B",
        rows=2,
        cols=1,
    )


# ---------------------------------------------------------------------------
# GameMap — field storage
# ---------------------------------------------------------------------------

class TestGameMapFields:
    def test_floor_stored(self):
        gm = _two_node_map()
        assert gm.floor == 1

    def test_nodes_stored(self):
        gm = _two_node_map()
        assert "A" in gm.nodes
        assert "B" in gm.nodes

    def test_boss_id_stored(self):
        gm = _two_node_map()
        assert gm.boss_id == "B"

    def test_rows_stored(self):
        gm = _two_node_map()
        assert gm.rows == 2

    def test_cols_stored(self):
        gm = _two_node_map()
        assert gm.cols == 1

    def test_node_count(self):
        gm = _two_node_map()
        assert len(gm.nodes) == 2


# ---------------------------------------------------------------------------
# available_nodes()
# ---------------------------------------------------------------------------

class TestAvailableNodes:
    def test_returns_only_available_unvisited(self):
        gm = _two_node_map()
        result = gm.available_nodes()
        assert len(result) == 1

    def test_available_node_is_a(self):
        gm = _two_node_map()
        result = gm.available_nodes()
        assert result[0].id == "A"

    def test_visited_node_excluded(self):
        gm = _two_node_map()
        gm.nodes["A"].visited = True
        result = gm.available_nodes()
        assert len(result) == 0

    def test_empty_when_none_available(self):
        a = _node("A", row=0, col=0, available=False)
        gm = GameMap(floor=1, nodes={"A": a}, boss_id="A", rows=1, cols=1)
        assert gm.available_nodes() == []

    def test_both_available_returns_two(self):
        a = _node("A", row=0, col=0, available=True)
        b = _node("B", row=0, col=1, available=True)
        gm = GameMap(floor=1, nodes={"A": a, "B": b}, boss_id="A", rows=1, cols=2)
        assert len(gm.available_nodes()) == 2

    def test_available_and_visited_excluded(self):
        a = _node("A", row=0, col=0, available=True, visited=True)
        gm = GameMap(floor=1, nodes={"A": a}, boss_id="A", rows=1, cols=1)
        assert gm.available_nodes() == []


# ---------------------------------------------------------------------------
# mark_visited()
# ---------------------------------------------------------------------------

class TestMarkVisited:
    def test_sets_visited_true_on_node(self):
        gm = _two_node_map()
        gm.mark_visited("A")
        assert gm.nodes["A"].visited is True

    def test_sets_connected_node_available(self):
        gm = _two_node_map()
        gm.mark_visited("A")
        assert gm.nodes["B"].available is True

    def test_visited_node_becomes_unavailable(self):
        gm = _two_node_map()
        gm.mark_visited("A")
        assert gm.nodes["A"].available is False

    def test_non_existent_id_no_crash(self):
        gm = _two_node_map()
        gm.mark_visited("DOES_NOT_EXIST")   # must not raise
        assert gm.nodes["A"].visited is False

    def test_node_with_no_connections(self):
        a = _node("A", row=0, col=0, available=True, connections=[])
        gm = GameMap(floor=1, nodes={"A": a}, boss_id="A", rows=1, cols=1)
        gm.mark_visited("A")
        assert gm.nodes["A"].visited is True

    def test_already_visited_child_stays_visited(self):
        a = _node("A", row=0, col=0, available=True, connections=["B"])
        b = _node("B", row=1, col=0, available=False, visited=True)
        gm = GameMap(floor=1, nodes={"A": a, "B": b}, boss_id="B", rows=2, cols=1)
        gm.mark_visited("A")
        # B was already visited — should NOT become available again
        assert gm.nodes["B"].available is False

    def test_available_nodes_updated_after_mark_visited(self):
        gm = _two_node_map()
        gm.mark_visited("A")
        result = gm.available_nodes()
        assert len(result) == 1
        assert result[0].id == "B"

    def test_chain_mark_visited(self):
        a = _node("A", row=0, col=0, available=True, connections=["B"])
        b = _node("B", row=1, col=0, connections=["C"])
        c = _node("C", row=2, col=0)
        gm = GameMap(floor=1, nodes={"A": a, "B": b, "C": c}, boss_id="C", rows=3, cols=1)
        gm.mark_visited("A")
        gm.mark_visited("B")
        assert gm.nodes["C"].available is True
