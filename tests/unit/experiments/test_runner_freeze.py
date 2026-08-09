"""Tests for formal runner precision and environment gates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from secondaryexploration.analysis.precision import (
    load_audited_calibration_evidence,
    load_formal_precision_evidence,
)
from secondaryexploration.experiments import (
    StudyManifestError,
    StudyPhase,
    SyntheticSizeCell,
    load_study_design_manifest,
)
from secondaryexploration.experiments.runner import (
    runtime_environment,
    runtime_environment_fingerprint,
    preflight_synthetic_study,
    validate_frozen_execution_context,
)


_ROOT = Path(__file__).resolve().parents[3]
_CALIBRATION_MANIFEST = (
    _ROOT / "configs" / "pilot" / "synthetic-calibration-v1.json"
)
_CALIBRATION_EVIDENCE = (
    _ROOT / "results" / "pilot" / "synthetic-calibration-v1" / "evidence.json"
)
_PRECISION = _ROOT / "results" / "planning" / "formal-precision-v1.json"
_CODE_REVISION = "a" * 40


def _precision() -> dict[str, object]:
    calibration = load_audited_calibration_evidence(_CALIBRATION_EVIDENCE)
    return load_formal_precision_evidence(
        _PRECISION,
        calibration_evidence=calibration,
    )


def _calibration_manifest():
    return load_study_design_manifest(_CALIBRATION_MANIFEST)


def _formal_manifest(phase: StudyPhase = StudyPhase.FORMAL):
    pilot = load_study_design_manifest(_CALIBRATION_MANIFEST)
    environment = runtime_environment()
    return replace(
        pilot,
        study_id=(
            "synthetic-formal-v1"
            if phase is StudyPhase.FORMAL
            else "synthetic-confirmation-v1"
        ),
        phase=phase,
        base_seed=(2026081001 if phase is StudyPhase.FORMAL else 2026081002),
        output_root=(
            "outputs/formal/synthetic-formal-v1"
            if phase is StudyPhase.FORMAL
            else "outputs/confirmation/synthetic-confirmation-v1"
        ),
        basis_fingerprint=_precision()["precision_fingerprint"],
        code_revision=_CODE_REVISION,
        environment_fingerprint=runtime_environment_fingerprint(environment),
        size_cells=(
            SyntheticSizeCell(30, 3, 4, 60),
            SyntheticSizeCell(60, 3, 4, 128),
            SyntheticSizeCell(120, 3, 4, 263),
            SyntheticSizeCell(240, 3, 4, 533),
        ),
        parent_replicates=20,
    )


class FrozenRunnerContextTests(unittest.TestCase):
    def test_preflight_replays_formal_sources_without_creating_outputs(self) -> None:
        manifest = _formal_manifest()
        output_root = _ROOT / manifest.output_root
        existed_before = output_root.exists()
        with TemporaryDirectory(dir=_ROOT) as directory:
            manifest_path = Path(directory) / "formal.json"
            manifest_path.write_text(manifest.canonical_json, encoding="utf-8")
            with patch(
                "secondaryexploration.experiments.runner._verify_execution_code_snapshot"
            ):
                result = preflight_synthetic_study(
                    manifest_path,
                    workspace_root=_ROOT,
                    code_revision=_CODE_REVISION,
                    precision_path=_PRECISION,
                    calibration_evidence_path=_CALIBRATION_EVIDENCE,
                    calibration_manifest_path=_CALIBRATION_MANIFEST,
                )

        self.assertEqual(result["status"], "preflight-valid-no-execution")
        self.assertEqual(result["expected_block_count"], 240)
        self.assertEqual(result["manifest_fingerprint"], manifest.fingerprint)
        self.assertEqual(output_root.exists(), existed_before)

    def test_formal_and_confirmation_match_the_strict_precision_freeze(self) -> None:
        precision = _precision()
        environment = runtime_environment()

        for phase in (StudyPhase.FORMAL, StudyPhase.CONFIRMATION):
            with self.subTest(phase=phase.value):
                validate_frozen_execution_context(
                    _formal_manifest(phase),
                    code_revision=_CODE_REVISION,
                    environment=environment,
                    precision_evidence=precision,
                    calibration_manifest=_calibration_manifest(),
                )

    def test_basis_seed_horizon_count_revision_and_environment_fail_closed(self) -> None:
        precision = _precision()
        environment = runtime_environment()
        manifest = _formal_manifest()
        attacks = (
            (replace(manifest, basis_fingerprint="0" * 64), _CODE_REVISION, environment, "basis"),
            (replace(manifest, base_seed=manifest.base_seed + 1), _CODE_REVISION, environment, "seed"),
            (replace(manifest, requests_per_node=13), _CODE_REVISION, environment, "horizon"),
            (replace(manifest, parent_replicates=19), _CODE_REVISION, environment, "parent counts"),
            (manifest, "b" * 40, environment, "code_revision"),
            (
                manifest,
                _CODE_REVISION,
                {**environment, "python_version": "0.0.0"},
                "environment",
            ),
        )
        for attacked, revision, attacked_environment, message in attacks:
            with self.subTest(message=message):
                with self.assertRaisesRegex(StudyManifestError, message):
                    validate_frozen_execution_context(
                        attacked,
                        code_revision=revision,
                        environment=attacked_environment,
                        precision_evidence=precision,
                        calibration_manifest=_calibration_manifest(),
                    )

        with self.assertRaisesRegex(StudyManifestError, "requires"):
            validate_frozen_execution_context(
                manifest,
                code_revision=_CODE_REVISION,
                environment=environment,
                precision_evidence=None,
                calibration_manifest=None,
            )

    def test_non_gate_manifest_fields_cannot_be_changed(self) -> None:
        precision = _precision()
        environment = runtime_environment()
        manifest = _formal_manifest()
        attacks = (
            replace(manifest, study_id="synthetic-formal-attacked"),
            replace(manifest, output_root="outputs/formal/attacked"),
            replace(manifest, maximum_parent_attempts=999),
            replace(manifest, per_node_capital=121),
        )
        for attacked in attacks:
            with self.subTest(study_id=attacked.study_id, output=attacked.output_root):
                with self.assertRaisesRegex(StudyManifestError, "exact frozen"):
                    validate_frozen_execution_context(
                        attacked,
                        code_revision=_CODE_REVISION,
                        environment=environment,
                        precision_evidence=precision,
                        calibration_manifest=_calibration_manifest(),
                    )

    def test_pilot_rejects_formal_precision_but_needs_no_frozen_environment(self) -> None:
        pilot = load_study_design_manifest(_CALIBRATION_MANIFEST)
        environment = runtime_environment()

        validate_frozen_execution_context(
            pilot,
            code_revision=_CODE_REVISION,
            environment=environment,
            precision_evidence=None,
            calibration_manifest=None,
        )
        with self.assertRaisesRegex(StudyManifestError, "pilot"):
            validate_frozen_execution_context(
                pilot,
                code_revision=_CODE_REVISION,
                environment=environment,
                precision_evidence=_precision(),
                calibration_manifest=_calibration_manifest(),
            )


if __name__ == "__main__":
    unittest.main()
