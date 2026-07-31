"""Contract tests for the core request-clock and first service events."""

from __future__ import annotations

from fractions import Fraction
import random
import unittest

from secondaryexploration import rng_for
from secondaryexploration.model import (
    HypergraphState,
    PaymentRequest,
    Route,
    TransferStep,
    apply_atomic_payment,
)
from secondaryexploration.routing import RouteSearchResult, find_feasible_route
from secondaryexploration.simulation.core import (
    CoreRequestOutcome,
    CoreSimulationResult,
    EventObservation,
    FailureEpisode,
    RecoveryObservation,
    SimulationError,
    run_core_trace,
)


def binary_state(source_balance: int = 1, destination_balance: int = 3) -> HypergraphState:
    return HypergraphState.from_balances(
        nodes=("s", "t"),
        hyperedges={
            "edge": {
                "s": source_balance,
                "t": destination_balance,
            }
        },
    )


class ObservationValueTests(unittest.TestCase):
    def test_event_observation_factories_distinguish_event_from_censoring(self) -> None:
        observed = EventObservation.observed_at(3)
        censored = EventObservation.censored_at(3)

        self.assertTrue(observed.observed)
        self.assertFalse(censored.observed)
        self.assertEqual(observed.request_index, censored.request_index)

    def test_invalid_event_observations_are_rejected(self) -> None:
        invalid_cases = ((1, 0), (True, -1), (False, -1), (False, 1.0))
        for observed, request_index in invalid_cases:
            with self.subTest(observed=observed, request_index=request_index):
                with self.assertRaises(SimulationError):
                    EventObservation(  # type: ignore[arg-type]
                        observed=observed,
                        request_index=request_index,
                    )

    def test_recovery_observation_reports_event_or_censor_delay(self) -> None:
        recovered = RecoveryObservation(
            origin_request=2,
            observed=True,
            request_index=5,
        )
        censored = RecoveryObservation(
            origin_request=2,
            observed=False,
            request_index=6,
        )

        self.assertEqual(recovered.elapsed_requests, 3)
        self.assertEqual(censored.elapsed_requests, 4)

        with self.assertRaisesRegex(SimulationError, "later"):
            RecoveryObservation(
                origin_request=2,
                observed=True,
                request_index=2,
            )

    def test_failure_episode_has_exact_inclusive_end(self) -> None:
        episode = FailureEpisode(
            start_request=3,
            length=2,
            ended_by_success=True,
        )

        self.assertEqual(episode.end_request, 4)


