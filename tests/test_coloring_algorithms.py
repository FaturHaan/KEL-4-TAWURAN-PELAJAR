import pytest
from cases.scenario_loader import ScenarioLoader
from algorithms.registry import AlgorithmRegistry


@pytest.fixture
def scenario_model():
    loader = ScenarioLoader("cases/scenarios/case_05_graf_2_google_maps.yaml")
    return loader.build_graph_model()


@pytest.mark.parametrize("algo_key", ["greedy_coloring", "dynamic_welsh_powell", "dsatur"])
def test_coloring_algorithms_validity(scenario_model, algo_key):
    solver = AlgorithmRegistry.create(algo_key, scenario_model)
    colors = solver.run()

    # 1. Pastikan semua simpul terwarnai
    for node in scenario_model.nx_graph.nodes:
        assert node in colors
        assert colors[node] is not None
        assert isinstance(colors[node], int)

    # 2. Verifikasi aturan Graph Coloring: Simpul bertetangga tidak boleh satu warna
    for u, v in scenario_model.nx_graph.edges:
        assert colors[u] != colors[v], f"Pelanggaran pewarnaan graf pada edge ({u}, {v}) dengan warna {colors[u]}"

    # 3. Verifikasi penghitungan kromatik
    chromatic = solver.get_chromatic_number()
    assert chromatic > 0
    assert chromatic == len(set(colors.values()))

    # 4. Verifikasi Dynamic Event
    event = {
        "type": "CONFLICT_NODE_TRIGGER",
        "target_node": 2,
        "description": "Tawuran pecah di simpul 2",
    }
    result = solver.handle_dynamic_event(event)
    assert "colors" in result
    assert "recolor_cost" in result
    assert "chromatic_number" in result
