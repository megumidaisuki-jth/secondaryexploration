"""Arithmetic tests for parent-stratified calibration evidence."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import unittest

from secondaryexploration.analysis.calibration import (
    _aggregate_parent_cells,
    _censoring_gate,
    _event_coverage,
    _extract_observations,
    _parent_dispersion,
    _runtime_evidence,
    _validate_frozen_calibration_inputs,
)
from secondaryexploration.experiments import StudyManifestError, load_study_design_manifest


_COST_FIELDS = (
    "traversed_hyperedge_count",
    "signaled_participant_slots",
    "unique_signaled_participants",
    "quadratic_coordination_exposure",
)


def _observation(
    parent_replicate: int,
    regime_id: str,
    difference: int,
    *,
    source_event: bool,
    accepted_defined: bool = True,
    binary_events: tuple[bool, bool] = (False, False),
) -> dict[str, object]:
    triplet = (Fraction(difference), Fraction(0), Fraction(difference))
    return {
        "node_count": 30,
        "parent_model": "er_gnm",
        "parent_replicate": parent_replicate,
        "parent_graph_id": f"n0030-r{parent_replicate:04d}-er_gnm",
        "source_variant_id": "fhs5",
        "scope": "same_distribution",
        "regime_id": regime_id,
        "binary_arm_count": 2,
        "source_tau_nopath_observed": source_event,
        "binary_tau_nopath_event_mean": Fraction(1, 2),
        "binary_tau_nopath_observations": (
            ("binary-left", binary_events[0]),
            ("binary-right", binary_events[1]),
        ),
        "metrics": {
            "normalized_restricted_tau_nopath": triplet,
            "failure_risk": triplet,
            "success_rate": triplet,
            "accepted_value": triplet,
        },
        "dynamic_cost_per_attempt": {field: triplet for field in _COST_FIELDS},
        "dynamic_cost_per_accepted": {
            field: triplet if accepted_defined else None for field in _COST_FIELDS
        },
    }


def _runtime_artifact(size: int, model: str, replicate: int, total: int):
    return {
        "block": {
            "node_count": size,
            "parent_model": model,
            "parent_replicate": replicate,
        },
        "timing_ns": {
            "generation": total // 2,
            "exact_validation": total - total // 2,
        },
    }


class CalibrationArithmeticTests(unittest.TestCase):
    def test_censoring_gate_is_parentwise_and_requires_every_binary_arm(self) -> None:
        concentrated = [
            _observation(
                parent,
                f"regime-{trace}",
                0,
                source_event=(parent == 0 and trace < 2),
                binary_events=(True, True),
            )
            for parent in range(3)
            for trace in range(4)
        ]
        concentrated_gate = _censoring_gate(concentrated, Fraction(1, 10))[0]
        self.assertFalse(
            concentrated_gate[
                "all_parents_source_and_binary_lower_quantiles_identified"
            ]
        )
        self.assertEqual(
            [
                row["source_lower_quantile_identified"]
                for row in concentrated_gate["parents"]
            ],
            [True, False, False],
        )

        missing_binary = [
            _observation(
                parent,
                f"regime-{trace}",
                0,
                source_event=(trace == 0),
                binary_events=(trace == 0, False),
            )
            for parent in range(3)
            for trace in range(4)
        ]
        missing_binary_gate = _censoring_gate(missing_binary, Fraction(1, 10))[0]
        self.assertFalse(
            missing_binary_gate[
                "all_parents_source_and_binary_lower_quantiles_identified"
            ]
        )
        self.assertTrue(
            all(
                row["source_lower_quantile_identified"]
                for row in missing_binary_gate["parents"]
            )
        )
        self.assertTrue(
            all(
                not row["all_binary_lower_quantiles_identified"]
                for row in missing_binary_gate["parents"]
            )
        )

    def test_frozen_manifest_and_exact_18_block_set_are_required(self) -> None:
        root = Path(__file__).resolve().parents[3]
        manifest = load_study_design_manifest(
            root / "configs" / "pilot" / "synthetic-calibration-v1.json"
        )
        artifacts = [
            {
                "block": {
                    "node_count": node_count,
                    "parent_model": model,
                    "parent_replicate": replicate,
                }
            }
            for node_count in (30, 60)
            for replicate in range(3)
            for model in ("barabasi_albert", "er_gnm", "sbm_fixed_count")
        ]

        _validate_frozen_calibration_inputs(manifest, artifacts)
        with self.assertRaisesRegex(StudyManifestError, "exact frozen 18"):
            _validate_frozen_calibration_inputs(manifest, artifacts[:-1])
        with self.assertRaisesRegex(StudyManifestError, "fingerprint"):
            _validate_frozen_calibration_inputs(
                replace(manifest, base_seed=manifest.base_seed + 1),
                artifacts,
            )

    def test_manifest_shift_enum_is_mapped_to_the_two_registered_scopes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        manifest = load_study_design_manifest(
            root / "configs" / "pilot" / "synthetic-calibration-v1.json"
        )
        variant = {
            "variant_id": "fhs5",
            "horizon": 10,
            "tau_nopath": {"observed": False, "request_index": 10},
            "success_rate": [10, 10],
            "accepted_request_count": 10,
            "accepted_value": 10,
            "dynamic_costs": {field: 10 for field in _COST_FIELDS},
        }
        binary = dict(variant, variant_id="binary")
        artifact = {
            "block": {
                "node_count": 30,
                "parent_model": "er_gnm",
                "parent_replicate": 0,
            },
            "resource_panels": [
                {
                    "source_variant_id": "fhs5",
                    "binary_variant_ids": ["binary"],
                }
            ],
            "held_out": [
                {
                    "trace_seed": {"regime_id": regime_id},
                    "variants": [variant, binary],
                }
                for regime_id in ("test-uniform-id", "test-community-cross")
            ],
        }

        observations = _extract_observations(manifest, [artifact])

        self.assertEqual(
            {item["regime_id"]: item["scope"] for item in observations},
            {
                "test-community-cross": "distribution_shift",
                "test-uniform-id": "same_distribution",
            },
        )

    def test_trace_means_precede_parent_dispersion(self) -> None:
        observations = []
        for replicate, values in enumerate(((1, 3), (5, 7), (9, 11))):
            observations.extend(
                (
                    _observation(
                        replicate,
                        f"regime-{index}",
                        value,
                        source_event=(index == 0),
                        accepted_defined=not (replicate == 2 and index == 1),
                    )
                    for index, value in enumerate(values)
                )
            )

        parents = _aggregate_parent_cells(observations)
        dispersion = _parent_dispersion(parents)
        coverage = _event_coverage(observations)

        self.assertEqual(len(parents), 3)
        self.assertEqual(
            [row["values"]["success_rate"] for row in parents],
            [Fraction(2), Fraction(6), Fraction(10)],
        )
        success = dispersion[0]["metrics"]["success_rate"]
        self.assertEqual(success["mean"], [6, 1])
        self.assertEqual(success["sample_variance"], [16, 1])
        self.assertEqual(success["defined_parent_count"], 3)
        accepted_cost = dispersion[0]["metrics"][
            "dynamic_cost_per_accepted.traversed_hyperedge_count"
        ]
        self.assertEqual(accepted_cost["defined_parent_count"], 2)
        self.assertEqual(coverage[0]["parent_graph_count"], 3)
        self.assertEqual(coverage[0]["nested_trace_count"], 6)
        self.assertEqual(coverage[0]["source_event_count"], 3)
        self.assertEqual(coverage[0]["binary_arm_observation_count"], 12)
        self.assertEqual(coverage[0]["binary_event_arm_count"], 6)
        self.assertEqual(coverage[0]["binary_event_equivalent"], [3, 1])

    def test_runtime_projection_repeats_model_specific_doubling_ratio(self) -> None:
        artifacts = []
        for model in ("er_gnm", "barabasi_albert", "sbm_fixed_count"):
            artifacts.extend(
                _runtime_artifact(30, model, replicate, total)
                for replicate, total in enumerate((90, 100, 110))
            )
            artifacts.extend(
                _runtime_artifact(60, model, replicate, total)
                for replicate, total in enumerate((360, 400, 440))
            )

        runtime = _runtime_evidence(artifacts)

        er = [
            row
            for row in runtime["projected_cells"]
            if row["parent_model"] == "er_gnm"
        ]
        self.assertEqual(er[0]["observed_doubling_ratio"], [4, 1])
        self.assertEqual(er[0]["projected_total_seconds_per_block_ceiling"], 1)
        self.assertEqual(er[1]["projected_total_seconds_per_block_ceiling"], 1)


if __name__ == "__main__":
    unittest.main()
