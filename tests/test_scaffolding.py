import traceback
from typing import Type
from cases.scenario_loader import ScenarioLoader
from core.base_algorithm import BaseGraphAlgorithm


class SOTAScaffoldingAuditor:
    """Modul Scaffolding untuk mendiagnosis dan membedah integritas algoritma Graph Coloring."""

    def __init__(self, algorithm_class: Type[BaseGraphAlgorithm], yaml_path: str):
        self.algorithm_class = algorithm_class
        self.yaml_path = yaml_path
        self.loader = ScenarioLoader(yaml_path)
        self.metadata = self.loader.get_metadata()
        self.plan = self.loader.get_execution_plan()
        self.model = self.loader.build_graph_model()
        self.solver = None

    def run_full_diagnostic(self) -> bool:
        print(f"\n============================================================")
        print(f"  DIAGNOSTIC AUDIT: {self.algorithm_class.__name__}")
        print(f"  Case: {self.metadata.get('title', 'Unknown Case')}")
        print(f"============================================================\n")

        if not self._audit_class_structure():
            return False
        if not self._audit_initial_run():
            return False
        if not self._audit_dynamic_events():
            return False
        if not self._audit_trace_integrity():
            return False

        print(f"\n[PASSED] ALL TESTS PASSED! Algoritma Anda Valid & Robust.")
        return True

    def _audit_class_structure(self) -> bool:
        print("[STAGE 1/4] Auditing Class Inheritance & Interface...")
        if not issubclass(self.algorithm_class, BaseGraphAlgorithm):
            print("❌ FAIL: Kelas harus menuruni 'BaseGraphAlgorithm'!")
            return False
        try:
            self.solver = self.algorithm_class(self.model)
            print("  ✓ Class Instantiation Success.")
            return True
        except Exception as e:
            print(f"❌ FAIL: Eror saat inisialisasi kelas {self.algorithm_class.__name__}: {e}")
            traceback.print_exc()
            return False

    def _audit_initial_run(self) -> bool:
        print("\n[STAGE 2/4] Auditing Initial Run / Graph Coloring (Phase 1)...")
        start, goal = self.plan.get("start_node"), self.plan.get("goal_node")
        try:
            raw_output = self.solver.run(start, goal)
            G = self.model.nx_graph

            if isinstance(raw_output, dict):
                colors = raw_output
                if len(colors) != len(G.nodes):
                    print(f"❌ FAIL: Simpul terwarnai tidak lengkap ({len(colors)}/{len(G.nodes)})")
                    return False

                # Verifikasi constraint pewarnaan graf
                for u, v in G.edges:
                    if u in colors and v in colors and u != v and colors[u] == colors[v]:
                        print(f"❌ FAIL: Pelanggaran ketetanggaan! Simpul {u} dan {v} bertetangga tapi sama-sama warna {colors[u]}")
                        return False

                chromatic = getattr(self.solver, "get_chromatic_number", lambda: len(set(colors.values())))()
                print(f"  ✓ Initial Coloring Valid -> Total Simpul: {len(colors)} | Bilangan Kromatik: {chromatic}")
                return True
            elif isinstance(raw_output, tuple) and len(raw_output) == 2:
                path, cost = raw_output
                if not isinstance(path, list) or len(path) == 0:
                    print(f"❌ FAIL: Rute tidak valid atau kosong: {path}")
                    return False
                print(f"  ✓ Initial Path Valid: {path} | Cost: {cost}")
                return True
            else:
                print(f"❌ FAIL: Format output run() tidak dikenali: {type(raw_output)}")
                return False
        except Exception as e:
            print(f"❌ FAIL: Crash pada method run():")
            traceback.print_exc()
            return False

    def _audit_dynamic_events(self) -> bool:
        print("\n[STAGE 3/4] Auditing Dynamic Event Handling (Phase 2)...")
        start, goal = self.plan.get("start_node"), self.plan.get("goal_node")
        G = self.model.nx_graph

        for idx, event in enumerate(self.plan.get("events", []), 1):
            event_data = dict(event)
            if start is not None and "start" not in event_data:
                event_data["start"] = start
            if goal is not None and "goal" not in event_data:
                event_data["goal"] = goal
            if "target_edge" in event:
                event_data["edge"] = tuple(event["target_edge"])
                event_data["target_edge"] = tuple(event["target_edge"])

            print(f"  -> Testing Event #{idx}: {event.get('type')} ({event.get('description', '')[:50]}...)")
            try:
                event_res = self.solver.handle_dynamic_event(event_data)
                if isinstance(event_res, dict) and "colors" in event_res:
                    colors = event_res["colors"]
                    # Verifikasi validitas graf pasca event
                    for u, v in G.edges:
                        if u in colors and v in colors and u != v and colors[u] == colors[v]:
                            print(f"❌ FAIL: Konflik pasca-event pada edge ({u}, {v}) warna {colors[u]}")
                            return False
                    print(f"  ✓ Dynamic Event #{idx} Success -> Recolor Cost: {event_res.get('recolor_cost', 0)}")
                elif isinstance(event_res, tuple):
                    path, cost = event_res
                    print(f"  ✓ Dynamic Event #{idx} Success -> Path: {path} | Cost: {cost}")
                else:
                    print(f"  ✓ Dynamic Event #{idx} Success.")
            except Exception as e:
                print(f"❌ FAIL: Crash pada handle_dynamic_event() Event #{idx}:")
                traceback.print_exc()
                return False
        return True

    def _audit_trace_integrity(self) -> bool:
        print("\n[STAGE 4/4] Auditing Quantitative Trace Log Integrity...")
        if self.solver.step_count == 0 or len(self.solver.delta_logs) == 0:
            print("❌ FAIL: 'delta_logs' kosong! Panggil 'self.log_step()' di dalam algoritma Anda.")
            return False
        print(f"  ✓ Trace Log Integrity OK. Total Logged Steps: {self.solver.step_count}")
        return True


# Fungsi tes otomatis untuk PyTest
def test_dsatur_scaffolding():
    from algorithms.coloring.dsatur import DSATUR
    from config.settings import DEFAULT_YAML_SCENARIO

    auditor = SOTAScaffoldingAuditor(DSATUR, str(DEFAULT_YAML_SCENARIO))
    assert auditor.run_full_diagnostic() is True


def test_welsh_powell_scaffolding():
    from algorithms.coloring.dynamic_welsh_powell import DynamicWelshPowell
    from config.settings import DEFAULT_YAML_SCENARIO

    auditor = SOTAScaffoldingAuditor(DynamicWelshPowell, str(DEFAULT_YAML_SCENARIO))
    assert auditor.run_full_diagnostic() is True


def test_greedy_coloring_scaffolding():
    from algorithms.coloring.greedy_coloring import GreedyColoring
    from config.settings import DEFAULT_YAML_SCENARIO

    auditor = SOTAScaffoldingAuditor(GreedyColoring, str(DEFAULT_YAML_SCENARIO))
    assert auditor.run_full_diagnostic() is True
