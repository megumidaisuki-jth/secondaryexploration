"""Efficient, replayable shortest-available-path engine for Gate V1."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import hashlib

from secondaryexploration.model import HypergraphState, PaymentRequest
from secondaryexploration.topology import HypergraphTopology

from .paired import route_choice_rng
from .prior_paper import PriorPaperError


_ACCEPTED = "accepted"
_NO_PATH = "no_path"
_UNAVAILABLE_ENDPOINT = "unavailable_endpoint"
_VALID_STATUSES = {_ACCEPTED, _NO_PATH, _UNAVAILABLE_ENDPOINT}


@dataclass(frozen=True, slots=True)
class PriorPaperReplayOutcome:
    """One compact request outcome under the Gate-V1 comparison policy."""

    request_index: int
    status: str
    hop_count: int | None

    def __post_init__(self) -> None:
        if type(self.request_index) is not int or self.request_index < 1:
            raise PriorPaperError("request_index must be a positive integer")
        if self.status not in _VALID_STATUSES:
            raise PriorPaperError("unknown prior-paper replay status")
        if self.status == _ACCEPTED:
            if type(self.hop_count) is not int or self.hop_count < 1:
                raise PriorPaperError("accepted replay outcome needs positive hops")
        elif self.hop_count is not None:
            raise PriorPaperError("failed replay outcome cannot report hops")


@dataclass(frozen=True, slots=True)
class PriorPaperReplayManifest:
    """Input binding for one complete Gate-V1 comparison-policy replay."""

    topology_fingerprint: str
    initial_state_fingerprint: str
    request_trace_fingerprint: str
    request_count: int
    amount_multiplier: Fraction
    routing_root_seed: int

    def __post_init__(self) -> None:
        _validate_lower_hex(self.topology_fingerprint, 64, "topology fingerprint")
        _validate_lower_hex(
            self.initial_state_fingerprint,
            64,
            "initial-state fingerprint",
        )
        _validate_lower_hex(
            self.request_trace_fingerprint,
            64,
            "request-trace fingerprint",
        )
        if type(self.request_count) is not int or self.request_count < 1:
            raise PriorPaperError("request_count must be a positive integer")
        _validate_multiplier(self.amount_multiplier)
        if type(self.routing_root_seed) is not int or not 0 <= self.routing_root_seed < 2**64:
            raise PriorPaperError("routing_root_seed must be an unsigned 64-bit integer")


@dataclass(frozen=True, slots=True)
class PriorPaperReplayResult:
    """Input-bound fixed-horizon service and path-length record.

    Construction validates the record's local shape. Use
    :func:`validate_prior_paper_replay` for full input-bound re-execution.
    """

    manifest: PriorPaperReplayManifest
    outcomes: tuple[PriorPaperReplayOutcome, ...]
    final_balance_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, PriorPaperReplayManifest):
            raise PriorPaperError("manifest must be a PriorPaperReplayManifest")
        if type(self.outcomes) is not tuple or any(
            not isinstance(outcome, PriorPaperReplayOutcome)
            for outcome in self.outcomes
        ):
            raise PriorPaperError("outcomes must be a replay-outcome tuple")
        if tuple(outcome.request_index for outcome in self.outcomes) != tuple(
            range(1, len(self.outcomes) + 1)
        ):
            raise PriorPaperError("replay request indices must be consecutive")
        if len(self.outcomes) != self.manifest.request_count:
            raise PriorPaperError("outcome count must match the replay manifest")
        _validate_lower_hex(self.final_balance_fingerprint, 64, "final fingerprint")

    @property
    def amount_multiplier(self) -> Fraction:
        return self.manifest.amount_multiplier

    @property
    def routing_root_seed(self) -> int:
        return self.manifest.routing_root_seed

    @property
    def request_count(self) -> int:
        return len(self.outcomes)

    @property
    def accepted_count(self) -> int:
        return sum(outcome.status == _ACCEPTED for outcome in self.outcomes)

    @property
    def no_path_count(self) -> int:
        return sum(outcome.status == _NO_PATH for outcome in self.outcomes)

    @property
    def unavailable_endpoint_count(self) -> int:
        return sum(
            outcome.status == _UNAVAILABLE_ENDPOINT for outcome in self.outcomes
        )

    @property
    def success_rate(self) -> Fraction:
        if not self.outcomes:
            raise PriorPaperError("empty replay has no success rate")
        return Fraction(self.accepted_count, self.request_count)

    @property
    def average_successful_path_length(self) -> Fraction | None:
        hops = tuple(
            outcome.hop_count
            for outcome in self.outcomes
            if outcome.status == _ACCEPTED
        )
        if not hops:
            return None
        return Fraction(sum(hops), len(hops))


def run_prior_paper_replay(
    topology: HypergraphTopology,
    initial_state: HypergraphState,
    requests: tuple[PaymentRequest, ...],
    amount_multiplier: Fraction,
    routing_root_seed: int,
) -> PriorPaperReplayResult:
    """Run a common trace with uniform shortest-available-path routing.

    ``initial_state`` and request amounts must already use the exact doubled
    units defined by :mod:`secondaryexploration.experiments.prior_paper`.
    """

    _validate_inputs(
        topology,
        initial_state,
        requests,
        amount_multiplier,
        routing_root_seed,
    )
    members = tuple(edge.members for edge in topology.hyperedges)
    balances = [
        [balance for _, balance in edge.balances]
        for edge in initial_state.hyperedges
    ]
    node_index = {node_id: index for index, node_id in enumerate(topology.nodes)}
    indexed_members = tuple(
        tuple(node_index[member] for member in edge_members)
        for edge_members in members
    )
    incidence_lists: list[list[tuple[int, int]]] = [
        [] for _ in topology.nodes
    ]
    for edge_index, edge_members in enumerate(indexed_members):
        for position, member_index in enumerate(edge_members):
            incidence_lists[member_index].append((edge_index, position))
    incidence = tuple(tuple(entries) for entries in incidence_lists)
    member_positions = tuple(
        {member_index: position for position, member_index in enumerate(edge_members)}
        for edge_members in indexed_members
    )
    static_distance_cache: dict[int, tuple[int, ...]] = {}
    outcomes: list[PriorPaperReplayOutcome] = []
    for request_index, request in enumerate(requests, start=1):
        source_index = node_index.get(request.source)
        destination_index = node_index.get(request.destination)
        if source_index is None or destination_index is None:
            outcomes.append(
                PriorPaperReplayOutcome(
                    request_index,
                    _UNAVAILABLE_ENDPOINT,
                    None,
                )
            )
            continue
        numerator = request.amount * amount_multiplier.numerator
        if numerator % amount_multiplier.denominator:
            raise PriorPaperError(
                "amount multiplier does not produce an integer replay amount"
            )
        amount = numerator // amount_multiplier.denominator
        static_distances = static_distance_cache.get(destination_index)
        if static_distances is None:
            static_distances = _static_distances_to_target(
                indexed_members,
                incidence,
                destination_index,
            )
            static_distance_cache[destination_index] = static_distances
        static_hops = static_distances[source_index]
        route = None
        if static_hops >= 1:
            route = _uniform_available_route_at_static_distance(
                indexed_members,
                member_positions,
                balances,
                incidence,
                static_distances,
                source_index,
                destination_index,
                static_hops,
                amount,
                routing_root_seed,
                request_index,
            )
        if route is None and static_hops >= 0:
            route = _uniform_shortest_available_route(
                indexed_members,
                balances,
                incidence,
                source_index,
                destination_index,
                amount,
                routing_root_seed,
                request_index,
            )
        if route is None:
            outcomes.append(PriorPaperReplayOutcome(request_index, _NO_PATH, None))
            continue
        for arc in route:
            edge_index, payer_position, _, payee_position = arc
            if balances[edge_index][payer_position] < amount:
                raise RuntimeError("selected replay route became infeasible atomically")
        for arc in route:
            edge_index, payer_position, _, payee_position = arc
            balances[edge_index][payer_position] -= amount
            balances[edge_index][payee_position] += amount
        outcomes.append(
            PriorPaperReplayOutcome(request_index, _ACCEPTED, len(route))
        )
    return PriorPaperReplayResult(
        manifest=_replay_manifest(
            topology,
            initial_state,
            requests,
            amount_multiplier,
            routing_root_seed,
        ),
        outcomes=tuple(outcomes),
        final_balance_fingerprint=_balance_fingerprint(
            topology,
            members,
            balances,
        ),
    )


def validate_prior_paper_replay(
    result: PriorPaperReplayResult,
    topology: HypergraphTopology,
    initial_state: HypergraphState,
    requests: tuple[PaymentRequest, ...],
) -> None:
    """Bind ``result`` to its inputs and verify it by complete re-execution."""

    if not isinstance(result, PriorPaperReplayResult):
        raise PriorPaperError("result must be a PriorPaperReplayResult")
    _validate_inputs(
        topology,
        initial_state,
        requests,
        result.amount_multiplier,
        result.routing_root_seed,
    )
    expected_manifest = _replay_manifest(
        topology,
        initial_state,
        requests,
        result.amount_multiplier,
        result.routing_root_seed,
    )
    if result.manifest != expected_manifest:
        raise PriorPaperError("replay manifest does not bind the supplied inputs")
    exact = run_prior_paper_replay(
        topology,
        initial_state,
        requests,
        result.amount_multiplier,
        result.routing_root_seed,
    )
    if result != exact:
        raise PriorPaperError("result does not match complete input-bound replay")


def state_balance_fingerprint(state: HypergraphState) -> str:
    """Return the replay engine's canonical fingerprint for an immutable state."""

    if not isinstance(state, HypergraphState):
        raise PriorPaperError("state must be a HypergraphState")
    topology = HypergraphTopology.from_edges(
        state.nodes,
        {edge.hyperedge_id: edge.members for edge in state.hyperedges},
    )
    members = tuple(edge.members for edge in state.hyperedges)
    balances = [[balance for _, balance in edge.balances] for edge in state.hyperedges]
    return _balance_fingerprint(topology, members, balances)


