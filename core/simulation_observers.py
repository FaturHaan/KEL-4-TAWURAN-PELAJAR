from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import OUTPUT_DIR
from core.base_algorithm import BaseGraphAlgorithm
from core.simulation_runner import RerouteResult, SimulationObserver, SimulationResult
from core.visualizer import SimpleGraphVisualizer


class ConsoleReportObserver(SimulationObserver):
    """Observer untuk mencetak status eksekusi dan metrik kuantitatif ke terminal/konsol."""

    def on_initial_route(self, result: SimulationResult) -> None:
        print(f"\n======================================================================")
        print(f"=== RUNNING SIMULATION: {result.metadata.get('title', 'Unknown Case')} ===")
        print(f"======================================================================")
        print(f"Algorithm : {result.algorithm_name}")

        if result.colors:
            print(f"-> Bilangan Kromatik (Total Shift) : {result.chromatic_number}")
            print(f"-> Distribusi Simpul per Shift     : {result.color_distribution}")
            print(f"-> Keseimbangan Beban (Std Dev)    : {result.color_balance_std:.4f}")
            print(f"-> Runtime Inisialisasi            : {result.initial_elapsed_ms:.4f} ms")
        else:
            print(f"-> Rute Awal  : {result.initial_path} (Cost: {result.initial_cost})")

    def on_reroute(self, result: SimulationResult, reroute: RerouteResult) -> None:
        print(f"\n----------------------------------------------------------------------")
        print(f"[EVENT INJECTED] {reroute.description}")
        print(f"----------------------------------------------------------------------")

        if reroute.colors:
            print(f"-> Recolor Cost (Simpul Berubah)   : {reroute.recolor_cost} simpul")
            print(f"-> Bilangan Kromatik Pasca-Event   : {reroute.chromatic_number}")
            if reroute.target_node is not None:
                print(f"-> Titik Konflik / Target Node     : {reroute.target_node}")
            if reroute.target_edge is not None:
                print(f"-> Jalur Konflik / Target Edge     : {reroute.target_edge}")
            print(f"-> Waktu Komputasi Rekolorisasi    : {reroute.elapsed_ms:.4f} ms")
        else:
            print(f"-> Rute Baru  : {reroute.path} (Cost: {reroute.cost})")

    def on_event_skipped(self, result: SimulationResult, event: Dict[str, Any]) -> None:
        print(
            f"\n[EVENT SKIPPED] {event.get('type')} "
            f"tidak didukung oleh {result.algorithm_name} (butuh algoritma kategori lain)."
        )


class VisualizerSnapshotObserver(SimulationObserver):
    """Observer untuk menampilkan visualisasi graf spasial Matplotlib dan menyimpan snapshot gambar."""

    def __init__(
        self,
        graph: Any,
        show: bool = True,
        save_dir: Optional[Path] = OUTPUT_DIR,
    ):
        self.visualizer = SimpleGraphVisualizer(graph)
        self.show = show
        self.save_dir = save_dir
        self.event_counter = 0

    def on_initial_route(self, result: SimulationResult) -> None:
        case_id = result.metadata.get("case_id", "simulation")
        algo = result.algorithm_name.lower()
        save_path = None
        if self.save_dir:
            save_path = str(self.save_dir / f"snapshot_{case_id}_{algo}_initial.png")

        if result.colors:
            self.visualizer.draw_snapshot(
                title=(
                    f"Kondisi Awal - {result.metadata.get('title', '')}\n"
                    f"Pewarnaan Simpul ({result.algorithm_name}) | Total Shift: {result.chromatic_number}"
                ),
                colors=result.colors,
                save_path=save_path,
                show=self.show,
            )
        else:
            self.visualizer.draw_snapshot(
                title=(
                    f"Kondisi Normal - {result.metadata.get('title', '')}\n"
                    f"Rute Awal: {result.initial_path} (Cost: {result.initial_cost})"
                ),
                active_path=result.initial_path,
                save_path=save_path,
                show=self.show,
            )
        if save_path:
            print(f"[IMAGE] Snapshot graf awal disimpan ke: {save_path}")

    def on_reroute(self, result: SimulationResult, reroute: RerouteResult) -> None:
        self.event_counter += 1
        case_id = result.metadata.get("case_id", "simulation")
        algo = result.algorithm_name.lower()
        save_path = None
        if self.save_dir:
            save_path = str(
                self.save_dir / f"snapshot_{case_id}_{algo}_event_{self.event_counter}.png"
            )

        if reroute.colors:
            self.visualizer.draw_snapshot(
                title=(
                    f"Event Dinamis #{self.event_counter}: {reroute.description}\n"
                    f"Shift Pasca-Event | Recolor Cost: {reroute.recolor_cost} | Total Shift: {reroute.chromatic_number}"
                ),
                colors=reroute.colors,
                highlighted_node=reroute.target_node,
                highlighted_edge=reroute.target_edge,
                save_path=save_path,
                show=self.show,
            )
        else:
            self.visualizer.draw_snapshot(
                title=(
                    f"Event #{self.event_counter}: {reroute.description}\n"
                    f"Rute Baru: {reroute.path} (Cost: {reroute.cost})"
                ),
                active_path=reroute.path,
                highlighted_edge=reroute.target_edge,
                save_path=save_path,
                show=self.show,
            )
        if save_path:
            print(f"[IMAGE] Snapshot pasca-event #{self.event_counter} disimpan ke: {save_path}")


class TraceExportObserver(SimulationObserver):
    """Observer untuk mengekspor jejak kuantitatif (semantic trace log) ke folder output/."""

    def __init__(self, solver: BaseGraphAlgorithm):
        self.solver = solver

    def on_complete(self, result: SimulationResult) -> None:
        filename = f"output_{result.metadata.get('case_id', 'simulation')}.json"
        saved_path = self.solver.export_trace_json(
            filename,
            metadata={
                **result.metadata,
                "algorithm": result.algorithm_name,
                "chromatic_number": result.chromatic_number,
                "color_distribution": result.color_distribution,
                "color_balance_std": round(result.color_balance_std, 4),
            },
        )
        print(f"\n[SUCCESS] Quantitative Trace Log exported to: {saved_path}")
