"""Primary-size smoke test for bounded deterministic topology training."""

from __future__ import annotations

from fractions import Fraction
import unittest

from secondaryexploration.model import PaymentRequest
from secondaryexploration.optimization import (
    DemandAwareObjectiveWeights,
    DemandAwareSearchPlan,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    generate_connected_candidate_pool,
    train_demand_aware_topology,
    validate_demand_aware_topology,
)
from secondaryexploration.topology import ParentGraph, binary_topology


class DemandAwareConstructorScaleTests(unittest.TestCase):
    def test_n240_candidate_and_search_budget_remain_exact_and_bounded(self) -> None:
        nodes = tuple(f"n{index:03d}" for index in range(240))
        parent = ParentGraph.from_edges(nodes, tuple(zip(nodes, nodes[1:])))
        demand = DirectedDemandMatrix.from_requests(
            nodes,
            tuple(
                PaymentRequest(nodes[index], nodes[index + 2], 1)
                for index in range(238)
            ),
        )
        seed = binary_topology(parent)
        manifest = DemandAwareTrainingManifest.create(
            parent,
            demand,
            seed.resources.incidence_count,
            5,
            DemandAwareObjectiveWeights(
                Fraction(1),
                Fraction(1),
                Fraction(1),
                Fraction(1),
            ),
        )

        pool = generate_connected_candidate_pool(parent, demand, manifest)
        result = train_demand_aware_topology(
            parent,
            demand,
            seed,
            manifest,
            DemandAwareSearchPlan(100, 1, 3),
        )

        self.assertEqual(len(pool.candidates), 950)
        self.assertEqual(result.proposals_considered, 100)
        self.assertLessEqual(result.feasible_evaluations, 100)
        self.assertEqual(
            result.topology.resources.incidence_count,
            seed.resources.incidence_count,
        )
        self.assertLessEqual(result.topology.resources.maximum_arity, 5)
        validate_demand_aware_topology(parent, result.topology, manifest)


if __name__ == "__main__":
    unittest.main()
