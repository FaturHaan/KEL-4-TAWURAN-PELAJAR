from typing import Any, Dict, List, Optional, Set
import statistics

from algorithms.registry import AlgorithmRegistry
from core.base_algorithm import BaseGraphAlgorithm
from core.graph_model import SpatialGraphModel


class GreedyColoring(BaseGraphAlgorithm):
    """Algoritma Dasar Pewarnaan Graf (Greedy / Sequential Coloring).
    
    Mengiterasi simpul sesuai urutan indeks/ID dan memberikan warna integer
    terkecil yang belum dipakai oleh tetangga terdekat.
    """

    SUPPORTED_EVENT_TYPES = frozenset({
        "CONFLICT_NODE_TRIGGER",
        "CONFLICT_EDGE_TRIGGER",
        "DYNAMIC_EDGE_WEIGHT",
        "DYNAMIC_EDGE_CAPACITY",
    })

    def __init__(self, model: SpatialGraphModel):
        super().__init__(model)
        self.colors: Dict[Any, Optional[int]] = {}
        self.recolor_cost: int = 0

    def _get_neighbors(self, node: Any) -> Set[Any]:
        """Mendapatkan seluruh tetangga simpul (undirected view untuk conflict graph)."""
        if self.graph.is_directed():
            return set(self.graph.predecessors(node)) | set(self.graph.successors(node))
        return set(self.graph.neighbors(node))

    def _get_degree(self, node: Any) -> int:
        return len(self._get_neighbors(node))

    def get_chromatic_number(self) -> int:
        """Menghitung jumlah warna unik yang digunakan."""
        return len(set(c for c in self.colors.values() if c is not None))

    def get_color_distribution(self) -> Dict[int, int]:
        """Menghitung distribusi jumlah simpul per warna/shift."""
        dist: Dict[int, int] = {}
        for c in self.colors.values():
            if c is not None:
                dist[c] = dist.get(c, 0) + 1
        return dist

    def get_color_balance_std(self) -> float:
        """Menghitung standar deviasi distribusi warna (color balance)."""
        dist = self.get_color_distribution()
        if not dist or len(dist) <= 1:
            return 0.0
        return float(statistics.pstdev(list(dist.values())))

    def run(self, start_node: Optional[int] = None, goal_node: Optional[int] = None, **kwargs) -> Dict[Any, int]:
        """Menjalankan pewarnaan Greedy secara berurutan."""
        nodes = sorted(list(self.graph.nodes()))
        self.colors = {node: None for node in nodes}

        self.log_step(
            event_type="INITIALIZATION",
            state_mutations={
                "algorithm": "GreedyColoring",
                "total_nodes": len(nodes),
                "nodes_order": nodes,
                "colors": self.colors.copy(),
            },
        )

        for node in nodes:
            neighbor_colors = {
                self.colors[neighbor]
                for neighbor in self._get_neighbors(node)
                if self.colors.get(neighbor) is not None
            }

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
                    "chromatic_so_far": self.get_chromatic_number(),
                    "colors": self.colors.copy(),
                },
            )

        self.log_step(
            event_type="COLORING_COMPLETED",
            state_mutations={
                "total_colors_used": self.get_chromatic_number(),
                "distribution": self.get_color_distribution(),
                "color_balance_std": round(self.get_color_balance_std(), 4),
            },
        )

        return self.colors

    def handle_dynamic_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Menangani kejadian dinamis tawuran dan melakukan recoloring."""
        event_type = event_data.get("type", "UNKNOWN_EVENT")
        old_colors = self.colors.copy()

        # Tangani penambahan sisi konflik baru jika ada
        if "target_edge" in event_data:
            u, v = event_data["target_edge"]
            if not self.graph.has_edge(u, v):
                self.graph.add_edge(u, v, weight=event_data.get("weight", 1.0))

        # Jika ada simpul target insiden (misal bentrokan meletus di persimpangan)
        target_node = event_data.get("target_node")

        self.log_step(
            event_type="DYNAMIC_EVENT_TRIGGERED",
            state_mutations={
                "event_type": event_type,
                "target_node": target_node,
                "description": event_data.get("description", ""),
            },
        )

        # Lakukan recoloring greedy ulang
        self.run()

        # Hitung recolor cost (berapa banyak simpul yang berubah warna)
        self.recolor_cost = sum(
            1 for n in self.colors if old_colors.get(n) != self.colors.get(n)
        )

        self.log_step(
            event_type="DYNAMIC_RECOLOR_COMPLETED",
            state_mutations={
                "recolor_cost": self.recolor_cost,
                "new_chromatic_number": self.get_chromatic_number(),
                "colors": self.colors.copy(),
            },
        )

        return {
            "colors": self.colors,
            "recolor_cost": self.recolor_cost,
            "chromatic_number": self.get_chromatic_number(),
        }


AlgorithmRegistry.register("greedy_coloring", GreedyColoring)
