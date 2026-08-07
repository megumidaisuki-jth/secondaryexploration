"""Exact contracts for parent-aware pilot evidence arithmetic."""

from __future__ import annotations

import copy
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from secondaryexploration.analysis.pilot import (
    _fingerprint,
    _summarize_observations,
    _trace_observation,
    generate_pilot_evidence,
    load_pilot_evidence,
    validate_pilot_evidence,
)
from secondaryexploration.experiments import (
    StudyManifestError,
    load_study_design_manifest,
)


_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST = _ROOT / "configs" / "pilot" / "synthetic-pipeline-v1.json"
_EVIDENCE = _ROOT / "results" / "pilot" / "synthetic-pipeline-v1" / "evidence.json"


def _variant(
    *,
    observed: bool,
    request_index: int,
    accepted: int,
    value: int,
    costs: tuple[int, int, int, int],
) -> dict[str, object]:
    return {
        "horizon": 10,
        "tau_nopath": {"observed": observed, "request_index": request_index},
        "success_rate": [accepted, 10],
        "accepted_request_count": accepted,
        "accepted_value": value,
        "dynamic_costs": {
            "traversed_hyperedge_count": costs[0],
            "signaled_participant_slots": costs[1],
            "unique_signaled_participants": costs[2],
            "quadratic_coordination_exposure": costs[3],
        },
    }


class PilotEvidenceArithmeticTests(unittest.TestCase):
    def test_tracked_evidence_has_strict_identity_and_context_binding(self) -> None:
        evidence = load_pilot_evidence(_EVIDENCE)
        self.assertEqual(
            evidence["evidence_fingerprint"],
            "bbb7f921d45a9ac0307d0a6e5205dca0f3baa1d9e12c816ccba960ba3b2d1076",
        )
        self.assertEqual(evidence["counts"]["panel_trace_contrast_count"], 168)

        bit_flip = copy.deepcopy(evidence)
        bit_flip["limitations"].append("forged")
        with self.assertRaisesRegex(StudyManifestError, "fingerprint"):
            validate_pilot_evidence(bit_flip)

        coordinated = copy.deepcopy(evidence)
        coordinated["manifest_fingerprint"] = "f" * 64
        coordinated["evidence_fingerprint"] = _fingerprint(coordinated)
        with self.assertRaisesRegex(StudyManifestError, "study manifest"):
            validate_pilot_evidence(
                coordinated,
                manifest=load_study_design_manifest(_MANIFEST),
            )

        attacks = []
        nested_unknown = copy.deepcopy(evidence)
        nested_unknown["summaries"]["global_by_size"][0]["unknown"] = 1
        attacks.append(("nested-unknown", nested_unknown, "keys mismatch"))
        false_difference = copy.deepcopy(evidence)
        false_difference["summaries"]["global_by_size"][0]["metrics"][
            "success_rate"
        ]["difference"] = [999, 1]
        attacks.append(("false-difference", false_difference, "does not match"))
        unknown_environment = copy.deepcopy(evidence)
        unknown_environment["environment"]["unknown"] = "x"
        attacks.append(("environment", unknown_environment, "keys mismatch"))
        for name, attack, message in attacks:
            with self.subTest(standalone_attack=name):
                attack["evidence_fingerprint"] = _fingerprint(attack)
                with self.assertRaisesRegex(StudyManifestError, message):
                    validate_pilot_evidence(attack)

    def test_explicit_summary_path_cannot_escape_workspace(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            root.mkdir()
            outside = Path(directory) / "outside-summary.json"
            with self.assertRaisesRegex(StudyManifestError, "summary_path escapes"):
                generate_pilot_evidence(
                    _MANIFEST,
                    workspace_root=root,
                    summary_path=outside,
                    output_path=root / "evidence.json",
                )

    def test_binary_brackets_are_averaged_within_trace_before_contrast(self) -> None:
        source = _variant(
            observed=False,
            request_index=10,
            accepted=8,
            value=20,
            costs=(16, 32, 24, 80),
        )
        binary = [
            _variant(
                observed=True,
                request_index=4,
                accepted=4,
                value=8,
                costs=(12, 24, 18, 48),
            ),
            _variant(
                observed=False,
                request_index=10,
                accepted=6,
                value=14,
                costs=(18, 36, 27, 72),
            ),
        ]
        observation = _trace_observation(
            node_count=30,
            parent_graph_id="parent-a",
            regime_id="regime-a",
            scope="same_distribution",
            source_variant_id="fhs5",
            binary_arm_count=2,
            horizon=10,
            source=source,
            binary=binary,
        )

        self.assertEqual(
            observation["metrics"]["normalized_restricted_tau_nopath"],
            (Fraction(1), Fraction(7, 10), Fraction(3, 10)),
        )
        self.assertEqual(
            observation["metrics"]["failure_risk"],
            (Fraction(0), Fraction(1, 2), Fraction(-1, 2)),
        )
        self.assertEqual(
            observation["metrics"]["success_rate"],
            (Fraction(4, 5), Fraction(1, 2), Fraction(3, 10)),
        )
        self.assertEqual(
            observation["dynamic_cost_per_accepted"][
                "traversed_hyperedge_count"
            ],
            (Fraction(2), Fraction(3), Fraction(-1)),
        )

    def test_trace_means_are_formed_within_parent_before_parent_equal_mean(self) -> None:
        base = {
            "node_count": 30,
            "regime_id": "regime-a",
            "scope": "same_distribution",
            "source_variant_id": "fhs5",
            "binary_arm_count": 1,
            "source_tau_nopath_observed": False,
            "binary_tau_nopath_event_mean": Fraction(0),
            "dynamic_cost_per_attempt": {},
            "dynamic_cost_per_accepted": {},
        }
        for field in (
            "traversed_hyperedge_count",
            "signaled_participant_slots",
            "unique_signaled_participants",
            "quadratic_coordination_exposure",
        ):
            base["dynamic_cost_per_attempt"][field] = (
                Fraction(1),
                Fraction(0),
                Fraction(1),
            )
            base["dynamic_cost_per_accepted"][field] = (
                Fraction(1),
                Fraction(0),
                Fraction(1),
            )

        def item(parent: str, difference: int) -> dict[str, object]:
            value = dict(base)
            value["parent_graph_id"] = parent
            value["metrics"] = {
                metric: (Fraction(difference), Fraction(0), Fraction(difference))
                for metric in (
                    "normalized_restricted_tau_nopath",
                    "failure_risk",
                    "success_rate",
                    "accepted_value",
                )
            }
            return value

        summary = _summarize_observations(
            [item("parent-a", 0), item("parent-a", 2), item("parent-b", 5)]
        )
        # Parent A contributes mean 1 and parent B contributes mean 5: (1 + 5) / 2.
        self.assertEqual(
            summary["metrics"]["success_rate"]["difference"],
            [3, 1],
        )
        self.assertEqual(summary["parent_graph_count"], 2)
        self.assertEqual(summary["trace_contrast_count"], 3)


if __name__ == "__main__":
    unittest.main()
