import json
import mimetypes
import os
import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Tuple

import networkx as nx

# Pastikan path modul utama bisa di-import
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from cases.scenario_loader import ScenarioLoader
from algorithms.registry import AlgorithmRegistry


# --- KONFIGURASI SIMULASI KEJADIAN (Kasus 5, insiden 11 Jan 2025) ---
# Semua anotasi di bawah bersumber dari artikel yang tercantum di INCIDENT_SOURCES.
# Skor risiko adalah HEURISTIK NARATIF, bukan probabilitas dan bukan status aman absolut.
SIMULATION_SCENARIO_ID = "case_05_graf_2_google_maps"

INCIDENT_SOURCES = [
    {
        "label": "detikJabar - Kebiasaan Buruk Pelajar Sukabumi Picu Tawuran 3 Sekolah (14 Jan 2025)",
        "url": "https://www.detik.com/jabar/berita/d-7730657/kebiasaan-buruk-pelajar-sukabumi-picu-tawuran-3-sekolah",
    },
    {
        "label": "detikJabar - 5 Fakta Tawuran 3 Sekolah Gegara Dendam Turun-Temurun (14 Jan 2025)",
        "url": "https://www.detik.com/jabar/hukum-dan-kriminal/d-7730786/5-fakta-tawuran-3-sekolah-gegara-dendam-turun-temurun",
    },
    {
        "label": "detikJabar - Catatan Kelam Kekerasan Pelajar di Sukabumi (20 Jan 2025)",
        "url": "https://www.detik.com/jabar/hukum-dan-kriminal/d-7739681/catatan-kelam-kekerasan-pelajar-di-sukabumi",
    },
    {
        "label": "wartahukum.net - Tawuran Berdarah di Sukabumi, Tiga Orang Terluka Akibat Sajam (12 Jan 2025)",
        "url": "https://wartahukum.net/2025/01/12/tawuran-berdarah-di-sukabumi-tiga-orang-terluka-akibat-sajam/",
    },
    {
        "label": "JENTERA NEWS - Tawuran Antar Pelajar Pecah di Tegalbuleud (13 Jan 2025)",
        "url": "https://jenteranews.com/tawuran-antar-pelajar-pecah-di-tegalbuleud-tiga-orang-terluka-akibat-senjata-tajam/",
    },
]

# Simpul kunci pada Graf 2. Node 9 dan 8 adalah PROXY spasial, bukan nama berita persis.
INCIDENT_NODES = {
    0: {"role": "asal", "label": "SMKN 1 Sagaranten", "risk": 1,
        "reason": "Titik berangkat rombongan; SALAH SATU pihak dalam konflik antarsekolah."},
    9: {"role": "janji", "label": "Jembatan Gantung Rambay (proxy Jembatan Cibeureum)", "risk": 1,
        "reason": "Titik janji awal; rombongan tidak menemukan lawan di sini, lalu melanjutkan perjalanan."},
    8: {"role": "tkp", "label": "Kantor Desa Rambay (proxy Kampung Tagog Bayur / TKP)", "risk": 2,
        "reason": "TKP bentrokan ~01.00 WIB; lokasi jauh dari permukiman sehingga warga enggan melerai; 3 korban sabetan sajam."},
    22: {"role": "koalisi", "label": "SMKN 1 Agrabinta", "risk": 1,
         "reason": "Berkoalisi dengan SMKN 1 Tegalbuleud dalam konflik ini."},
    31: {"role": "koalisi", "label": "SMKN 1 Tegalbuleud", "risk": 1,
         "reason": "Berkoalisi dengan SMKN 1 Agrabinta dalam konflik ini."},
}

# Sisi konflik antarsekolah pada YAML adalah relasi konflik, BUKAN jalan transportasi.
# Dikeluarkan dari perhitungan rute pergerakan, tetap ditampilkan sebagai sisi rawan.
CONFLICT_EDGES = frozenset({frozenset((0, 22)), frozenset((0, 31)), frozenset((22, 31))})

