from typing import Any, Dict, Optional, Set
from algorithms.registry import AlgorithmRegistry
from core.base_algorithm import BaseGraphAlgorithm
from core.graph_model import SpatialGraphModel


class DSATUR(BaseGraphAlgorithm):
    """Algoritma Pewarnaan Graf DSATUR (Degree of Saturation - Daniel Brélaz)."""

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
        nodes = list(self.graph.nodes())
        self.colors = {node: None for node in nodes}

        self.log_step(
            event_type="INITIALIZATION",
            state_mutations={
                "algorithm": "DSATUR",
                "total_nodes": len(nodes),
                "colors": self.colors.copy(),
            },
        )

        uncolored: Set[Any] = set(nodes)

        while uncolored:
            # Hitung saturation degree (jumlah warna berbeda pada tetangga)
            def get_sat_deg(node) -> int:
                return len({
                    self.colors[neighbor]
                    for neighbor in self.graph.neighbors(node)
                    if self.colors.get(neighbor) is not None
                })

            # Simpul dengan sat_deg tertinggi, tie-break derajat awal di graf
            best_node = max(
                uncolored,
                key=lambda n: (get_sat_deg(n), self.graph.degree(n))
            )

            # Cari warna terkecil yang valid
            neighbor_colors = {
                self.colors[neighbor]
                for neighbor in self.graph.neighbors(best_node)
                if self.colors.get(neighbor) is not None
            }
            color = 0
            while color in neighbor_colors:
                color += 1

            self.colors[best_node] = color
            uncolored.remove(best_node)

            self.log_step(
                event_type="COLOR_ASSIGNED",
                state_mutations={
                    "current_node": best_node,
                    "saturation_degree": get_sat_deg(best_node),
                    "degree": self.graph.degree(best_node),
                    "assigned_color": color,
                    "neighbor_colors": sorted(list(neighbor_colors)),
                    "colors": self.colors.copy(),
                },
            )

        return self.colors

    def handle_dynamic_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Menangani kejadian dinamis pada graf dengan evaluasi ulang derajat saturasi."""
        self.log_step(
            event_type="DYNAMIC_EVENT_TRIGGERED",
            state_mutations={"event_data": event_data},
        )
        return self.run()


AlgorithmRegistry.register("dsatur", DSATUR)
AlgorithmRegistry.register_alias("coloring", "dsatur")
AlgorithmRegistry.register_alias("graph_coloring", "dsatur")
