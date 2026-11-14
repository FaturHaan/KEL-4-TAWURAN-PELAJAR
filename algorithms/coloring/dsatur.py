from typing import Any, Dict, List, Optional, Set
import statistics

from algorithms.registry import AlgorithmRegistry
from core.base_algorithm import BaseGraphAlgorithm
from core.graph_model import SpatialGraphModel


class DSATUR(BaseGraphAlgorithm):
    """Algoritma Pewarnaan Graf DSATUR (Degree of Saturation - Daniel Brélaz, 1979).
    
    Memilih simpul berikutnya untuk diwarnai berdasarkan Derajat Saturasi (SatDeg)
    tertinggi, yaitu jumlah warna unik berbeda yang telah digunakan oleh tetangga-tetangganya.
    Tie-break diselesaikan menggunakan derajat asli simpul dalam graf.
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
        """Menghitung derajat (degree) simpul."""
        return len(self._get_neighbors(node))

    def _get_saturation_degree(self, node: Any) -> int:
        """Menghitung Saturation Degree (SatDeg): jumlah warna unik berbeda pada tetangga."""
        neighbor_colors = {
            self.colors[neighbor]
            for neighbor in self._get_neighbors(node)
            if self.colors.get(neighbor) is not None
        }
        return len(neighbor_colors)

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
        """Menjalankan algoritma pewarnaan DSATUR."""
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
            # 1. Pilih simpul dengan Saturation Degree tertinggi
            # Tie-break 1: Derajat asli simpul dalam graf
            # Tie-break 2: ID simpul (string representation) untuk determinisme
            best_node = max(
                uncolored,
                key=lambda n: (
                    self._get_saturation_degree(n),
                    self._get_degree(n),
                    str(n),
                ),
            )

            sat_deg = self._get_saturation_degree(best_node)
            deg = self._get_degree(best_node)

            # 2. Cari warna terkecil yang belum digunakan oleh tetangga
            neighbor_colors = {
                self.colors[neighbor]
                for neighbor in self._get_neighbors(best_node)
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
                    "saturation_degree": sat_deg,
                    "degree": deg,
                    "assigned_color": color,
                    "neighbor_colors": sorted(list(neighbor_colors)),
                    "remaining_uncolored": len(uncolored),
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
        """Menangani kejadian dinamis tawuran dan melakukan evaluasi saturasi ulang."""
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

        # Re-run DSATUR untuk mencari solusi optimal pada graf terkini
        self.run()

        # Hitung recolor cost (jumlah simpul yang berubah shift)
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


AlgorithmRegistry.register("dsatur", DSATUR)
AlgorithmRegistry.register_alias("coloring", "dsatur")
AlgorithmRegistry.register_alias("graph_coloring", "dsatur")
