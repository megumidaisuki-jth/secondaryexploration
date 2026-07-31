"""Exact baseline capital allocation for structural topologies."""

from __future__ import annotations

from secondaryexploration.model import HypergraphState

from .structure import HypergraphTopology, TopologyError


def equal_node_capital_state(
    topology: HypergraphTopology,
    per_node_capital: int,
) -> HypergraphState:
    """Divide each integer node budget equally across its incident edges."""

    if not isinstance(topology, HypergraphTopology):
        raise TopologyError("topology must be a HypergraphTopology")
    if type(per_node_capital) is not int or per_node_capital <= 0:
        raise TopologyError("per_node_capital must be a positive integer")

    degrees = dict(topology.node_incidence_degrees)
    isolated = tuple(node_id for node_id, degree in degrees.items() if degree == 0)
    if isolated:
        rendered = ", ".join(repr(node_id) for node_id in isolated)
        raise TopologyError(f"cannot allocate capital to isolated node {rendered}")

    indivisible = tuple(
        node_id
        for node_id, degree in degrees.items()
        if per_node_capital % degree != 0
    )
    if indivisible:
        rendered = ", ".join(repr(node_id) for node_id in indivisible)
        raise TopologyError(
            f"per_node_capital is not divisible by the incidence degree of {rendered}"
        )

    hyperedge_balances = {
        edge.hyperedge_id: {
            member: per_node_capital // degrees[member]
            for member in edge.members
        }
        for edge in topology.hyperedges
    }
    return HypergraphState.from_balances(topology.nodes, hyperedge_balances)


def node_capital_totals(
    state: HypergraphState,
) -> tuple[tuple[str, int], ...]:
    """Return exact node totals summed over all incident hyperedges."""

    if not isinstance(state, HypergraphState):
        raise TopologyError("state must be a HypergraphState")
    totals = {node_id: 0 for node_id in state.nodes}
    for edge in state.hyperedges:
        for node_id, balance in edge.balances:
            totals[node_id] += balance
    return tuple((node_id, totals[node_id]) for node_id in state.nodes)


__all__ = ["equal_node_capital_state", "node_capital_totals"]
