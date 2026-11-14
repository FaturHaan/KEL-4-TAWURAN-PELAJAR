import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.base_algorithm import BaseGraphAlgorithm


@dataclass
class RerouteResult:
    """Hasil eksekusi event dinamis graf (re-routing / re-coloring)."""
    description: str
    target_edge: Optional[Tuple[int, int]] = None
    new_weight: Optional[float] = None
    path: Optional[List[int]] = None
    cost: Optional[float] = None
    elapsed_ms: float = 0.0

    # Atribut khusus algoritma Pewarnaan Graf (Graph Coloring)
    target_node: Optional[Any] = None
    event_type: Optional[str] = None
    colors: Optional[Dict[Any, int]] = None
    recolor_cost: int = 0
    chromatic_number: int = 0
    distribution: Optional[Dict[int, int]] = None
    color_balance_std: float = 0.0


@dataclass
class SimulationResult:
    """Hasil akhir simulasi graf (mendukung rute terpendek dan pewarnaan simpul)."""
    metadata: Dict[str, Any]
    algorithm_name: str
    initial_path: Optional[List[int]] = None
    initial_cost: Optional[float] = None
    initial_elapsed_ms: float = 0.0
    reroutes: List[RerouteResult] = field(default_factory=list)
    skipped_events: List[Dict[str, Any]] = field(default_factory=list)

    # Atribut khusus algoritma Pewarnaan Graf (Graph Coloring)
    colors: Dict[Any, int] = field(default_factory=dict)
    chromatic_number: int = 0
    color_distribution: Dict[int, int] = field(default_factory=dict)
    color_balance_std: float = 0.0


class SimulationObserver:

    def on_initial_route(self, result: SimulationResult) -> None:
        pass

    def on_reroute(self, result: SimulationResult, reroute: RerouteResult) -> None:
        pass

    def on_event_skipped(self, result: SimulationResult, event: Dict[str, Any]) -> None:
        pass

    def on_complete(self, result: SimulationResult) -> None:
        pass


class SimulationRunner:

    def __init__(
        self,
        solver: BaseGraphAlgorithm,
        plan: Dict[str, Any],
        metadata: Dict[str, Any],
        observers: Optional[List[SimulationObserver]] = None,
    ):
        self.solver = solver
        self.plan = plan
        self.metadata = metadata
        self.observers: List[SimulationObserver] = list(observers or [])

    def attach(self, observer: SimulationObserver) -> None:
        self.observers.append(observer)

    def execute(self) -> SimulationResult:
        start_node = self.plan.get("start_node")
        goal_node = self.plan.get("goal_node")

        t_start = time.perf_counter()
        raw_result = self.solver.run(start_node, goal_node)
        initial_elapsed_ms = (time.perf_counter() - t_start) * 1000

        # Deteksi tipe hasil eksekusi (Coloring dict vs Pathfinding tuple)
        if isinstance(raw_result, dict):
            colors = raw_result
            chromatic_number = getattr(
                self.solver,
                "get_chromatic_number",
                lambda: len(set(c for c in colors.values() if c is not None)),
            )()
            distribution = getattr(
                self.solver,
                "get_color_distribution",
                lambda: {},
            )()
            color_balance_std = getattr(
                self.solver,
                "get_color_balance_std",
                lambda: 0.0,
            )()

            result = SimulationResult(
                metadata=self.metadata,
                algorithm_name=self.solver.__class__.__name__,
                initial_path=list(colors.keys()),
                initial_cost=float(chromatic_number),
                initial_elapsed_ms=initial_elapsed_ms,
                colors=colors,
                chromatic_number=chromatic_number,
                color_distribution=distribution,
                color_balance_std=color_balance_std,
            )
        elif isinstance(raw_result, tuple) and len(raw_result) == 2:
            path, cost = raw_result
            result = SimulationResult(
                metadata=self.metadata,
                algorithm_name=self.solver.__class__.__name__,
                initial_path=path,
                initial_cost=cost,
                initial_elapsed_ms=initial_elapsed_ms,
            )
        else:
            result = SimulationResult(
                metadata=self.metadata,
                algorithm_name=self.solver.__class__.__name__,
                initial_path=None,
                initial_cost=None,
                initial_elapsed_ms=initial_elapsed_ms,
            )

        self._notify("on_initial_route", result)

        supported_types = getattr(self.solver, "SUPPORTED_EVENT_TYPES", None)
        for event in self.plan.get("events", []):
            if supported_types is not None and event.get("type") not in supported_types:
                result.skipped_events.append(event)
                self._notify("on_event_skipped", result, event)
                continue
            reroute = self._execute_event(event, start_node, goal_node)
            result.reroutes.append(reroute)
            self._notify("on_reroute", result, reroute)

        self._notify("on_complete", result)
        return result

    def _execute_event(
        self, event: Dict[str, Any], start_node: Optional[int], goal_node: Optional[int]
    ) -> RerouteResult:
        event_data = dict(event)
        if start_node is not None and "start" not in event_data:
            event_data["start"] = start_node
        if goal_node is not None and "goal" not in event_data:
            event_data["goal"] = goal_node

        target_edge = None
        if "target_edge" in event:
            target_edge = tuple(event["target_edge"])
            event_data["target_edge"] = target_edge
            event_data["edge"] = target_edge

        new_weight = event.get("new_weight", event.get("weight"))
        if new_weight is not None:
            event_data["new_weight"] = new_weight

        target_node = event.get("target_node")
        if target_node is not None:
            event_data["target_node"] = target_node

        t_start = time.perf_counter()
        raw_event_result = self.solver.handle_dynamic_event(event_data)
        elapsed_ms = (time.perf_counter() - t_start) * 1000

        # Deteksi tipe hasil event dinamis (Coloring dict vs Pathfinding tuple)
        if isinstance(raw_event_result, dict):
            event_colors = raw_event_result.get("colors", getattr(self.solver, "colors", {}))
            recolor_cost = raw_event_result.get(
                "recolor_cost", getattr(self.solver, "recolor_cost", 0)
            )
            chromatic_num = raw_event_result.get(
                "chromatic_number",
                getattr(
                    self.solver,
                    "get_chromatic_number",
                    lambda: len(set(c for c in event_colors.values() if c is not None)),
                )(),
            )
            dist = getattr(self.solver, "get_color_distribution", lambda: {})()
            bal_std = getattr(self.solver, "get_color_balance_std", lambda: 0.0)()

            return RerouteResult(
                description=event.get("description", ""),
                target_edge=target_edge,
                new_weight=new_weight,
                path=list(event_colors.keys()),
                cost=float(chromatic_num),
                elapsed_ms=elapsed_ms,
                target_node=target_node,
                event_type=event.get("type"),
                colors=event_colors,
                recolor_cost=recolor_cost,
                chromatic_number=chromatic_num,
                distribution=dist,
                color_balance_std=bal_std,
            )
        elif isinstance(raw_event_result, tuple) and len(raw_event_result) == 2:
            path, cost = raw_event_result
            return RerouteResult(
                description=event.get("description", ""),
                target_edge=target_edge,
                new_weight=new_weight,
                path=path,
                cost=cost,
                elapsed_ms=elapsed_ms,
                target_node=target_node,
                event_type=event.get("type"),
            )
        else:
            return RerouteResult(
                description=event.get("description", ""),
                target_edge=target_edge,
                new_weight=new_weight,
                elapsed_ms=elapsed_ms,
                target_node=target_node,
                event_type=event.get("type"),
            )

    def _notify(self, hook: str, *args) -> None:
        for observer in self.observers:
            getattr(observer, hook)(*args)
