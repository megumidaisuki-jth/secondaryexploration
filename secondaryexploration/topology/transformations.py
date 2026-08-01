"""Deterministic binary, clique, NCH, and FHS transformations."""

from __future__ import annotations

from collections import deque
import heapq
from itertools import combinations

from .parent import GraphEdge, ParentGraph
from .structure import HypergraphTopology, TopologyError


def canonical_local_ratio_vertex_cover(parent: ParentGraph) -> tuple[str, ...]:
    """Return the frozen unweighted local-ratio 2-approximate vertex cover."""

    if not isinstance(parent, ParentGraph):
        raise TopologyError("parent must be a ParentGraph")
    residual_cost = {node_id: 1 for node_id in parent.nodes}
    cover: set[str] = set()
    for edge in parent.edges:
        if edge.left in cover or edge.right in cover:
            continue
        if residual_cost[edge.left] <= residual_cost[edge.right]:
            cover.add(edge.left)
            residual_cost[edge.right] -= residual_cost[edge.left]
        else:
            cover.add(edge.right)
            residual_cost[edge.left] -= residual_cost[edge.right]
    return tuple(sorted(cover))


def binary_topology(parent: ParentGraph) -> HypergraphTopology:
    """Convert every parent edge into one distinct binary channel."""

    if not isinstance(parent, ParentGraph):
        raise TopologyError("parent must be a ParentGraph")
    hyperedges = {
        f"binary-{edge_index:08d}": edge.endpoints
        for edge_index, edge in enumerate(parent.edges)
    }
    return HypergraphTopology.from_edges(parent.nodes, hyperedges)


def clique_expansion(topology: HypergraphTopology) -> HypergraphTopology:
    """Expand every within-hyperedge member pair into a distinct channel."""

    if not isinstance(topology, HypergraphTopology):
        raise TopologyError("topology must be a HypergraphTopology")
    hyperedges: dict[str, tuple[str, str]] = {}
    for edge_index, edge in enumerate(topology.hyperedges):
        for pair_index, pair in enumerate(combinations(edge.members, 2)):
            hyperedges[
                f"clique-{edge_index:08d}-{pair_index:08d}"
            ] = pair
    return HypergraphTopology.from_edges(topology.nodes, hyperedges)


def closed_neighborhood_nch(parent: ParentGraph) -> HypergraphTopology:
    """Create one explicitly closed-neighborhood channel per cover node."""

    _validate_primary_parent(parent)
    cover = canonical_local_ratio_vertex_cover(parent)
    hyperedges = {
        f"nch-{cover_index:08d}": (cover_node,) + parent.neighbors(cover_node)
        for cover_index, cover_node in enumerate(cover)
    }
    topology = HypergraphTopology.from_edges(parent.nodes, hyperedges)
    _validate_transformation_output(parent, topology, "NCH")
    return topology


def fixed_hyperedge_size(
    parent: ParentGraph,
    maximum_arity: int,
) -> HypergraphTopology:
    """Apply deterministic residual-degree and bounded-BFS FHS clustering."""

    _validate_primary_parent(parent)
    if (
        type(maximum_arity) is not int
        or not 2 <= maximum_arity <= len(parent.nodes)
    ):
        raise TopologyError(
            "maximum_arity must be an integer between two and parent node count"
        )

    residual = {node_id: set(parent.neighbors(node_id)) for node_id in parent.nodes}
    degree_heap = [(-len(residual[node_id]), node_id) for node_id in parent.nodes]
    heapq.heapify(degree_heap)
    hyperedges: dict[str, tuple[str, ...]] = {}
    iteration = 0
    while True:
        center: str | None = None
        while degree_heap:
            negative_degree, candidate = heapq.heappop(degree_heap)
            if residual[candidate] and -negative_degree == len(residual[candidate]):
                center = candidate
                break
        if center is None:
            break
        visited = _bounded_bfs(residual, center, maximum_arity)
        selected = set(visited)
        if len(selected) < 2:
            raise TopologyError("FHS iteration failed to select a removable edge")

        removed_edges = 0
        for left in tuple(sorted(selected)):
            for right in tuple(sorted(residual[left].intersection(selected))):
                if left < right:
                    residual[left].remove(right)
                    residual[right].remove(left)
                    removed_edges += 1
        if removed_edges == 0:
            raise TopologyError("FHS iteration did not remove a residual edge")

        for node_id in selected:
            heapq.heappush(degree_heap, (-len(residual[node_id]), node_id))

        hyperedges[f"fhs-{iteration:08d}"] = tuple(sorted(selected))
        iteration += 1

    topology = HypergraphTopology.from_edges(parent.nodes, hyperedges)
    _validate_transformation_output(parent, topology, "FHS")
    if any(edge.arity > maximum_arity for edge in topology.hyperedges):
        raise TopologyError("FHS output exceeded maximum_arity")
    return topology


def uncovered_parent_edges(
    parent: ParentGraph,
    topology: HypergraphTopology,
) -> tuple[GraphEdge, ...]:
    """Return parent edges whose endpoints share no output hyperedge."""

    if not isinstance(parent, ParentGraph):
        raise TopologyError("parent must be a ParentGraph")
    if not isinstance(topology, HypergraphTopology):
        raise TopologyError("topology must be a HypergraphTopology")
    if parent.nodes != topology.nodes:
        raise TopologyError("parent and topology must have the same canonical nodes")
    incidence = {node_id: set() for node_id in topology.nodes}
    for edge_index, hyperedge in enumerate(topology.hyperedges):
        for member in hyperedge.members:
            incidence[member].add(edge_index)
    return tuple(
        edge
        for edge in parent.edges
        if incidence[edge.left].isdisjoint(incidence[edge.right])
    )


def _bounded_bfs(
    residual: dict[str, set[str]],
    source: str,
    limit: int,
) -> tuple[str, ...]:
    visited = [source]
    seen = {source}
    queue: deque[str] = deque((source,))
    while queue and len(visited) < limit:
        current = queue.popleft()
        for neighbor in sorted(residual[current]):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            visited.append(neighbor)
            queue.append(neighbor)
            if len(visited) == limit:
                break
    return tuple(visited)


def _validate_primary_parent(parent: object) -> None:
    if not isinstance(parent, ParentGraph):
        raise TopologyError("parent must be a ParentGraph")
    if len(parent.nodes) < 2 or parent.edge_count == 0 or not parent.is_connected:
        raise TopologyError(
            "primary transformation parent must be a connected graph with edges"
        )


def _validate_transformation_output(
    parent: ParentGraph,
    topology: HypergraphTopology,
    label: str,
) -> None:
    if uncovered_parent_edges(parent, topology):
        raise TopologyError(f"{label} output did not cover every parent edge")
    if not topology.is_connected:
        raise TopologyError(f"{label} output is not connected")
    if any(degree == 0 for _, degree in topology.node_incidence_degrees):
        raise TopologyError(f"{label} output contains an isolated node")


__all__ = [
    "binary_topology",
    "canonical_local_ratio_vertex_cover",
    "clique_expansion",
    "closed_neighborhood_nch",
    "fixed_hyperedge_size",
    "uncovered_parent_edges",
]
