"""Independent tiny-simplex oracles for common capacity optimization."""

from __future__ import annotations

from fractions import Fraction
from itertools import product
import random
import unittest

from secondaryexploration.experiments import route_choice_rng
from secondaryexploration.model import HypergraphState
from secondaryexploration.optimization import (
    CapacityOptimizationManifest,
    CapacityOptimizationPlan,
    CapacityTrainingScenario,
    DirectedDemandMatrix,
    optimize_common_capacity,
)
from secondaryexploration.simulation import run_core_trace_with_request_rngs
from secondaryexploration.topology import HypergraphTopology
from secondaryexploration.traffic import (
    AmountDistribution,
    DemandKernel,
    generate_request_trace,
    uniform_kernel,
)


class CommonCapacityOracleTests(unittest.TestCase):
    def test_search_reaches_exhaustive_three_state_simplex_optimum(self) -> None:
        nodes = ("a", "b", "c")
        topology = HypergraphTopology.from_edges(
            nodes,
            {"left": ("a", "b"), "right": ("b", "c")},
        )
        scenarios = tuple(
            CapacityTrainingScenario(
                f"uniform-{index}",
                "uniform",
                generate_request_trace(
                    uniform_kernel(nodes),
                    AmountDistribution.from_weights(((1, 1),)),
                    14,
                    root_seed=1_100 + index,
                ),
                1_200 + index,
            )
            for index in range(3)
        )
        demand = _aggregate_demand(nodes, scenarios)
        manifest = CapacityOptimizationManifest.create(
            demand,
            4,
            Fraction(1),
            Fraction(1),
            Fraction(1, 2),
            scenarios,
        )
        states = tuple(_enumerate_positive_states(topology, 4))
        independent_scores = tuple(
            _independent_score(state, scenarios, Fraction(1, 2))
            for state in states
        )
        independent_optimum = max(score[0] for score in independent_scores)

        result = optimize_common_capacity(
            topology,
            demand,
            manifest,
            CapacityOptimizationPlan(80, 1_300, 2),
        )
        result_score = _independent_score(
            result.state,
            scenarios,
            Fraction(1, 2),
        )

        self.assertEqual(result_score[0], independent_optimum)
        _assert_production_matches_independent(self, result.score, result_score)

    def test_random_small_simplex_grid_uses_independent_simulation_oracle(self) -> None:
        rng = random.Random(20_260_803)
        for case_index in range(10):
            node_count = rng.randrange(3, 5)
            nodes = tuple(f"n{index}" for index in range(node_count))
            edges = {(nodes[index - 1], nodes[index]) for index in range(1, node_count)}
            possible = tuple(
                (nodes[left], nodes[right])
                for left in range(node_count)
                for right in range(left + 1, node_count)
                if (nodes[left], nodes[right]) not in edges
            )
            for edge in possible:
                if rng.randrange(2) == 0:
                    edges.add(edge)
            topology = HypergraphTopology.from_edges(
                nodes,
                {
                    f"edge-{index:02d}": edge
                    for index, edge in enumerate(sorted(edges))
                },
            )
            maximum_degree = max(degree for _, degree in topology.node_incidence_degrees)
            per_node_capital = maximum_degree + 1
            scenarios = _random_scenarios(nodes, case_index)
            demand = _aggregate_demand(nodes, scenarios)
            quantile = Fraction(1, 2)
            manifest = CapacityOptimizationManifest.create(
                demand,
                per_node_capital,
                Fraction(1),
                Fraction(1, 2),
                quantile,
                scenarios,
            )
            exhaustive_scores = tuple(
                _independent_score(state, scenarios, quantile)[0]
                for state in _enumerate_positive_states(
                    topology,
                    per_node_capital,
                )
            )
            independent_upper_bound = max(exhaustive_scores)
            result = optimize_common_capacity(
                topology,
                demand,
                manifest,
                CapacityOptimizationPlan(18, 3_000 + case_index, 2),
            )
            independent_result = _independent_score(
                result.state,
                scenarios,
                quantile,
            )

            with self.subTest(case_index=case_index, edges=len(edges)):
                _assert_production_matches_independent(
                    self,
                    result.score,
                    independent_result,
                )
                self.assertLessEqual(independent_result[0], independent_upper_bound)


