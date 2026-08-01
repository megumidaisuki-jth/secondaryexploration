"""Independent finite-grid checks for demand-aware objective bounds and terms."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import comb
import unittest

from secondaryexploration.model import PaymentRequest
from secondaryexploration.optimization import (
    DemandAwareObjectiveWeights,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    OptimizationError,
    score_demand_aware_topology,
    validate_demand_aware_topology,
)
from secondaryexploration.topology import HypergraphTopology, ParentGraph


class DemandObjectiveFiniteGridTests(unittest.TestCase):
    def test_all_small_feasible_topologies_match_independent_raw_oracle(self) -> None:
        checked = 0
        for node_count in range(2, 5):
            nodes = tuple(chr(ord("a") + index) for index in range(node_count))
            possible_parent_edges = tuple(combinations(nodes, 2))
            for parent_mask in range(1, 1 << len(possible_parent_edges)):
                parent = ParentGraph.from_edges(
                    nodes,
                    tuple(
                        edge
                        for index, edge in enumerate(possible_parent_edges)
                        if parent_mask & (1 << index)
                    ),
                )
                if not parent.is_connected:
                    continue
                demand = DirectedDemandMatrix.from_requests(
                    nodes,
                    tuple(
                        PaymentRequest(source, destination, (i + 1) * (j + 2))
                        for i, source in enumerate(nodes)
                        for j, destination in enumerate(nodes)
                        if source != destination
                    ),
                )
                candidates = tuple(
                    members
                    for arity in range(2, min(3, node_count) + 1)
                    for members in combinations(nodes, arity)
                    if _connected_induced(parent, members)
                )
                for topology_mask in range(1, 1 << len(candidates)):
                    selected = tuple(
                        members
                        for index, members in enumerate(candidates)
                        if topology_mask & (1 << index)
                    )
                    incidence_budget = sum(map(len, selected))
                    if incidence_budget < node_count:
                        continue
                    topology = HypergraphTopology.from_edges(
                        nodes,
                        {
                            f"edge-{index:02d}": members
                            for index, members in enumerate(selected)
                        },
                    )
                    manifest = DemandAwareTrainingManifest.create(
                        parent,
                        demand,
                        incidence_budget,
                        max(map(len, selected)),
                        DemandAwareObjectiveWeights(
                            Fraction(2, 1),
                            Fraction(3, 1),
                            Fraction(5, 1),
                            Fraction(7, 1),
                        ),
                    )
                    try:
                        validate_demand_aware_topology(parent, topology, manifest)
                    except OptimizationError:
                        continue
                    score = score_demand_aware_topology(
                        parent,
                        demand,
                        topology,
                        manifest,
                    )
                    pair_multiplicity: dict[tuple[str, str], int] = {}
                    for members in selected:
                        for pair in combinations(members, 2):
                            pair_multiplicity[pair] = (
                                pair_multiplicity.get(pair, 0) + 1
                            )
                    expected_capture = sum(
                        min(demand.amount(a, b), demand.amount(b, a))
                        for a, b in pair_multiplicity
                    )
                    expected_imbalance = sum(
                        abs(demand.amount(a, b) - demand.amount(b, a))
                        for a, b in pair_multiplicity
                    )
                    expected_participation = sum(
                        comb(sum(node in members for members in selected), 2)
                        for node in nodes
                    )
                    expected_coordination = sum(
                        comb(len(members), 2) for members in selected
                    ) + sum(
                        comb(multiplicity, 2)
                        for multiplicity in pair_multiplicity.values()
                    )
                    self.assertEqual(score.captured_bidirectional, expected_capture)
                    self.assertEqual(score.captured_imbalance, expected_imbalance)
                    self.assertEqual(
                        score.participation_burden,
                        expected_participation,
                    )
                    self.assertEqual(
                        score.coordination_overlap_burden,
                        expected_coordination,
                    )
                    for normalized in (
                        score.normalized_capture,
                        score.normalized_imbalance,
                        score.normalized_participation,
                        score.normalized_coordination_overlap,
                    ):
                        self.assertGreaterEqual(normalized, 0)
                        self.assertLessEqual(normalized, 1)
                    checked += 1
        self.assertEqual(checked, 4_095)


def _connected_induced(parent: ParentGraph, members: tuple[str, ...]) -> bool:
    allowed = set(members)
    reached = {members[0]}
    frontier = [members[0]]
    while frontier:
        current = frontier.pop()
        for neighbor in parent.neighbors(current):
            if neighbor in allowed and neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return len(reached) == len(members)


if __name__ == "__main__":
    unittest.main()
