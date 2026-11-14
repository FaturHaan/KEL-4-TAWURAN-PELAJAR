from typing import Any, Dict, List, Optional, Tuple
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx


# Palet Warna Pastel Shift Pengawasan (sesuai dokumen laporan dan perancangan draw.io)
PASTEL_SHIFT_COLORS: Dict[int, Dict[str, str]] = {
    0: {
        "color": "#F8CECC",
        "border": "#B85450",
        "name": "Shift 1: Merah (22.00–00.00)",
    },
    1: {
        "color": "#DAE8FC",
        "border": "#6C8EBF",
        "name": "Shift 2: Biru (00.00–02.00)",
    },
    2: {
        "color": "#D5E8D4",
        "border": "#82B366",
        "name": "Shift 3: Hijau (02.00–04.00)",
    },
    3: {
        "color": "#FFE6CC",
        "border": "#D79B00",
        "name": "Shift 4: Oranye (04.00–06.00)",
    },
    4: {
        "color": "#E1D5E7",
        "border": "#9673A6",
        "name": "Shift 5: Ungu (Cadangan)",
    },
    5: {
        "color": "#FFF2CC",
        "border": "#D6B656",
        "name": "Shift 6: Kuning (Cadangan)",
    },
}

DEFAULT_NODE_COLOR = "#E2E8F0"
DEFAULT_BORDER_COLOR = "#4A5568"


class SimpleGraphVisualizer:
    """Visualizer Graf berbasis Matplotlib untuk Pemodelan Tawuran Pelajar & Shift Pengawasan."""

    def __init__(self, graph: nx.Graph):
        self.graph = graph
        # Ambil posisi node dari attribute 'pos' di YAML skenario
        self.pos = nx.get_node_attributes(graph, "pos")
        # Jika pos tidak didefinisikan, gunakan spring layout otomatis
        if not self.pos:
            self.pos = nx.spring_layout(graph, seed=42)

    def draw_snapshot(
        self,
        title: str,
        active_path: Optional[List[Any]] = None,
        highlighted_edge: Optional[Tuple[Any, Any]] = None,
        colors: Optional[Dict[Any, int]] = None,
        highlighted_node: Optional[Any] = None,
        save_path: Optional[str] = None,
        show: bool = True,
    ):
        """Menggambar snapshot kondisi graf dengan pewarnaan simpul (shift patroli)."""
        num_nodes = len(self.graph.nodes())
        # Sesuaikan ukuran figure secara dinamis agar label terbaca jelas
        if num_nodes > 25:
            fig_size = (15, 10)
            font_size = 7
            node_size = 750
        elif num_nodes > 10:
            fig_size = (12, 8)
            font_size = 8
            node_size = 700
        else:
            fig_size = (9, 6)
            font_size = 9
            node_size = 650

        fig, ax = plt.subplots(figsize=fig_size)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=15)

        # 1. Tentukan Warna Setiap Simpul berdasarkan Shift
        node_colors = []
        node_borders = []
        node_border_widths = []
        used_color_indices = set()

        # Deteksi jika active_path dikirim berupa dictionary pewarnaan
        if colors is None and isinstance(active_path, dict):
            colors = active_path

        for node in self.graph.nodes():
            c_idx = colors.get(node) if colors else None

            # Cek apakah node merupakan target insiden dinamis
            is_highlighted = (node == highlighted_node)

            if c_idx is not None and c_idx in PASTEL_SHIFT_COLORS:
                used_color_indices.add(c_idx)
                node_colors.append(PASTEL_SHIFT_COLORS[c_idx]["color"])
                if is_highlighted:
                    node_borders.append("#DC2626")  # Merah menyala untuk insiden
                    node_border_widths.append(3.5)
                else:
                    node_borders.append(PASTEL_SHIFT_COLORS[c_idx]["border"])
                    node_border_widths.append(1.8)
            else:
                node_colors.append(DEFAULT_NODE_COLOR)
                if is_highlighted:
                    node_borders.append("#DC2626")
                    node_border_widths.append(3.5)
                else:
                    node_borders.append(DEFAULT_BORDER_COLOR)
                    node_border_widths.append(1.5)

        # 2. Gambar Simpul (Nodes)
        nx.draw_networkx_nodes(
            self.graph,
            self.pos,
            ax=ax,
            node_size=node_size,
            node_color=node_colors,
            edgecolors=node_borders,
            linewidths=node_border_widths,
        )

        # 3. Label Nama Simpul
        node_labels = {}
        for node, data in self.graph.nodes(data=True):
            lbl = data.get("label", "")
            if lbl:
                node_labels[node] = f"{node}\n({lbl})"
            else:
                node_labels[node] = str(node)

        nx.draw_networkx_labels(
            self.graph,
            self.pos,
            labels=node_labels,
            font_size=font_size,
            font_family="sans-serif",
            font_weight="bold",
            ax=ax,
        )

        # 4. Gambar Sisi/Jalur (Edges)
        is_directed = self.graph.is_directed()
        nx.draw_networkx_edges(
            self.graph,
            self.pos,
            edgelist=list(self.graph.edges()),
            edge_color="#94A3B8",
            width=1.5,
            arrows=is_directed,
            arrowsize=12 if is_directed else 0,
            ax=ax,
        )

        # 5. Label Bobot Sisi (Jika graf kecil/sedang)
        edge_weights = nx.get_edge_attributes(self.graph, "weight")
        if edge_weights and len(self.graph.nodes()) <= 15:
            nx.draw_networkx_edge_labels(
                self.graph,
                self.pos,
                edge_labels=edge_weights,
                font_size=7,
                ax=ax,
            )

        # 6. Highlight Sisi Khusus (Misal jalur tawuran baru / penutupan jalur)
        if highlighted_edge:
            u, v = highlighted_edge
            if self.graph.has_edge(u, v) or self.graph.has_edge(v, u):
                nx.draw_networkx_edges(
                    self.graph,
                    self.pos,
                    edgelist=[(u, v)],
                    edge_color="#EF4444",
                    width=3.5,
                    arrows=is_directed,
                    arrowsize=16,
                    ax=ax,
                )

        # 7. Highlight Jalur Aktif (Jika mode pencarian rute konvensional)
        if active_path and isinstance(active_path, list) and len(active_path) > 1:
            path_edges = list(zip(active_path[:-1], active_path[1:]))
            nx.draw_networkx_edges(
                self.graph,
                self.pos,
                edgelist=path_edges,
                edge_color="#10B981",
                width=3.5,
                arrows=is_directed,
                arrowsize=16,
                ax=ax,
            )

        # 8. Legend / Keterangan Shift Patroli
        if used_color_indices:
            legend_patches = []
            for idx in sorted(used_color_indices):
                meta = PASTEL_SHIFT_COLORS[idx]
                legend_patches.append(
                    mpatches.Patch(
                        facecolor=meta["color"],
                        edgecolor=meta["border"],
                        label=meta["name"],
                        linewidth=1.5,
                    )
                )
            if highlighted_node is not None:
                legend_patches.append(
                    mpatches.Patch(
                        facecolor="#FEE2E2",
                        edgecolor="#DC2626",
                        label=f"Titik Insiden Tawuran (Node {highlighted_node})",
                        linewidth=2.0,
                    )
                )
            ax.legend(
                handles=legend_patches,
                loc="upper right",
                fontsize=8,
                title="Jadwal Shift Pengawasan",
                title_fontsize=9,
                framealpha=0.9,
            )

        ax.axis("off")
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")

        if show:
            try:
                plt.show()
            except Exception:
                pass
        else:
            plt.close(fig)
