"""Unit contract for common fixed-node-capital optimization."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import unittest
from unittest.mock import patch

from secondaryexploration.experiments import route_choice_rng
from secondaryexploration.model import HypergraphState
from secondaryexploration.optimization import (
    CapacityOptimizationManifest,
    CapacityOptimizationPlan,
    CapacityTrainingScenario,
    DirectedDemandMatrix,
    OptimizationError,
    initialize_load_risk_state,
    optimize_common_capacity,
    score_capacity_state,
    validate_capacity_state,
    validate_common_capacity_result,
)
from secondaryexploration.simulation import run_core_trace_with_request_rngs
from secondaryexploration.topology import HypergraphTopology, node_capital_totals
from secondaryexploration.traffic import (
    AmountDistribution,
    DemandKernel,
    generate_request_trace,
    uniform_kernel,
)
from secondaryexploration.optimization.capacity import _unbiased_choice_index


class CommonCapacityUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.nodes = ("a", "b", "c", "d")
        self.topology = HypergraphTopology.from_edges(
            self.nodes,
            {
                "e-ab": ("a", "b"),
                "e-ac": ("a", "c"),
                "e-cd": ("c", "d"),
            },
        )
        amounts = AmountDistribution.from_weights(((1, 1), (2, 1)))
        self.scenarios = tuple(
            sorted(
                (
                    CapacityTrainingScenario(
                        "hot-0",
                        "hot",
                        generate_request_trace(
                            _ab_weighted_kernel(self.nodes),
                            amounts,
                            12,
                            root_seed=41,
                        ),
                        401,
                    ),
                    CapacityTrainingScenario(
                        "uniform-0",
                        "uniform",
                        generate_request_trace(
                            uniform_kernel(self.nodes),
                            amounts,
                            12,
                            root_seed=42,
                        ),
                        402,
                    ),
                ),
                key=lambda item: (item.regime_id, item.scenario_id),
            )
        )
        self.demand = _aggregate_demand(self.nodes, self.scenarios)
        self.manifest = CapacityOptimizationManifest.create(
            self.demand,
            12,
            Fraction(1),
            Fraction(1),
            Fraction(1, 2),
            self.scenarios,
        )

    def test_manifest_binds_exact_aggregate_training_demand(self) -> None:
        self.assertEqual(self.manifest.demand_fingerprint, self.demand.fingerprint)
        self.assertEqual(self.manifest.nodes, self.nodes)
        self.assertEqual(self.manifest.scenarios, self.scenarios)

        wrong_demand = DirectedDemandMatrix.from_requests(
            self.nodes,
            self.scenarios[0].trace.requests,
        )
        with self.assertRaisesRegex(OptimizationError, "aggregate registered"):
            CapacityOptimizationManifest.create(
                wrong_demand,
                12,
                Fraction(1),
                Fraction(1),
                Fraction(1, 2),
                self.scenarios,
            )

        with self.assertRaisesRegex(OptimizationError, "canonical"):
            replace(self.manifest, scenarios=tuple(reversed(self.scenarios)))

    def test_manifest_rejects_mixed_horizons_and_non_fraction_controls(self) -> None:
        short_trace = generate_request_trace(
            uniform_kernel(self.nodes),
            AmountDistribution.from_weights(((1, 1),)),
            4,
            root_seed=99,
        )
        mixed = (
            self.scenarios[0],
            CapacityTrainingScenario("uniform-short", "uniform", short_trace, 8),
        )
        with self.assertRaisesRegex(OptimizationError, "one horizon"):
            replace(self.manifest, scenarios=mixed)
        with self.assertRaisesRegex(OptimizationError, "Fraction"):
            replace(self.manifest, load_weight=1)
        with self.assertRaisesRegex(OptimizationError, r"\(0, 1\]"):
            replace(self.manifest, lower_quantile=Fraction(0))

    def test_load_risk_initializer_is_exact_positive_and_demand_responsive(self) -> None:
        state = initialize_load_risk_state(
            self.topology,
            self.demand,
            self.manifest,
        )
        validate_capacity_state(self.topology, state, self.manifest)
        self.assertEqual(
            node_capital_totals(state),
            tuple((node_id, 12) for node_id in self.nodes),
        )
        self.assertTrue(
            all(amount >= 1 for edge in state.hyperedges for _, amount in edge.balances)
        )

        ab_load = self.demand.amount("a", "b") + self.demand.amount("b", "a")
        ac_load = self.demand.amount("a", "c") + self.demand.amount("c", "a")
        self.assertGreater(ab_load, ac_load)
        self.assertGreater(
            state.edge("e-ab").balance_of("a"),
            state.edge("e-ac").balance_of("a"),
        )
        self.assertEqual(
            state,
            initialize_load_risk_state(self.topology, self.demand, self.manifest),
        )

    def test_score_matches_independent_scenario_reexecution_and_quantiles(self) -> None:
        state = initialize_load_risk_state(
            self.topology,
            self.demand,
            self.manifest,
        )
        score = score_capacity_state(
            self.topology,
            state,
            self.demand,
            self.manifest,
        )
        independent = []
        for scenario in self.scenarios:
            simulation = run_core_trace_with_request_rngs(
                state,
                scenario.trace.requests,
                (
                    route_choice_rng(scenario.routing_root_seed, request_index)
                    for request_index in range(1, scenario.trace.length + 1)
                ),
            )
            independent.append(
                (
                    scenario.scenario_id,
                    simulation.tau_nopath.request_index,
                    simulation.tau_nopath.observed,
                    sum(item.accepted for item in simulation.outcomes),
                )
            )
        self.assertEqual(
            tuple(
                (
                    item.scenario_id,
                    item.tau_nopath,
                    item.observed,
                    item.accepted_requests,
                )
                for item in score.outcomes
            ),
            tuple(independent),
        )
        self.assertEqual(
            score.robust_lower_quantile,
            min(value for _, value in score.regime_quantiles),
        )

    def test_optimizer_exhausts_common_budget_and_full_replay(self) -> None:
        plan = CapacityOptimizationPlan(10, 7_001, 2)
        result = optimize_common_capacity(
            self.topology,
            self.demand,
            self.manifest,
            plan,
        )
        self.assertEqual(result.evaluation_count, 10)
        self.assertEqual(len(result.proposals), 8)
        self.assertEqual(
            tuple(item.evaluation_index for item in result.proposals),
            tuple(range(3, 11)),
        )
        validate_capacity_state(self.topology, result.state, self.manifest)
        validate_common_capacity_result(
            result,
            self.topology,
            self.demand,
            self.manifest,
            plan,
        )
        self.assertEqual(
            result,
            optimize_common_capacity(
                self.topology,
                self.demand,
                self.manifest,
                plan,
            ),
        )

    def test_larger_budget_preserves_complete_proposal_prefix(self) -> None:
        short = optimize_common_capacity(
            self.topology,
            self.demand,
            self.manifest,
            CapacityOptimizationPlan(7, 8_001, 2),
        )
        long = optimize_common_capacity(
            self.topology,
            self.demand,
            self.manifest,
            CapacityOptimizationPlan(11, 8_001, 2),
        )
        self.assertEqual(long.proposals[: len(short.proposals)], short.proposals)

    def test_external_expected_plan_rejects_valid_alternate_run(self) -> None:
        expected_plan = CapacityOptimizationPlan(7, 9_001, 2)
        alternate_plan = CapacityOptimizationPlan(7, 9_002, 2)
        alternate = optimize_common_capacity(
            self.topology,
            self.demand,
            self.manifest,
            alternate_plan,
        )
        with self.assertRaisesRegex(OptimizationError, "expected capacity plan"):
            validate_common_capacity_result(
                alternate,
                self.topology,
                self.demand,
                self.manifest,
                expected_plan,
            )

    def test_result_and_score_tampering_fail_full_replay(self) -> None:
        plan = CapacityOptimizationPlan(7, 10_001, 2)
        result = optimize_common_capacity(
            self.topology,
            self.demand,
            self.manifest,
            plan,
        )
        altered_score = replace(
            result.score,
            state_fingerprint="0" * 64,
        )
        with self.assertRaises(OptimizationError):
            replace(result, score=altered_score)
        altered = replace(
            result,
            topology_fingerprint="0" * 64,
        )
        with self.assertRaisesRegex(OptimizationError, "complete optimization replay"):
            validate_common_capacity_result(
                altered,
                self.topology,
                self.demand,
                self.manifest,
                plan,
            )

    def test_state_validator_rejects_zero_and_wrong_node_budget(self) -> None:
        valid = initialize_load_risk_state(
            self.topology,
            self.demand,
            self.manifest,
        )
        balances = {
            edge.hyperedge_id: dict(edge.balances) for edge in valid.hyperedges
        }
        moved = balances["e-ab"]["a"]
        balances["e-ab"]["a"] = 0
        balances["e-ac"]["a"] += moved
        zero_state = HypergraphState.from_balances(self.nodes, balances)
        with self.assertRaisesRegex(OptimizationError, "positive"):
            validate_capacity_state(self.topology, zero_state, self.manifest)

        balances = {
            edge.hyperedge_id: dict(edge.balances) for edge in valid.hyperedges
        }
        balances["e-ab"]["a"] += 1
        wrong_budget = HypergraphState.from_balances(self.nodes, balances)
        with self.assertRaisesRegex(OptimizationError, "per-node budget"):
            validate_capacity_state(self.topology, wrong_budget, self.manifest)

    def test_insufficient_capital_for_positive_simplex_is_rejected(self) -> None:
        too_small = replace(self.manifest, per_node_capital=1)
        with self.assertRaisesRegex(OptimizationError, "one positive unit"):
            initialize_load_risk_state(self.topology, self.demand, too_small)

    def test_non_power_of_two_choice_rejects_tail_before_exact_modulo(self) -> None:
        with patch(
            "secondaryexploration.optimization.capacity.derive_seed",
            side_effect=(2**64 - 1, 5),
        ) as mocked:
            selected = _unbiased_choice_index(1, "test.choice", 1, 3)
        self.assertEqual(selected, 2)
        self.assertEqual(mocked.call_count, 2)


def _aggregate_demand(
    nodes: tuple[str, ...],
    scenarios: tuple[CapacityTrainingScenario, ...],
) -> DirectedDemandMatrix:
    return DirectedDemandMatrix.from_requests(
        nodes,
        tuple(
            request
            for scenario in scenarios
            for request in scenario.trace.requests
        ),
    )


def _ab_weighted_kernel(nodes: tuple[str, ...]) -> DemandKernel:
    return DemandKernel.from_weights(
        nodes,
        tuple(
            (
                source,
                destination,
                100 if {source, destination} == {"a", "b"} else 1,
            )
            for source in nodes
            for destination in nodes
            if source != destination
        ),
    )


if __name__ == "__main__":
    unittest.main()
