"""Exact contracts for primary iid demand kernels and amount weights."""

from __future__ import annotations

from collections import Counter
import unittest

from secondaryexploration.traffic import (
    AmountDistribution,
    DemandKernel,
    TrafficError,
    community_local_kernel,
    directional_drift_kernel,
    hotspot_kernel,
    uniform_kernel,
)


class DemandKernelTests(unittest.TestCase):
    def test_uniform_kernel_contains_every_ordered_pair_once(self) -> None:
        kernel = uniform_kernel(("c", "a", "b"))

        self.assertEqual(kernel.nodes, ("a", "b", "c"))
        self.assertEqual(len(kernel.pair_weights), 6)
        self.assertEqual(kernel.total_weight, 6)
        self.assertEqual(
            tuple(kernel.pair_for_ticket(ticket) for ticket in range(6)),
            (
                ("a", "b"),
                ("a", "c"),
                ("b", "a"),
                ("b", "c"),
                ("c", "a"),
                ("c", "b"),
            ),
        )

    def test_community_kernel_has_exact_local_and_cross_weights(self) -> None:
        kernel = community_local_kernel(
            ("a", "b", "c", "d"),
            (("a", "b"), ("c", "d")),
            within_weight=3,
            cross_weight=1,
        )

        self.assertEqual(kernel.total_weight, 20)
        self.assertEqual(kernel.weight_of("a", "b"), 3)
        self.assertEqual(kernel.weight_of("b", "a"), 3)
        self.assertEqual(kernel.weight_of("a", "c"), 1)
        self.assertEqual(kernel.weight_of("d", "b"), 1)

    def test_hotspot_multiplier_applies_per_endpoint(self) -> None:
        kernel = hotspot_kernel(
            ("a", "b", "c"),
            ("a", "b"),
            base_weight=2,
            hotspot_multiplier=3,
        )

        self.assertEqual(kernel.weight_of("a", "b"), 18)
        self.assertEqual(kernel.weight_of("a", "c"), 6)
        self.assertEqual(kernel.weight_of("c", "a"), 6)
        self.assertEqual(kernel.weight_of("b", "c"), 6)
        self.assertEqual(kernel.total_weight, 60)

    def test_directional_cut_uses_three_exact_weights(self) -> None:
        kernel = directional_drift_kernel(
            ("a", "b", "c", "d"),
            left_group=("a", "b"),
            right_group=("c", "d"),
            forward_weight=5,
            reverse_weight=1,
            within_weight=2,
        )

        self.assertEqual(kernel.total_weight, 32)
        self.assertEqual(kernel.weight_of("a", "c"), 5)
        self.assertEqual(kernel.weight_of("d", "a"), 1)
        self.assertEqual(kernel.weight_of("a", "b"), 2)
        self.assertEqual(kernel.weight_of("c", "d"), 2)

    def test_weighted_ticket_maps_realize_every_declared_multiplicity(self) -> None:
        kernels = (
            community_local_kernel(
                ("a", "b", "c", "d"),
                (("a", "b"), ("c", "d")),
                3,
                1,
            ),
            hotspot_kernel(("a", "b", "c"), ("a",), 2, 4),
            directional_drift_kernel(
                ("a", "b", "c", "d"),
                ("a", "b"),
                ("c", "d"),
                5,
                1,
                2,
            ),
        )
        for kernel in kernels:
            with self.subTest(fingerprint=kernel.fingerprint):
                tickets = Counter(
                    kernel.pair_for_ticket(ticket)
                    for ticket in range(kernel.total_weight)
                )
                self.assertEqual(
                    tickets,
                    Counter(
                        {
                            (source, destination): weight
                            for source, destination, weight in kernel.pair_weights
                        }
                    ),
                )

    def test_invalid_kernel_inputs_fail_closed(self) -> None:
        calls = (
            lambda: uniform_kernel(("a",)),
            lambda: uniform_kernel(("a", "a")),
            lambda: community_local_kernel(
                ("a", "b", "c"), (("a", "b"),), 2, 1
            ),
            lambda: community_local_kernel(
                ("a", "b"), (("a",), ("a", "b")), 2, 1
            ),
            lambda: hotspot_kernel(("a", "b"), (), 1, 2),
            lambda: hotspot_kernel(("a", "b"), ("a", "b"), 1, 2),
            lambda: directional_drift_kernel(
                ("a", "b"), ("a",), ("a", "b"), 2, 1, 1
            ),
            lambda: directional_drift_kernel(
                ("a", "b"), ("a",), ("b",), True, 1, 1
            ),
            lambda: DemandKernel.from_weights(
                ("a", "b", "c"), (("a", "b", 1),)
            ),
            lambda: DemandKernel.from_weights(("a", "b"), (1,)),
        )
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(TrafficError):
                    call()


class AmountDistributionTests(unittest.TestCase):
    def test_amount_tickets_repeat_exact_integer_weights(self) -> None:
        distribution = AmountDistribution.from_weights(((5, 2), (1, 1), (9, 3)))

        self.assertEqual(distribution.amount_weights, ((1, 1), (5, 2), (9, 3)))
        self.assertEqual(distribution.total_weight, 6)
        self.assertEqual(
            tuple(distribution.amount_for_ticket(ticket) for ticket in range(6)),
            (1, 5, 5, 9, 9, 9),
        )

    def test_invalid_amount_tables_fail_closed(self) -> None:
        for values in ((), ((0, 1),), ((1, 0),), ((1, 1), (1, 2)), "bad"):
            with self.subTest(values=values):
                with self.assertRaises(TrafficError):
                    AmountDistribution.from_weights(values)


if __name__ == "__main__":
    unittest.main()
