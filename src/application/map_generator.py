"""Seeded, STS-style map generator.

Each floor is generated deterministically from (seed, floor):
  floor_rng_seed = seed * _PRIME1 + floor * _PRIME2

Layout rules:
  - Row 0:       initial available rooms (all paths begin here).
  - Rows 1..N-2: regular rooms (COMBAT, TREASURE, SHOP, EVENT).
  - Row N-1:     single BOSS node.

Special rooms (exactly 1 TREASURE, 1 SHOP, 1–2 EVENTs placed in rows 1..N-3)
are randomly distributed after paths are generated.
"""
from __future__ import annotations

import random

from src.domain.game_map import GameMap
from src.domain.map_node import MapNode, RoomType

# Large primes for floor-seeding
_PRIME1: int = 6_364_136_223_846_793_005
_PRIME2: int = 1_442_695_040_888_963_407


def _rows_for_floor(floor: int) -> int:
    return min(7 + (floor - 1) // 2, 12)


def _cols_for_floor(floor: int) -> int:
    return min(5 + (floor - 1) // 3, 8)


def _paths_for_floor(floor: int) -> int:
    return min(3 + (floor - 1) // 3, 6)


def generate_map(seed: int, floor: int) -> GameMap:
    """Return a fully-connected GameMap for the given run seed and floor."""
    floor_seed = (seed * _PRIME1 + floor * _PRIME2) & 0xFFFF_FFFF_FFFF_FFFF
    rng = random.Random(floor_seed)

    rows     = _rows_for_floor(floor)
    max_cols = _cols_for_floor(floor)
    n_paths  = _paths_for_floor(floor)

    # ------------------------------------------------------------------
    # Phase 1: build edges via path wandering
    # ------------------------------------------------------------------
    # grid:  set of (row, col) that have a room
    # edges: (row, col) -> set of (row+1, col') outgoing connections
    grid: set[tuple[int, int]] = set()
    edges: dict[tuple[int, int], set[tuple[int, int]]] = {}

    boss_row = rows - 1
    boss_col = max_cols // 2
    boss_pos = (boss_row, boss_col)

    for _ in range(n_paths):
        col = rng.randint(0, max_cols - 1)
        for row in range(rows - 1):            # rows 0 to rows-2
            grid.add((row, col))
            if row < rows - 2:
                step     = rng.choice([-1, 0, 1])
                next_col = max(0, min(max_cols - 1, col + step))
                edges.setdefault((row, col), set()).add((row + 1, next_col))
                col = next_col
            else:
                # Last normal row → connect to boss
                edges.setdefault((row, col), set()).add(boss_pos)

    grid.add(boss_pos)

    # ------------------------------------------------------------------
    # Phase 2: create MapNode objects
    # ------------------------------------------------------------------
    def node_id(row: int, col: int) -> str:
        return f"f{floor}_r{row}_c{col}"

    nodes: dict[str, MapNode] = {}
    for (row, col) in grid:
        nid       = node_id(row, col)
        room_type = RoomType.BOSS if (row, col) == boss_pos else RoomType.COMBAT
        conns     = [node_id(nr, nc) for (nr, nc) in edges.get((row, col), set())]
        nodes[nid] = MapNode(
            id=nid,
            room_type=room_type,
            row=row,
            col=col,
            connections=conns,
            visited=False,
            available=(row == 0),   # row-0 rooms are immediately clickable
        )

    # ------------------------------------------------------------------
    # Phase 3: assign special rooms
    # ------------------------------------------------------------------
    mid_rows = list(range(1, rows - 2))   # rows 1..rows-3

    def _pick_from_rows(target_rows: list[int], pool: list[str]) -> str | None:
        candidates = [
            nid for nid in pool
            if nodes[nid].row in target_rows and nodes[nid].room_type == RoomType.COMBAT
        ]
        if not candidates:
            return None
        chosen = rng.choice(candidates)
        pool.remove(chosen)
        return chosen

    mutable_pool = [
        nid for nid, n in nodes.items()
        if n.room_type == RoomType.COMBAT and n.row in mid_rows
    ]

    # TREASURE (mid rows)
    treasure_id = _pick_from_rows(mid_rows, mutable_pool)
    if treasure_id:
        nodes[treasure_id].room_type = RoomType.TREASURE

    # SHOP (different row from TREASURE)
    treasure_row = nodes[treasure_id].row if treasure_id else -1
    shop_rows    = [r for r in mid_rows if r != treasure_row]
    shop_id      = _pick_from_rows(shop_rows, mutable_pool)
    if shop_id:
        nodes[shop_id].room_type = RoomType.SHOP

    # EVENTs (1 or 2)
    n_events = rng.choice([1, 2])
    for _ in range(n_events):
        event_id = _pick_from_rows(mid_rows, mutable_pool)
        if event_id:
            nodes[event_id].room_type = RoomType.EVENT

    return GameMap(
        floor=floor,
        nodes=nodes,
        boss_id=node_id(*boss_pos),
        rows=rows,
        cols=max_cols,
    )
