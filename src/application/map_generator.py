"""Seeded, STS-style map generator — orthogonal connections only.

Every connection between nodes is either:
  • horizontal: same row, adjacent column  (col diff = 1)
  • vertical:   same column, adjacent row  (row diff = 1)

No diagonal edges are created, so the MapScene renders pure horizontal /
vertical corridors (crossword style).

Horizontal connections are bidirectional — the player can walk sideways along
a row before choosing to ascend.  Nodes with no upward connection are optional
side rooms that can be skipped.

Floor dimensions:
  rows  = min(7 + (floor-1)//2, 12)
  cols  = min(5 + (floor-1)//3, 8)
  paths = min(3 + (floor-1)//3, 6)
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
    """Return a fully-connected GameMap with orthogonal-only edges."""
    floor_seed = (seed * _PRIME1 + floor * _PRIME2) & 0xFFFF_FFFF_FFFF_FFFF
    rng = random.Random(floor_seed)

    rows     = _rows_for_floor(floor)
    max_cols = _cols_for_floor(floor)
    n_paths  = _paths_for_floor(floor)

    boss_row  = rows - 1
    boss_col  = max_cols // 2
    boss_pos  = (boss_row, boss_col)
    start_col = max_cols // 2      # single entry point, same column as boss
    start_pos = (0, start_col)

    # ------------------------------------------------------------------
    # Phase 1: build orthogonal edges via path wandering
    # ------------------------------------------------------------------
    grid: set[tuple[int, int]] = set()
    # vert_edges[A]  → set of B  where A→B goes one row up (directed)
    # horiz_edges[A] → set of B  where A↔B are same-row neighbours (bidirectional)
    vert_edges:  dict[tuple[int, int], set[tuple[int, int]]] = {}
    horiz_edges: dict[tuple[int, int], set[tuple[int, int]]] = {}

    def _add_horiz(a: tuple[int, int], b: tuple[int, int]) -> None:
        grid.add(a)
        grid.add(b)
        horiz_edges.setdefault(a, set()).add(b)
        horiz_edges.setdefault(b, set()).add(a)

    def _add_vert(a: tuple[int, int], b: tuple[int, int]) -> None:
        grid.add(a)
        grid.add(b)
        vert_edges.setdefault(a, set()).add(b)

    for _ in range(n_paths):
        col = start_col                      # all paths begin at single entry node
        for row in range(rows - 1):          # rows 0 .. rows-2
            grid.add((row, col))

            if row < rows - 2:
                # Row 0 never steps sideways — keeps single entry point intact
                step     = 0 if row == 0 else rng.choice([-1, 0, 1])
                next_col = max(0, min(max_cols - 1, col + step))

                if next_col != col:
                    # Horizontal hop within this row, then go straight up
                    _add_horiz((row, col), (row, next_col))

                _add_vert((row, next_col), (row + 1, next_col))
                col = next_col

            else:
                # Last normal row: walk horizontally to boss_col, then ascend
                cur = col
                while cur != boss_col:
                    nxt = cur + (1 if boss_col > cur else -1)
                    _add_horiz((row, cur), (row, nxt))
                    cur = nxt
                _add_vert((row, boss_col), boss_pos)

    grid.add(boss_pos)

    # ------------------------------------------------------------------
    # Phase 2: create MapNode objects
    # ------------------------------------------------------------------
    def node_id(r: int, c: int) -> str:
        return f"f{floor}_r{r}_c{c}"

    nodes: dict[str, MapNode] = {}
    for (row, col) in grid:
        nid       = node_id(row, col)
        room_type = RoomType.BOSS if (row, col) == boss_pos else RoomType.COMBAT
        conns: set[str] = set()
        for (nr, nc) in vert_edges.get((row, col), set()):
            conns.add(node_id(nr, nc))
        for (nr, nc) in horiz_edges.get((row, col), set()):
            conns.add(node_id(nr, nc))
        nodes[nid] = MapNode(
            id=nid,
            room_type=room_type,
            row=row,
            col=col,
            connections=list(conns),
            visited=False,
            available=((row, col) == start_pos),
        )

    # ------------------------------------------------------------------
    # Phase 3: assign special rooms
    # ------------------------------------------------------------------
    mid_rows = list(range(1, rows - 2))

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

    treasure_id = _pick_from_rows(mid_rows, mutable_pool)
    if treasure_id:
        nodes[treasure_id].room_type = RoomType.TREASURE

    treasure_row = nodes[treasure_id].row if treasure_id else -1
    shop_rows    = [r for r in mid_rows if r != treasure_row]
    shop_id      = _pick_from_rows(shop_rows, mutable_pool)
    if shop_id:
        nodes[shop_id].room_type = RoomType.SHOP

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
