"""Component-wise exact cost witnesses for one topology simulation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from secondaryexploration.experiments import TopologyVariant
from secondaryexploration.simulation import CoreSimulationResult

from .errors import MetricError


@dataclass(frozen=True, slots=True)
class RunCostMetrics:
    """Auditable static and dynamic costs without an aggregate score."""

    variant: TopologyVariant
    simulation: CoreSimulationResult

    def __post_init__(self) -> None:
        if not isinstance(self.variant, TopologyVariant):
            raise MetricError("variant must be a TopologyVariant")
        if not isinstance(self.simulation, CoreSimulationResult):
            raise MetricError("simulation must be a CoreSimulationResult")
        if self.simulation.initial_state != self.variant.initial_state:
            raise MetricError("simulation initial state does not match the variant")

    @property
    def locked_capital(self) -> int:
        return self.variant.initial_state.total_balance

    @property
    def hyperedge_count(self) -> int:
        return self.variant.topology.resources.hyperedge_count

    @property
    def incidence_count(self) -> int:
        return self.variant.topology.resources.incidence_count

    @property
    def maximum_arity(self) -> int:
        return self.variant.topology.resources.maximum_arity

    @property
    def pairwise_member_exposure(self) -> int:
        return self.variant.topology.resources.pairwise_member_exposure

    @property
    def accepted_request_count(self) -> int:
        return sum(outcome.accepted for outcome in self.simulation.outcomes)

    @property
    def accepted_value(self) -> int:
        return sum(
            outcome.request.amount
            for outcome in self.simulation.outcomes
            if outcome.accepted
        )

    @property
    def traversed_hyperedge_count(self) -> int:
        return sum(self._arity_counts().values())

    @property
    def signaled_participant_slots(self) -> int:
        return sum(
            arity * count for arity, count in self._arity_counts().items()
        )

    @property
    def quadratic_coordination_exposure(self) -> int:
        return sum(
            arity * arity * count
            for arity, count in self._arity_counts().items()
        )

    @property
    def unique_signaled_participants(self) -> int:
        edge_members = {
            edge.hyperedge_id: set(edge.members)
            for edge in self.variant.topology.hyperedges
        }
        total = 0
        for outcome in self.simulation.outcomes:
            route = outcome.search_result.route
            if route is None:
                continue
            signaled: set[str] = set()
            for step in route.steps:
                signaled.update(edge_members[step.hyperedge_id])
            total += len(signaled)
        return total

    @property
    def route_arity_histogram(self) -> tuple[tuple[int, int], ...]:
        return tuple(sorted(self._arity_counts().items()))

    def _arity_counts(self) -> Counter[int]:
        arity_by_edge = {
            edge.hyperedge_id: edge.arity for edge in self.variant.topology.hyperedges
        }
        counts: Counter[int] = Counter()
        for outcome in self.simulation.outcomes:
            route = outcome.search_result.route
            if route is None:
                continue
            for step in route.steps:
                try:
                    counts[arity_by_edge[step.hyperedge_id]] += 1
                except KeyError as exc:
                    raise MetricError(
                        "simulation route references an edge outside the variant"
                    ) from exc
        return counts


__all__ = ["RunCostMetrics"]
