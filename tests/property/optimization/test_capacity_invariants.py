"""Finite randomized invariants for common capacity optimization."""

from __future__ import annotations

from fractions import Fraction
import random
import unittest

from secondaryexploration.optimization import (
    CapacityOptimizationManifest,
    CapacityOptimizationPlan,
    CapacityTrainingScenario,
    DirectedDemandMatrix,
    optimize_common_capacity,
    validate_capacity_state,
)
from secondaryexploration.topology import ParentGraph, binary_topology, node_capital_totals
from secondaryexploration.traffic import (
    AmountDistribution,
    generate_request_trace,
    uniform_kernel,
)


class CommonCapacityPropertyTests(unittest.TestCase):
    def test_random_connected_cells_preserve_all_registered_invariants(self) -> None:
        rng = random.Random(20_260_801)
        for case_index in range(12):
            node_count = rng.randrange(3, 7)
            nodes = tuple(f"n{index}" for index in range(node_count))
            edges = {(nodes[index - 1], nodes[index]) for index in range(1, node_count)}
            possible = tuple(
                (nodes[left], nodes[right])
                for left in range(node_count)
                for right in range(left + 1, node_count)
                if (nodes[left], nodes[right]) not in edges
            )
            for edge in possible:
                if rng.randrange(4) == 0:
                    edges.add(edge)
            topology = binary_topology(ParentGraph.from_edges(nodes, tuple(edges)))
            horizon = 6
            scenarios = tuple(
                CapacityTrainingScenario(
                    f"scenario-{replicate}",
                    "uniform",
                    generate_request_trace(
                        uniform_kernel(nodes),
                        AmountDistribution.from_weights(((1, 2), (2, 1))),
                        horizon,
                        root_seed=50_000 + case_index * 10 + replicate,
                    ),
                    60_000 + case_index * 10 + replicate,
                )
                for replicate in range(2)
            )
            demand = DirectedDemandMatrix.from_requests(
                nodes,
                tuple(
                    request
                    for scenario in scenarios
                    for request in scenario.trace.requests
                ),
            )
            maximum_degree = max(degree for _, degree in topology.node_incidence_degrees)
            per_node_capital = max(8, maximum_degree + 2)
            manifest = CapacityOptimizationManifest.create(
                demand,
                per_node_capital,
                Fraction(1),
                Fraction(1, 3),
                Fraction(1, 2),
                scenarios,
            )
            plan = CapacityOptimizationPlan(6, 70_000 + case_index, 2)

            first = optimize_common_capacity(topology, demand, manifest, plan)
            second = optimize_common_capacity(topology, demand, manifest, plan)

            with self.subTest(case_index=case_index, node_count=node_count):
                self.assertEqual(first, second)
                self.assertEqual(first.evaluation_count, plan.evaluation_budget)
                validate_capacity_state(topology, first.state, manifest)
                self.assertEqual(
                    node_capital_totals(first.state),
                    tuple((node_id, per_node_capital) for node_id in nodes),
                )
                self.assertTrue(
                    all(
                        amount >= 1
                        for edge in first.state.hyperedges
                        for _, amount in edge.balances
                    )
                )
                self.assertTrue(
                    all(
                        1 <= outcome.tau_nopath <= horizon
                        for outcome in first.score.outcomes
                    )
                )
                ordered = sorted(
                    outcome.tau_nopath for outcome in first.score.outcomes
                )
                self.assertEqual(
                    first.score.regime_quantiles,
                    (("uniform", ordered[0]),),
                )


if __name__ == "__main__":
    unittest.main()
