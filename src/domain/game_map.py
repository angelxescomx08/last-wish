from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.map_node import MapNode


@dataclass
class GameMap:
    floor: int
    nodes: dict[str, MapNode]
    boss_id: str
    rows: int
    cols: int

    def available_nodes(self) -> list[MapNode]:
        return [n for n in self.nodes.values() if n.available and not n.visited]

    def mark_visited(self, node_id: str) -> None:
        """Mark a node visited and unlock its outgoing connections."""
        node = self.nodes.get(node_id)
        if node is None:
            return
        node.visited = True
        node.available = False
        for child_id in node.connections:
            child = self.nodes.get(child_id)
            if child and not child.visited:
                child.available = True
