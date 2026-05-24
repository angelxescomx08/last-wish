"""Map scene — crossword-style dungeon floor map.

Every room occupies one square cell on a regular grid.  Thick corridor
rectangles connect adjacent cells.  Empty cells are dark "blocked" squares
(like a crossword).  Row 0 (start) is rendered at the bottom; the boss is at
the top, so the player visually moves upward each floor.

Public flag consumed by SceneManager:
  selected_node: MapNode | None — set when the player clicks an available node.
"""
from __future__ import annotations

import pygame

from src.domain.game_map import GameMap
from src.domain.map_node import MapNode, RoomType
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

_BG            = pygame.Color(8, 10, 14)
_GRID_EMPTY    = pygame.Color(18, 22, 28)      # blocked crossword square
_GRID_BORDER   = pygame.Color(30, 36, 46)      # thin border around every cell

_CORRIDOR_IDLE = pygame.Color(28, 34, 42)      # locked corridor (dark)
_CORRIDOR_LIVE = pygame.Color(60, 74, 90)      # reachable / visited corridor

_FILL_AVAIL: dict[RoomType, pygame.Color] = {
    RoomType.COMBAT:   pygame.Color(155,  45,  45),
    RoomType.TREASURE: pygame.Color(185, 145,  25),
    RoomType.SHOP:     pygame.Color( 35, 110, 185),
    RoomType.EVENT:    pygame.Color(110,  50, 170),
    RoomType.BOSS:     pygame.Color(200,  25,  25),
}
_FILL_LOCKED: dict[RoomType, pygame.Color] = {
    t: pygame.Color(max(c.r - 130, 14), max(c.g - 130, 14), max(c.b - 130, 14))
    for t, c in _FILL_AVAIL.items()
}
_FILL_VISITED  = pygame.Color(30, 40, 30)
_BORDER_AVAIL  = pygame.Color(255, 230, 80)
_BORDER_HOVER  = pygame.Color(255, 255, 160)
_BORDER_LOCKED = pygame.Color(36, 44, 54)
_BORDER_VISIT  = pygame.Color(55, 80, 55)

_LABEL_AVAIL   = pygame.Color(235, 235, 235)
_LABEL_LOCKED  = pygame.Color(55,  58,  68)
_LABEL_VISIT   = pygame.Color(65,  95,  65)

_LABELS: dict[RoomType, str] = {
    RoomType.COMBAT:   "Combate",
    RoomType.TREASURE: "Tesoro",
    RoomType.SHOP:     "Tienda",
    RoomType.EVENT:    "Evento",
    RoomType.BOSS:     "JEFE",
}

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

_HEADER_H: int  = 72
_FOOTER_H: int  = 44
_PAD_X: int     = 90
_MAX_CELL: int  = 82
_MIN_CELL: int  = 36


