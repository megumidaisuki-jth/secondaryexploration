"""Tests for the frozen formal-precision decision."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from secondaryexploration.analysis.precision import (
    build_formal_precision_evidence,
    generate_formal_precision_evidence,
    load_formal_precision_evidence,
    validate_formal_precision_evidence,
)
from secondaryexploration.experiments import StudyManifestError


_ROOT = Path(__file__).resolve().parents[3]
_CALIBRATION = (
    _ROOT / "results" / "pilot" / "synthetic-calibration-v1" / "evidence.json"
)
_PRECISION = _ROOT / "results" / "planning" / "formal-precision-v1.json"


def _calibration() -> dict[str, object]:
    return json.loads(_CALIBRATION.read_text(encoding="utf-8"))


def _fingerprint(value: dict[str, object]) -> str:
    payload = dict(value)
    payload.pop("precision_fingerprint", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class FormalPrecisionEvidenceTests(unittest.TestCase):
    def test_tracked_precision_artifact_is_the_exact_replay(self) -> None:
        calibration = _calibration()
        tracked = load_formal_precision_evidence(
            _PRECISION,
            calibration_evidence=calibration,
        )

        self.assertEqual(tracked, build_formal_precision_evidence(calibration))
        self.assertEqual(
            tracked["precision_fingerprint"],
            "c2083ff1762ec7407412e702f99bf2c58ef244e4702accc90553112fb876a2d1",
        )

    def test_recommended_a_replays_counts_families_and_runtime(self) -> None:
        evidence = build_formal_precision_evidence(_calibration())

        self.assertEqual(evidence["decision"]["selection"], "recommended-a")
        self.assertEqual(len(evidence["confirmatory_families"]), 8)
        self.assertEqual(
            evidence["bootstrap"]["confirmatory_contrast_count"],
            40,
        )
        self.assertEqual(
            evidence["bootstrap"]["local_hierarchy_confidence_level"],
            [159, 160],
        )
        self.assertEqual(
            evidence["bootstrap"]["bonferroni_tail_probability"],
            [1, 1600],
        )
        self.assertEqual(
            evidence["bootstrap"]["expected_resamples_in_each_adjusted_tail"],
            [25, 2],
        )
        self.assertEqual(
            evidence["execution_seed_families"],
            {
                "formal_base_seed": 2026081001,
                "confirmation_base_seed": 2026081002,
                "bootstrap_root_seed": 2026081003,
                "all_three_roots_distinct": True,
            },
        )
        self.assertEqual(
            evidence["precision_targets"]["endpoint_horizon"]["requests_per_node"],
            12,
        )
        self.assertEqual(
            evidence["planning_method"]["maximum_raw_required_global"],
            19,
        )
        self.assertEqual(
            evidence["planning_method"]["maximum_raw_required_secondary"],
            12,
        )
        self.assertEqual(
            {
                item["formal_parent_count"]
                for item in evidence["planned_parent_count_per_size_model"]
            },
            {20},
        )
        self.assertEqual(
            evidence["runtime_allocation"]["block_count_per_phase"],
            240,
        )
        self.assertEqual(
            evidence["runtime_allocation"][
                "formal_estimated_sequential_seconds_ceiling"
            ],
            1_792_607,
        )

    def test_calibration_or_precision_tampering_fails_closed(self) -> None:
        calibration = _calibration()
        altered_calibration = deepcopy(calibration)
        altered_calibration["evidence_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(StudyManifestError, "fingerprint"):
            build_formal_precision_evidence(altered_calibration)

        evidence = build_formal_precision_evidence(calibration)
        altered_evidence = deepcopy(evidence)
        altered_evidence["decision"]["selection"] = "recommended-b"
        with self.assertRaisesRegex(StudyManifestError, "fingerprint"):
            validate_formal_precision_evidence(altered_evidence)

    def test_generator_and_loader_require_exact_source_replay(self) -> None:
        calibration = _calibration()
        with TemporaryDirectory(dir=_ROOT) as directory:
            target = generate_formal_precision_evidence(
                _CALIBRATION,
                workspace_root=_ROOT,
                output_path=Path(directory) / "precision.json",
            )
            loaded = load_formal_precision_evidence(
                target,
                calibration_evidence=calibration,
            )
            self.assertEqual(loaded, build_formal_precision_evidence(calibration))

            forged = deepcopy(loaded)
            forged["decision"]["selection"] = "recommended-b"
            forged["precision_fingerprint"] = _fingerprint(forged)
            forged_path = Path(directory) / "forged.json"
            forged_path.write_text(
                json.dumps(forged, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(StudyManifestError, "replay mismatch"):
                load_formal_precision_evidence(
                    forged_path,
                    calibration_evidence=calibration,
                )

            malformed = Path(directory) / "duplicate.json"
            malformed.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "duplicate"):
                load_formal_precision_evidence(
                    malformed,
                    calibration_evidence=calibration,
                )


if __name__ == "__main__":
    unittest.main()
