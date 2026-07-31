"""End-to-end state and routing checks for NCH/FHS transformations."""

from __future__ import annotations

from math import lcm
import random
import unittest

from secondaryexploration.model import PaymentRequest
from secondaryexploration.simulation import run_core_trace
from secondaryexploration.topology import (
    ParentGraph,
    closed_neighborhood_nch,
    equal_node_capital_state,
    fixed_hyperedge_size,
    node_capital_totals,
)


class TransformedTopologyPipelineTests(unittest.TestCase):
    def test_nch_and_fhs_support_equal_capital_and_end_to_end_service(self) -> None:
        parent = ParentGraph.from_edges(
            nodes=("a", "b", "c", "d", "e"),
            edges=(("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")),
        )
        for topology in (
            closed_neighborhood_nch(parent),
            fixed_hyperedge_size(parent, maximum_arity=3),
        ):
            with self.subTest(topology=topology):
                budget = lcm(
                    *(degree for _, degree in topology.node_incidence_degrees)
                )
                initial = equal_node_capital_state(topology, budget)
                result = run_core_trace(
                    initial,
                    (PaymentRequest("a", "e", 1),),
                    random.Random(8),
                )

                self.assertTrue(result.outcomes[0].accepted)
                totals = dict(node_capital_totals(result.final_state))
                self.assertEqual(totals["a"], budget - 1)
                self.assertEqual(totals["e"], budget + 1)
                for node_id in ("b", "c", "d"):
                    self.assertEqual(totals[node_id], budget)


if __name__ == "__main__":
    unittest.main()
