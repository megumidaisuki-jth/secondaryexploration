"""Canonical finite simple undirected parent graphs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction
from types import MappingProxyType
from typing import Mapping

from .structure import TopologyError, _validate_identifier


@dataclass(frozen=True, order=True, slots=True)
class GraphEdge:
    """One canonical undirected simple-graph edge."""

    left: str
    right: str

    def __post_init__(self) -> None:
        _validate_identifier(self.left, "left endpoint")
        _validate_identifier(self.right, "right endpoint")
        if self.left >= self.right:
            raise TopologyError(
                "graph edge endpoints must be distinct and in canonical order"
            )

    @classmethod
    def from_endpoints(cls, first: str, second: str) -> "GraphEdge":
        """Validate and canonicalize two undirected endpoints."""

        _validate_identifier(first, "first endpoint")
        _validate_identifier(second, "second endpoint")
        if first == second:
            raise TopologyError("a simple graph edge cannot be a self-loop")
        left, right = sorted((first, second))
        return cls(left, right)

    @property
    def endpoints(self) -> tuple[str, str]:
        return (self.left, self.right)


@dataclass(frozen=True, slots=True)
class ParentGraph:
    """Immutable canonical simple graph used to derive payment topologies."""

    nodes: tuple[str, ...]
    edges: tuple[GraphEdge, ...]
    _adjacency: Mapping[str, tuple[str, ...]] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if type(self.nodes) is not tuple:
            raise TopologyError("parent nodes must be a canonical tuple")
        if not self.nodes:
            raise TopologyError("parent nodes must contain at least one node")
        for node_id in self.nodes:
            _validate_identifier(node_id, "parent node_id")
        if len(set(self.nodes)) != len(self.nodes):
            raise TopologyError("parent nodes must be unique")
        if tuple(sorted(self.nodes)) != self.nodes:
            raise TopologyError("parent nodes must be in canonical order")

        if type(self.edges) is not tuple:
            raise TopologyError("parent edges must be a canonical tuple")
        if any(not isinstance(edge, GraphEdge) for edge in self.edges):
            raise TopologyError("parent edges must contain only GraphEdge objects")
        if len(set(self.edges)) != len(self.edges):
            raise TopologyError("parent graph edges must be unique")
        if tuple(sorted(self.edges)) != self.edges:
            raise TopologyError("parent graph edges must be in canonical order")

        node_set = set(self.nodes)
        for edge in self.edges:
            unknown = tuple(
                endpoint for endpoint in edge.endpoints if endpoint not in node_set
            )
            if unknown:
                rendered = ", ".join(repr(endpoint) for endpoint in unknown)
                raise TopologyError(f"parent edge has unknown endpoint {rendered}")

        adjacency_sets = {node_id: set() for node_id in self.nodes}
        for edge in self.edges:
            adjacency_sets[edge.left].add(edge.right)
            adjacency_sets[edge.right].add(edge.left)
        object.__setattr__(
            self,
            "_adjacency",
            MappingProxyType(
                {
                    node_id: tuple(sorted(adjacency_sets[node_id]))
                    for node_id in self.nodes
                }
            ),
        )

    @classmethod
    def from_edges(
        cls,
        nodes: Iterable[str],
        edges: Iterable[Iterable[str]],
    ) -> "ParentGraph":
        """Validate and canonicalize user-facing nodes and undirected edges."""

        if isinstance(nodes, (str, bytes)):
            raise TopologyError("parent nodes must be an iterable of identifiers")
        try:
            node_tuple = tuple(nodes)
        except TypeError as exc:
            raise TopologyError(
                "parent nodes must be an iterable of identifiers"
            ) from exc
        for node_id in node_tuple:
            _validate_identifier(node_id, "parent node_id")
        if len(set(node_tuple)) != len(node_tuple):
            raise TopologyError("parent nodes must be unique")

        if isinstance(edges, (str, bytes)):
            raise TopologyError("parent edges must be an iterable of endpoint pairs")
        try:
            raw_edges = tuple(edges)
        except TypeError as exc:
            raise TopologyError(
                "parent edges must be an iterable of endpoint pairs"
            ) from exc
        canonical_edges: list[GraphEdge] = []
        for raw_edge in raw_edges:
            if isinstance(raw_edge, (str, bytes)):
                raise TopologyError("each parent edge must contain two endpoints")
            try:
                endpoints = tuple(raw_edge)
            except TypeError as exc:
                raise TopologyError(
                    "each parent edge must contain two endpoints"
                ) from exc
            if len(endpoints) != 2:
                raise TopologyError("each parent edge must contain two endpoints")
            canonical_edges.append(
                GraphEdge.from_endpoints(endpoints[0], endpoints[1])
            )
        return cls(
            nodes=tuple(sorted(node_tuple)),
            edges=tuple(sorted(canonical_edges)),
        )

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def neighbors(self, node_id: str) -> tuple[str, ...]:
        if node_id not in self._adjacency:
            raise TopologyError(f"unknown node {node_id!r}")
        return self._adjacency[node_id]

    def degree(self, node_id: str) -> int:
        return len(self.neighbors(node_id))

    @property
    def node_degrees(self) -> tuple[tuple[str, int], ...]:
        return tuple((node_id, self.degree(node_id)) for node_id in self.nodes)

    @property
    def mean_degree(self) -> Fraction:
        return Fraction(2 * self.edge_count, len(self.nodes))

    @property
    def is_connected(self) -> bool:
        visited = {self.nodes[0]}
        frontier = [self.nodes[0]]
        while frontier:
            current = frontier.pop()
            for neighbor in self._adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    frontier.append(neighbor)
        return len(visited) == len(self.nodes)


__all__ = ["GraphEdge", "ParentGraph"]
