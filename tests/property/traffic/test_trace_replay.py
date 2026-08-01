"""Finite replay grids for iid traffic traces."""

from __future__ import annotations

import unittest

from secondaryexploration.traffic import (
    AmountDistribution,
    community_local_kernel,
    directional_drift_kernel,
    generate_request_trace,
    hotspot_kernel,
    uniform_kernel,
)


class TraceReplayGridTests(unittest.TestCase):
    def test_kernel_seed_and_length_grid_replays_exactly(self) -> None:
        nodes = ("a", "b", "c", "d")
        kernels = (
            uniform_kernel(nodes),
            community_local_kernel(nodes, (("a", "b"), ("c", "d")), 4, 1),
            hotspot_kernel(nodes, ("a",), 1, 5),
            directional_drift_kernel(
                nodes, ("a", "b"), ("c", "d"), 5, 1, 2
            ),
        )
        amounts = AmountDistribution.from_weights(((1, 4), (2, 2), (5, 1)))
        checked = 0
        for kernel in kernels:
            for root_seed in range(16):
                for length in (0, 1, 7, 31):
                    with self.subTest(
                        fingerprint=kernel.fingerprint,
                        root_seed=root_seed,
                        length=length,
                    ):
                        first = generate_request_trace(
                            kernel, amounts, length, root_seed=root_seed
                        )
                        second = generate_request_trace(
                            kernel, amounts, length, root_seed=root_seed
                        )
                        self.assertEqual(first, second)
                        self.assertTrue(
                            all(
                                request.source in kernel.nodes
                                and request.destination in kernel.nodes
                                and request.source != request.destination
                                for request in first.requests
                            )
                        )
                        checked += 1
        self.assertEqual(checked, 256)


if __name__ == "__main__":
    unittest.main()