def _replay_manifest(
    topology: HypergraphTopology,
    initial_state: HypergraphState,
    requests: tuple[PaymentRequest, ...],
    amount_multiplier: Fraction,
    routing_root_seed: int,
) -> PriorPaperReplayManifest:
    return PriorPaperReplayManifest(
        topology_fingerprint=_topology_fingerprint(topology),
        initial_state_fingerprint=_initial_state_fingerprint(initial_state),
        request_trace_fingerprint=_request_trace_fingerprint(requests),
        request_count=len(requests),
        amount_multiplier=amount_multiplier,
        routing_root_seed=routing_root_seed,
    )


def _topology_fingerprint(topology: HypergraphTopology) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.prior-paper-topology.v2\x00")
    _hash_count(digest, len(topology.nodes))
    for node_id in topology.nodes:
        _hash_field(digest, node_id)
    _hash_count(digest, len(topology.hyperedges))
    for edge in topology.hyperedges:
        _hash_field(digest, edge.hyperedge_id)
        _hash_count(digest, len(edge.members))
        for member in edge.members:
            _hash_field(digest, member)
    return digest.hexdigest()


def _initial_state_fingerprint(state: HypergraphState) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.prior-paper-initial-state.v2\x00")
    _hash_count(digest, len(state.nodes))
    for node_id in state.nodes:
        _hash_field(digest, node_id)
    _hash_count(digest, len(state.hyperedges))
    for edge in state.hyperedges:
        _hash_field(digest, edge.hyperedge_id)
        _hash_count(digest, len(edge.balances))
        for member, balance in edge.balances:
            _hash_field(digest, member)
            _hash_field(digest, str(balance))
    return digest.hexdigest()


