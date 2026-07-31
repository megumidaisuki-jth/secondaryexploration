"""Deterministic uniform overlap-chain and common-core sunflower anchors."""

from __future__ import annotations

from .structure import HypergraphTopology, TopologyError


def uniform_overlap_chain(
    arity: int,
    overlap: int,
    edge_count: int,
) -> HypergraphTopology:
    """Return the canonical sliding `k`-uniform `r`-overlap chain."""

    _validate_anchor_parameters(arity, overlap, edge_count)
    stride = arity - overlap
    node_count = overlap + edge_count * stride
    nodes = tuple(_node_id(index) for index in range(node_count))
    hyperedges = {
        _edge_id(edge_index): tuple(
            _node_id(index)
            for index in range(
                edge_index * stride,
                edge_index * stride + arity,
            )
        )
        for edge_index in range(edge_count)
    }
    return HypergraphTopology.from_edges(nodes, hyperedges)


def common_core_sunflower(
    arity: int,
    overlap: int,
    edge_count: int,
) -> HypergraphTopology:
    """Return a `k`-uniform sunflower whose common core has size `r`."""

    _validate_anchor_parameters(arity, overlap, edge_count)
    private_count = arity - overlap
    node_count = overlap + edge_count * private_count
    nodes = tuple(_node_id(index) for index in range(node_count))
    core = tuple(_node_id(index) for index in range(overlap))
    hyperedges = {}
    for edge_index in range(edge_count):
        private_start = overlap + edge_index * private_count
        private = tuple(
            _node_id(index)
            for index in range(private_start, private_start + private_count)
        )
        hyperedges[_edge_id(edge_index)] = core + private
    return HypergraphTopology.from_edges(nodes, hyperedges)


def _validate_anchor_parameters(
    arity: object,
    overlap: object,
    edge_count: object,
) -> None:
    if type(arity) is not int or arity < 2:
        raise TopologyError("arity must be an integer at least two")
    if type(overlap) is not int or not 1 <= overlap < arity:
        raise TopologyError("overlap must be an integer in [1, arity)")
    if type(edge_count) is not int or edge_count < 2:
        raise TopologyError("edge_count must be an integer at least two")


def _node_id(index: int) -> str:
    return f"v{index:08d}"


def _edge_id(index: int) -> str:
    return f"e{index:08d}"


__all__ = ["common_core_sunflower", "uniform_overlap_chain"]
