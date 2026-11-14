from pathlib import Path
import pytest

from algorithms.registry import AlgorithmRegistry
from cases.scenario_loader import ScenarioLoader
from config.settings import CASES_DIR, DEFAULT_ALGORITHM, SCENARIO_FILE_PATTERNS


def _discover_scenario_files() -> list:
    files = []
    for pattern in SCENARIO_FILE_PATTERNS:
        files.extend(CASES_DIR.glob(pattern))
    return sorted(set(files))


SCENARIO_FILES = _discover_scenario_files()


@pytest.mark.parametrize("yaml_path", SCENARIO_FILES, ids=lambda p: p.stem)
def test_scenario_pipeline_contract(yaml_path: Path):
    """Audit kontrak data-driven untuk setiap skenario: load, build, run, event, trace."""
    loader = ScenarioLoader(yaml_path)

    metadata = loader.get_metadata()
    assert metadata.get("case_id"), f"{yaml_path.name}: case_id tidak ditemukan"
    assert metadata.get("title"), f"{yaml_path.name}: title tidak ditemukan"

    plan = loader.get_execution_plan()
    model = loader.build_graph_model()
    G = model.nx_graph
    assert len(G.nodes) > 0, f"{yaml_path.name}: graf tanpa node"
    assert len(G.edges) > 0, f"{yaml_path.name}: graf tanpa edge"

    solver = AlgorithmRegistry.create(DEFAULT_ALGORITHM, model)
    raw_result = solver.run(plan.get("start_node"), plan.get("goal_node"))

    # Audit Validitas Output Pewarnaan Graf (Graph Coloring)
    if isinstance(raw_result, dict):
        colors = raw_result
        assert len(colors) == len(G.nodes), f"{yaml_path.name}: seluruh simpul harus terwarnai"
        for u, v in G.edges:
            if u in colors and v in colors and u != v:
                assert colors[u] != colors[v], (
                    f"{yaml_path.name}: pelanggaran pewarnaan graf pada edge ({u}, {v}) dengan warna {colors[u]}"
                )
    elif isinstance(raw_result, tuple):
        path, cost = raw_result
        assert isinstance(path, list) and len(path) >= 2, f"{yaml_path.name}: rute tidak valid"

    # Audit Validitas Dynamic Events
    supported_types = getattr(solver, "SUPPORTED_EVENT_TYPES", None)
    for idx, event in enumerate(plan.get("events", []), 1):
        assert event.get("type"), f"{yaml_path.name}: event #{idx} tanpa 'type'"
        assert event.get("description"), f"{yaml_path.name}: event #{idx} tanpa 'description'"

        if supported_types is not None and event["type"] not in supported_types:
            if "target_edge" in event:
                u, v = event["target_edge"]
                assert G.has_edge(u, v) or G.has_edge(v, u), (
                    f"{yaml_path.name}: event #{idx} menunjuk edge ({u}, {v}) yang tidak ada"
                )
            if "target_node" in event:
                assert event["target_node"] in G.nodes, (
                    f"{yaml_path.name}: event #{idx} menunjuk node {event['target_node']} yang tidak ada"
                )
            continue

        event_data = dict(event)
        if "start_node" in plan and "start" not in event_data:
            event_data["start"] = plan["start_node"]
        if "goal_node" in plan and "goal" not in event_data:
            event_data["goal"] = plan["goal_node"]
        if "target_edge" in event:
            target_edge = tuple(event["target_edge"])
            event_data["edge"] = target_edge
            event_data["target_edge"] = target_edge
        if "new_weight" in event:
            event_data["new_weight"] = event["new_weight"]
        elif "weight" in event:
            event_data["new_weight"] = event["weight"]

        event_res = solver.handle_dynamic_event(event_data)
        if isinstance(event_res, dict) and "colors" in event_res:
            ev_colors = event_res["colors"]
            assert len(ev_colors) == len(G.nodes), f"{yaml_path.name}: warna simpul tidak lengkap pasca-event #{idx}"
            for u, v in G.edges:
                if u in ev_colors and v in ev_colors and u != v:
                    assert ev_colors[u] != ev_colors[v], (
                        f"{yaml_path.name}: konflik pewarnaan pasca-event #{idx} pada edge ({u}, {v})"
                    )

    assert solver.step_count > 0, f"{yaml_path.name}: delta log kosong"
    assert len(solver.delta_logs) == solver.step_count, (
        f"{yaml_path.name}: jumlah log tidak sinkron dengan step_count"
    )