RISK_LABELS = {
    0: "Tidak ada catatan insiden pada sumber yang dibaca (relatif tenang)",
    1: "Perlu kewaspadaan: dekat titik/aktor konflik",
    2: "Rawan: TKP, titik janji gagal, atau relasi konflik antarsekolah",
}

ACTORS = {
    "sagaranten": {"label": "Rombongan SMKN 1 Sagaranten", "color": "#facc15", "origin": 0},
    "agrabinta": {"label": "Koalisi SMKN 1 Agrabinta", "color": "#38bdf8", "origin": 22},
    "tegalbuleud": {"label": "Koalisi SMKN 1 Tegalbuleud", "color": "#a855f7", "origin": 31},
}


class GraphDashboardHandler(SimpleHTTPRequestHandler):
    """Handler HTTP Server untuk Web Dashboard Graf Matematika Diskrit."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR / "visualizer"), **kwargs)

    def do_GET(self):
        url_path = self.path.split("?")[0]

        if url_path in ("/", "/index.html"):
            index_path = BASE_DIR / "visualizer" / "index.html"
            self._send_file(index_path, "text/html")
            return

        if url_path == "/api/scenarios":
            self._handle_get_scenarios()
            return

        if url_path == "/api/benchmark":
            query = self.path.split("?")[1] if "?" in self.path else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            scenario_id = params.get("scenario_id", "case_05_graf_2_google_maps")
            self._handle_get_benchmark(scenario_id)
            return

        # Static assets
        super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length).decode("utf-8")
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            body = {}

        if self.path == "/api/run":
            self._handle_post_run(body)
            return

        if self.path == "/api/event":
            self._handle_post_event(body)
            return

        if self.path == "/api/simulate":
            self._handle_post_simulate(body)
            return

        self.send_error(404, "Endpoint not found")

    def _send_json(self, data: Any, status: int = 200):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, file_path: Path, mime_type: str):
        if not file_path.exists():
            self.send_error(404, "File not found")
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _handle_get_scenarios(self):
        scenarios_dir = BASE_DIR / "cases" / "scenarios"
        scenario_files = sorted(scenarios_dir.glob("case_05_*.yaml"))
        results = []

        for p in scenario_files:
            try:
                loader = ScenarioLoader(p)
                meta = loader.get_metadata()
                plan = loader.get_execution_plan()
                model = loader.build_graph_model()
                results.append({
                    "id": p.stem,
                    "title": meta.get("title", p.stem),
                    "description": meta.get("description", ""),
                    "node_count": len(model.nx_graph.nodes),
                    "edge_count": len(model.nx_graph.edges),
                    "has_events": len(plan.get("events", [])) > 0,
                    "events": plan.get("events", []),
                })
            except Exception as e:
                results.append({"id": p.stem, "title": p.stem, "error": str(e)})

        self._send_json({"scenarios": results})

    def _handle_post_run(self, body: Dict[str, Any]):
        scenario_id = body.get("scenario_id", "case_05_graf_2_google_maps")
        algo_key = body.get("algorithm", "dsatur")

        yaml_path = BASE_DIR / "cases" / "scenarios" / f"{scenario_id}.yaml"
        if not yaml_path.exists():
            self._send_json({"error": f"Skenario {scenario_id} tidak ditemukan"}, status=404)
            return

        loader = ScenarioLoader(yaml_path)
        metadata = loader.get_metadata()
        plan = loader.get_execution_plan()
        model = loader.build_graph_model()

        solver = AlgorithmRegistry.create(algo_key, model)

        t_start = time.perf_counter()
        colors = solver.run(plan.get("start_node"), plan.get("goal_node"))
        elapsed_ms = (time.perf_counter() - t_start) * 1000

        # Analisis rentang koordinat untuk scaling dan normalisasi
        xs = [data.get("pos", [0.0, 0.0])[0] for _, data in model.nx_graph.nodes(data=True)]
        ys = [data.get("pos", [0.0, 0.0])[1] for _, data in model.nx_graph.nodes(data=True)]
        min_x, max_x = min(xs) if xs else 0.0, max(xs) if xs else 100.0
        min_y, max_y = min(ys) if ys else 0.0, max(ys) if ys else 100.0
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)

        # Jika Graf 2 (Draw.io 101 km): rentang ribuan piksel (>500)
        # Sesuai Draw.io: sumbu X ke kanan, sumbu Y ke bawah (JANGAN dibalik!)
        is_drawio_scale = (span_x > 500 or span_y > 500)
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0

        nodes_out = []
        is_large = len(model.nx_graph.nodes) > 15

        for node_id, data in model.nx_graph.nodes(data=True):
            pos = data.get("pos", [0.0, 0.0])
            raw_label = data.get("label", str(node_id)).replace("<div>", " ").replace("</div>", " ").strip()
            color_id = colors.get(node_id, 0) if isinstance(colors, dict) else 0

            # Label ringkas vs label detail
            short_label = raw_label
            if is_large and len(raw_label) > 20:
                short_label = raw_label[:18] + ".."

            if is_drawio_scale:
                # Koordinat langsung Draw.io (pos[0], pos[1])
                node_x = float(pos[0])
                node_y = float(pos[1])
            else:
                # Normalisasi & skala Graf 1 / Prototipe agar tidak numpuk
                # Skala target ~1500px lebar x 1200px tinggi
                scale_factor = min(1500.0 / span_x, 1200.0 / span_y)
                node_x = (float(pos[0]) - cx) * scale_factor
                node_y = -(float(pos[1]) - cy) * scale_factor  # Balik Cartesian Y ke Canvas Y

            nodes_out.append({
                "id": node_id,
                "label": f"[{node_id}] {short_label}",
                "full_label": raw_label,
                "x": node_x,
                "y": node_y,
                "color_id": color_id,
                "shift": f"Shift {color_id}",
            })

        edges_out = []
        for u, v, data in model.nx_graph.edges(data=True):
            edges_out.append({
                "from": u,
                "to": v,
                "weight": float(data.get("weight", 1.0)),
                "arrows": "to",
            })

        chi = getattr(solver, "get_chromatic_number", lambda: len(set(c for c in colors.values() if c is not None)))()
        dist = getattr(solver, "get_color_distribution", lambda: {})()

        # Ekstrak urutan pewarnaan untuk animasi interaktif langkah demi langkah
        coloring_steps = []
        logs = getattr(solver, "delta_logs", None) or getattr(solver, "semantic_logs", [])
        for log in logs:
            if log.get("event_type") == "COLOR_ASSIGNED":
                mut = log.get("mutations", {}) or log.get("state_mutations", {})
                if "current_node" in mut and "assigned_color" in mut:
                    coloring_steps.append({
                        "node_id": mut["current_node"],
                        "color_id": mut["assigned_color"],
                        "step": log.get("step", len(coloring_steps) + 1),
                        "degree": mut.get("degree"),
                        "sat_deg": mut.get("saturation_degree"),
                    })

        self._send_json({
            "scenario_id": scenario_id,
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "algorithm": algo_key,
            "algorithm_name": solver.__class__.__name__,
            "chromatic_number": chi,
            "distribution": dist,
            "runtime_ms": round(elapsed_ms, 3),
            "step_count": solver.step_count,
            "nodes": nodes_out,
            "edges": edges_out,
            "coloring_steps": coloring_steps,
            "events": plan.get("events", []),
        })

    def _handle_post_event(self, body: Dict[str, Any]):
        scenario_id = body.get("scenario_id", "case_05_graf_2_google_maps")
        algo_key = body.get("algorithm", "dsatur")
        event_index = int(body.get("event_index", 0))

        yaml_path = BASE_DIR / "cases" / "scenarios" / f"{scenario_id}.yaml"
        loader = ScenarioLoader(yaml_path)
        plan = loader.get_execution_plan()
        events = plan.get("events", [])

        if event_index < 0 or event_index >= len(events):
            self._send_json({"error": "Event index tidak valid"}, status=400)
            return

        event = events[event_index]
        model = loader.build_graph_model()
        solver = AlgorithmRegistry.create(algo_key, model)

        # Jalankan pewarnaan awal
        initial_colors = solver.run(plan.get("start_node"), plan.get("goal_node"))

        # Eksekusi event dinamis
        event_data = dict(event)
        event_data.setdefault("start", plan.get("start_node"))
        event_data.setdefault("goal", plan.get("goal_node"))

        t_start = time.perf_counter()
        event_res = solver.handle_dynamic_event(event_data)
        elapsed_ms = (time.perf_counter() - t_start) * 1000

        new_colors = event_res.get("colors", getattr(solver, "colors", {}))
        recolor_cost = event_res.get("recolor_cost", getattr(solver, "recolor_cost", 0))
        new_chi = getattr(solver, "get_chromatic_number", lambda: len(set(c for c in new_colors.values() if c is not None)))()

        # Daftar simpul yang mengalami perubahan shift (untuk animasi visualizer)
        changed_nodes = [
            int(n) for n in new_colors
            if initial_colors.get(n) is not None and initial_colors.get(n) != new_colors.get(n)
        ]

        # Update edges jika ada edge baru
        edges_out = [{"from": u, "to": v, "arrows": "to"} for u, v in model.nx_graph.edges()]

        self._send_json({
            "event_index": event_index,
            "description": event.get("description", ""),
            "target_node": event.get("target_node"),
            "target_edge": event.get("target_edge"),
            "initial_colors": initial_colors,
            "new_colors": new_colors,
            "changed_nodes": changed_nodes,
            "recolor_cost": recolor_cost,
            "new_chromatic_number": new_chi,
            "elapsed_ms": round(elapsed_ms, 3),
            "edges": edges_out,
        })

    def _handle_post_simulate(self, body: Dict[str, Any]):
        scenario_id = body.get("scenario_id", SIMULATION_SCENARIO_ID)
        if scenario_id != SIMULATION_SCENARIO_ID:
            self._send_json(
                {"error": "Simulasi kejadian hanya tersedia untuk Graf 2 (case_05_graf_2_google_maps)."},
                status=400,
            )
            return

        yaml_path = BASE_DIR / "cases" / "scenarios" / f"{scenario_id}.yaml"
        if not yaml_path.exists():
            self._send_json({"error": f"Skenario {scenario_id} tidak ditemukan"}, status=404)
            return

        loader = ScenarioLoader(yaml_path)
        metadata = loader.get_metadata()
        plan = loader.get_execution_plan()
        model = loader.build_graph_model()

        travel_graph = model.nx_graph.to_undirected()
        for pair in CONFLICT_EDGES:
            u, v = tuple(pair)
            if travel_graph.has_edge(u, v):
                travel_graph.remove_edge(u, v)

        try:
            route_to_janji = list(nx.shortest_path(travel_graph, source=0, target=9))
            route_to_tkp = list(nx.shortest_path(travel_graph, source=9, target=8))
            route_agrabinta = list(nx.shortest_path(travel_graph, source=22, target=8))
            route_tegalbuleud = list(nx.shortest_path(travel_graph, source=31, target=8))
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            self._send_json({"error": f"Rute simulasi tidak ditemukan: {exc}"}, status=400)
            return

        def node_risk(node: int) -> int:
            return INCIDENT_NODES.get(node, {}).get("risk", 0)

        def edge_risk(u: int, v: int) -> int:
            if frozenset((u, v)) in CONFLICT_EDGES:
                return 2
            if u == 8 or v == 8:
                return 2
            return max(node_risk(u), node_risk(v))

        steps: List[Dict[str, Any]] = []

        def add_step(phase: str, actor: str, u, v, narrative: str, clock: str):
            level = edge_risk(u, v) if u is not None and v is not None else node_risk(v if v is not None else u)
            steps.append({
                "index": len(steps) + 1,
                "phase": phase,
                "actor": actor,
                "from": u,
                "to": v,
                "risk": level,
                "risk_label": RISK_LABELS[level],
                "narrative": narrative,
                "clock": clock,
                "sources": [s["url"] for s in INCIDENT_SOURCES],
            })

        berangkat_clock = "Jumat, 10 Jan 2025 (malam)"
        for i in range(len(route_to_janji) - 1):
            u, v = route_to_janji[i], route_to_janji[i + 1]
            if i == 0:
                narrative = (
                    "Rombongan SMKN 1 Sagaranten berangkat menuju Tegalbuleud dengan tujuh sepeda motor. "
                    "Titik tujuan awal: Jembatan Cibeureum."
                )
            elif i == len(route_to_janji) - 2:
                narrative = "Rombongan tiba di Jembatan Cibeureum (proxy: Jembatan Gantung Rambay, node 9)."
            elif v == 8:
                narrative = "Rombongan melintasi kawasan Kantor Desa Rambay (node 8) menuju jembatan; belum ada kontak dengan pihak lain."
            else:
                narrative = f"Rombongan melintasi simpul {u} menuju simpul {v}."
            add_step("BERANGKAT", "sagaranten", u, v, narrative, berangkat_clock)

        add_step(
            "JANJI_KOSONG",
            "sagaranten",
            9,
            None,
            "Di titik janji tidak ditemukan lawan. Rombongan memutuskan melanjutkan perjalanan.",
            berangkat_clock,
        )

        tkp_clock = "Sabtu, 11 Jan 2025, menjelang 01.00 WIB"
        for i in range(len(route_to_tkp) - 1):
            u, v = route_to_tkp[i], route_to_tkp[i + 1]
            add_step(
                "LANJUT_KE_TKP",
                "sagaranten",
                u,
                v,
                "Karena titik janji kosong, rombongan bergerak ke Kampung Tagog Bayur (node 8), Jalan Raya Rambay.",
                tkp_clock,
            )

        for i in range(max(len(route_agrabinta), len(route_tegalbuleud)) - 1):
            for actor_key, route in (("agrabinta", route_agrabinta), ("tegalbuleud", route_tegalbuleud)):
                if i < len(route) - 1:
                    u, v = route[i], route[i + 1]
                    add_step(
                        "KOALISI_MENDEKAT",
                        actor_key,
                        u,
                        v,
                        f"Koalisi {ACTORS[actor_key]['label']} bergerak menuju titik konflik lewat simpul {v}.",
                        tkp_clock,
                    )

        add_step(
            "BENTROKAN",
            "tkp",
            None,
            8,
            "Sekitar 01.00 WIB kedua kelompok bertemu di Jalan Raya Rambay, Kampung Tagog Bayur. "
            "Bentrokan berlangsung sekitar dua menit dengan senjata tajam; tiga orang dari Sagaranten terluka. "
            "Lokasi jauh dari permukiman warga sehingga warga enggan melerai.",
            "Sabtu, 11 Jan 2025, ~01.00 WIB",
        )

        algorithm_key = body.get("algorithm", "dsatur")
        solver = AlgorithmRegistry.create(algorithm_key, model)
        initial_colors = solver.run(plan.get("start_node"), plan.get("goal_node"))
        event_summaries = []
        for event in plan.get("events", []):
            event_data = dict(event)
            event_data.setdefault("start", plan.get("start_node"))
            event_data.setdefault("goal", plan.get("goal_node"))
            event_result = solver.handle_dynamic_event(event_data)
            event_summaries.append({
                "type": event.get("type", ""),
                "description": event.get("description", ""),
                "recolor_cost": event_result.get("recolor_cost", 0),
                "chromatic_number": event_result.get("chromatic_number", 0),
            })
        new_colors = solver.colors
        changed_nodes = [
            int(n) for n in new_colors
            if initial_colors.get(n) != new_colors.get(n)
        ]

        risk_nodes = [
            {
                "id": node_id,
                "level": info["risk"],
                "role": info["role"],
                "label": info["label"],
                "reason": info["reason"],
            }
            for node_id, info in INCIDENT_NODES.items()
            if node_id in model.nx_graph.nodes
        ]

        risk_edges = []
        for u, v, edge_data in model.nx_graph.edges(data=True):
            is_conflict = frozenset((u, v)) in CONFLICT_EDGES
            level = edge_risk(u, v)
            if is_conflict:
                reason = "Relasi konflik antarsekolah; bukan jalan tempuh."
            elif u == 8 or v == 8:
                reason = "Bersentuhan langsung dengan TKP Kampung Tagog Bayur."
            else:
                reason = RISK_LABELS[level]
            risk_edges.append({
                "from": u,
                "to": v,
                "level": level,
                "is_conflict": is_conflict,
                "weight": float(edge_data.get("weight", 1.0)),
                "reason": reason,
            })

        self._send_json({
            "scenario_id": scenario_id,
            "title": metadata.get("title", ""),
            "incident": "Tawuran 3 SMK - Jl. Raya Rambay, Kampung Tagog Bayur (11 Jan 2025)",
            "algorithm_name": solver.__class__.__name__,
            "actors": ACTORS,
            "steps": steps,
            "routes": {
                "sagaranten": route_to_janji + route_to_tkp[1:],
                "agrabinta": route_agrabinta,
                "tegalbuleud": route_tegalbuleud,
            },
            "risk_nodes": risk_nodes,
            "risk_edges": risk_edges,
            "risk_labels": {str(k): v for k, v in RISK_LABELS.items()},
            "sources": INCIDENT_SOURCES,
            "disclaimer": (
                "Perkiraan berbasis catatan dan wawancara polisi pada sumber yang dicantumkan, "
                "bukan data statistik kejadian dan bukan pernyataan bahwa suatu ruas aman secara absolut. "
                "Ruas berlabel 'tidak ada catatan insiden' hanya berarti tidak disebut dalam sumber ini."
            ),
            "recolor": {
                "new_colors": new_colors,
                "changed_nodes": changed_nodes,
                "recolor_cost": len(changed_nodes),
                "chromatic_number": solver.get_chromatic_number(),
                "events": event_summaries,
            },
        })

    def _handle_get_benchmark(self, scenario_id: str):
        yaml_path = BASE_DIR / "cases" / "scenarios" / f"{scenario_id}.yaml"
        if not yaml_path.exists():
            self._send_json({"error": "Skenario tidak ditemukan"}, status=404)
            return

        loader = ScenarioLoader(yaml_path)
        plan = loader.get_execution_plan()
        algos = ["dsatur", "dynamic_welsh_powell", "greedy_coloring"]
        results = []

        for a_key in algos:
            model = loader.build_graph_model()
            solver = AlgorithmRegistry.create(a_key, model)
            t0 = time.perf_counter()
            colors = solver.run(plan.get("start_node"), plan.get("goal_node"))
            t_init = (time.perf_counter() - t0) * 1000

            chi = getattr(solver, "get_chromatic_number", lambda: len(set(c for c in colors.values() if c is not None)))()
            std_dev = getattr(solver, "get_color_balance_std", lambda: 0.0)()

            results.append({
                "algorithm_key": a_key,
                "name": solver.__class__.__name__,
                "chromatic_number": chi,
                "steps": solver.step_count,
                "runtime_ms": round(t_init, 4),
                "color_balance_std": round(std_dev, 4),
            })

        self._send_json({"scenario_id": scenario_id, "comparison": results})


def run_server(port: int = 8080):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, GraphDashboardHandler)
    print("=" * 65)
    print(f"🚀 WEB DASHBOARD TAWURAN PELAJAR AKTIF!")
    print(f"👉 Akses di browser: http://localhost:{port}")
    print(f"   (Tekan Ctrl+C di terminal untuk berhenti)")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
        httpd.server_close()


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)
