"""Map scene — the STS-style node map between rooms.

The player clicks on available (highlighted) nodes to enter a room.
All other nodes are dimmed.  Visited nodes show a check mark via color.

Public flag consumed by SceneManager:
  selected_node: MapNode | None   — set when the player clicks an available node.
"""
from __future__ import annotations

import pygame

from src.domain.game_map import GameMap
from src.domain.map_node import MapNode, RoomType
from src.domain.run import Run
from src.infrastructure import colors
from src.infrastructure.fonts import FontRegistry

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

_BG            = pygame.Color(10, 15, 20)
_NODE_W: int   = 64
_NODE_H: int   = 36
_ROW_H: int    = 68
_MAP_TOP: int  = 580   # bottom of map area (row 0 at the top)
_MAP_LEFT: int = 80
_MAP_RIGHT: int= 1200

_COL_COLORS: dict[RoomType, pygame.Color] = {
    RoomType.COMBAT:   pygame.Color(180,  60,  60),
    RoomType.TREASURE: pygame.Color(210, 170,  30),
    RoomType.SHOP:     pygame.Color( 60, 140, 200),
    RoomType.EVENT:    pygame.Color(140,  80, 180),
    RoomType.BOSS:     pygame.Color(230,  40,  40),
}

_COL_LABELS: dict[RoomType, str] = {
    RoomType.COMBAT:   "⚔",
    RoomType.TREASURE: "★",
    RoomType.SHOP:     "🏪",
    RoomType.EVENT:    "?",
    RoomType.BOSS:     "☠",
}

_SPANISH_LABELS: dict[RoomType, str] = {
    RoomType.COMBAT:   "Combate",
    RoomType.TREASURE: "Tesoro",
    RoomType.SHOP:     "Tienda",
    RoomType.EVENT:    "Evento",
    RoomType.BOSS:     "Jefe",
}


def _node_pos(node: MapNode, game_map: GameMap) -> tuple[int, int]:
    """Return the centre pixel of a node on the virtual canvas."""
    cols      = game_map.cols
    usable_w  = _MAP_RIGHT - _MAP_LEFT
    col_step  = usable_w // max(1, cols)
    cx        = _MAP_LEFT + node.col * col_step + col_step // 2
    cy        = _MAP_TOP  - node.row * _ROW_H
    return cx, cy