class CoreTraceTests(unittest.TestCase):
    def test_empty_trace_is_fully_censored_at_zero(self) -> None:
        initial = binary_state()

        result = run_core_trace(initial, (), random.Random(1))

        self.assertEqual(result.horizon, 0)
        self.assertIs(result.final_state, initial)
        self.assertEqual(result.outcomes, ())
        self.assertEqual(result.tau_dep, EventObservation.censored_at(0))
        self.assertEqual(result.tau_nopath, EventObservation.censored_at(0))
        self.assertEqual(result.tau_rej, EventObservation.censored_at(0))
        self.assertEqual(result.cumulative_successes, ())
        self.assertIsNone(result.success_rate)
        self.assertEqual(result.failure_episodes, ())
        self.assertIsNone(result.recovery_after_first_rejection)

    def test_initial_zero_balance_sets_tau_dep_to_zero(self) -> None:
        result = run_core_trace(binary_state(0, 4), (), random.Random(1))

        self.assertEqual(result.tau_dep, EventObservation.observed_at(0))
        self.assertEqual(result.tau_nopath, EventObservation.censored_at(0))

    def test_exact_boundary_payment_is_accepted_at_request_one(self) -> None:
        result = run_core_trace(
            binary_state(1, 3),
            (PaymentRequest("s", "t", 1),),
            random.Random(1),
        )

        self.assertTrue(result.outcomes[0].accepted)
        self.assertFalse(result.outcomes[0].no_path)
        self.assertFalse(result.outcomes[0].final_rejected)
        self.assertEqual(result.tau_dep, EventObservation.observed_at(1))
        self.assertEqual(result.tau_nopath, EventObservation.censored_at(1))
        self.assertEqual(result.tau_rej, EventObservation.censored_at(1))
        self.assertEqual(result.final_state.edge("edge").balance_of("s"), 0)
        self.assertEqual(result.success_rate, Fraction(1, 1))

    def test_path_unavailability_can_precede_exact_depletion(self) -> None:
        requests = (
            PaymentRequest("s", "t", 2),
            PaymentRequest("t", "s", 1),
            PaymentRequest("s", "t", 2),
        )

        result = run_core_trace(binary_state(1, 3), requests, random.Random(1))

        self.assertEqual(
            tuple(outcome.accepted for outcome in result.outcomes),
            (False, True, True),
        )
        self.assertEqual(result.tau_nopath, EventObservation.observed_at(1))
        self.assertEqual(result.tau_rej, EventObservation.observed_at(1))
        self.assertEqual(result.tau_dep, EventObservation.observed_at(3))
        self.assertEqual(
            result.recovery_after_first_rejection,
            RecoveryObservation(
                origin_request=1,
                observed=True,
                request_index=2,
            ),
        )
        self.assertEqual(result.cumulative_successes, (0, 1, 2))
        self.assertEqual(result.success_rate, Fraction(2, 3))
        self.assertEqual(
            result.failure_episodes,
            (FailureEpisode(1, 1, True),),
        )
        self.assertEqual(result.final_state.edge("edge").balances, (("s", 0), ("t", 4)))

    def test_exact_depletion_can_precede_path_unavailability(self) -> None:
        requests = (
            PaymentRequest("s", "t", 1),
            PaymentRequest("t", "s", 1),
            PaymentRequest("s", "t", 2),
        )

        result = run_core_trace(binary_state(1, 3), requests, random.Random(1))

        self.assertEqual(
            tuple(outcome.accepted for outcome in result.outcomes),
            (True, True, False),
        )
        self.assertEqual(result.tau_dep, EventObservation.observed_at(1))
        self.assertEqual(result.tau_nopath, EventObservation.observed_at(3))
        self.assertEqual(result.tau_rej, EventObservation.observed_at(3))
        self.assertEqual(
            result.recovery_after_first_rejection,
            RecoveryObservation(
                origin_request=3,
                observed=False,
                request_index=3,
            ),
        )
        self.assertEqual(
            result.failure_episodes,
            (FailureEpisode(3, 1, False),),
        )

    def test_trace_continues_and_summarizes_multiple_failure_episodes(self) -> None:
        requests = (
            PaymentRequest("s", "t", 2),
            PaymentRequest("s", "t", 2),
            PaymentRequest("t", "s", 1),
            PaymentRequest("s", "t", 3),
        )

        result = run_core_trace(binary_state(1, 3), requests, random.Random(1))

        self.assertEqual(result.horizon, 4)
        self.assertEqual(
            tuple(outcome.request_index for outcome in result.outcomes),
            (1, 2, 3, 4),
        )
        self.assertEqual(
            tuple(outcome.accepted for outcome in result.outcomes),
            (False, False, True, False),
        )
        self.assertEqual(result.cumulative_successes, (0, 0, 1, 1))
        self.assertEqual(result.success_rate, Fraction(1, 4))
        self.assertEqual(
            result.failure_episodes,
            (
                FailureEpisode(1, 2, True),
                FailureEpisode(4, 1, False),
            ),
        )
        self.assertEqual(
            result.recovery_after_first_rejection,
            RecoveryObservation(1, True, 3),
        )
        self.assertEqual(result.tau_dep, EventObservation.censored_at(4))
        self.assertEqual(result.tau_nopath, EventObservation.observed_at(1))
        self.assertEqual(result.tau_rej, EventObservation.observed_at(1))
        self.assertEqual(result.final_state.edge("edge").balances, (("s", 2), ("t", 2)))

    def test_all_rejected_trace_preserves_exact_initial_state_object(self) -> None:
        initial = binary_state(1, 3)
        requests = (
            PaymentRequest("s", "t", 5),
            PaymentRequest("s", "t", 4),
        )

        result = run_core_trace(initial, requests, random.Random(1))

        self.assertIs(result.final_state, initial)
        self.assertTrue(all(outcome.no_path for outcome in result.outcomes))
        self.assertEqual(result.cumulative_successes, (0, 0))

    def test_same_seed_replays_complete_tied_route_trace(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first": {"a": 0, "s": 3},
                "a-second": {"a": 3, "t": 0},
                "b-first": {"b": 0, "s": 3},
                "b-second": {"b": 3, "t": 0},
            },
        )
        requests = tuple(PaymentRequest("s", "t", 1) for _ in range(3))

        first = run_core_trace(initial, requests, rng_for(44, "router", 0))
        second = run_core_trace(initial, requests, rng_for(44, "router", 0))

        self.assertEqual(first, second)
        self.assertEqual(initial.edge("a-first").balances, (("a", 0), ("s", 3)))

    def test_result_validation_rejects_tampered_state_or_event_time(self) -> None:
        initial = binary_state(1, 3)
        valid = run_core_trace(
            initial,
            (PaymentRequest("s", "t", 1),),
            random.Random(1),
        )

        with self.assertRaisesRegex(SimulationError, "final_state"):
            CoreSimulationResult(
                initial_state=valid.initial_state,
                final_state=valid.initial_state,
                outcomes=valid.outcomes,
                tau_dep=valid.tau_dep,
                tau_nopath=valid.tau_nopath,
                tau_rej=valid.tau_rej,
            )
        with self.assertRaisesRegex(SimulationError, "tau_dep"):
            CoreSimulationResult(
                initial_state=valid.initial_state,
                final_state=valid.final_state,
                outcomes=valid.outcomes,
                tau_dep=EventObservation.censored_at(1),
                tau_nopath=valid.tau_nopath,
                tau_rej=valid.tau_rej,
            )

    def test_result_validation_rejects_false_no_path_record(self) -> None:
        initial = binary_state(1, 3)
        request = PaymentRequest("s", "t", 1)
        forged_outcome = CoreRequestOutcome(
            request_index=1,
            request=request,
            search_result=RouteSearchResult.no_path(),
            depleted_coordinates=(),
        )

        with self.assertRaisesRegex(SimulationError, "no-path.*feasible"):
            CoreSimulationResult(
                initial_state=initial,
                final_state=initial,
                outcomes=(forged_outcome,),
                tau_dep=EventObservation.censored_at(1),
                tau_nopath=EventObservation.observed_at(1),
                tau_rej=EventObservation.observed_at(1),
            )

    def test_result_validation_rejects_nonoptimal_feasible_route(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("a", "s", "t"),
            hyperedges={
                "direct": {"s": 1, "t": 9},
                "first": {"a": 0, "s": 10},
                "second": {"a": 10, "t": 0},
            },
        )
        request = PaymentRequest("s", "t", 1)
        longer_route = Route(
            steps=(
                TransferStep("first", "s", "a"),
                TransferStep("second", "a", "t"),
            )
        )
        transition = apply_atomic_payment(initial, request, longer_route)
        forged_outcome = CoreRequestOutcome(
            request_index=1,
            request=request,
            search_result=RouteSearchResult(
                route=longer_route,
                shortest_hops=2,
                bottleneck=Fraction(9, 10),
                tied_route_count=1,
            ),
            depleted_coordinates=(),
        )

        with self.assertRaisesRegex(SimulationError, "search metadata"):
            CoreSimulationResult(
                initial_state=initial,
                final_state=transition.state,
                outcomes=(forged_outcome,),
                tau_dep=EventObservation.observed_at(0),
                tau_nopath=EventObservation.censored_at(1),
                tau_rej=EventObservation.censored_at(1),
            )

    def test_result_validation_rejects_equal_hop_lower_bottleneck_route(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first": {"a": 0, "s": 10},
                "a-second": {"a": 10, "t": 0},
                "b-first": {"b": 8, "s": 2},
                "b-second": {"b": 10, "t": 0},
            },
        )
        request = PaymentRequest("s", "t", 1)
        weaker_route = Route(
            steps=(
                TransferStep("b-first", "s", "b"),
                TransferStep("b-second", "b", "t"),
            )
        )
        transition = apply_atomic_payment(initial, request, weaker_route)
        forged_outcome = CoreRequestOutcome(
            request_index=1,
            request=request,
            search_result=RouteSearchResult(
                route=weaker_route,
                shortest_hops=2,
                bottleneck=Fraction(9, 10),
                tied_route_count=1,
            ),
            depleted_coordinates=(),
        )

        with self.assertRaisesRegex(SimulationError, "does not attain"):
            CoreSimulationResult(
                initial_state=initial,
                final_state=transition.state,
                outcomes=(forged_outcome,),
                tau_dep=EventObservation.observed_at(0),
                tau_nopath=EventObservation.censored_at(1),
                tau_rej=EventObservation.censored_at(1),
            )

    def test_result_validation_accepts_different_route_in_optimal_tie(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first": {"a": 0, "s": 3},
                "a-second": {"a": 3, "t": 0},
                "b-first": {"b": 0, "s": 3},
                "b-second": {"b": 3, "t": 0},
            },
        )
        request = PaymentRequest("s", "t", 1)
        recorded_route = Route(
            steps=(
                TransferStep("a-first", "s", "a"),
                TransferStep("a-second", "a", "t"),
            )
        )
        transition = apply_atomic_payment(initial, request, recorded_route)
        validator_selected = find_feasible_route(
            initial,
            request,
            random.Random(0),
        ).route
        self.assertNotEqual(validator_selected, recorded_route)
        outcome = CoreRequestOutcome(
            request_index=1,
            request=request,
            search_result=RouteSearchResult(
                route=recorded_route,
                shortest_hops=2,
                bottleneck=Fraction(2, 3),
                tied_route_count=2,
            ),
            depleted_coordinates=(),
        )

        validated = CoreSimulationResult(
            initial_state=initial,
            final_state=transition.state,
            outcomes=(outcome,),
            tau_dep=EventObservation.observed_at(0),
            tau_nopath=EventObservation.censored_at(1),
            tau_rej=EventObservation.censored_at(1),
        )

        self.assertEqual(validated.outcomes, (outcome,))


if __name__ == "__main__":
    unittest.main()
