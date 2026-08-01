"""Isolated shortest-path comparison routers for semantic bridges."""

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
from secondaryexploration.topology import HypergraphTopology

from .search import RouteSearchResult, RoutingError


@dataclass(frozen=True, slots=True)
class TopologyRouteSearchResult:
    """A route selected without consulting any balance state."""

    route: Route | None
    shortest_hops: int | None
    tied_route_count: int

    def __post_init__(self) -> None:
        if type(self.tied_route_count) is not int:
            raise RoutingError("tied_route_count must be an integer")
        if self.route is None:
            if self.shortest_hops is not None or self.tied_route_count != 0:
                raise RoutingError("no-path topology result must have empty metadata")
            return
        if not isinstance(self.route, Route):
            raise RoutingError("route must be a Route or None")
        if (
            type(self.shortest_hops) is not int
            or self.shortest_hops != self.route.hop_count
        ):
            raise RoutingError("shortest_hops must equal the route hop count")
        if self.tied_route_count <= 0:
            raise RoutingError("a found route must have a positive tied_route_count")

    @classmethod
    def no_path(cls) -> "TopologyRouteSearchResult":
        return cls(route=None, shortest_hops=None, tied_route_count=0)


@dataclass(frozen=True, slots=True)
class _Arc:
    hyperedge_id: str
    payer: str
    payee: str
    post_payment_fraction: Fraction | None


def find_uniform_shortest_available_route(
    state: HypergraphState,
    request: PaymentRequest,
    rng: random.Random,
) -> RouteSearchResult:
    """Choose uniformly among all shortest routes in the residual hypergraph.

    Unlike the primary router, this comparison policy does not maximize the
    normalized post-payment bottleneck before resolving a tie.
    """

    _validate_state_request_rng(state, request, rng)
    outgoing = _state_arcs(state, request.amount)
    route, shortest_hops, tied_route_count = _uniform_shortest_route(
        outgoing,
        request.source,
        request.destination,
        rng,
    )
    if route is None:
        return RouteSearchResult.no_path()
    fractions = tuple(
        _arc_fraction(outgoing, step)
        for step in route.steps
    )
    return RouteSearchResult(
        route=route,
        shortest_hops=shortest_hops,
        bottleneck=min(fractions),
        tied_route_count=tied_route_count,
    )


def find_balance_independent_uniform_shortest_route(
    topology: HypergraphTopology,
    request: PaymentRequest,
    rng: random.Random,
) -> TopologyRouteSearchResult:
    """Choose a uniform shortest route using topology alone.

    The selected route can later fail settlement because balances play no role
    in this paper-1 bridge policy.
    """

    if not isinstance(topology, HypergraphTopology):
        raise RoutingError("topology must be a HypergraphTopology")
    _validate_request_rng_and_nodes(topology.nodes, request, rng)
    outgoing_lists: dict[str, list[_Arc]] = {
        node_id: [] for node_id in topology.nodes
    }
    for edge in topology.hyperedges:
        for payer in edge.members:
            for payee in edge.members:
                if payer != payee:
                    outgoing_lists[payer].append(
                        _Arc(edge.hyperedge_id, payer, payee, None)
                    )
    outgoing = _canonical_outgoing(outgoing_lists)
    route, shortest_hops, tied_route_count = _uniform_shortest_route(
        outgoing,
        request.source,
        request.destination,
        rng,
    )
    if route is None:
        return TopologyRouteSearchResult.no_path()
    return TopologyRouteSearchResult(
        route=route,
        shortest_hops=shortest_hops,
        tied_route_count=tied_route_count,
    )


