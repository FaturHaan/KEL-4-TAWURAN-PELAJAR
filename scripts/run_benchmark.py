import argparse
import csv
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from algorithms.registry import AlgorithmRegistry, resolve_algorithm_key
from cases.scenario_loader import ScenarioLoader
from config.settings import DEFAULT_ALGORITHM, OUTPUT_DIR
from core.simulation_runner import SimulationResult, SimulationRunner
from scripts.cli_utils import collect_scenario_paths

AVAILABLE_COLORING_ALGORITHMS = [
    "greedy_coloring",
    "dynamic_welsh_powell",
    "dsatur",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.run_benchmark",
        description="Benchmark komparasi performa 3 algoritma pewarnaan graf (Greedy, Welsh-Powell, DSATUR).",
    )
    parser.add_argument(
        "scenarios",
        nargs="*",
        help="Path file YAML skenario. Kosongkan untuk memakai default/batch.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Benchmark seluruh skenario di folder cases/scenarios.",
    )
    parser.add_argument(
        "-a",
        "--algorithm",
        default=None,
        help="Registry key algoritma spesifik atau 'all' untuk membandingkan ketiga algoritma.",
    )
    parser.add_argument(
        "--compare-all",
        action="store_true",
        help="Bandingkan seluruh algoritma pewarnaan (Greedy, Welsh-Powell, DSATUR) pada setiap skenario.",
    )
    return parser


def run_single(
    yaml_path: Path, algorithm_key: str
) -> Tuple[str, Any, SimulationResult]:
    loader = ScenarioLoader(yaml_path)
    metadata = loader.get_metadata()
    plan = loader.get_execution_plan()
    graph_model = loader.build_graph_model()

    solver = AlgorithmRegistry.create(algorithm_key, graph_model)
    result = SimulationRunner(solver=solver, plan=plan, metadata=metadata).execute()
    return algorithm_key, solver, result


def export_benchmark_reports(rows: List[Dict[str, Any]]) -> Tuple[Path, Path]:
    """Mengekspor tabel ringkasan benchmark ke format Markdown dan CSV untuk laporan tubes."""
    csv_path = OUTPUT_DIR / "benchmark_summary.csv"
    md_path = OUTPUT_DIR / "benchmark_summary.md"

    # 1. Ekspor CSV
    fieldnames = [
        "case",
        "nodes",
        "algorithm",
        "chromatic",
        "steps",
        "init_ms",
        "recolor_cost",
        "balance_std",
        "event_ms",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # 2. Ekspor Markdown Table
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 📊 Hasil Benchmark Komparasi Algoritma Graph Coloring\n\n")
        f.write(
            "Tabel perbandingan performa 3 algoritma pewarnaan graf (*Greedy*, *Welsh-Powell*, dan *DSATUR*) "
            "pada kasus tawuran pelajar:\n\n"
        )
        f.write(
            "| Skenario Kasus | N (Simpul) | Algoritma | Bil. Kromatik (χ) | Step Count | Runtime Awal (ms) | Recolor Cost | Keseimbangan Shift (σ) | Runtime Event (ms) |\n"
        )
        f.write(
            "| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n"
        )
        for r in rows:
            f.write(
                f"| `{r['case']}` | {r['nodes']} | **{r['algorithm']}** | "
                f"{r['chromatic']} | {r['steps']} | {r['init_ms']:.4f} | "
                f"{r['recolor_cost']} | {r['balance_std']:.4f} | {r['event_ms']:.4f} |\n"
            )

    return md_path, csv_path


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    scenario_paths = collect_scenario_paths(args.scenarios, include_all=args.all)

    # Tentukan algoritma yang akan di-benchmark
    if args.compare_all or args.algorithm in ("all", "compare", None):
        target_algorithms = AVAILABLE_COLORING_ALGORITHMS
    else:
        target_algorithms = [args.algorithm]

    rows = []
    for yaml_path in scenario_paths:
        for algo_key in target_algorithms:
            algorithm_key, solver, result = run_single(yaml_path, algo_key)
            total_recolor = sum(r.recolor_cost for r in result.reroutes)
            event_ms = sum(r.elapsed_ms for r in result.reroutes)
            num_nodes = len(result.colors) if result.colors else len(result.initial_path or [])

            rows.append(
                {
                    "case": result.metadata.get("case_id", yaml_path.stem),
                    "nodes": num_nodes,
                    "algorithm": result.algorithm_name,
                    "chromatic": result.chromatic_number if result.chromatic_number > 0 else int(result.initial_cost or 0),
                    "steps": solver.step_count,
                    "init_ms": result.initial_elapsed_ms,
                    "recolor_cost": total_recolor,
                    "balance_std": result.color_balance_std,
                    "event_ms": event_ms,
                }
            )

    # Cetak Tabel ke Terminal
    print("\n" + "=" * 115)
    print(" " * 32 + "BENCHMARK KOMPARASI ALGORITMA GRAPH COLORING")
    print("=" * 115)
    print(
        f" {'Case (Skenario)':<30} {'N':>3} {'Algoritma':<20} {'Warna (χ)':>9} "
        f"{'Steps':>6} {'Init (ms)':>11} {'Recolor':>8} {'Balance(σ)':>11} {'Event (ms)':>11}"
    )
    print(" " + "-" * 113)

    for r in rows:
        print(
            f" {r['case']:<30} {r['nodes']:>3} {r['algorithm']:<20} {r['chromatic']:>9} "
            f"{r['steps']:>6} {r['init_ms']:>11.4f} {r['recolor_cost']:>8} "
            f"{r['balance_std']:>11.4f} {r['event_ms']:>11.4f}"
        )
    print(" " + "-" * 113)
    print(f" Total konfigurasi yang diuji: {len(rows)}")
    print("=" * 115)

    md_path, csv_path = export_benchmark_reports(rows)
    print(f"\n[REPORT] Ringkasan Markdown disimpan ke: {md_path}")
    print(f"[REPORT] Ringkasan CSV disimpan ke     : {csv_path}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
