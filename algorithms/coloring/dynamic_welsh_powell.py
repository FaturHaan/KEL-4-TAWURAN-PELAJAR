from typing import Any, Dict, List, Optional, Set
import statistics

from algorithms.registry import AlgorithmRegistry
from core.base_algorithm import BaseGraphAlgorithm
from core.graph_model import SpatialGraphModel


class DynamicWelshPowell(BaseGraphAlgorithm):
    """Algoritma Pewarnaan Graf Welsh-Powell (Largest First - LF Ordering) Dinamis.
    
    1. Mengurutkan seluruh simpul berdasarkan derajat (degree) dari tertinggi ke terendah.
    2. Mengalokasikan satu warna per putaran untuk simpul-simpul independen (tidak bertetangga).
    3. Merespons dynamic event dengan pembaruan derajat dinamis dan recoloring terarah.
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
        """Mendapatkan seluruh tetangga simpul (undirected view)."""
        if self.graph.is_directed():
            return set(self.graph.predecessors(node)) | set(self.graph.successors(node))
        return set(self.graph.neighbors(node))

    def _get_degree(self, node: Any) -> int:
        """Menghitung derajat (degree) simpul berdasarkan relasi ketetanggaan."""
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
        """Menjalankan pewarnaan graf dengan metode Welsh-Powell (Largest-First)."""
        nodes = list(self.graph.nodes())
        
        # 1. Urutkan simpul berdasarkan derajat tertinggi (descending)
        # Jika derajat sama, gunakan id simpul sebagai tie-breaker konsisten
        sorted_nodes = sorted(
            nodes,
            key=lambda n: (self._get_degree(n), str(n)),
            reverse=True,
        )

        self.colors = {node: None for node in sorted_nodes}

        self.log_step(
            event_type="INITIALIZATION",
            state_mutations={
                "algorithm": "DynamicWelshPowell",
                "total_nodes": len(sorted_nodes),
                "sorted_by_degree": [
                    {"node": n, "degree": self._get_degree(n)} for n in sorted_nodes
                ],
                "colors": self.colors.copy(),
            },
        )

        current_color = 0
        uncolored = list(sorted_nodes)

        # 2. Pewarnaan per putaran warna (round-by-round)
        while uncolored:
            nodes_colored_this_round = []

            for node in uncolored:
                # Cek apakah simpul bertetangga dengan simpul lain yang diwarnai warna ini
                has_neighbor_with_current_color = any(
                    self.colors.get(neighbor) == current_color
                    for neighbor in self._get_neighbors(node)
                )

                if not has_neighbor_with_current_color:
                    self.colors[node] = current_color
                    nodes_colored_this_round.append(node)

                    self.log_step(
                        event_type="COLOR_ASSIGNED",
                        state_mutations={
                            "current_node": node,
                            "degree": self._get_degree(node),
                            "assigned_color": current_color,
                            "nodes_in_this_shift": nodes_colored_this_round.copy(),
                            "colors": self.colors.copy(),
                        },
                    )

            # Buang simpul yang sudah terwarnai dari antrean
            uncolored = [n for n in uncolored if n not in nodes_colored_this_round]
            current_color += 1

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
        """Menangani kejadian dinamis dengan penyesuaian derajat simpul dan recoloring terarah."""
        event_type = event_data.get("type", "UNKNOWN_EVENT")
        old_colors = self.colors.copy()

        # Tangani penambahan sisi konflik baru
        if "target_edge" in event_data:
            u, v = event_data["target_edge"]
            if not self.graph.has_edge(u, v):
                self.graph.add_edge(u, v, weight=event_data.get("weight", 1.0))

        target_node = event_data.get("target_node")

        self.log_step(
            event_type="DYNAMIC_EVENT_TRIGGERED",
            state_mutations={
                "event_type": event_type,
                "target_node": target_node,
                "description": event_data.get("description", ""),
            },
        )

        # Re-run Welsh-Powell dengan urutan derajat yang telah ter-update secara dinamis
        self.run()

        # Hitung perubahan shift (recolor cost)
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


AlgorithmRegistry.register("dynamic_welsh_powell", DynamicWelshPowell)
