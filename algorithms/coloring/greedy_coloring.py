from typing import Any, Dict, Optional
from algorithms.registry import AlgorithmRegistry
from core.base_algorithm import BaseGraphAlgorithm
from core.graph_model import SpatialGraphModel


class GreedyColoring(BaseGraphAlgorithm):
    """Algoritma Dasar Pewarnaan Graf (Greedy Approach)."""

    SUPPORTED_EVENT_TYPES = frozenset({
        "CONFLICT_NODE_TRIGGER",
        "CONFLICT_EDGE_TRIGGER",
        "DYNAMIC_EDGE_WEIGHT",
        "DYNAMIC_EDGE_CAPACITY",
    })

    def __init__(self, model: SpatialGraphModel):
        super().__init__(model)
        self.colors: Dict[Any, Optional[int]] = {}

    def run(self, start_node: Optional[int] = None, goal_node: Optional[int] = None, **kwargs) -> Dict[Any, int]:
        nodes = sorted(list(self.graph.nodes()))
        self.colors = {node: None for node in nodes}

        self.log_step(
            event_type="INITIALIZATION",
            state_mutations={
                "algorithm": "GreedyColoring",
                "total_nodes": len(nodes),
                "colors": self.colors.copy(),
            },
        )

        for node in nodes:
            # Cari warna tetangga yang sudah di-assign
            neighbor_colors = {
                self.colors[neighbor]
                for neighbor in self.graph.neighbors(node)
                if self.colors.get(neighbor) is not None
            }

            # Cari warna integer non-negatif terkecil yang belum terpakai (0, 1, 2, ...)
            color = 0
            while color in neighbor_colors:
                color += 1

            self.colors[node] = color

            self.log_step(
                event_type="COLOR_ASSIGNED",
                state_mutations={
                    "current_node": node,
                    "assigned_color": color,
                    "neighbor_colors": sorted(list(neighbor_colors)),
                    "colors": self.colors.copy(),
                },
            )

        return self.colors

    def handle_dynamic_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Menangani kejadian dinamis pada graf (misal: penambahan edge konflik baru)."""
        self.log_step(
            event_type="DYNAMIC_EVENT_TRIGGERED",
            state_mutations={"event_data": event_data},
        )
        return self.run()


AlgorithmRegistry.register("greedy_coloring", GreedyColoring)