class MapScene:
    """Interactive floor map."""

    def __init__(self, run: Run, fonts: FontRegistry) -> None:
        self._run          = run
        self._fonts        = fonts
        self._node_rects:  dict[str, pygame.Rect] = {}
        self._hovered_id:  str | None = None
        self._mouse:       tuple[int, int] = (0, 0)
        self.selected_node: MapNode | None = None   # consumed by SceneManager

    # ------------------------------------------------------------------
    # Protocol
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
        self._draw_header(surface)
        game_map = self._run.current_map
        if game_map is None:
            return
        self._draw_connections(surface, game_map)
        self._draw_nodes(surface, game_map)
        self._draw_footer(surface)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_header(self, surface: pygame.Surface) -> None:
        run   = self._run
        floor = run.floor
        cx    = surface.get_width() // 2

        title = self._fonts.get(22).render(f"PISO {floor}", True, colors.TEXT_ACCENT)
        surface.blit(title, title.get_rect(centerx=cx, centery=22))

        # HP / Gold / Relic count
        hp_text  = f"HP: {run.player_current_hp}/{run.player_max_hp}"
        gld_text = f"Oro: {run.gold}"
        rel_text = f"Reliquias: {len(run.relics)}"
        deck_txt = f"Mazo: {len(run.deck)}"

        info = "  |  ".join([hp_text, gld_text, rel_text, deck_txt])
        info_surf = self._fonts.get(13).render(info, True, colors.TEXT_PRIMARY)
        surface.blit(info_surf, info_surf.get_rect(centerx=cx, centery=50))

        # Separator
        pygame.draw.line(surface, colors.PANEL_BORDER, (0, 66), (1280, 66))

    def _draw_connections(self, surface: pygame.Surface, game_map: GameMap) -> None:
        for node in game_map.nodes.values():
            x1, y1 = _node_pos(node, game_map)
            for child_id in node.connections:
                child = game_map.nodes.get(child_id)
                if child is None:
                    continue
                x2, y2 = _node_pos(child, game_map)
                col = pygame.Color(60, 70, 80)
                if node.visited:
                    col = pygame.Color(100, 120, 100)
                pygame.draw.line(surface, col, (x1, y1), (x2, y2), 2)

    def _draw_nodes(self, surface: pygame.Surface, game_map: GameMap) -> None:
        self._node_rects = {}
        for node in game_map.nodes.values():
            cx, cy = _node_pos(node, game_map)
            rect   = pygame.Rect(cx - _NODE_W // 2, cy - _NODE_H // 2, _NODE_W, _NODE_H)
            self._node_rects[node.id] = rect

            base_col  = _COL_COLORS.get(node.room_type, pygame.Color(100, 100, 100))
            hovered   = self._hovered_id == node.id
            available = node.available and not node.visited

            if node.visited:
                col    = pygame.Color(40, 50, 40)
                border = pygame.Color(60, 80, 60)
            elif available:
                col    = base_col
                border = pygame.Color(255, 220, 80) if hovered else colors.TEXT_ACCENT
            else:
                col    = pygame.Color(30, 30, 40)
                border = pygame.Color(50, 50, 60)

            pygame.draw.rect(surface, col,    rect, border_radius=5)
            pygame.draw.rect(surface, border, rect, 2 if available else 1, border_radius=5)

            label = _SPANISH_LABELS.get(node.room_type, "?")
            lsurf = self._fonts.get(10).render(label, True,
                                               colors.TEXT_PRIMARY if available else pygame.Color(80, 80, 80))
            surface.blit(lsurf, lsurf.get_rect(centerx=cx, centery=cy))

        # Tooltip when hovering available node
        if self._hovered_id and self._hovered_id in game_map.nodes:
            node = game_map.nodes[self._hovered_id]
            if node.available and not node.visited:
                self._draw_node_tooltip(surface, node)

    def _draw_node_tooltip(self, surface: pygame.Surface, node: MapNode) -> None:
        label  = _SPANISH_LABELS.get(node.room_type, "?")
        tsurf  = self._fonts.get(13).render(label, True, colors.TEXT_ACCENT)
        mx, my = self._mouse
        tx     = min(mx + 12, 1280 - tsurf.get_width() - 8)
        ty     = max(my - 28, 4)
        bg     = pygame.Rect(tx - 4, ty - 2, tsurf.get_width() + 8, tsurf.get_height() + 4)
        pygame.draw.rect(surface, colors.BG_PANEL, bg, border_radius=3)
        pygame.draw.rect(surface, colors.PANEL_BORDER, bg, 1, border_radius=3)
        surface.blit(tsurf, (tx, ty))

    def _draw_footer(self, surface: pygame.Surface) -> None:
        hint = "Haz clic en una habitación disponible para avanzar"
        hsurf = self._fonts.get(11).render(hint, True, colors.TEXT_SECONDARY)
        surface.blit(hsurf, hsurf.get_rect(centerx=640, centery=710))

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self._hovered_id = None
        game_map = self._run.current_map
        if game_map is None:
            return
        for node_id, rect in self._node_rects.items():
            if rect.collidepoint(pos):
                node = game_map.nodes.get(node_id)
                if node and node.available and not node.visited:
                    self._hovered_id = node_id
                return

    def _handle_click(self, pos: tuple[int, int]) -> None:
        game_map = self._run.current_map
        if game_map is None:
            return
        for node_id, rect in self._node_rects.items():
            if rect.collidepoint(pos):
                node = game_map.nodes.get(node_id)
                if node and node.available and not node.visited:
                    self.selected_node = node
                return