def _cell_px(rows: int, cols: int) -> int:
    usable_w = 1280 - _PAD_X * 2
    usable_h = 720 - _HEADER_H - _FOOTER_H - 20   # extra gap
    return max(_MIN_CELL, min(_MAX_CELL, min(usable_w // cols, usable_h // rows)))


def _origin(rows: int, cols: int, cell: int) -> tuple[int, int]:
    grid_w = cols * cell
    grid_h = rows * cell
    left   = (1280 - grid_w) // 2
    top    = _HEADER_H + (720 - _HEADER_H - _FOOTER_H - grid_h) // 2
    return left, top


def _centre(node: MapNode, org: tuple[int, int], cell: int, rows: int) -> tuple[int, int]:
    """Pixel centre of a node, with row 0 rendered at the BOTTOM."""
    left, top = org
    draw_row  = rows - 1 - node.row          # flip: start at bottom, boss at top
    cx = left + node.col * cell + cell // 2
    cy = top  + draw_row * cell  + cell // 2
    return cx, cy


def _cell_rect(node: MapNode, org: tuple[int, int], cell: int, rows: int) -> pygame.Rect:
    cx, cy = _centre(node, org, cell, rows)
    return pygame.Rect(cx - cell // 2, cy - cell // 2, cell, cell)


# ---------------------------------------------------------------------------
# Map scene
# ---------------------------------------------------------------------------

class MapScene:
    """Crossword-grid dungeon floor map."""

    def __init__(self, run: Run, fonts: FontRegistry) -> None:
        self._run          = run
        self._fonts        = fonts
        self._node_rects:  dict[str, pygame.Rect] = {}
        self._hovered_id:  str | None = None
        self._mouse:       tuple[int, int] = (0, 0)
        self.selected_node: MapNode | None = None

    # ------------------------------------------------------------------
    # Scene protocol
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._mouse = event.pos
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(_BG)
        gm = self._run.current_map
        self._draw_header(surface)
        if gm is not None:
            cell = _cell_px(gm.rows, gm.cols)
            org  = _origin(gm.rows, gm.cols, cell)
            self._draw_empty_grid(surface, gm, cell, org)
            self._draw_corridors(surface, gm, cell, org)
            self._draw_nodes(surface, gm, cell, org)
            self._draw_hover_tooltip(surface, gm)
        self._draw_footer(surface)

    # ------------------------------------------------------------------
    # Header / footer
    # ------------------------------------------------------------------

    def _draw_header(self, surface: pygame.Surface) -> None:
        run = self._run
        cx  = 640

        t = self._fonts.get(22).render(f"PISO {run.floor}", True, colors.TEXT_ACCENT)
        surface.blit(t, t.get_rect(centerx=cx, centery=22))

        info = "  |  ".join([
            f"HP: {run.player_current_hp}/{run.player_max_hp}",
            f"Oro: {run.gold}",
            f"Reliquias: {len(run.relics)}",
            f"Mazo: {len(run.deck)} cartas",
        ])
        s = self._fonts.get(13).render(info, True, colors.TEXT_PRIMARY)
        surface.blit(s, s.get_rect(centerx=cx, centery=52))

        pygame.draw.line(surface, colors.PANEL_BORDER, (0, 66), (1280, 66))

    def _draw_footer(self, surface: pygame.Surface) -> None:
        h = self._fonts.get(11).render(
            "Haz clic en una habitación disponible para avanzar",
            True, colors.TEXT_SECONDARY,
        )
        surface.blit(h, h.get_rect(centerx=640, centery=710))

    # ------------------------------------------------------------------
    # Empty-cell grid (crossword blocked squares)
    # ------------------------------------------------------------------

    def _draw_empty_grid(
        self,
        surface: pygame.Surface,
        gm: GameMap,
        cell: int,
        org: tuple[int, int],
    ) -> None:
        occupied = {(n.row, n.col) for n in gm.nodes.values()}
        left, top = org
        for r in range(gm.rows):
            draw_r = gm.rows - 1 - r       # Y-flip
            for c in range(gm.cols):
                x = left + c    * cell
                y = top  + draw_r * cell
                if (r, c) not in occupied:
                    pygame.draw.rect(surface, _GRID_EMPTY,  (x, y, cell, cell))
                pygame.draw.rect(surface, _GRID_BORDER, (x, y, cell, cell), 1)

    # ------------------------------------------------------------------
    # Corridors (connections between nodes)
    # ------------------------------------------------------------------

    def _draw_corridors(
        self,
        surface: pygame.Surface,
        gm: GameMap,
        cell: int,
        org: tuple[int, int],
    ) -> None:
        corr_w = max(8, cell // 4)
        for node in gm.nodes.values():
            x1, y1 = _centre(node, org, cell, gm.rows)
            live    = node.visited or node.available
            for cid in node.connections:
                child = gm.nodes.get(cid)
                if child is None:
                    continue
                x2, y2 = _centre(child, org, cell, gm.rows)
                col = _CORRIDOR_LIVE if live else _CORRIDOR_IDLE
                pygame.draw.line(surface, col, (x1, y1), (x2, y2), corr_w)

    # ------------------------------------------------------------------
    # Node squares
    # ------------------------------------------------------------------

    def _draw_nodes(
        self,
        surface: pygame.Surface,
        gm: GameMap,
        cell: int,
        org: tuple[int, int],
    ) -> None:
        self._node_rects = {}
        inset   = max(4, cell // 9)
        ns      = cell - inset * 2          # node square side length
        font_sz = max(8, min(11, cell // 7))

        for node in gm.nodes.values():
            cx, cy = _centre(node, org, cell, gm.rows)
            rect   = pygame.Rect(cx - ns // 2, cy - ns // 2, ns, ns)
            self._node_rects[node.id] = rect

            available = node.available and not node.visited
            hovered   = self._hovered_id == node.id

            if node.visited:
                fill, border, bw = _FILL_VISITED, _BORDER_VISIT, 1
            elif available:
                fill   = _FILL_AVAIL.get(node.room_type, pygame.Color(100, 100, 100))
                border = _BORDER_HOVER if hovered else _BORDER_AVAIL
                bw     = 2
            else:
                fill   = _FILL_LOCKED.get(node.room_type, pygame.Color(20, 20, 25))
                border = _BORDER_LOCKED
                bw     = 1

            pygame.draw.rect(surface, fill,   rect, border_radius=5)
            pygame.draw.rect(surface, border, rect, bw, border_radius=5)

            # Glow ring on available nodes
            if available and not hovered:
                glow = pygame.Rect(rect.x - 2, rect.y - 2, rect.w + 4, rect.h + 4)
                glow_col = pygame.Color(
                    min(border.r, 255), min(border.g, 255), min(border.b, 255), 80
                )
                pygame.draw.rect(surface, glow_col, glow, 1, border_radius=6)

            label_col = _LABEL_VISIT if node.visited else (
                _LABEL_AVAIL if available else _LABEL_LOCKED
            )
            text  = "✓" if node.visited else _LABELS.get(node.room_type, "?")
            lsurf = self._fonts.get(font_sz).render(text, True, label_col)
            surface.blit(lsurf, lsurf.get_rect(centerx=cx, centery=cy))

            # Floor indicator for row 0 nodes
            if node.row == 0 and available:
                arrow = self._fonts.get(max(7, font_sz - 2)).render(
                    "INICIO", True, pygame.Color(200, 200, 100)
                )
                surface.blit(arrow, arrow.get_rect(
                    centerx=cx, centery=rect.bottom + 6
                ))

    # ------------------------------------------------------------------
    # Tooltip
    # ------------------------------------------------------------------

    def _draw_hover_tooltip(self, surface: pygame.Surface, gm: GameMap) -> None:
        if not self._hovered_id:
            return
        node = gm.nodes.get(self._hovered_id)
        if node is None or not (node.available and not node.visited):
            return
        label = _LABELS.get(node.room_type, "?")
        ts    = self._fonts.get(13).render(label, True, colors.TEXT_ACCENT)
        mx, my = self._mouse
        tx = min(mx + 14, 1280 - ts.get_width() - 10)
        ty = max(my - 32,  4)
        bg = pygame.Rect(tx - 5, ty - 4, ts.get_width() + 10, ts.get_height() + 8)
        pygame.draw.rect(surface, colors.BG_PANEL,     bg, border_radius=4)
        pygame.draw.rect(surface, colors.PANEL_BORDER, bg, 1, border_radius=4)
        surface.blit(ts, (tx, ty))

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self._hovered_id = None
        gm = self._run.current_map
        if gm is None:
            return
        for nid, rect in self._node_rects.items():
            if rect.collidepoint(pos):
                node = gm.nodes.get(nid)
                if node and node.available and not node.visited:
                    self._hovered_id = nid
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        gm = self._run.current_map
        if gm is None:
            return
        for nid, rect in self._node_rects.items():
            if rect.collidepoint(pos):
                node = gm.nodes.get(nid)
                if node and node.available and not node.visited:
                    self.selected_node = node
                return