def _random_scenarios(
    nodes: tuple[str, ...],
    case_index: int,
) -> tuple[CapacityTrainingScenario, ...]:
    amounts = AmountDistribution.from_weights(((1, 2), (2, 1)))
    weighted = DemandKernel.from_weights(
        nodes,
        tuple(
            (
                source,
                destination,
                5 if source == nodes[0] else 1,
            )
            for source in nodes
            for destination in nodes
            if source != destination
        ),
    )
    scenarios = tuple(
        CapacityTrainingScenario(
            f"{regime}-{replicate}",
            regime,
            generate_request_trace(
                uniform_kernel(nodes) if regime == "uniform" else weighted,
                amounts,
                6,
                root_seed=10_000 + case_index * 100 + offset,
            ),
            20_000 + case_index * 100 + offset,
        )
        for regime, regime_offset in (("drift", 0), ("uniform", 10))
        for replicate, offset in enumerate(
            (regime_offset, regime_offset + 1),
        )
    )
    return tuple(sorted(scenarios, key=lambda item: (item.regime_id, item.scenario_id)))


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


def _enumerate_positive_states(
    topology: HypergraphTopology,
    per_node_capital: int,
):
    incident = {
        node_id: tuple(
            edge.hyperedge_id
            for edge in topology.hyperedges
            if node_id in edge.members
        )
        for node_id in topology.nodes
    }
    choices = tuple(
        tuple(_positive_compositions(per_node_capital, len(incident[node_id])))
        for node_id in topology.nodes
    )
    for node_allocations in product(*choices):
        balances = {
            edge.hyperedge_id: {} for edge in topology.hyperedges
        }
        for node_id, allocation in zip(topology.nodes, node_allocations):
            for edge_id, amount in zip(incident[node_id], allocation):
                balances[edge_id][node_id] = amount
        yield HypergraphState.from_balances(topology.nodes, balances)


def _positive_compositions(total: int, part_count: int):
    if part_count == 1:
        yield (total,)
        return
    for first in range(1, total - part_count + 2):
        for suffix in _positive_compositions(total - first, part_count - 1):
            yield (first,) + suffix


def _independent_score(
    state: HypergraphState,
    scenarios: tuple[CapacityTrainingScenario, ...],
    quantile: Fraction,
) -> tuple[
    tuple[int, int, int, int],
    tuple[tuple[str, str, int, bool, int], ...],
    tuple[tuple[str, int], ...],
]:
    outcomes = []
    for scenario in scenarios:
        simulation = run_core_trace_with_request_rngs(
            state,
            scenario.trace.requests,
            (
                route_choice_rng(scenario.routing_root_seed, request_index)
                for request_index in range(1, scenario.trace.length + 1)
            ),
        )
        outcomes.append(
            (
                scenario.scenario_id,
                scenario.regime_id,
                simulation.tau_nopath.request_index,
                simulation.tau_nopath.observed,
                sum(item.accepted for item in simulation.outcomes),
            )
        )
    regime_quantiles = tuple(
        (
            regime_id,
            _inverse_empirical_cdf(
                tuple(
                    outcome[2]
                    for outcome in outcomes
                    if outcome[1] == regime_id
                ),
                quantile,
            ),
        )
        for regime_id in sorted({outcome[1] for outcome in outcomes})
    )
    scientific_key = (
        min(value for _, value in regime_quantiles),
        sum(value for _, value in regime_quantiles),
        sum(outcome[2] for outcome in outcomes),
        sum(outcome[4] for outcome in outcomes),
    )
    return scientific_key, tuple(outcomes), regime_quantiles


def _inverse_empirical_cdf(values: tuple[int, ...], quantile: Fraction) -> int:
    ordered = sorted(values)
    rank = (
        quantile.numerator * len(ordered) + quantile.denominator - 1
    ) // quantile.denominator
    return ordered[max(1, rank) - 1]


def _assert_production_matches_independent(
    case: unittest.TestCase,
    production,
    independent,
) -> None:
    scientific_key, outcomes, regime_quantiles = independent
    case.assertEqual(
        (
            production.robust_lower_quantile,
            production.regime_quantile_sum,
            production.total_restricted_tau,
            production.total_accepted_requests,
        ),
        scientific_key,
    )
    case.assertEqual(production.regime_quantiles, regime_quantiles)
    case.assertEqual(
        tuple(
            (
                item.scenario_id,
                item.regime_id,
                item.tau_nopath,
                item.observed,
                item.accepted_requests,
            )
            for item in production.outcomes
        ),
        outcomes,
    )


if __name__ == "__main__":
    unittest.main()
