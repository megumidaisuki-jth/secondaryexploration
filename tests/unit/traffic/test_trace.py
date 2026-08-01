"""Replay and stream-separation contracts for iid request traces."""

from __future__ import annotations

import unittest

from secondaryexploration.model import PaymentRequest
from secondaryexploration.traffic import (
    AmountDistribution,
    RequestTrace,
    TrafficError,
    generate_request_trace,
    hotspot_kernel,
    uniform_kernel,
)


class RequestTraceTests(unittest.TestCase):
    def test_known_seeded_trace_vector(self) -> None:
        kernel = hotspot_kernel(
            ("a", "b", "c", "d"),
            ("a",),
            base_weight=1,
            hotspot_multiplier=4,
        )
        amounts = AmountDistribution.from_weights(((1, 2), (3, 1)))

        trace = generate_request_trace(
            kernel,
            amounts,
            length=8,
            root_seed=20260801,
        )

        self.assertEqual(trace.length, 8)
        self.assertEqual(
            kernel.fingerprint,
            "7a8bcf6728722473d59ecf0fdf3d80387cf6761f442d7d5ddcd87579819fa4d4",
        )
        self.assertEqual(
            amounts.fingerprint,
            "0dd537d50ce3cdc7ce0e1fc18aa82808f21c887a02f7318b325eb7fcd6921a28",
        )
        self.assertEqual(trace.pair_seed, 15387593755758008163)
        self.assertEqual(trace.amount_seed, 322676269124986467)
        self.assertEqual(
            trace.requests,
            (
                PaymentRequest("a", "c", 1),
                PaymentRequest("d", "a", 3),
                PaymentRequest("d", "a", 1),
                PaymentRequest("c", "a", 1),
                PaymentRequest("d", "a", 1),
                PaymentRequest("d", "a", 1),
                PaymentRequest("d", "a", 1),
                PaymentRequest("c", "d", 1),
            ),
        )

    def test_pair_and_amount_streams_are_separated(self) -> None:
        kernel = uniform_kernel(("a", "b", "c", "d"))
        first_amounts = AmountDistribution.from_weights(((1, 1), (2, 1)))
        second_amounts = AmountDistribution.from_weights(((7, 3), (9, 1)))

        first = generate_request_trace(kernel, first_amounts, 50, root_seed=17)
        second = generate_request_trace(kernel, second_amounts, 50, root_seed=17)
        other_kernel = hotspot_kernel(
            kernel.nodes,
            ("a",),
            base_weight=1,
            hotspot_multiplier=5,
        )
        third = generate_request_trace(other_kernel, first_amounts, 50, root_seed=17)

        self.assertEqual(
            tuple((request.source, request.destination) for request in first.requests),
            tuple((request.source, request.destination) for request in second.requests),
        )
        self.assertEqual(
            tuple(request.amount for request in first.requests),
            tuple(request.amount for request in third.requests),
        )

    def test_public_trace_record_rejects_forged_requests_or_seed(self) -> None:
        kernel = uniform_kernel(("a", "b", "c"))
        amounts = AmountDistribution.from_weights(((1, 1),))
        trace = generate_request_trace(kernel, amounts, 4, root_seed=19)
        forged = trace.requests[:-1] + (PaymentRequest("a", "b", 1),)

        for values in (
            dict(requests=forged),
            dict(root_seed=20),
            dict(length=3),
        ):
            kwargs = dict(
                kernel=trace.kernel,
                amount_distribution=trace.amount_distribution,
                length=trace.length,
                root_seed=trace.root_seed,
                requests=trace.requests,
            )
            kwargs.update(values)
            with self.subTest(values=values):
                with self.assertRaises(TrafficError):
                    RequestTrace(**kwargs)

    def test_empty_trace_is_replayable(self) -> None:
        trace = generate_request_trace(
            uniform_kernel(("a", "b")),
            AmountDistribution.from_weights(((1, 1),)),
            0,
            root_seed=0,
        )
        self.assertEqual(trace.requests, ())

    def test_invalid_length_and_seed_fail_closed(self) -> None:
        kernel = uniform_kernel(("a", "b"))
        amounts = AmountDistribution.from_weights(((1, 1),))
        calls = (
            lambda: generate_request_trace(kernel, amounts, -1, root_seed=0),
            lambda: generate_request_trace(kernel, amounts, True, root_seed=0),
            lambda: generate_request_trace(kernel, amounts, 1, root_seed=-1),
            lambda: generate_request_trace(kernel, amounts, 1, root_seed=2**64),
            lambda: generate_request_trace(kernel, amounts, 1, root_seed=True),
        )
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(TrafficError):
                    call()


if __name__ == "__main__":
    unittest.main()