def _request_trace_fingerprint(requests: tuple[PaymentRequest, ...]) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.prior-paper-request-trace.v2\x00")
    _hash_count(digest, len(requests))
    for request in requests:
        _hash_field(digest, request.source)
        _hash_field(digest, request.destination)
        _hash_field(digest, str(request.amount))
    return digest.hexdigest()


def _uniform_shortest_available_route(
    members: tuple[tuple[int, ...], ...],
    balances: list[list[int]],
    incidence: tuple[tuple[tuple[int, int], ...], ...],
    source: int,
    destination: int,
    amount: int,
    routing_root_seed: int,
    request_index: int,
) -> tuple[tuple[int, int, int, int], ...] | None:
    node_count = len(incidence)
    distances = [-1] * node_count
    distances[source] = 0
    eligible_arcs: dict[int, tuple[tuple[int, int, int, int], ...]] = {}
    queue: deque[int] = deque((source,))
    target_distance = -1
    while queue:
        payer = queue.popleft()
        depth = distances[payer]
        if target_distance >= 0 and depth >= target_distance:
            continue
        arcs: list[tuple[int, int, int, int]] = []
        for edge_index, payer_position in incidence[payer]:
            if balances[edge_index][payer_position] < amount:
                continue
            for payee_position, payee in enumerate(members[edge_index]):
                if payee != payer:
                    arcs.append((edge_index, payer_position, payee, payee_position))
        arcs.sort(key=lambda arc: (arc[2], arc[0]))
        eligible_arcs[payer] = tuple(arcs)
        for arc in arcs:
            payee = arc[2]
            if distances[payee] < 0:
                distances[payee] = depth + 1
                if payee == destination:
                    target_distance = depth + 1
                queue.append(payee)
    if target_distance < 0:
        return None

    shortest_hops = target_distance
    layers: list[list[int]] = [[] for _ in range(shortest_hops + 1)]
    for node_id, depth in enumerate(distances):
        if 0 <= depth <= shortest_hops:
            layers[depth].append(node_id)
    suffix_counts = [0] * node_count
    suffix_counts[destination] = 1
    for depth in range(shortest_hops - 1, -1, -1):
        for payer in layers[depth]:
            suffix_counts[payer] = sum(
                suffix_counts[arc[2]]
                for arc in eligible_arcs.get(payer, ())
                if distances[arc[2]] == depth + 1
            )
    tied_count = suffix_counts[source]
    rng = route_choice_rng(routing_root_seed, request_index)
    ticket = rng.randrange(tied_count) if tied_count > 1 else 0
    route: list[tuple[int, int, int, int]] = []
    current = source
    while current != destination:
        for arc in eligible_arcs[current]:
            payee = arc[2]
            if distances[payee] != distances[current] + 1:
                continue
            count = suffix_counts[payee]
            if count == 0:
                continue
            if ticket < count:
                route.append(arc)
                current = payee
                break
            ticket -= count
        else:
            raise RuntimeError("replay route ticket could not be resolved")
    return tuple(route)


