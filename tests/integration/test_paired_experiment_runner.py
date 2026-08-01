"""Integration checks for paired topology comparisons."""

from __future__ import annotations

import unittest

from secondaryexploration.experiments import (
    PairedRunManifest,
    TopologyVariant,
    route_choice_rng,
    run_paired_experiment,
)
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


class PairedRunnerIntegrationTests(unittest.TestCase):
    def test_each_recorded_route_uses_its_request_index_ticket(self) -> None:
        chain = uniform_overlap_chain(3, 1, 3)
        sunflower = common_core_sunflower(3, 1, 3)
        trace = generate_request_trace(
            uniform_kernel(chain.nodes),
            AmountDistribution.from_weights(((1, 1),)),
            40,
            root_seed=700,
        )
        manifest = PairedRunManifest(
            block_id="integration/block-1",
            trace=trace,
            routing_root_seed=701,
            variants=(
                TopologyVariant("chain", "chain", chain, equal_node_capital_state(chain, 12)),
                TopologyVariant("sunflower", "sunflower", sunflower, equal_node_capital_state(sunflower, 12)),
            ),
        )

        first = run_paired_experiment(manifest)
        second = run_paired_experiment(manifest)

        self.assertEqual(first, second)
        self.assertEqual(first.manifest_fingerprint, manifest.fingerprint)
        self.assertNotEqual(chain.hyperedges, sunflower.hyperedges)
        for index in range(1, trace.length + 1):
            self.assertEqual(
                route_choice_rng(701, index).randrange(97),
                route_choice_rng(701, index).randrange(97),
            )


if __name__ == "__main__":
    unittest.main()
