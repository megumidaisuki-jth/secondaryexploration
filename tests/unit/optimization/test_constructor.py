"""Deterministic candidate-pool and fixed-resource topology-search tests."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import unittest

from secondaryexploration.model import PaymentRequest
from secondaryexploration.optimization import (
    ConnectedCandidate,
    DemandAwareObjectiveWeights,
    DemandAwareSearchPlan,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    OptimizationError,
    generate_connected_candidate_pool,
    train_demand_aware_topology,
    validate_connected_candidate_pool,
    validate_demand_aware_topology,
    validate_demand_aware_topology_result,
)
from secondaryexploration.topology import HypergraphTopology, ParentGraph, binary_topology


def _capture_only_weights() -> DemandAwareObjectiveWeights:
    return DemandAwareObjectiveWeights(
        Fraction(1, 1),
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(0, 1),
    )


class ConnectedCandidatePoolTests(unittest.TestCase):
    def test_small_parent_pool_is_every_connected_subset_through_maximum_arity(self) -> None:
        parent = ParentGraph.from_edges(
            ("a", "b", "c", "d"),
            (("a", "b"), ("b", "c"), ("c", "d")),
        )
        demand = DirectedDemandMatrix.from_requests(parent.nodes, ())
        manifest = DemandAwareTrainingManifest.create(
            parent,
            demand,
            incidence_budget=6,
            maximum_arity=3,
            weights=_capture_only_weights(),
        )

        pool = generate_connected_candidate_pool(parent, demand, manifest)

        self.assertEqual(
            {candidate.members for candidate in pool.candidates},
            {
                ("a", "b"),
                ("b", "c"),
                ("c", "d"),
                ("a", "b", "c"),
                ("b", "c", "d"),
            },
        )
        self.assertTrue(all(candidate.priority == 0 for candidate in pool.candidates))
        validate_connected_candidate_pool(pool, parent, demand, manifest)

    def test_pool_regeneration_rejects_priority_membership_and_manifest_tampering(self) -> None:
        parent = ParentGraph.from_edges(
            ("a", "b", "c"),
            (("a", "b"), ("b", "c")),
        )
        demand = DirectedDemandMatrix.from_requests(
            parent.nodes,
            (PaymentRequest("a", "c", 2), PaymentRequest("c", "a", 2)),
        )
        manifest = DemandAwareTrainingManifest.create(
            parent,
            demand,
            4,
            3,
            _capture_only_weights(),
        )
        pool = generate_connected_candidate_pool(parent, demand, manifest)
        priorities = {candidate.members: candidate.priority for candidate in pool.candidates}
        self.assertEqual(priorities[("a", "b", "c")], Fraction(1, 1))
        self.assertEqual(priorities[("a", "b")], Fraction(0, 1))
        changed_candidate = replace(
            pool.candidates[0],
            priority=pool.candidates[0].priority + 1,
        )
        tampered = replace(pool, candidates=(changed_candidate,) + pool.candidates[1:])
        with self.assertRaisesRegex(OptimizationError, "complete regeneration"):
            validate_connected_candidate_pool(tampered, parent, demand, manifest)
        with self.assertRaisesRegex(OptimizationError, "complete regeneration"):
            validate_connected_candidate_pool(
                pool,
                parent,
                demand,
                replace(manifest, incidence_budget=5),
            )

    def test_large_parent_uses_bounded_expansions_and_keeps_every_parent_edge(self) -> None:
        nodes = tuple(f"n{index:02d}" for index in range(11))
        parent = ParentGraph.from_edges(nodes, tuple(zip(nodes, nodes[1:])))
        requests = tuple(
            PaymentRequest(nodes[0], node, index + 1)
            for index, node in enumerate(nodes[1:])
        )
        demand = DirectedDemandMatrix.from_requests(nodes, requests)
        manifest = DemandAwareTrainingManifest.create(
            parent,
            demand,
            20,
            4,
            _capture_only_weights(),
        )

        first = generate_connected_candidate_pool(parent, demand, manifest)
        second = generate_connected_candidate_pool(parent, demand, manifest)

        memberships = {candidate.members for candidate in first.candidates}
        self.assertTrue(all(edge.endpoints in memberships for edge in parent.edges))
        self.assertTrue(all(2 <= len(members) <= 4 for members in memberships))
        self.assertEqual(first, second)
        self.assertEqual(first.fingerprint, second.fingerprint)


class DemandAwareTopologySearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = ParentGraph.from_edges(
            ("a", "b", "c", "d"),
            (("a", "b"), ("b", "c"), ("c", "d")),
        )
        self.demand = DirectedDemandMatrix.from_requests(
            self.parent.nodes,
            (
                PaymentRequest("a", "c", 10),
                PaymentRequest("c", "a", 10),
                PaymentRequest("b", "d", 10),
                PaymentRequest("d", "b", 10),
            ),
        )
        self.manifest = DemandAwareTrainingManifest.create(
            self.parent,
            self.demand,
            incidence_budget=6,
            maximum_arity=3,
            weights=_capture_only_weights(),
        )
        self.seed = binary_topology(self.parent)

    def test_three_binary_edges_can_train_into_two_triads_at_exact_budget(self) -> None:
        search_plan = DemandAwareSearchPlan(
            proposal_budget=1_000,
            maximum_rounds=3,
            maximum_move_edges=3,
        )
        result = train_demand_aware_topology(
            self.parent,
            self.demand,
            self.seed,
            self.manifest,
            search_plan,
        )

        self.assertEqual(
            tuple(edge.members for edge in result.topology.hyperedges),
            (("a", "b", "c"), ("b", "c", "d")),
        )
        self.assertEqual(result.topology.resources.incidence_count, 6)
        self.assertEqual(result.topology.resources.maximum_arity, 3)
        self.assertEqual(result.score.normalized_capture, Fraction(1, 1))
        self.assertGreater(result.score.objective_value, 0)
        self.assertEqual(len(result.steps), 1)
        validate_demand_aware_topology(self.parent, result.topology, self.manifest)
        validate_demand_aware_topology_result(
            result,
            self.parent,
            self.demand,
            self.seed,
            self.manifest,
            search_plan,
        )

    def test_one_for_one_move_changes_membership_without_changing_resources(self) -> None:
        seed = HypergraphTopology.from_edges(
            self.parent.nodes,
            {
                "ab": ("a", "b"),
                "bc": ("b", "c"),
                "cd": ("c", "d"),
                "triad": ("a", "b", "c"),
            },
        )
        demand = DirectedDemandMatrix.from_requests(
            self.parent.nodes,
            (PaymentRequest("b", "d", 10), PaymentRequest("d", "b", 10)),
        )
        manifest = DemandAwareTrainingManifest.create(
            self.parent,
            demand,
            9,
            3,
            _capture_only_weights(),
        )
        result = train_demand_aware_topology(
            self.parent,
            demand,
            seed,
            manifest,
            DemandAwareSearchPlan(1_000, 1, 1),
        )

        self.assertIn(
            ("b", "c", "d"),
            tuple(edge.members for edge in result.topology.hyperedges),
        )
        self.assertEqual(result.score.normalized_capture, 1)

    def test_two_for_one_merge_changes_hyperedge_count_at_fixed_incidence(self) -> None:
        demand = DirectedDemandMatrix.from_requests(
            self.parent.nodes,
            (PaymentRequest("a", "d", 10), PaymentRequest("d", "a", 10)),
        )
        manifest = DemandAwareTrainingManifest.create(
            self.parent,
            demand,
            6,
            4,
            _capture_only_weights(),
        )
        result = train_demand_aware_topology(
            self.parent,
            demand,
            self.seed,
            manifest,
            DemandAwareSearchPlan(5_000, 1, 2),
        )

        self.assertEqual(len(result.topology.hyperedges), 2)
        self.assertIn(
            ("a", "b", "c", "d"),
            tuple(edge.members for edge in result.topology.hyperedges),
        )
        self.assertEqual(result.topology.resources.incidence_count, 6)

    def test_one_for_two_split_reduces_coordination_at_fixed_incidence(self) -> None:
        seed = HypergraphTopology.from_edges(
            self.parent.nodes,
            {"all": ("a", "b", "c", "d"), "middle": ("b", "c")},
        )
        zero_demand = DirectedDemandMatrix.from_requests(self.parent.nodes, ())
        manifest = DemandAwareTrainingManifest.create(
            self.parent,
            zero_demand,
            6,
            4,
            DemandAwareObjectiveWeights(
                Fraction(1),
                Fraction(0),
                Fraction(0),
                Fraction(1),
            ),
        )
        result = train_demand_aware_topology(
            self.parent,
            zero_demand,
            seed,
            manifest,
            DemandAwareSearchPlan(5_000, 1, 2),
        )

        self.assertEqual(len(result.topology.hyperedges), 3)
        self.assertEqual(result.topology.resources.incidence_count, 6)
        self.assertLess(
            result.score.coordination_overlap_burden,
            8,
        )

    def test_two_for_two_move_crosses_infeasible_single_replacement_barrier(self) -> None:
        parent = ParentGraph.from_edges(
            ("a", "b", "c", "d"),
            (("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")),
        )
        seed = HypergraphTopology.from_edges(
            parent.nodes,
            {"first": ("a", "b", "c"), "second": ("a", "c", "d")},
        )
        demand = DirectedDemandMatrix.from_requests(
            parent.nodes,
            (PaymentRequest("b", "d", 10), PaymentRequest("d", "b", 10)),
        )
        manifest = DemandAwareTrainingManifest.create(
            parent,
            demand,
            6,
            3,
            _capture_only_weights(),
        )
        result = train_demand_aware_topology(
            parent,
            demand,
            seed,
            manifest,
            DemandAwareSearchPlan(5_000, 1, 2),
        )

        self.assertEqual(result.score.normalized_capture, 1)
        self.assertEqual(
            set(edge.members for edge in result.topology.hyperedges),
            {("a", "b", "d"), ("b", "c", "d")},
        )

    def test_one_round_proposal_record_is_prefix_stable_when_budget_increases(self) -> None:
        smaller = train_demand_aware_topology(
            self.parent,
            self.demand,
            self.seed,
            self.manifest,
            DemandAwareSearchPlan(7, 1, 3),
        )
        larger = train_demand_aware_topology(
            self.parent,
            self.demand,
            self.seed,
            self.manifest,
            DemandAwareSearchPlan(19, 1, 3),
        )

        self.assertEqual(
            smaller.proposal_fingerprints,
            larger.proposal_fingerprints[: smaller.proposals_considered],
        )

    def test_complete_training_replay_rejects_result_step_plan_and_input_tampering(self) -> None:
        result = train_demand_aware_topology(
            self.parent,
            self.demand,
            self.seed,
            self.manifest,
            DemandAwareSearchPlan(100, 2, 3),
        )
        expected_plan = result.search_plan
        forged = replace(
            result,
            proposal_fingerprints=("0" * 64,) + result.proposal_fingerprints[1:],
        )
        with self.assertRaisesRegex(OptimizationError, "complete training replay"):
            validate_demand_aware_topology_result(
                forged,
                self.parent,
                self.demand,
                self.seed,
                self.manifest,
                expected_plan,
            )
        changed_plan = replace(
            result,
            search_plan=replace(result.search_plan, maximum_move_edges=2),
        )
        with self.assertRaisesRegex(OptimizationError, "expected search plan"):
            validate_demand_aware_topology_result(
                changed_plan,
                self.parent,
                self.demand,
                self.seed,
                self.manifest,
                expected_plan,
            )
        changed_score = replace(
            result,
            score=replace(
                result.score,
                objective_value=result.score.objective_value + 1,
            ),
        )
        with self.assertRaisesRegex(OptimizationError, "complete training replay"):
            validate_demand_aware_topology_result(
                changed_score,
                self.parent,
                self.demand,
                self.seed,
                self.manifest,
                expected_plan,
            )
        if result.steps:
            changed_step = replace(
                result,
                steps=(
                    replace(
                        result.steps[0],
                        accepted_topology_fingerprint="0" * 64,
                    ),
                )
                + result.steps[1:],
            )
            with self.assertRaisesRegex(OptimizationError, "complete training replay"):
                validate_demand_aware_topology_result(
                    changed_step,
                    self.parent,
                    self.demand,
                    self.seed,
                    self.manifest,
                    expected_plan,
                )
        changed_demand = DirectedDemandMatrix.from_requests(
            self.parent.nodes,
            (PaymentRequest("a", "b", 1),),
        )
        with self.assertRaisesRegex(OptimizationError, "candidate-generation inputs"):
            validate_demand_aware_topology_result(
                result,
                self.parent,
                changed_demand,
                self.seed,
                self.manifest,
                expected_plan,
            )
        with self.assertRaisesRegex(OptimizationError, "maximum_move_edges"):
            replace(result.search_plan, maximum_move_edges=4)

    def test_infeasible_seed_and_wrong_resource_manifest_fail_before_search(self) -> None:
        bad_seed = HypergraphTopology.from_edges(
            self.parent.nodes,
            {"left": ("a", "b", "c"), "right": ("c", "d")},
        )
        with self.assertRaisesRegex(OptimizationError, "incidence budget"):
            train_demand_aware_topology(
                self.parent,
                self.demand,
                bad_seed,
                self.manifest,
                DemandAwareSearchPlan(10, 1),
            )


if __name__ == "__main__":
    unittest.main()
