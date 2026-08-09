"""Complete feasible-path search with exact balance-aware tie-breaking."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import random

from secondaryexploration.model import (
    HypergraphState,
    PaymentRequest,
    Route,
    TransferStep,
)


class RoutingError(ValueError):
    """Raised when a route-search request or result violates its contract."""


@dataclass(frozen=True, slots=True)
class RouteSearchResult:
    """A selected optimal route plus auditable search metadata."""

    route: Route | None
    shortest_hops: int | None
    bottleneck: Fraction | None
    tied_route_count: int

    def __post_init__(self) -> None:
        if type(self.tied_route_count) is not int:
            raise RoutingError("tied_route_count must be an integer")

        if self.route is None:
            if (
                self.shortest_hops is not None
                or self.bottleneck is not None
                or self.tied_route_count != 0
            ):
                raise RoutingError("no-path result must have empty route metadata")
            return

        if not isinstance(self.route, Route):
            raise RoutingError("route must be a Route or None")
        if (
            type(self.shortest_hops) is not int
            or self.shortest_hops != self.route.hop_count
        ):
            raise RoutingError("shortest_hops must equal the found route hop count")
        if not isinstance(self.bottleneck, Fraction):
            raise RoutingError("a found route must have an exact Fraction bottleneck")
        if not 0 <= self.bottleneck <= 1:
            raise RoutingError("route bottleneck must be in [0, 1]")
        if self.tied_route_count <= 0:
            raise RoutingError("a found route must have a positive tied_route_count")

    @classmethod
    def no_path(cls) -> "RouteSearchResult":
        """Return the canonical result for a globally infeasible request."""

        return cls(
            route=None,
            shortest_hops=None,
            bottleneck=None,
            tied_route_count=0,
        )


@dataclass(frozen=True, slots=True)
class _ResidualArc:
    hyperedge_id: str
    payer: str
    payee: str
    post_payment_fraction: Fraction


def find_feasible_route(
    state: HypergraphState,
    request: PaymentRequest,
    rng: random.Random,
) -> RouteSearchResult:
    """Search the full residual hypergraph and select one optimal route."""

    _validate_search_inputs(state, request, rng)
    outgoing = _build_residual_arcs(state, request.amount)
    distances = _breadth_first_distances(
        outgoing,
        request.source,
        request.destination,
    )
    if request.destination not in distances:
        return RouteSearchResult.no_path()

    shortest_hops = distances[request.destination]
    shortest_dag = _shortest_path_dag(outgoing, distances, shortest_hops)
    bottleneck = _maximum_bottleneck(
        shortest_dag,
        distances,
        request.source,
        request.destination,
        shortest_hops,
    )
    suffix_counts = _optimal_suffix_counts(
        shortest_dag,
        distances,
        request.destination,
        shortest_hops,
        bottleneck,
    )
    tied_route_count = suffix_counts[request.source]
    ticket = rng.randrange(tied_route_count) if tied_route_count > 1 else 0
    route = _route_for_ticket(
        shortest_dag,
        suffix_counts,
        request.source,
        request.destination,
        bottleneck,
        ticket,
    )
    return RouteSearchResult(
        route=route,
        shortest_hops=shortest_hops,
        bottleneck=bottleneck,
        tied_route_count=tied_route_count,
    )


def _validate_search_inputs(
    state: object,
    request: object,
    rng: object,
) -> None:
    if not isinstance(state, HypergraphState):
        raise RoutingError("state must be a HypergraphState")
    if not isinstance(request, PaymentRequest):
        raise RoutingError("request must be a PaymentRequest")
    if not isinstance(rng, random.Random):
        raise RoutingError("rng must be an explicit random.Random instance")
    node_set = set(state.nodes)
    if request.source not in node_set:
        raise RoutingError(
            f"request source {request.source!r} is not in the network node set"
        )
    if request.destination not in node_set:
        raise RoutingError(
            f"request destination {request.destination!r} is not in the network node set"
        )


def _build_residual_arcs(
    state: HypergraphState,
    amount: int,
) -> dict[str, tuple[_ResidualArc, ...]]:
    outgoing_lists: dict[str, list[_ResidualArc]] = {
        node_id: [] for node_id in state.nodes
    }
    for edge in state.hyperedges:
        # ``balances`` is already the canonical member ordering.  Iterating it
        # directly avoids rebuilding ``members``, rescanning for
        # ``balance_of``, and recomputing the conserved edge total for every
        # payer/payee pair in this hot path.
        edge_balances = edge.balances
        edge_total = sum(balance for _, balance in edge_balances)
        for payer, payer_balance in edge_balances:
            if payer_balance < amount:
                continue
            residual_fraction = Fraction(
                payer_balance - amount,
                edge_total,
            )
            for payee, _ in edge_balances:
                if payee == payer:
                    continue
                outgoing_lists[payer].append(
                    _ResidualArc(
                        hyperedge_id=edge.hyperedge_id,
                        payer=payer,
                        payee=payee,
                        post_payment_fraction=residual_fraction,
                    )
                )

    return {
        node_id: tuple(
            sorted(
                arcs,
                key=lambda arc: (arc.payee, arc.hyperedge_id),
            )
        )
        for node_id, arcs in outgoing_lists.items()
    }


def _breadth_first_distances(
    outgoing: dict[str, tuple[_ResidualArc, ...]],
    source: str,
    destination: str,
) -> dict[str, int]:
    distances = {source: 0}
    queue: deque[str] = deque((source,))
    while queue:
        payer = queue.popleft()
        payer_distance = distances[payer]
        if destination in distances and payer_distance >= distances[destination]:
            continue
        for arc in outgoing[payer]:
            if arc.payee not in distances:
                distances[arc.payee] = payer_distance + 1
                queue.append(arc.payee)
    return distances


def _shortest_path_dag(
    outgoing: dict[str, tuple[_ResidualArc, ...]],
    distances: dict[str, int],
    shortest_hops: int,
) -> dict[str, tuple[_ResidualArc, ...]]:
    return {
        payer: tuple(
            arc
            for arc in arcs
            if distances.get(arc.payee) == distances[payer] + 1
        )
        for payer, arcs in outgoing.items()
        if payer in distances and distances[payer] < shortest_hops
    }


def _maximum_bottleneck(
    shortest_dag: dict[str, tuple[_ResidualArc, ...]],
    distances: dict[str, int],
    source: str,
    destination: str,
    shortest_hops: int,
) -> Fraction:
    best: dict[str, Fraction] = {source: Fraction(1, 1)}
    nodes_by_depth = _nodes_by_depth(distances, shortest_hops)
    for depth in range(shortest_hops):
        for payer in nodes_by_depth[depth]:
            if payer not in best:
                continue
            for arc in shortest_dag.get(payer, ()):
                candidate = min(best[payer], arc.post_payment_fraction)
                if arc.payee not in best or candidate > best[arc.payee]:
                    best[arc.payee] = candidate
    return best[destination]


def _optimal_suffix_counts(
    shortest_dag: dict[str, tuple[_ResidualArc, ...]],
    distances: dict[str, int],
    destination: str,
    shortest_hops: int,
    bottleneck: Fraction,
) -> dict[str, int]:
    suffix_counts = {destination: 1}
    nodes_by_depth = _nodes_by_depth(distances, shortest_hops)
    for depth in range(shortest_hops - 1, -1, -1):
        for payer in nodes_by_depth[depth]:
            suffix_counts[payer] = sum(
                suffix_counts.get(arc.payee, 0)
                for arc in shortest_dag.get(payer, ())
                if arc.post_payment_fraction >= bottleneck
            )
    return suffix_counts


def _route_for_ticket(
    shortest_dag: dict[str, tuple[_ResidualArc, ...]],
    suffix_counts: dict[str, int],
    source: str,
    destination: str,
    bottleneck: Fraction,
    ticket: int,
) -> Route:
    current = source
    steps: list[TransferStep] = []
    while current != destination:
        for arc in shortest_dag[current]:
            if arc.post_payment_fraction < bottleneck:
                continue
            route_count = suffix_counts.get(arc.payee, 0)
            if route_count == 0:
                continue
            if ticket < route_count:
                steps.append(
                    TransferStep(
                        hyperedge_id=arc.hyperedge_id,
                        payer=arc.payer,
                        payee=arc.payee,
                    )
                )
                current = arc.payee
                break
            ticket -= route_count
        else:
            raise RuntimeError("optimal-route ticket could not be resolved")
    return Route(steps=tuple(steps))


def _nodes_by_depth(
    distances: dict[str, int],
    maximum_depth: int,
) -> tuple[tuple[str, ...], ...]:
    layers: list[list[str]] = [[] for _ in range(maximum_depth + 1)]
    for node_id, depth in distances.items():
        if depth <= maximum_depth:
            layers[depth].append(node_id)
    return tuple(tuple(sorted(layer)) for layer in layers)


__all__ = [
    "RouteSearchResult",
    "RoutingError",
    "find_feasible_route",
]
