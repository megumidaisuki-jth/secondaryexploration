"""Exact checks for the demand-aware four-term objective contract."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import unittest

from secondaryexploration.model import PaymentRequest
from secondaryexploration.optimization import (
    DemandAwareObjectiveWeights,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    OptimizationError,
    score_demand_aware_topology,
    validate_demand_aware_score,
    validate_demand_aware_topology,
)
from secondaryexploration.topology import HypergraphTopology, ParentGraph


def _weights() -> DemandAwareObjectiveWeights:
    return DemandAwareObjectiveWeights(
        Fraction(1, 1),
        Fraction(1, 1),
        Fraction(1, 1),
        Fraction(1, 1),
    )


class DirectedDemandTests(unittest.TestCase):
    def test_training_matrix_is_amount_weighted_complete_and_fingerprinted(self) -> None:
        requests = (
            PaymentRequest("a", "b", 2),
            PaymentRequest("a", "b", 3),
            PaymentRequest("b", "a", 4),
        )
        demand = DirectedDemandMatrix.from_requests(("b", "a", "c"), requests)

        self.assertEqual(demand.nodes, ("a", "b", "c"))
        self.assertEqual(len(demand.values), 6)
        self.assertEqual(demand.amount("a", "b"), 5)
        self.assertEqual(demand.amount("b", "a"), 4)
        self.assertEqual(demand.amount("a", "c"), 0)
        self.assertEqual(demand.total_bidirectional_volume, 4)
        self.assertEqual(demand.total_directional_imbalance, 1)
        self.assertEqual(
            demand,
            DirectedDemandMatrix.from_requests(("a", "b", "c"), requests),
        )
        changed = DirectedDemandMatrix.from_requests(
            ("a", "b", "c"),
            requests + (PaymentRequest("c", "a", 1),),
        )
        self.assertNotEqual(demand.fingerprint, changed.fingerprint)

    def test_training_matrix_fails_closed_on_malformed_or_outside_inputs(self) -> None:
        with self.assertRaisesRegex(OptimizationError, "outside"):
            DirectedDemandMatrix.from_requests(
                ("a", "b"),
                (PaymentRequest("a", "outside", 1),),
            )
        with self.assertRaisesRegex(OptimizationError, "every ordered"):
            DirectedDemandMatrix(
                ("a", "b"),
                (("a", "b", 1),),
            )
        with self.assertRaisesRegex(OptimizationError, "distinct declared"):
            DirectedDemandMatrix.from_requests(("a", "b"), ()).amount("a", "a")
        with self.assertRaisesRegex(OptimizationError, "valid UTF-8"):
            DirectedDemandMatrix.from_requests(("a", "\ud800"), ())


class DemandAwareObjectiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = ParentGraph.from_edges(
            ("a", "b", "c", "d"),
            (("a", "b"), ("b", "c"), ("c", "d")),
        )
        self.demand = DirectedDemandMatrix.from_requests(
            self.parent.nodes,
            (
                PaymentRequest("a", "b", 1),
                PaymentRequest("b", "a", 1),
                PaymentRequest("a", "c", 5),
                PaymentRequest("c", "a", 3),
                PaymentRequest("b", "d", 2),
                PaymentRequest("d", "b", 2),
            ),
        )
        self.topology = HypergraphTopology.from_edges(
            self.parent.nodes,
            {"left": ("a", "b", "c"), "right": ("b", "c", "d")},
        )
        self.manifest = DemandAwareTrainingManifest.create(
            self.parent,
            self.demand,
            incidence_budget=6,
            maximum_arity=3,
            weights=_weights(),
        )

    def test_hand_calculated_four_term_score_is_exact(self) -> None:
        score = score_demand_aware_topology(
            self.parent,
            self.demand,
            self.topology,
            self.manifest,
        )

        self.assertEqual(score.captured_bidirectional, 6)
        self.assertEqual(score.captured_imbalance, 2)
        self.assertEqual(score.participation_burden, 2)
        self.assertEqual(score.coordination_overlap_burden, 7)
        self.assertEqual(score.normalized_capture, Fraction(1, 1))
        self.assertEqual(score.normalized_imbalance, Fraction(1, 1))
        self.assertEqual(score.normalized_participation, Fraction(2, 3))
        self.assertEqual(score.normalized_coordination_overlap, Fraction(7, 15))
        self.assertEqual(score.objective_value, Fraction(-17, 15))
        validate_demand_aware_score(
            score,
            self.parent,
            self.demand,
            self.topology,
            self.manifest,
        )

    def test_complete_score_replay_rejects_forgery_and_wrong_demand(self) -> None:
        score = score_demand_aware_topology(
            self.parent,
            self.demand,
            self.topology,
            self.manifest,
        )
        forged = replace(score, objective_value=score.objective_value + 1)
        with self.assertRaisesRegex(OptimizationError, "complete objective replay"):
            validate_demand_aware_score(
                forged,
                self.parent,
                self.demand,
                self.topology,
                self.manifest,
            )
        changed_demand = DirectedDemandMatrix.from_requests(
            self.parent.nodes,
            (PaymentRequest("a", "b", 1),),
        )
        with self.assertRaisesRegex(OptimizationError, "training demand"):
            score_demand_aware_topology(
                self.parent,
                changed_demand,
                self.topology,
                self.manifest,
            )

    def test_feasible_set_rejects_budget_arity_coverage_connectivity_and_duplicates(self) -> None:
        wrong_budget = HypergraphTopology.from_edges(
            self.parent.nodes,
            {
                "ab": ("a", "b"),
                "bc": ("b", "c"),
                "cd": ("c", "d"),
            },
        )
        with self.assertRaisesRegex(OptimizationError, "incidence budget"):
            validate_demand_aware_topology(
                self.parent,
                wrong_budget,
                replace(self.manifest, incidence_budget=7),
            )
        with self.assertRaisesRegex(OptimizationError, "maximum arity"):
            validate_demand_aware_topology(
                self.parent,
                self.topology,
                replace(self.manifest, maximum_arity=2),
            )
        disconnected_member_set = HypergraphTopology.from_edges(
            self.parent.nodes,
            {"ac": ("a", "c"), "all": ("a", "b", "c", "d")},
        )
        disconnected_manifest = DemandAwareTrainingManifest.create(
            self.parent,
            self.demand,
            6,
            4,
            _weights(),
        )
        with self.assertRaisesRegex(OptimizationError, "induce a connected"):
            validate_demand_aware_topology(
                self.parent,
                disconnected_member_set,
                disconnected_manifest,
            )
        uncovered = HypergraphTopology.from_edges(
            self.parent.nodes,
            {"abc": ("a", "b", "c"), "ad": ("a", "d")},
        )
        uncovered_manifest = DemandAwareTrainingManifest.create(
            self.parent,
            self.demand,
            5,
            3,
            _weights(),
        )
        with self.assertRaisesRegex(OptimizationError, "induce a connected"):
            validate_demand_aware_topology(
                self.parent,
                uncovered,
                uncovered_manifest,
            )
        duplicate = HypergraphTopology.from_edges(
            self.parent.nodes,
            {"one": ("a", "b", "c"), "two": ("a", "b", "c")},
        )
        with self.assertRaisesRegex(OptimizationError, "duplicate member sets"):
            validate_demand_aware_topology(
                self.parent,
                duplicate,
                self.manifest,
            )

    def test_manifest_binds_parent_constraints_weights_and_demand(self) -> None:
        changed_parent = ParentGraph.from_edges(
            self.parent.nodes,
            (("a", "b"), ("b", "d"), ("c", "d")),
        )
        with self.assertRaisesRegex(OptimizationError, "supplied parent"):
            validate_demand_aware_topology(
                changed_parent,
                self.topology,
                self.manifest,
            )
        with self.assertRaisesRegex(OptimizationError, "node_count"):
            validate_demand_aware_topology(
                self.parent,
                self.topology,
                replace(self.manifest, node_count=5),
            )
        changed_weights = replace(
            self.manifest,
            weights=replace(
                self.manifest.weights,
                participation=Fraction(2, 1),
            ),
        )
        self.assertNotEqual(self.manifest.fingerprint, changed_weights.fingerprint)
        with self.assertRaisesRegex(OptimizationError, "incidence_budget"):
            replace(self.manifest, incidence_budget=2**64)

    def test_zero_demand_denominators_map_to_exact_zero(self) -> None:
        zero = DirectedDemandMatrix.from_requests(self.parent.nodes, ())
        manifest = DemandAwareTrainingManifest.create(
            self.parent,
            zero,
            6,
            3,
            _weights(),
        )
        score = score_demand_aware_topology(
            self.parent,
            zero,
            self.topology,
            manifest,
        )
        self.assertEqual(score.normalized_capture, 0)
        self.assertEqual(score.normalized_imbalance, 0)


if __name__ == "__main__":
    unittest.main()
