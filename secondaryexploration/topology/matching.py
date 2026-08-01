"""Deterministic binary baselines for exact or adjacent incidence budgets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import combinations
from math import comb

from .parent import ParentGraph
from .structure import HypergraphTopology, TopologyError


_PAIR_PRIORITY_DOMAIN = b"secondaryexploration.binary-pair-priority.v1\x00"
_MAX_UNSIGNED_64 = 2**64 - 1


class TopologyMatchingError(TopologyError):
    """Raised when an exact or adjacent binary budget match is impossible."""


@dataclass(frozen=True, slots=True)
class BinaryIncidenceMatch:
    """Replayable exact or adjacent-budget binary topology pair."""

    parent: ParentGraph
    source_incidence_count: int
    root_seed: int
    lower: HypergraphTopology
    upper: HypergraphTopology

    def __post_init__(self) -> None:
        if not isinstance(self.parent, ParentGraph):
            raise TopologyMatchingError("parent must be a ParentGraph")
        _validate_root_seed(self.root_seed)
        lower_edges, upper_edges = _target_edge_counts(
            self.parent,
            self.source_incidence_count,
        )
        if not isinstance(self.lower, HypergraphTopology) or not isinstance(
            self.upper,
            HypergraphTopology,
        ):
            raise TopologyMatchingError(
                "lower and upper must be HypergraphTopology objects"
            )
        expected_lower = _binary_topology_for_target(
            self.parent,
            lower_edges,
            self.root_seed,
        )
        expected_upper = (
            expected_lower
            if lower_edges == upper_edges
            else _binary_topology_for_target(
                self.parent,
                upper_edges,
                self.root_seed,
            )
        )
        if self.lower != expected_lower or self.upper != expected_upper:
            raise TopologyMatchingError(
                "binary brackets do not match the declared parent, budget, and seed"
            )

    @property
    def is_exact(self) -> bool:
        return self.source_incidence_count % 2 == 0

    @property
    def lower_incidence_delta(self) -> int:
        return (
            self.lower.resources.incidence_count - self.source_incidence_count
        )

    @property
    def upper_incidence_delta(self) -> int:
        return (
            self.upper.resources.incidence_count - self.source_incidence_count
        )


def binary_incidence_match(
    parent: ParentGraph,
    source_incidence_count: int,
    *,
    root_seed: int,
) -> BinaryIncidenceMatch:
    """Select exact or adjacent simple connected binary budget baselines."""

    if not isinstance(parent, ParentGraph):
        raise TopologyMatchingError("parent must be a ParentGraph")
    _validate_root_seed(root_seed)
    lower_edges, upper_edges = _target_edge_counts(
        parent,
        source_incidence_count,
    )
    lower = _binary_topology_for_target(parent, lower_edges, root_seed)
    upper = (
        lower
        if lower_edges == upper_edges
        else _binary_topology_for_target(parent, upper_edges, root_seed)
    )
    return BinaryIncidenceMatch(
        parent=parent,
        source_incidence_count=source_incidence_count,
        root_seed=root_seed,
        lower=lower,
        upper=upper,
    )


def match_binary_to_topology(
    parent: ParentGraph,
    source: HypergraphTopology,
    *,
    root_seed: int,
) -> BinaryIncidenceMatch:
    """Match a binary baseline to a source topology's incidence budget."""

    if not isinstance(parent, ParentGraph):
        raise TopologyMatchingError("parent must be a ParentGraph")
    if not isinstance(source, HypergraphTopology):
        raise TopologyMatchingError("source must be a HypergraphTopology")
    if source.nodes != parent.nodes:
        raise TopologyMatchingError(
            "source topology and parent graph must use the same node set"
        )
    return binary_incidence_match(
        parent,
        source.resources.incidence_count,
        root_seed=root_seed,
    )


def _target_edge_counts(
    parent: ParentGraph,
    source_incidence_count: object,
) -> tuple[int, int]:
    if not parent.is_connected or len(parent.nodes) < 2:
        raise TopologyMatchingError(
            "binary incidence matching requires a connected parent with at least two nodes"
        )
    if type(source_incidence_count) is not int or source_incidence_count < 1:
        raise TopologyMatchingError(
            "source_incidence_count must be a positive integer"
        )
    lower_edges = source_incidence_count // 2
    upper_edges = (source_incidence_count + 1) // 2
    minimum_edges = len(parent.nodes) - 1
    maximum_edges = comb(len(parent.nodes), 2)
    if lower_edges < minimum_edges:
        raise TopologyMatchingError(
            "lower binary bracket cannot be connected at this incidence budget"
        )
    if upper_edges > maximum_edges:
        raise TopologyMatchingError(
            "upper binary bracket exceeds simple-graph pair capacity"
        )
    return lower_edges, upper_edges


