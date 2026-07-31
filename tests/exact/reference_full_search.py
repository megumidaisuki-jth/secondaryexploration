"""Independent exhaustive oracle for tiny feasible-routing instances."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from secondaryexploration.model import (
    HypergraphState,
    ModelError,
    PaymentRequest,
    Route,
    TransferStep,
)


@dataclass(frozen=True, slots=True)
class ReferenceOptimum:
    routes: tuple[Route, ...]
    shortest_hops: int | None
    bottleneck: Fraction | None


def exhaustive_optimal_routes(
    state: HypergraphState,
    request: PaymentRequest,
) -> ReferenceOptimum:
    """Enumerate every simple feasible route and retain all ordered optima."""

    if request.source not in state.nodes or request.destination not in state.nodes:
        raise ModelError("reference request endpoints must belong to the state")

    feasible_routes: list[Route] = []

    def visit(
        current: str,
        steps: tuple[TransferStep, ...],
        used_nodes: frozenset[str],
        used_edges: frozenset[str],
    ) -> None:
        if current == request.destination:
            feasible_routes.append(Route(steps=steps))
            return
        if len(steps) >= len(state.nodes) - 1:
            return

        for edge in state.hyperedges:
            if edge.hyperedge_id in used_edges or current not in edge.members:
                continue
            if edge.balance_of(current) < request.amount:
                continue
            for next_node in edge.members:
                if next_node == current or next_node in used_nodes:
                    continue
                visit(
                    next_node,
                    steps
                    + (
                        TransferStep(
                            hyperedge_id=edge.hyperedge_id,
                            payer=current,
                            payee=next_node,
                        ),
                    ),
                    used_nodes | frozenset((next_node,)),
                    used_edges | frozenset((edge.hyperedge_id,)),
                )

    visit(
        request.source,
        (),
        frozenset((request.source,)),
        frozenset(),
    )
    if not feasible_routes:
        return ReferenceOptimum(routes=(), shortest_hops=None, bottleneck=None)

    shortest_hops = min(route.hop_count for route in feasible_routes)
    shortest_routes = [
        route for route in feasible_routes if route.hop_count == shortest_hops
    ]
    scored_routes = [
        (_route_bottleneck(state, request, route), route)
        for route in shortest_routes
    ]
    best_bottleneck = max(score for score, _ in scored_routes)
    optimal_routes = tuple(
        sorted(
            (
                route
                for score, route in scored_routes
                if score == best_bottleneck
            ),
            key=_route_signature,
        )
    )
    return ReferenceOptimum(
        routes=optimal_routes,
        shortest_hops=shortest_hops,
        bottleneck=best_bottleneck,
    )


def _route_bottleneck(
    state: HypergraphState,
    request: PaymentRequest,
    route: Route,
) -> Fraction:
    margins = []
    for step in route.steps:
        edge = state.edge(step.hyperedge_id)
        margins.append(
            Fraction(
                edge.balance_of(step.payer) - request.amount,
                edge.total_balance,
            )
        )
    return min(margins)


def _route_signature(route: Route) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (step.hyperedge_id, step.payer, step.payee) for step in route.steps
    )


__all__ = ["ReferenceOptimum", "exhaustive_optimal_routes"]
