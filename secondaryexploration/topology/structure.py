"""Immutable balance-free hypergraph topology and exact resource counts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from math import comb
from types import MappingProxyType
from typing import Mapping as TypingMapping


class TopologyError(ValueError):
    """Raised when a topology or structural resource value is invalid."""


@dataclass(frozen=True, order=True, slots=True)
class HyperedgeSpec:
    """One canonical balance-free hyperedge."""

    hyperedge_id: str
    members: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.hyperedge_id, "hyperedge_id")
        if type(self.members) is not tuple:
            raise TopologyError("hyperedge members must be a canonical tuple")
        if len(self.members) < 2:
            raise TopologyError("a structural hyperedge must have at least two members")
        for member in self.members:
            _validate_identifier(member, "member")
        if len(set(self.members)) != len(self.members):
            raise TopologyError("hyperedge members must be unique")
        if tuple(sorted(self.members)) != self.members:
            raise TopologyError("hyperedge members must be in canonical order")

    @classmethod
    def from_members(
        cls,
        hyperedge_id: str,
        members: Iterable[str],
    ) -> "HyperedgeSpec":
        """Validate and canonicalize a user-facing member collection."""

        _validate_identifier(hyperedge_id, "hyperedge_id")
        if isinstance(members, (str, bytes)):
            raise TopologyError("hyperedge members must be an iterable of identifiers")
        try:
            member_tuple = tuple(members)
        except TypeError as exc:
            raise TopologyError(
                "hyperedge members must be an iterable of identifiers"
            ) from exc
        for member in member_tuple:
            _validate_identifier(member, "member")
        if len(set(member_tuple)) != len(member_tuple):
            raise TopologyError("hyperedge members must be unique")
        return cls(hyperedge_id, tuple(sorted(member_tuple)))

    @property
    def arity(self) -> int:
        return len(self.members)


@dataclass(frozen=True, slots=True)
class TopologyResources:
    """Exact resource counts derived from a canonical arity witness."""

    node_count: int
    arities: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.node_count) is not int or self.node_count < 1:
            raise TopologyError("node_count must be positive")
        if type(self.arities) is not tuple:
            raise TopologyError("arities must be a canonical tuple")
        for arity in self.arities:
            if type(arity) is not int or not 2 <= arity <= self.node_count:
                raise TopologyError(
                    "every arity must be an integer between two and node_count"
                )
        if tuple(sorted(self.arities)) != self.arities:
            raise TopologyError("arities must be in canonical order")

    @property
    def hyperedge_count(self) -> int:
        return len(self.arities)

    @property
    def incidence_count(self) -> int:
        return sum(self.arities)

    @property
    def maximum_arity(self) -> int:
        return max(self.arities, default=0)

    @property
    def pairwise_member_exposure(self) -> int:
        return sum(comb(arity, 2) for arity in self.arities)


@dataclass(frozen=True, slots=True)
class HypergraphTopology:
    """Canonical nodes and structural hyperedges without balances."""

    nodes: tuple[str, ...]
    hyperedges: tuple[HyperedgeSpec, ...]
    _incidence: TypingMapping[str, tuple[int, ...]] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if type(self.nodes) is not tuple:
            raise TopologyError("nodes must be a canonical tuple")
        if not self.nodes:
            raise TopologyError("nodes must contain at least one node")
        for node_id in self.nodes:
            _validate_identifier(node_id, "node_id")
        if len(set(self.nodes)) != len(self.nodes):
            raise TopologyError("nodes must be unique")
        if tuple(sorted(self.nodes)) != self.nodes:
            raise TopologyError("nodes must be in canonical order")

        if type(self.hyperedges) is not tuple:
            raise TopologyError("hyperedges must be a canonical tuple")
        if any(not isinstance(edge, HyperedgeSpec) for edge in self.hyperedges):
            raise TopologyError("hyperedges must contain only HyperedgeSpec objects")
        edge_ids = tuple(edge.hyperedge_id for edge in self.hyperedges)
        if len(set(edge_ids)) != len(edge_ids):
            raise TopologyError("hyperedges must use unique identifiers")
        if tuple(sorted(edge_ids)) != edge_ids:
            raise TopologyError("hyperedges must be in canonical identifier order")

        node_set = set(self.nodes)
        for edge in self.hyperedges:
            unknown_members = tuple(
                member for member in edge.members if member not in node_set
            )
            if unknown_members:
                rendered = ", ".join(repr(member) for member in unknown_members)
                raise TopologyError(
                    f"hyperedge {edge.hyperedge_id!r} has unknown member {rendered}"
                )

        incidence_lists = {node_id: [] for node_id in self.nodes}
        for edge_index, edge in enumerate(self.hyperedges):
            for member in edge.members:
                incidence_lists[member].append(edge_index)
        object.__setattr__(
            self,
            "_incidence",
            MappingProxyType(
                {
                    node_id: tuple(incidence_lists[node_id])
                    for node_id in self.nodes
                }
            ),
        )

    @classmethod
    def from_edges(
        cls,
        nodes: Iterable[str],
        hyperedges: Mapping[str, Iterable[str]],
    ) -> "HypergraphTopology":
        """Validate and canonicalize user-facing nodes and edge memberships."""

        if isinstance(nodes, (str, bytes)):
            raise TopologyError("nodes must be an iterable of identifiers")
        try:
            node_tuple = tuple(nodes)
        except TypeError as exc:
            raise TopologyError("nodes must be an iterable of identifiers") from exc
        for node_id in node_tuple:
            _validate_identifier(node_id, "node_id")
        if len(set(node_tuple)) != len(node_tuple):
            raise TopologyError("nodes must be unique")
        if not isinstance(hyperedges, Mapping):
            raise TopologyError("hyperedges must be a mapping")

        edge_specs = tuple(
            sorted(
                (
                    HyperedgeSpec.from_members(hyperedge_id, members)
                    for hyperedge_id, members in hyperedges.items()
                ),
                key=lambda edge: edge.hyperedge_id,
            )
        )
        return cls(nodes=tuple(sorted(node_tuple)), hyperedges=edge_specs)

    @property
    def resources(self) -> TopologyResources:
        arities = tuple(edge.arity for edge in self.hyperedges)
        return TopologyResources(
            node_count=len(self.nodes),
            arities=tuple(sorted(arities)),
        )

    @property
    def node_incidence_degrees(self) -> tuple[tuple[str, int], ...]:
        return tuple(
            (node_id, len(self._incidence[node_id]))
            for node_id in self.nodes
        )

    def incidence_degree(self, node_id: str) -> int:
        if node_id not in self._incidence:
            raise TopologyError(f"unknown node {node_id!r}")
        return len(self._incidence[node_id])

    @property
    def is_connected(self) -> bool:
        visited_nodes = {self.nodes[0]}
        visited_edges: set[int] = set()
        frontier = [self.nodes[0]]
        while frontier:
            current = frontier.pop()
            for edge_index in self._incidence[current]:
                if edge_index in visited_edges:
                    continue
                visited_edges.add(edge_index)
                for member in self.hyperedges[edge_index].members:
                    if member not in visited_nodes:
                        visited_nodes.add(member)
                        frontier.append(member)
        return len(visited_nodes) == len(self.nodes)


def _validate_identifier(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise TopologyError(f"{field} must be a string")
    if not value or value != value.strip():
        raise TopologyError(f"{field} must be non-empty and have no outer whitespace")
    if "\x00" in value:
        raise TopologyError(f"{field} must not contain NUL")


__all__ = [
    "HyperedgeSpec",
    "HypergraphTopology",
    "TopologyError",
    "TopologyResources",
]