def _binary_topology_for_target(
    parent: ParentGraph,
    target_edge_count: int,
    root_seed: int,
) -> HypergraphTopology:
    selected_pairs = _selected_pairs(parent, target_edge_count, root_seed)
    node_index = {node: index for index, node in enumerate(parent.nodes)}
    hyperedges = {
        (
            f"b{node_index[left]:08d}-{node_index[right]:08d}"
        ): (left, right)
        for left, right in selected_pairs
    }
    topology = HypergraphTopology.from_edges(parent.nodes, hyperedges)
    if topology.resources.hyperedge_count != target_edge_count:
        raise AssertionError("internal binary selector returned the wrong edge count")
    if not topology.is_connected:
        raise AssertionError("internal binary selector returned a disconnected graph")
    return topology


def _selected_pairs(
    parent: ParentGraph,
    target_edge_count: int,
    root_seed: int,
) -> tuple[tuple[str, str], ...]:
    parent_pairs = tuple(edge.endpoints for edge in parent.edges)
    ranked_parent = tuple(
        sorted(
            parent_pairs,
            key=lambda pair: (_pair_priority(root_seed, pair), pair),
        )
    )
    disjoint_set = _DisjointSet(parent.nodes)
    spanning_tree: list[tuple[str, str]] = []
    for pair in ranked_parent:
        if disjoint_set.union(pair[0], pair[1]):
            spanning_tree.append(pair)
            if len(spanning_tree) == len(parent.nodes) - 1:
                break
    if len(spanning_tree) != len(parent.nodes) - 1:
        raise TopologyMatchingError("parent graph does not contain a spanning tree")

    selected = set(spanning_tree)
    if target_edge_count <= parent.edge_count:
        for pair in ranked_parent:
            if len(selected) == target_edge_count:
                break
            selected.add(pair)
    else:
        selected.update(parent_pairs)
        parent_pair_set = set(parent_pairs)
        nonparent_pairs = tuple(
            pair
            for pair in combinations(parent.nodes, 2)
            if pair not in parent_pair_set
        )
        ranked_nonparent = tuple(
            sorted(
                nonparent_pairs,
                key=lambda pair: (_pair_priority(root_seed, pair), pair),
            )
        )
        for pair in ranked_nonparent:
            if len(selected) == target_edge_count:
                break
            selected.add(pair)
    if len(selected) != target_edge_count:
        raise TopologyMatchingError(
            "simple binary candidate pairs cannot realize the target edge count"
        )
    return tuple(sorted(selected))


def _pair_priority(root_seed: int, pair: tuple[str, str]) -> bytes:
    framed = bytearray(_PAIR_PRIORITY_DOMAIN)
    framed.extend(root_seed.to_bytes(8, byteorder="big", signed=False))
    for endpoint in pair:
        encoded = endpoint.encode("utf-8")
        framed.extend(len(encoded).to_bytes(4, byteorder="big", signed=False))
        framed.extend(encoded)
    return hashlib.sha256(framed).digest()


class _DisjointSet:
    def __init__(self, nodes: tuple[str, ...]) -> None:
        self._parent = {node: node for node in nodes}
        self._rank = {node: 0 for node in nodes}

    def find(self, node: str) -> str:
        root = node
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[node] != node:
            parent = self._parent[node]
            self._parent[node] = root
            node = parent
        return root

    def union(self, left: str, right: str) -> bool:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return False
        left_rank = self._rank[left_root]
        right_rank = self._rank[right_root]
        if left_rank < right_rank:
            left_root, right_root = right_root, left_root
        self._parent[right_root] = left_root
        if left_rank == right_rank:
            self._rank[left_root] += 1
        return True


def _validate_root_seed(root_seed: object) -> None:
    if type(root_seed) is not int or not 0 <= root_seed <= _MAX_UNSIGNED_64:
        raise TopologyMatchingError(
            "root_seed must be an integer in [0, 2**64 - 1]"
        )


__all__ = [
    "BinaryIncidenceMatch",
    "TopologyMatchingError",
    "binary_incidence_match",
    "match_binary_to_topology",
]
