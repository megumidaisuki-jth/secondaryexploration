"""Tests for formal runner precision and environment gates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

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
                    )

        with self.assertRaisesRegex(StudyManifestError, "requires"):
            validate_frozen_execution_context(
                manifest,
                code_revision=_CODE_REVISION,
                environment=environment,
                precision_evidence=None,
            )

    def test_pilot_rejects_formal_precision_but_needs_no_frozen_environment(self) -> None:
        pilot = load_study_design_manifest(_CALIBRATION_MANIFEST)
        environment = runtime_environment()

        validate_frozen_execution_context(
            pilot,
            code_revision=_CODE_REVISION,
            environment=environment,
            precision_evidence=None,
        )
        with self.assertRaisesRegex(StudyManifestError, "pilot"):
            validate_frozen_execution_context(
                pilot,
                code_revision=_CODE_REVISION,
                environment=environment,
                precision_evidence=_precision(),
            )


if __name__ == "__main__":
    unittest.main()
