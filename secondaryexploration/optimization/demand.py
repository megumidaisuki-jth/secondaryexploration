"""Exact training-demand objective for the demand-aware HPN variant."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
from itertools import combinations
from math import comb
from types import MappingProxyType
from typing import Mapping

from secondaryexploration.model import PaymentRequest
from secondaryexploration.topology import HypergraphTopology, ParentGraph


DEMAND_OBJECTIVE_VERSION = "demand-aware-objective.v1"
_MAX_UNSIGNED_64 = 2**64 - 1


class OptimizationError(ValueError):
    """Raised when a demand-aware optimization contract is violated."""


@dataclass(frozen=True, slots=True)
class DirectedDemandMatrix:
    """Canonical amount-weighted demand for every ordered distinct node pair."""

    nodes: tuple[str, ...]
    values: tuple[tuple[str, str, int], ...]
    _lookup: Mapping[tuple[str, str], int] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if type(self.nodes) is not tuple or len(self.nodes) < 2:
            raise OptimizationError("demand nodes must be a tuple of at least two nodes")
        if tuple(sorted(self.nodes)) != self.nodes or len(set(self.nodes)) != len(
            self.nodes
        ):
            raise OptimizationError("demand nodes must be canonical and unique")
        for node_id in self.nodes:
            _validate_node_id(node_id)
        if type(self.values) is not tuple:
            raise OptimizationError("demand values must be a canonical tuple")
        expected_pairs = tuple(
            (source, destination)
            for source in self.nodes
            for destination in self.nodes
            if source != destination
        )
        observed_pairs: list[tuple[str, str]] = []
        for entry in self.values:
            if type(entry) is not tuple or len(entry) != 3:
                raise OptimizationError(
                    "each demand value must be a (source, destination, amount) tuple"
                )
            source, destination, amount = entry
            if type(amount) is not int or amount < 0:
                raise OptimizationError("demand amounts must be non-negative integers")
            observed_pairs.append((source, destination))
        if tuple(observed_pairs) != expected_pairs:
            raise OptimizationError(
                "demand values must contain every ordered distinct pair canonically"
            )
        object.__setattr__(
            self,
            "_lookup",
            MappingProxyType(
                {
                    (source, destination): amount
                    for source, destination, amount in self.values
                }
            ),
        )

    @classmethod
    def from_requests(
        cls,
        nodes: Iterable[str],
        requests: Iterable[PaymentRequest],
    ) -> "DirectedDemandMatrix":
        if isinstance(nodes, (str, bytes)):
            raise OptimizationError("demand nodes must be an iterable of identifiers")
        try:
            canonical_nodes = tuple(sorted(tuple(nodes)))
        except TypeError as exc:
            raise OptimizationError(
                "demand nodes must be an iterable of identifiers"
            ) from exc
        if len(canonical_nodes) < 2 or len(set(canonical_nodes)) != len(
            canonical_nodes
        ):
            raise OptimizationError("demand nodes must contain at least two unique nodes")
        for node_id in canonical_nodes:
            _validate_node_id(node_id)
        if isinstance(requests, (str, bytes)):
            raise OptimizationError("requests must be an iterable of PaymentRequest")
        try:
            request_tuple = tuple(requests)
        except TypeError as exc:
            raise OptimizationError(
                "requests must be an iterable of PaymentRequest"
            ) from exc
        if any(not isinstance(request, PaymentRequest) for request in request_tuple):
            raise OptimizationError("requests must contain only PaymentRequest objects")
        node_set = set(canonical_nodes)
        totals = {
            (source, destination): 0
            for source in canonical_nodes
            for destination in canonical_nodes
            if source != destination
        }
        for request in request_tuple:
            if request.source not in node_set or request.destination not in node_set:
                raise OptimizationError("training request endpoint is outside demand nodes")
            totals[(request.source, request.destination)] += request.amount
        return cls(
            canonical_nodes,
            tuple(
                (source, destination, totals[(source, destination)])
                for source in canonical_nodes
                for destination in canonical_nodes
                if source != destination
            ),
        )

    def amount(self, source: str, destination: str) -> int:
        if source == destination or source not in self.nodes or destination not in self.nodes:
            raise OptimizationError("demand lookup requires distinct declared nodes")
        return self._lookup[(source, destination)]

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.directed-demand.v1\x00")
        _hash_count(digest, len(self.nodes))
        for node_id in self.nodes:
            _hash_field(digest, node_id)
        _hash_count(digest, len(self.values))
        for source, destination, amount in self.values:
            _hash_field(digest, source)
            _hash_field(digest, destination)
            _hash_integer(digest, amount)
        return digest.hexdigest()

    @property
    def total_bidirectional_volume(self) -> int:
        return sum(
            min(self.amount(left, right), self.amount(right, left))
            for left, right in combinations(self.nodes, 2)
        )

    @property
    def total_directional_imbalance(self) -> int:
        return sum(
            abs(self.amount(left, right) - self.amount(right, left))
            for left, right in combinations(self.nodes, 2)
        )


@dataclass(frozen=True, slots=True)
class DemandAwareObjectiveWeights:
    """Frozen rational coefficients for the four-term training objective."""

    bidirectional_capture: Fraction
    directional_imbalance: Fraction
    participation: Fraction
    coordination_overlap: Fraction

    def __post_init__(self) -> None:
        fields = (
            ("bidirectional_capture", self.bidirectional_capture),
            ("directional_imbalance", self.directional_imbalance),
            ("participation", self.participation),
            ("coordination_overlap", self.coordination_overlap),
        )
        for name, value in fields:
            if not isinstance(value, Fraction) or value < 0:
                raise OptimizationError(f"{name} weight must be a non-negative Fraction")
        if self.bidirectional_capture <= 0:
            raise OptimizationError("bidirectional_capture weight must be positive")


@dataclass(frozen=True, slots=True)
class DemandAwareTrainingManifest:
    """Input and constraint binding for one demand-aware topology training cell."""

    parent_fingerprint: str
    demand_fingerprint: str
    node_count: int
    incidence_budget: int
    maximum_arity: int
    weights: DemandAwareObjectiveWeights
    objective_version: str = DEMAND_OBJECTIVE_VERSION

    def __post_init__(self) -> None:
        _validate_digest(self.parent_fingerprint, "parent_fingerprint")
        _validate_digest(self.demand_fingerprint, "demand_fingerprint")
        if (
            type(self.node_count) is not int
            or not 2 <= self.node_count <= _MAX_UNSIGNED_64
        ):
            raise OptimizationError("node_count must be an integer of at least two")
        if (
            type(self.incidence_budget) is not int
            or not self.node_count <= self.incidence_budget <= _MAX_UNSIGNED_64
        ):
            raise OptimizationError("incidence_budget must be at least node_count")
        if (
            type(self.maximum_arity) is not int
            or not 2 <= self.maximum_arity <= self.node_count
        ):
            raise OptimizationError("maximum_arity must be between two and node_count")
        if not isinstance(self.weights, DemandAwareObjectiveWeights):
            raise OptimizationError("weights must be DemandAwareObjectiveWeights")
        if self.objective_version != DEMAND_OBJECTIVE_VERSION:
            raise OptimizationError("unsupported demand-aware objective version")

    @classmethod
    def create(
        cls,
        parent: ParentGraph,
        demand: DirectedDemandMatrix,
        incidence_budget: int,
        maximum_arity: int,
        weights: DemandAwareObjectiveWeights,
    ) -> "DemandAwareTrainingManifest":
        _validate_parent_and_demand(parent, demand)
        return cls(
            parent_fingerprint=_parent_fingerprint(parent),
            demand_fingerprint=demand.fingerprint,
            node_count=len(parent.nodes),
            incidence_budget=incidence_budget,
            maximum_arity=maximum_arity,
            weights=weights,
        )

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.demand-training-manifest.v1\x00")
        _hash_field(digest, self.parent_fingerprint)
        _hash_field(digest, self.demand_fingerprint)
        _hash_count(digest, self.node_count)
        _hash_count(digest, self.incidence_budget)
        _hash_count(digest, self.maximum_arity)
        for weight in (
            self.weights.bidirectional_capture,
            self.weights.directional_imbalance,
            self.weights.participation,
            self.weights.coordination_overlap,
        ):
            _hash_integer(digest, weight.numerator)
            _hash_count(digest, weight.denominator)
        _hash_field(digest, self.objective_version)
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class DemandAwareObjectiveScore:
    """Exact four-term score bound to a training manifest and topology."""

    manifest_fingerprint: str
    topology_fingerprint: str
    captured_bidirectional: int
    captured_imbalance: int
    participation_burden: int
    coordination_overlap_burden: int
    normalized_capture: Fraction
    normalized_imbalance: Fraction
    normalized_participation: Fraction
    normalized_coordination_overlap: Fraction
    objective_value: Fraction

    def __post_init__(self) -> None:
        _validate_digest(self.manifest_fingerprint, "manifest_fingerprint")
        _validate_digest(self.topology_fingerprint, "topology_fingerprint")
        for name, value in (
            ("captured_bidirectional", self.captured_bidirectional),
            ("captured_imbalance", self.captured_imbalance),
            ("participation_burden", self.participation_burden),
            ("coordination_overlap_burden", self.coordination_overlap_burden),
        ):
            if type(value) is not int or value < 0:
                raise OptimizationError(f"{name} must be a non-negative integer")
        for name, value in (
            ("normalized_capture", self.normalized_capture),
            ("normalized_imbalance", self.normalized_imbalance),
            ("normalized_participation", self.normalized_participation),
            (
                "normalized_coordination_overlap",
                self.normalized_coordination_overlap,
            ),
        ):
            if not isinstance(value, Fraction) or not 0 <= value <= 1:
                raise OptimizationError(f"{name} must be a Fraction in [0, 1]")
        if not isinstance(self.objective_value, Fraction):
            raise OptimizationError("objective_value must be a Fraction")


def validate_demand_aware_topology(
    parent: ParentGraph,
    topology: HypergraphTopology,
    manifest: DemandAwareTrainingManifest,
) -> None:
    """Fail closed unless a candidate satisfies the registered feasible set."""

    if not isinstance(parent, ParentGraph):
        raise OptimizationError("parent must be a ParentGraph")
    if not isinstance(topology, HypergraphTopology):
        raise OptimizationError("topology must be a HypergraphTopology")
    if not isinstance(manifest, DemandAwareTrainingManifest):
        raise OptimizationError("manifest must be a DemandAwareTrainingManifest")
    if _parent_fingerprint(parent) != manifest.parent_fingerprint:
        raise OptimizationError("manifest does not bind the supplied parent graph")
    if len(parent.nodes) != manifest.node_count:
        raise OptimizationError("manifest node_count does not match the parent")
    if topology.nodes != parent.nodes:
        raise OptimizationError("candidate topology must preserve parent nodes")
    if topology.resources.incidence_count != manifest.incidence_budget:
        raise OptimizationError("candidate topology must match the incidence budget")
    if topology.resources.maximum_arity > manifest.maximum_arity:
        raise OptimizationError("candidate topology exceeds maximum arity")
    memberships = tuple(edge.members for edge in topology.hyperedges)
    if len(set(memberships)) != len(memberships):
        raise OptimizationError("candidate topology has duplicate member sets")
    for members in memberships:
        if not _induced_members_are_connected(parent, members):
            raise OptimizationError(
                "every candidate hyperedge must induce a connected parent subgraph"
            )
    exposed_pairs = {
        pair
        for members in memberships
        for pair in combinations(members, 2)
    }
    if any(edge.endpoints not in exposed_pairs for edge in parent.edges):
        raise OptimizationError("candidate topology must cover every parent edge")
    if not topology.is_connected:
        raise OptimizationError("candidate topology must be connected")


def score_demand_aware_topology(
    parent: ParentGraph,
    demand: DirectedDemandMatrix,
    topology: HypergraphTopology,
    manifest: DemandAwareTrainingManifest,
) -> DemandAwareObjectiveScore:
    """Return the exact normalized four-term training score."""

    _validate_parent_and_demand(parent, demand)
    if not isinstance(manifest, DemandAwareTrainingManifest):
        raise OptimizationError("manifest must be a DemandAwareTrainingManifest")
    if demand.fingerprint != manifest.demand_fingerprint:
        raise OptimizationError("manifest does not bind the supplied training demand")
    if len(parent.nodes) != manifest.node_count:
        raise OptimizationError("manifest node_count does not match the parent")
    validate_demand_aware_topology(parent, topology, manifest)

    pair_multiplicity: dict[tuple[str, str], int] = {}
    for edge in topology.hyperedges:
        for pair in combinations(edge.members, 2):
            pair_multiplicity[pair] = pair_multiplicity.get(pair, 0) + 1
    captured_pairs = tuple(sorted(pair_multiplicity))
    captured_bidirectional = sum(
        min(demand.amount(left, right), demand.amount(right, left))
        for left, right in captured_pairs
    )
    captured_imbalance = sum(
        abs(demand.amount(left, right) - demand.amount(right, left))
        for left, right in captured_pairs
    )
    participation_burden = sum(
        comb(degree, 2) for _, degree in topology.node_incidence_degrees
    )
    coordination_overlap_burden = sum(
        comb(edge.arity, 2) for edge in topology.hyperedges
    ) + sum(comb(multiplicity, 2) for multiplicity in pair_multiplicity.values())

    normalized_capture = _normalized(
        captured_bidirectional,
        demand.total_bidirectional_volume,
    )
    normalized_imbalance = _normalized(
        captured_imbalance,
        demand.total_directional_imbalance,
    )
    participation_upper = comb(
        manifest.incidence_budget - manifest.node_count + 1,
        2,
    )
    coordination_upper = (
        manifest.incidence_budget * (manifest.maximum_arity - 1) // 2
        + comb(manifest.incidence_budget // 2, 2)
        * comb(manifest.maximum_arity, 2)
    )
    normalized_participation = _normalized(
        participation_burden,
        participation_upper,
    )
    normalized_coordination_overlap = _normalized(
        coordination_overlap_burden,
        coordination_upper,
    )
    weights = manifest.weights
    objective_value = (
        weights.bidirectional_capture * normalized_capture
        - weights.directional_imbalance * normalized_imbalance
        - weights.participation * normalized_participation
        - weights.coordination_overlap * normalized_coordination_overlap
    )
    return DemandAwareObjectiveScore(
        manifest_fingerprint=manifest.fingerprint,
        topology_fingerprint=_topology_fingerprint(topology),
        captured_bidirectional=captured_bidirectional,
        captured_imbalance=captured_imbalance,
        participation_burden=participation_burden,
        coordination_overlap_burden=coordination_overlap_burden,
        normalized_capture=normalized_capture,
        normalized_imbalance=normalized_imbalance,
        normalized_participation=normalized_participation,
        normalized_coordination_overlap=normalized_coordination_overlap,
        objective_value=objective_value,
    )


def validate_demand_aware_score(
    score: DemandAwareObjectiveScore,
    parent: ParentGraph,
    demand: DirectedDemandMatrix,
    topology: HypergraphTopology,
    manifest: DemandAwareTrainingManifest,
) -> None:
    """Recompute every term and reject a forged or input-misaligned score."""

    if not isinstance(score, DemandAwareObjectiveScore):
        raise OptimizationError("score must be a DemandAwareObjectiveScore")
    exact = score_demand_aware_topology(parent, demand, topology, manifest)
    if score != exact:
        raise OptimizationError("score does not match complete objective replay")


def _validate_parent_and_demand(
    parent: object,
    demand: object,
) -> None:
    if not isinstance(parent, ParentGraph):
        raise OptimizationError("parent must be a ParentGraph")
    if not parent.is_connected:
        raise OptimizationError("demand-aware training requires a connected parent")
    if not isinstance(demand, DirectedDemandMatrix):
        raise OptimizationError("demand must be a DirectedDemandMatrix")
    if demand.nodes != parent.nodes:
        raise OptimizationError("training demand must preserve parent nodes")


def _induced_members_are_connected(
    parent: ParentGraph,
    members: tuple[str, ...],
) -> bool:
    member_set = set(members)
    visited = {members[0]}
    frontier = [members[0]]
    while frontier:
        current = frontier.pop()
        for neighbor in parent.neighbors(current):
            if neighbor in member_set and neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return len(visited) == len(members)


def _normalized(numerator: int, denominator: int) -> Fraction:
    if denominator == 0:
        return Fraction(0, 1)
    value = Fraction(numerator, denominator)
    if not 0 <= value <= 1:
        raise OptimizationError("normalization bound is inconsistent with score terms")
    return value


def _parent_fingerprint(parent: ParentGraph) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.parent-for-demand.v1\x00")
    _hash_count(digest, len(parent.nodes))
    for node_id in parent.nodes:
        _hash_field(digest, node_id)
    _hash_count(digest, len(parent.edges))
    for edge in parent.edges:
        _hash_field(digest, edge.left)
        _hash_field(digest, edge.right)
    return digest.hexdigest()


def _topology_fingerprint(topology: HypergraphTopology) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.demand-topology.v1\x00")
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


def _validate_digest(value: object, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OptimizationError(f"{field} must be lowercase SHA-256 hexadecimal")


def _hash_field(digest, value: str) -> None:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise OptimizationError("fingerprinted text must be valid UTF-8") from exc
    _hash_count(digest, len(encoded))
    digest.update(encoded)


def _hash_count(digest, value: int) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise OptimizationError("fingerprint count must be an unsigned 64-bit integer")
    digest.update(value.to_bytes(8, "big"))


def _hash_integer(digest, value: int) -> None:
    sign = b"-" if value < 0 else b"+"
    magnitude = str(abs(value)).encode("ascii")
    digest.update(sign)
    _hash_count(digest, len(magnitude))
    digest.update(magnitude)


def _validate_node_id(value: object) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise OptimizationError(
            "demand node identifiers must be nonempty strings without outer "
            "whitespace or NUL"
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise OptimizationError("demand node identifiers must be valid UTF-8") from exc


__all__ = [
    "DEMAND_OBJECTIVE_VERSION",
    "DemandAwareObjectiveScore",
    "DemandAwareObjectiveWeights",
    "DemandAwareTrainingManifest",
    "DirectedDemandMatrix",
    "OptimizationError",
    "score_demand_aware_topology",
    "validate_demand_aware_score",
    "validate_demand_aware_topology",
]
