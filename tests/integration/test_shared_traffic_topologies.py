"""One immutable traffic trace shared by structurally distinct topologies."""

from __future__ import annotations

import random
import unittest

from secondaryexploration.simulation import run_core_trace
from secondaryexploration.topology import (
    common_core_sunflower,
    equal_node_capital_state,
    uniform_overlap_chain,
)
from secondaryexploration.traffic import (
    AmountDistribution,
    generate_request_trace,
    uniform_kernel,
)


class SharedTrafficTopologyTests(unittest.TestCase):
    def test_same_request_objects_feed_chain_and_sunflower(self) -> None:
        chain = uniform_overlap_chain(arity=3, overlap=1, edge_count=3)
        sunflower = common_core_sunflower(arity=3, overlap=1, edge_count=3)
        self.assertEqual(chain.nodes, sunflower.nodes)
        trace = generate_request_trace(
            uniform_kernel(chain.nodes),
            AmountDistribution.from_weights(((1, 1),)),
            24,
            root_seed=53,
        )

        chain_result = run_core_trace(
            equal_node_capital_state(chain, 6),
            trace.requests,
            random.Random(71),
        )
        sunflower_result = run_core_trace(
            equal_node_capital_state(sunflower, 6),
            trace.requests,
            random.Random(71),
        )

        self.assertEqual(
            tuple(outcome.request for outcome in chain_result.outcomes),
            trace.requests,
        )
        self.assertEqual(
            tuple(outcome.request for outcome in sunflower_result.outcomes),
            trace.requests,
        )
        self.assertEqual(chain_result.horizon, trace.length)
        self.assertEqual(sunflower_result.horizon, trace.length)
        for request, chain_outcome, sunflower_outcome in zip(
            trace.requests,
            chain_result.outcomes,
            sunflower_result.outcomes,
        ):
            self.assertIs(chain_outcome.request, request)
            self.assertIs(sunflower_outcome.request, request)


if __name__ == "__main__":
    unittest.main()
