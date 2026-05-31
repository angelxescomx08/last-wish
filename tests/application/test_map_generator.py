"""Tests for src/application/map_generator.py.

Covers determinism, structure invariants (boss node, row-0 availability,
special room counts), connection validity, and floor-scaling behaviour.
No pygame dependency.
"""
from __future__ import annotations

from src.application.map_generator import generate_map
from src.domain.game_map import GameMap
from src.domain.map_node import RoomType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map(seed: int = 1, floor: int = 1) -> GameMap:
    return generate_map(seed, floor)


def _row_set(gm: GameMap) -> set[int]:
    return {n.row for n in gm.nodes.values()}


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_gamemap(self):
        assert isinstance(_map(), GameMap)

    def test_boss_id_in_nodes(self):
        gm = _map()
        assert gm.boss_id in gm.nodes

    def test_boss_node_room_type(self):
        gm = _map()
        assert gm.nodes[gm.boss_id].room_type == RoomType.BOSS


# ---------------------------------------------------------------------------
# Row-0 availability
# ---------------------------------------------------------------------------

class TestRowZeroAvailability:
    def test_exactly_one_start_node(self):
        gm = _map()
        row0 = [n for n in gm.nodes.values() if n.row == 0]
        assert len(row0) == 1

    def test_start_node_is_available(self):
        gm = _map()
        row0 = [n for n in gm.nodes.values() if n.row == 0]
        assert row0[0].available is True

    def test_only_start_node_available_initially(self):
        gm = _map()
        available = [n for n in gm.nodes.values() if n.available]
        assert len(available) == 1
        assert available[0].row == 0

    def test_boss_not_available_initially(self):
        gm = _map()
        assert gm.nodes[gm.boss_id].available is False


# ---------------------------------------------------------------------------
# Special room counts
# ---------------------------------------------------------------------------

class TestSpecialRooms:
    def test_at_least_one_treasure(self):
        gm = _map()
        treasures = [n for n in gm.nodes.values() if n.room_type == RoomType.TREASURE]
        assert len(treasures) >= 1

    def test_at_least_one_shop(self):
        gm = _map()
        shops = [n for n in gm.nodes.values() if n.room_type == RoomType.SHOP]
        assert len(shops) >= 1

    def test_at_least_one_event(self):
        gm = _map()
        events = [n for n in gm.nodes.values() if n.room_type == RoomType.EVENT]
        assert len(events) >= 1

    def test_exactly_one_boss(self):
        gm = _map()
        bosses = [n for n in gm.nodes.values() if n.room_type == RoomType.BOSS]
        assert len(bosses) == 1


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_node_count(self):
        gm1 = _map(seed=999, floor=1)
        gm2 = _map(seed=999, floor=1)
        assert len(gm1.nodes) == len(gm2.nodes)

    def test_same_seed_same_boss_id(self):
        gm1 = _map(seed=123, floor=2)
        gm2 = _map(seed=123, floor=2)
        assert gm1.boss_id == gm2.boss_id

    def test_different_seeds_give_varied_structures(self):
        counts = {len(generate_map(seed=s, floor=1).nodes) for s in range(10)}
        assert len(counts) >= 2


# ---------------------------------------------------------------------------
# Floor scaling
# ---------------------------------------------------------------------------

class TestFloorScaling:
    def test_floor5_more_rows_than_floor1(self):
        rows_floor1 = len(_row_set(_map(seed=7, floor=1)))
        rows_floor5 = len(_row_set(_map(seed=7, floor=5)))
        assert rows_floor5 > rows_floor1


# ---------------------------------------------------------------------------
# Connection validity
# ---------------------------------------------------------------------------

class TestConnectionValidity:
    def test_all_connection_ids_exist_in_nodes(self):
        gm = _map(seed=42, floor=1)
        for node in gm.nodes.values():
            for cid in node.connections:
                assert cid in gm.nodes

    def test_no_self_connections(self):
        gm = _map(seed=42, floor=1)
        for node in gm.nodes.values():
            assert node.id not in node.connections

    def test_connection_validity_floor3(self):
        gm = _map(seed=77, floor=3)
        for node in gm.nodes.values():
            for cid in node.connections:
                assert cid in gm.nodes

    def test_connection_validity_floor10(self):
        gm = _map(seed=1234, floor=10)
        for node in gm.nodes.values():
            for cid in node.connections:
                assert cid in gm.nodes


# ---------------------------------------------------------------------------
# Orthogonal connections (no diagonals)
# ---------------------------------------------------------------------------

def _is_orthogonal(a, b) -> bool:
    row_diff = abs(a.row - b.row)
    col_diff = abs(a.col - b.col)
    return (row_diff == 1 and col_diff == 0) or (row_diff == 0 and col_diff == 1)


class TestOrthogonalConnections:
    def test_no_diagonal_connections_floor1(self):
        gm = _map(seed=42, floor=1)
        for node in gm.nodes.values():
            for cid in node.connections:
                assert _is_orthogonal(node, gm.nodes[cid]), \
                    f"diagonal: {node.id} → {cid}"

    def test_no_diagonal_connections_floor3(self):
        gm = _map(seed=7, floor=3)
        for node in gm.nodes.values():
            for cid in node.connections:
                assert _is_orthogonal(node, gm.nodes[cid])

    def test_no_diagonal_connections_floor10(self):
        gm = _map(seed=1234, floor=10)
        for node in gm.nodes.values():
            for cid in node.connections:
                assert _is_orthogonal(node, gm.nodes[cid])

    def test_horizontal_connections_are_bidirectional(self):
        gm = _map(seed=99, floor=2)
        for node in gm.nodes.values():
            for cid in node.connections:
                child = gm.nodes[cid]
                if node.row == child.row:   # horizontal edge
                    assert node.id in child.connections, \
                        f"horizontal edge {node.id}→{cid} not bidirectional"

    def test_vertical_connections_go_upward(self):
        gm = _map(seed=55, floor=1)
        for node in gm.nodes.values():
            for cid in node.connections:
                child = gm.nodes[cid]
                if node.col == child.col and node.row != child.row:
                    assert child.row == node.row + 1, \
                        f"vertical edge goes downward: {node.id} → {cid}"

    def test_orthogonal_invariant_many_seeds(self):
        for s in range(20):
            gm = generate_map(seed=s, floor=1)
            for node in gm.nodes.values():
                for cid in node.connections:
                    assert _is_orthogonal(node, gm.nodes[cid])
