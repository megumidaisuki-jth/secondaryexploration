"""Exact static and dynamic component-wise cost witnesses."""

from __future__ import annotations

import random
import unittest

from secondaryexploration.experiments import TopologyVariant
from secondaryexploration.metrics import MetricError, RunCostMetrics
from secondaryexploration.model import HypergraphState, PaymentRequest
from secondaryexploration.simulation import run_core_trace
from secondaryexploration.topology import HypergraphTopology


def _two_hop_variant() -> TopologyVariant:
    topology = HypergraphTopology.from_edges(
        ("a", "s", "t"),
        {
            "first": ("a", "s"),
            "second": ("a", "t"),
        },
    )
    state = HypergraphState.from_balances(
        topology.nodes,
        {
            "first": {"a": 0, "s": 2},
            "second": {"a": 2, "t": 0},
        },
    )
    return TopologyVariant("two-hop", "test", topology, state)


class RunCostMetricTests(unittest.TestCase):
    def test_hand_calculated_two_hop_costs(self) -> None:
        variant = _two_hop_variant()
        simulation = run_core_trace(
            variant.initial_state,
            (PaymentRequest("s", "t", 1),),
            random.Random(0),
        )

        costs = RunCostMetrics(variant, simulation)

        self.assertEqual(costs.locked_capital, 4)
        self.assertEqual(costs.hyperedge_count, 2)
        self.assertEqual(costs.incidence_count, 4)
        self.assertEqual(costs.maximum_arity, 2)
        self.assertEqual(costs.pairwise_member_exposure, 2)
        self.assertEqual(costs.accepted_request_count, 1)
        self.assertEqual(costs.accepted_value, 1)
        self.assertEqual(costs.traversed_hyperedge_count, 2)
        self.assertEqual(costs.signaled_participant_slots, 4)
        self.assertEqual(costs.unique_signaled_participants, 3)
        self.assertEqual(costs.quadratic_coordination_exposure, 8)
        self.assertEqual(costs.route_arity_histogram, ((2, 2),))

    def test_rejections_add_no_dynamic_route_cost(self) -> None:
        variant = _two_hop_variant()
        simulation = run_core_trace(
            variant.initial_state,
            (PaymentRequest("s", "t", 3),),
            random.Random(0),
        )

        costs = RunCostMetrics(variant, simulation)

        self.assertEqual(costs.accepted_request_count, 0)
        self.assertEqual(costs.accepted_value, 0)
        self.assertEqual(costs.traversed_hyperedge_count, 0)
        self.assertEqual(costs.route_arity_histogram, ())

    def test_mismatched_variant_and_simulation_fail_closed(self) -> None:
        variant = _two_hop_variant()
        altered_state = HypergraphState.from_balances(
            variant.topology.nodes,
            {
                "first": {"a": 1, "s": 1},
                "second": {"a": 1, "t": 1},
            },
        )
        simulation = run_core_trace(altered_state, (), random.Random(0))

        with self.assertRaisesRegex(MetricError, "initial state"):
            RunCostMetrics(variant, simulation)
        with self.assertRaises(MetricError):
            RunCostMetrics("variant", simulation)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
