"""Exhaustive short-sequence cross-check for the core request clock."""

from __future__ import annotations

from fractions import Fraction
import inspect
import itertools
import random
import unittest

from secondaryexploration.model import HypergraphState, PaymentRequest
from secondaryexploration.simulation import run_core_trace
from tests.exact import reference_core_trace
from tests.exact.reference_core_trace import (
    ReferenceRequest,
    run_two_node_reference,
)


class CoreTraceOracleTests(unittest.TestCase):
    def test_reference_trace_has_no_production_dependency(self) -> None:
        source = inspect.getsource(reference_core_trace)

        self.assertNotIn("secondaryexploration", source)
        self.assertNotIn("run_core_trace", source)
        self.assertNotIn("find_feasible_route", source)
        self.assertNotIn("apply_atomic_payment", source)

    def test_all_short_binary_request_sequences_match_integer_oracle(self) -> None:
        request_alphabet = (
            ReferenceRequest("s", "t", 1),
            ReferenceRequest("s", "t", 2),
            ReferenceRequest("t", "s", 1),
            ReferenceRequest("t", "s", 2),
        )
        request_sequences = tuple(
            sequence
            for length in range(5)
            for sequence in itertools.product(request_alphabet, repeat=length)
        )
        checked_cases = 0

        for source_balance in range(5):
            destination_balance = 4 - source_balance
            initial_state = HypergraphState.from_balances(
                nodes=("s", "t"),
                hyperedges={
                    "edge": {
                        "s": source_balance,
                        "t": destination_balance,
                    }
                },
            )
            for reference_requests in request_sequences:
                with self.subTest(
                    source_balance=source_balance,
                    reference_requests=reference_requests,
                ):
                    requests = tuple(
                        PaymentRequest(
                            request.source,
                            request.destination,
                            request.amount,
                        )
                        for request in reference_requests
                    )
                    reference = run_two_node_reference(
                        source_balance,
                        destination_balance,
                        reference_requests,
                    )
                    production = run_core_trace(
                        initial_state,
                        requests,
                        random.Random(0),
                    )

                    self.assertEqual(
                        production.final_state.edge("edge").balances,
                        (
                            ("s", reference.final_source_balance),
                            ("t", reference.final_destination_balance),
                        ),
                    )
                    self.assertEqual(
                        tuple(outcome.accepted for outcome in production.outcomes),
                        reference.accepted,
                    )
                    self.assertEqual(
                        (production.tau_dep.observed, production.tau_dep.request_index),
                        reference.tau_dep,
                    )
                    self.assertEqual(
                        (
                            production.tau_nopath.observed,
                            production.tau_nopath.request_index,
                        ),
                        reference.tau_nopath,
                    )
                    self.assertEqual(
                        (production.tau_rej.observed, production.tau_rej.request_index),
                        reference.tau_rej,
                    )
                    self.assertEqual(
                        production.cumulative_successes,
                        reference.cumulative_successes,
                    )
                    self.assertEqual(
                        tuple(
                            (
                                episode.start_request,
                                episode.length,
                                episode.ended_by_success,
                            )
                            for episode in production.failure_episodes
                        ),
                        reference.failure_episodes,
                    )
                    if reference.recovery is None:
                        self.assertIsNone(production.recovery_after_first_rejection)
                    else:
                        assert production.recovery_after_first_rejection is not None
                        self.assertEqual(
                            (
                                production.recovery_after_first_rejection.origin_request,
                                production.recovery_after_first_rejection.observed,
                                production.recovery_after_first_rejection.request_index,
                            ),
                            reference.recovery,
                        )
                    expected_success_rate = (
                        None
                        if not reference.accepted
                        else Fraction(sum(reference.accepted), len(reference.accepted))
                    )
                    self.assertEqual(production.success_rate, expected_success_rate)
                    checked_cases += 1

        self.assertEqual(checked_cases, 1_705)


if __name__ == "__main__":
    unittest.main()