def _uniform_available_route_at_static_distance(
    members: tuple[tuple[int, ...], ...],
    member_positions: tuple[dict[int, int], ...],
    balances: list[list[int]],
    incidence: tuple[tuple[tuple[int, int], ...], ...],
    static_distances: tuple[int, ...],
    source: int,
    destination: int,
    shortest_hops: int,
    amount: int,
    routing_root_seed: int,
    request_index: int,
) -> tuple[tuple[int, int, int, int], ...] | None:
    """Search only the static shortest-path DAG before full fallback."""

    node_count = len(incidence)
    distances = [-1] * node_count
    distances[source] = 0
    layers: list[list[int]] = [[] for _ in range(shortest_hops + 1)]
    layers[0].append(source)
    eligible_arcs: dict[int, tuple[tuple[int, int, int, int], ...]] = {}
    for depth in range(shortest_hops):
        remaining_after_step = shortest_hops - depth - 1
        for payer in layers[depth]:
            arcs: list[tuple[int, int, int, int]] = []
            for edge_index, payer_position in incidence[payer]:
                if balances[edge_index][payer_position] < amount:
                    continue
                if remaining_after_step == 0:
                    payee_position = member_positions[edge_index].get(destination)
                    if payee_position is not None and destination != payer:
                        arcs.append(
                            (
                                edge_index,
                                payer_position,
                                destination,
                                payee_position,
                            )
                        )
                    continue
                for payee_position, payee in enumerate(members[edge_index]):
                    if (
                        payee != payer
                        and static_distances[payee] == remaining_after_step
                    ):
                        arcs.append(
                            (edge_index, payer_position, payee, payee_position)
                        )
            arcs.sort(key=lambda arc: (arc[2], arc[0]))
            eligible_arcs[payer] = tuple(arcs)
            for arc in arcs:
                payee = arc[2]
                if distances[payee] < 0:
                    distances[payee] = depth + 1
                    layers[depth + 1].append(payee)
    if distances[destination] != shortest_hops:
        return None
    return _ticketed_route_from_layers(
        eligible_arcs,
        distances,
        layers,
        source,
        destination,
        shortest_hops,
        routing_root_seed,
        request_index,
    )


