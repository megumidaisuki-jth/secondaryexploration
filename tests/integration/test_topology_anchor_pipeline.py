"""End-to-end checks from deterministic anchors to core settlement."""

from __future__ import annotations

import random
import unittest

from secondaryexploration.model import PaymentRequest
from secondaryexploration.simulation import EventObservation, run_core_trace
from secondaryexploration.topology import (
    common_core_sunflower,
    equal_node_capital_state,
    node_capital_totals,
    uniform_overlap_chain,
)


class AnchorPipelineTests(unittest.TestCase):
    def test_chain_and_sunflower_feed_complete_router_and_atomic_state_engine(
        self,
    ) -> None:
        cases = (
            (
                uniform_overlap_chain(arity=3, overlap=1, edge_count=4),
                "v00000000",
                "v00000008",
                4,
            ),
            (
                common_core_sunflower(arity=3, overlap=1, edge_count=4),
                "v00000001",
                "v00000008",
                2,
            ),
        )
        for topology, source, destination, expected_hops in cases:
            with self.subTest(topology=topology):
                initial = equal_node_capital_state(topology, per_node_capital=12)
                result = run_core_trace(
                    initial,
                    (PaymentRequest(source, destination, 1),),
                    random.Random(7),
                )

                self.assertTrue(result.outcomes[0].accepted)
                self.assertEqual(
                    result.outcomes[0].search_result.shortest_hops,
                    expected_hops,
                )
                self.assertEqual(result.final_state.total_balance, initial.total_balance)
                self.assertEqual(result.tau_dep, EventObservation.censored_at(1))
                self.assertEqual(result.tau_nopath, EventObservation.censored_at(1))

                final_totals = dict(node_capital_totals(result.final_state))
                self.assertEqual(final_totals[source], 11)
                self.assertEqual(final_totals[destination], 13)
                for node_id in topology.nodes:
                    if node_id not in {source, destination}:
                        self.assertEqual(final_totals[node_id], 12)


if __name__ == "__main__":
    unittest.main()