def _state_arcs(
    state: HypergraphState,
    amount: int,
) -> dict[str, tuple[_Arc, ...]]:
    outgoing_lists: dict[str, list[_Arc]] = {
        node_id: [] for node_id in state.nodes
    }
    for edge in state.hyperedges:
        for payer in edge.members:
            payer_balance = edge.balance_of(payer)
            if payer_balance < amount:
                continue
            post_fraction = Fraction(
                payer_balance - amount,
                edge.total_balance,
            )
            for payee in edge.members:
                if payer != payee:
                    outgoing_lists[payer].append(
                        _Arc(
                            edge.hyperedge_id,
                            payer,
                            payee,
                            post_fraction,
                        )
                    )
    return _canonical_outgoing(outgoing_lists)


def _canonical_outgoing(
    outgoing_lists: dict[str, list[_Arc]],
) -> dict[str, tuple[_Arc, ...]]:
    return {
        node_id: tuple(
            sorted(arcs, key=lambda arc: (arc.payee, arc.hyperedge_id))
        )
        for node_id, arcs in outgoing_lists.items()
    }


def _uniform_shortest_route(
    outgoing: dict[str, tuple[_Arc, ...]],
    source: str,
    destination: str,
    rng: random.Random,
) -> tuple[Route | None, int | None, int]:
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
    if destination not in distances:
        return None, None, 0

    shortest_hops = distances[destination]
    dag = {
        payer: tuple(
            arc
            for arc in outgoing[payer]
            if distances.get(arc.payee) == distances[payer] + 1
        )
        for payer in distances
        if distances[payer] < shortest_hops
    }
    layers: list[list[str]] = [[] for _ in range(shortest_hops + 1)]
    for node_id, depth in distances.items():
        if depth <= shortest_hops:
            layers[depth].append(node_id)
    suffix_counts = {destination: 1}
    for depth in range(shortest_hops - 1, -1, -1):
        for payer in sorted(layers[depth]):
            suffix_counts[payer] = sum(
                suffix_counts.get(arc.payee, 0)
                for arc in dag.get(payer, ())
            )

    tied_route_count = suffix_counts[source]
    ticket = rng.randrange(tied_route_count) if tied_route_count > 1 else 0
    current = source
    steps: list[TransferStep] = []
    while current != destination:
        for arc in dag[current]:
            route_count = suffix_counts.get(arc.payee, 0)
            if route_count == 0:
                continue
            if ticket < route_count:
                steps.append(
                    TransferStep(arc.hyperedge_id, arc.payer, arc.payee)
                )
                current = arc.payee
                break
            ticket -= route_count
        else:
            raise RuntimeError("shortest-route ticket could not be resolved")
    return Route(tuple(steps)), shortest_hops, tied_route_count


def _arc_fraction(
    outgoing: dict[str, tuple[_Arc, ...]],
    step: TransferStep,
) -> Fraction:
    for arc in outgoing[step.payer]:
        if arc.hyperedge_id == step.hyperedge_id and arc.payee == step.payee:
            if arc.post_payment_fraction is None:
                raise RuntimeError("state route arc is missing its balance fraction")
            return arc.post_payment_fraction
    raise RuntimeError("selected route arc is absent from the residual graph")


def _validate_state_request_rng(
    state: object,
    request: object,
    rng: object,
) -> None:
    if not isinstance(state, HypergraphState):
        raise RoutingError("state must be a HypergraphState")
    _validate_request_rng_and_nodes(state.nodes, request, rng)


def _validate_request_rng_and_nodes(
    nodes: tuple[str, ...],
    request: object,
    rng: object,
) -> None:
    if not isinstance(request, PaymentRequest):
        raise RoutingError("request must be a PaymentRequest")
    if not isinstance(rng, random.Random):
        raise RoutingError("rng must be an explicit random.Random instance")
    node_set = set(nodes)
    if request.source not in node_set:
        raise RoutingError(
            f"request source {request.source!r} is not in the network node set"
        )
    if request.destination not in node_set:
        raise RoutingError(
            f"request destination {request.destination!r} is not in the network node set"
        )


__all__ = [
    "TopologyRouteSearchResult",
    "find_balance_independent_uniform_shortest_route",
    "find_uniform_shortest_available_route",
]
