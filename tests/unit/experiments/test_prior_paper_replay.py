"""Cross-checks for the efficient Gate-V1 replay engine."""

from __future__ import annotations

from fractions import Fraction
from dataclasses import replace
import unittest

from secondaryexploration.experiments import (
    PriorPaperError,
    PriorPaperReplayOutcome,
    route_choice_rng,
    run_prior_paper_replay,
    state_balance_fingerprint,
    validate_prior_paper_replay,
)
from secondaryexploration.model import (
    HypergraphState,
    PaymentRequest,
    apply_atomic_payment,
)
from secondaryexploration.routing import find_uniform_shortest_available_route
from secondaryexploration.topology import HypergraphTopology


def _topology_for(state: HypergraphState) -> HypergraphTopology:
    return HypergraphTopology.from_edges(
        state.nodes,
        {edge.hyperedge_id: edge.members for edge in state.hyperedges},
    )


def _reference_replay(
    state: HypergraphState,
    requests: tuple[PaymentRequest, ...],
    seed: int,
) -> tuple[tuple[tuple[str, int | None], ...], HypergraphState]:
    outcomes: list[tuple[str, int | None]] = []
    node_set = set(state.nodes)
    for index, request in enumerate(requests, start=1):
        if request.source not in node_set or request.destination not in node_set:
            outcomes.append(("unavailable_endpoint", None))
            continue
        search = find_uniform_shortest_available_route(
            state,
            request,
            route_choice_rng(seed, index),
        )
        if search.route is None:
            outcomes.append(("no_path", None))
            continue
        transition = apply_atomic_payment(state, request, search.route)
        if not transition.accepted:
            raise AssertionError("reference router selected an infeasible route")
        state = transition.state
        outcomes.append(("accepted", search.route.hop_count))
    return tuple(outcomes), state


class PriorPaperReplayTests(unittest.TestCase):
    def test_specialized_engine_matches_immutable_reference_request_by_request(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first": {"a": 0, "s": 3},
                "a-second": {"a": 3, "t": 0},
                "b-first": {"b": 0, "s": 2},
                "b-second": {"b": 2, "t": 0},
            },
        )
        requests = (
            PaymentRequest("s", "t", 1),
            PaymentRequest("s", "t", 1),
            PaymentRequest("t", "s", 1),
            PaymentRequest("outside", "t", 1),
            PaymentRequest("s", "t", 3),
        )
        seed = 481

        result = run_prior_paper_replay(
            _topology_for(initial),
            initial,
            requests,
            Fraction(1, 1),
            seed,
        )
        reference_outcomes, reference_state = _reference_replay(
            initial,
            requests,
            seed,
        )

        self.assertEqual(
            tuple((outcome.status, outcome.hop_count) for outcome in result.outcomes),
            reference_outcomes,
        )
        self.assertEqual(
            result.final_balance_fingerprint,
            state_balance_fingerprint(reference_state),
        )
        validate_prior_paper_replay(result, _topology_for(initial), initial, requests)

    def test_full_validator_rejects_forged_outcomes_and_wrong_inputs(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("s", "t"),
            hyperedges={"edge": {"s": 2, "t": 2}},
        )
        topology = _topology_for(initial)
        requests = (PaymentRequest("s", "t", 1),)
        result = run_prior_paper_replay(
            topology,
            initial,
            requests,
            Fraction(1, 1),
            7,
        )
        forged = replace(
            result,
            outcomes=(PriorPaperReplayOutcome(1, "accepted", 999),),
            final_balance_fingerprint="0" * 64,
        )

        with self.assertRaisesRegex(PriorPaperError, "complete input-bound replay"):
            validate_prior_paper_replay(forged, topology, initial, requests)
        with self.assertRaisesRegex(PriorPaperError, "manifest does not bind"):
            validate_prior_paper_replay(
                result,
                topology,
                initial,
                (PaymentRequest("t", "s", 1),),
            )

    def test_fingerprints_encode_structure_boundaries(self) -> None:
        nodes = ("0", "a", "b", "z")
        topology_1 = HypergraphTopology.from_edges(
            nodes,
            {"/": ("a", "b", "z"), "0": ("a", "b")},
        )
        state_1 = HypergraphState.from_balances(
            nodes,
            {"/": {"a": 1, "b": 1, "z": 0}, "0": {"a": 1, "b": 1}},
        )
        topology_2 = HypergraphTopology.from_edges(
            nodes,
            {"/": ("a", "b"), "z": ("0", "a", "b")},
        )
        state_2 = HypergraphState.from_balances(
            nodes,
            {"/": {"a": 1, "b": 1}, "z": {"0": 0, "a": 1, "b": 1}},
        )
        requests = (PaymentRequest("a", "b", 1),)

        result_1 = run_prior_paper_replay(
            topology_1,
            state_1,
            requests,
            Fraction(1, 1),
            7,
        )
        result_2 = run_prior_paper_replay(
            topology_2,
            state_2,
            requests,
            Fraction(1, 1),
            7,
        )

        self.assertNotEqual(result_1.manifest, result_2.manifest)
        self.assertNotEqual(
            result_1.final_balance_fingerprint,
            result_2.final_balance_fingerprint,
        )
        with self.assertRaisesRegex(PriorPaperError, "manifest does not bind"):
            validate_prior_paper_replay(
                result_1,
                topology_2,
                state_2,
                requests,
            )

    def test_parallel_hyperedges_and_high_arity_routes_match_reference(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("a", "s", "t"),
            hyperedges={
                "edge-a": {"a": 0, "s": 4, "t": 0},
                "edge-b": {"a": 1, "s": 3, "t": 0},
            },
        )
        requests = tuple(PaymentRequest("s", "t", 1) for _ in range(5))

        result = run_prior_paper_replay(
            _topology_for(initial),
            initial,
            requests,
            Fraction(1, 1),
            9,
        )
        reference_outcomes, reference_state = _reference_replay(initial, requests, 9)

        self.assertEqual(
            tuple((outcome.status, outcome.hop_count) for outcome in result.outcomes),
            reference_outcomes,
        )
        self.assertEqual(
            result.final_balance_fingerprint,
            state_balance_fingerprint(reference_state),
        )

    def test_summary_keeps_endpoint_and_liquidity_failures_distinct(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("s", "t"),
            hyperedges={"edge": {"s": 1, "t": 1}},
        )
        result = run_prior_paper_replay(
            _topology_for(initial),
            initial,
            (
                PaymentRequest("s", "t", 1),
                PaymentRequest("s", "t", 1),
                PaymentRequest("outside", "t", 1),
            ),
            Fraction(1, 1),
            1,
        )

        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.no_path_count, 1)
        self.assertEqual(result.unavailable_endpoint_count, 1)
        self.assertEqual(result.success_rate, Fraction(1, 3))
        self.assertEqual(result.average_successful_path_length, Fraction(1, 1))

    def test_fractional_multiplier_must_yield_integer_request_amount(self) -> None:
        initial = HypergraphState.from_balances(
            nodes=("s", "t"),
            hyperedges={"edge": {"s": 3, "t": 3}},
        )

        with self.assertRaisesRegex(PriorPaperError, "integer replay amount"):
            run_prior_paper_replay(
                _topology_for(initial),
                initial,
                (PaymentRequest("s", "t", 1),),
                Fraction(1, 2),
                1,
            )


if __name__ == "__main__":
    unittest.main()