def _ticketed_route_from_layers(
    eligible_arcs: dict[int, tuple[tuple[int, int, int, int], ...]],
    distances: list[int],
    layers: list[list[int]],
    source: int,
    destination: int,
    shortest_hops: int,
    routing_root_seed: int,
    request_index: int,
) -> tuple[tuple[int, int, int, int], ...]:
    suffix_counts = [0] * len(distances)
    suffix_counts[destination] = 1
    for depth in range(shortest_hops - 1, -1, -1):
        for payer in layers[depth]:
            suffix_counts[payer] = sum(
                suffix_counts[arc[2]]
                for arc in eligible_arcs.get(payer, ())
                if distances[arc[2]] == depth + 1
            )
    tied_count = suffix_counts[source]
    if tied_count <= 0:
        raise RuntimeError("reachable shortest-path DAG has zero suffix count")
    rng = route_choice_rng(routing_root_seed, request_index)
    ticket = rng.randrange(tied_count) if tied_count > 1 else 0
    route: list[tuple[int, int, int, int]] = []
    current = source
    while current != destination:
        for arc in eligible_arcs[current]:
            payee = arc[2]
            if distances[payee] != distances[current] + 1:
                continue
            count = suffix_counts[payee]
            if count == 0:
                continue
            if ticket < count:
                route.append(arc)
                current = payee
                break
            ticket -= count
        else:
            raise RuntimeError("replay route ticket could not be resolved")
    return tuple(route)


def _static_distances_to_target(
    members: tuple[tuple[int, ...], ...],
    incidence: tuple[tuple[tuple[int, int], ...], ...],
    destination: int,
) -> tuple[int, ...]:
    """Compute topology-only distances, expanding each undirected edge once."""

    distances = [-1] * len(incidence)
    distances[destination] = 0
    visited_edges: set[int] = set()
    queue: deque[int] = deque((destination,))
    while queue:
        current = queue.popleft()
        next_distance = distances[current] + 1
        for edge_index, _ in incidence[current]:
            if edge_index in visited_edges:
                continue
            visited_edges.add(edge_index)
            for member in members[edge_index]:
                if distances[member] < 0:
                    distances[member] = next_distance
                    queue.append(member)
    return tuple(distances)


def _balance_fingerprint(
    topology: HypergraphTopology,
    members: tuple[tuple[str, ...], ...],
    balances: list[list[int]],
) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.prior-paper-balance-state.v2\x00")
    _hash_count(digest, len(topology.nodes))
    for node_id in topology.nodes:
        _hash_field(digest, node_id)
    _hash_count(digest, len(topology.hyperedges))
    for edge, edge_members, edge_balances in zip(
        topology.hyperedges,
        members,
        balances,
    ):
        _hash_field(digest, edge.hyperedge_id)
        _hash_count(digest, len(edge_members))
        for member, balance in zip(edge_members, edge_balances):
            _hash_field(digest, member)
            _hash_field(digest, str(balance))
    return digest.hexdigest()


def _hash_field(digest, value: str) -> None:
    encoded = value.encode("utf-8")
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)


def _hash_count(digest, value: int) -> None:
    digest.update(value.to_bytes(8, "big"))


def _validate_inputs(
    topology: object,
    initial_state: object,
    requests: object,
    amount_multiplier: object,
    routing_root_seed: object,
) -> None:
    if not isinstance(topology, HypergraphTopology):
        raise PriorPaperError("topology must be a HypergraphTopology")
    if not isinstance(initial_state, HypergraphState):
        raise PriorPaperError("initial_state must be a HypergraphState")
    expected = tuple(
        (edge.hyperedge_id, edge.members) for edge in topology.hyperedges
    )
    observed = tuple(
        (edge.hyperedge_id, edge.members) for edge in initial_state.hyperedges
    )
    if initial_state.nodes != topology.nodes or observed != expected:
        raise PriorPaperError("initial state structure must match the topology")
    if type(requests) is not tuple or not requests or any(
        not isinstance(request, PaymentRequest) for request in requests
    ):
        raise PriorPaperError("requests must be a nonempty PaymentRequest tuple")
    _validate_multiplier(amount_multiplier)
    if type(routing_root_seed) is not int or not 0 <= routing_root_seed < 2**64:
        raise PriorPaperError("routing_root_seed must be an unsigned 64-bit integer")


def _validate_multiplier(value: object) -> None:
    if not isinstance(value, Fraction) or value <= 0:
        raise PriorPaperError("amount_multiplier must be a positive Fraction")


def _validate_lower_hex(value: object, length: int, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != length
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PriorPaperError(f"{field} must be lowercase hexadecimal")


__all__ = [
    "PriorPaperReplayOutcome",
    "PriorPaperReplayManifest",
    "PriorPaperReplayResult",
    "run_prior_paper_replay",
    "state_balance_fingerprint",
    "validate_prior_paper_replay",
]
