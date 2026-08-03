"""Cross-topology integration tests for the common capacity optimizer."""

from __future__ import annotations

from fractions import Fraction
import unittest

from secondaryexploration.optimization import (
    CapacityOptimizationManifest,
    CapacityOptimizationPlan,
    CapacityTrainingScenario,
    DirectedDemandMatrix,
    optimize_common_capacity,
    validate_common_capacity_result,
)
from secondaryexploration.topology import HypergraphTopology, node_capital_totals
from secondaryexploration.traffic import (
    AmountDistribution,
    generate_request_trace,
    uniform_kernel,
)


class CommonCapacityIntegrationTests(unittest.TestCase):
    def test_distinct_topologies_receive_identical_full_evaluation_budget(self) -> None:
        nodes = ("a", "b", "c", "d")
        binary = HypergraphTopology.from_edges(
            nodes,
            {
                "b-0": ("a", "b"),
                "b-1": ("b", "c"),
                "b-2": ("c", "d"),
            },
        )
        hypergraph = HypergraphTopology.from_edges(
            nodes,
            {
                "h-0": ("a", "b", "c"),
                "h-1": ("b", "c", "d"),
            },
        )
        trace = generate_request_trace(
            uniform_kernel(nodes),
            AmountDistribution.from_weights(((1, 2), (2, 1))),
            16,
            root_seed=901,
        )
        scenarios = (
            CapacityTrainingScenario("uniform-0", "uniform", trace, 902),
        )
        demand = DirectedDemandMatrix.from_requests(nodes, trace.requests)
        manifest = CapacityOptimizationManifest.create(
            demand,
            12,
            Fraction(1),
            Fraction(1, 2),
            Fraction(1, 2),
            scenarios,
        )
        plan = CapacityOptimizationPlan(9, 903, 2)

        results = tuple(
            optimize_common_capacity(topology, demand, manifest, plan)
            for topology in (binary, hypergraph)
        )

        self.assertEqual(tuple(item.evaluation_count for item in results), (9, 9))
        self.assertEqual(tuple(len(item.proposals) for item in results), (7, 7))
        for topology, result in zip((binary, hypergraph), results):
            self.assertEqual(
                node_capital_totals(result.state),
                tuple((node_id, 12) for node_id in nodes),
            )
            validate_common_capacity_result(
                result,
                topology,
                demand,
                manifest,
                plan,
            )


if __name__ == "__main__":
    unittest.main()
