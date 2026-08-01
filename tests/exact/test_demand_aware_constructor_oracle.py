"""Exhaustive small-graph oracle for deterministic demand-aware training."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
import unittest

from secondaryexploration.model import PaymentRequest
from secondaryexploration.optimization import (
    DemandAwareObjectiveWeights,
    DemandAwareSearchPlan,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    OptimizationError,
    score_demand_aware_topology,
    train_demand_aware_topology,
    validate_demand_aware_topology,
)
from secondaryexploration.optimization.constructor import (
    _proposal_membership_stream,
)
from secondaryexploration.topology import HypergraphTopology, ParentGraph, binary_topology


class DemandAwareConstructorOracleTests(unittest.TestCase):
    def test_search_reaches_global_optimum_on_registered_path_anchors(self) -> None:
        for node_count in (4, 5):
            with self.subTest(node_count=node_count):
                nodes = tuple(chr(ord("a") + index) for index in range(node_count))
                parent = ParentGraph.from_edges(nodes, tuple(zip(nodes, nodes[1:])))
                requests = tuple(
                    request
                    for left_index in range(node_count)
                    for right_index in range(left_index + 2, node_count)
                    for request in (
                        PaymentRequest(nodes[left_index], nodes[right_index], 10),
                        PaymentRequest(nodes[right_index], nodes[left_index], 10),
                    )
                )
                demand = DirectedDemandMatrix.from_requests(nodes, requests)
                seed = binary_topology(parent)
                manifest = DemandAwareTrainingManifest.create(
                    parent,
                    demand,
                    seed.resources.incidence_count,
                    3,
                    DemandAwareObjectiveWeights(
                        Fraction(1, 1),
                        Fraction(0, 1),
                        Fraction(0, 1),
                        Fraction(0, 1),
                    ),
                )

                trained = train_demand_aware_topology(
                    parent,
                    demand,
                    seed,
                    manifest,
                    DemandAwareSearchPlan(100_000, 5, 3),
                )
                oracle_value = _exhaustive_best_value(parent, demand, manifest)

                self.assertEqual(trained.score.objective_value, oracle_value)

    def test_production_move_stream_equals_independent_up_to_three_edge_enumerator(self) -> None:
        nodes = ("a", "b", "c", "d")
        parent = ParentGraph.from_edges(
            nodes,
            (("a", "b"), ("b", "c"), ("c", "d")),
        )
        demand = DirectedDemandMatrix.from_requests(nodes, ())
        seed = binary_topology(parent)
        manifest = DemandAwareTrainingManifest.create(
            parent,
            demand,
            seed.resources.incidence_count,
            3,
            DemandAwareObjectiveWeights(
                Fraction(1),
                Fraction(0),
                Fraction(0),
                Fraction(0),
            ),
        )
        from secondaryexploration.optimization import generate_connected_candidate_pool

        pool = generate_connected_candidate_pool(parent, demand, manifest)
        current = tuple(edge.members for edge in seed.hyperedges)
        production = tuple(_proposal_membership_stream(current, pool, 3))
        independent = _independent_proposals(
            current,
            tuple(candidate.members for candidate in pool.candidates),
            3,
        )

        self.assertEqual(set(production), independent)
        self.assertEqual(len(production), len(set(production)))
        self.assertTrue(
            all(
                sum(map(len, proposal)) == seed.resources.incidence_count
                for proposal in production
            )
        )


def _exhaustive_best_value(
    parent: ParentGraph,
    demand: DirectedDemandMatrix,
    manifest: DemandAwareTrainingManifest,
) -> Fraction:
    connected_memberships = tuple(
        members
        for arity in range(2, manifest.maximum_arity + 1)
        for members in combinations(parent.nodes, arity)
        if _induced_connected(parent, members)
    )
    best: Fraction | None = None
    for selected_count in range(1, len(connected_memberships) + 1):
        for selected in combinations(connected_memberships, selected_count):
            if sum(map(len, selected)) != manifest.incidence_budget:
                continue
            topology = HypergraphTopology.from_edges(
                parent.nodes,
                {
                    f"oracle-{index:04d}": members
                    for index, members in enumerate(selected)
                },
            )
            try:
                validate_demand_aware_topology(parent, topology, manifest)
            except OptimizationError:
                continue
            value = score_demand_aware_topology(
                parent,
                demand,
                topology,
                manifest,
            ).objective_value
            if best is None or value > best:
                best = value
    if best is None:
        raise AssertionError("oracle found no feasible topology")
    return best


def _induced_connected(parent: ParentGraph, members: tuple[str, ...]) -> bool:
    allowed = set(members)
    reached = {members[0]}
    frontier = [members[0]]
    while frontier:
        current = frontier.pop()
        for neighbor in parent.neighbors(current):
            if neighbor in allowed and neighbor not in reached:
                reached.add(neighbor)
                frontier.append(neighbor)
    return len(reached) == len(members)


def _independent_proposals(
    current: tuple[tuple[str, ...], ...],
    candidates: tuple[tuple[str, ...], ...],
    width: int,
) -> set[tuple[tuple[str, ...], ...]]:
    outputs: set[tuple[tuple[str, ...], ...]] = set()
    canonical_current = tuple(sorted(current))
    for removed_count in range(1, width + 1):
        for removed_indices in combinations(range(len(current)), removed_count):
            retained = tuple(
                members
                for index, members in enumerate(current)
                if index not in removed_indices
            )
            removed_incidence = sum(len(current[index]) for index in removed_indices)
            for added_count in range(1, width + 1):
                for added in combinations(candidates, added_count):
                    if sum(map(len, added)) != removed_incidence:
                        continue
                    proposal = tuple(sorted(retained + added))
                    if proposal == canonical_current:
                        continue
                    outputs.add(proposal)
    return outputs


if __name__ == "__main__":
    unittest.main()
