"""Tests for deterministic formal and confirmation manifest generation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from secondaryexploration.analysis.formal_freeze import (
    build_frozen_phase_manifest,
    generate_frozen_phase_manifest,
)
from secondaryexploration.analysis.precision import (
    load_audited_calibration_evidence,
    load_formal_precision_evidence,
)
from secondaryexploration.experiments import (
    StudyManifestError,
    StudyPhase,
    build_study_seed_ledger,
    load_study_design_manifest,
)


_ROOT = Path(__file__).resolve().parents[3]
_CALIBRATION_MANIFEST = _ROOT / "configs" / "pilot" / "synthetic-calibration-v1.json"
_CALIBRATION_EVIDENCE = (
    _ROOT / "results" / "pilot" / "synthetic-calibration-v1" / "evidence.json"
)
_PRECISION = _ROOT / "results" / "planning" / "formal-precision-v1.json"
_CODE_REVISION = "70ecdc5e90da4f3321a128b93813431f1fcd19b8"
_FORMAL = _ROOT / "configs" / "formal" / "synthetic-formal-v1.json"
_CONFIRMATION = (
    _ROOT / "configs" / "confirmation" / "synthetic-confirmation-v1.json"
)
_ENVIRONMENT = {
    "python_implementation": "cpython",
    "python_version": "3.12.13",
    "platform_system": "Windows",
    "machine": "AMD64",
}


def _sources():
    calibration_manifest = load_study_design_manifest(_CALIBRATION_MANIFEST)
    calibration = load_audited_calibration_evidence(_CALIBRATION_EVIDENCE)
    precision = load_formal_precision_evidence(
        _PRECISION,
        calibration_evidence=calibration,
    )
    return calibration_manifest, precision


def _all_seeds(manifest) -> set[int]:
    ledger = build_study_seed_ledger(manifest)
    return {
        seed
        for item in ledger.parent_seeds
        for seed in (
            item.ensemble_base_seed,
            item.capacity_search_seed,
            item.binary_matching_seed,
        )
    } | {
        seed
        for item in ledger.trace_seeds
        for seed in (item.trace_root_seed, item.routing_root_seed)
    }


class FrozenPhaseManifestTests(unittest.TestCase):
    def test_tracked_manifests_are_exact_frozen_replays(self) -> None:
        calibration_manifest, precision = _sources()
        expected = {
            StudyPhase.FORMAL: (
                _FORMAL,
                "8ed7ef5f85aa167e0e556edb546f3139fae664624d8f401415f378d1f203af2b",
            ),
            StudyPhase.CONFIRMATION: (
                _CONFIRMATION,
                "536cfc14ac540d021a0531204fde396c67295ff8442a312abac4bf40a2514c22",
            ),
        }
        for phase, (path, fingerprint) in expected.items():
            with self.subTest(phase=phase.value):
                tracked = load_study_design_manifest(path)
                replay = build_frozen_phase_manifest(
                    calibration_manifest,
                    precision,
                    phase=phase,
                    code_revision=_CODE_REVISION,
                    environment=_ENVIRONMENT,
                )
                self.assertEqual(tracked, replay)
                self.assertEqual(tracked.fingerprint, fingerprint)

    def test_formal_and_confirmation_are_disjoint_and_precision_bound(self) -> None:
        calibration_manifest, precision = _sources()
        formal = build_frozen_phase_manifest(
            calibration_manifest,
            precision,
            phase=StudyPhase.FORMAL,
            code_revision=_CODE_REVISION,
            environment=_ENVIRONMENT,
        )
        confirmation = build_frozen_phase_manifest(
            calibration_manifest,
            precision,
            phase=StudyPhase.CONFIRMATION,
            code_revision=_CODE_REVISION,
            environment=_ENVIRONMENT,
        )

        self.assertEqual(formal.parent_replicates, 20)
        self.assertEqual(confirmation.parent_replicates, 20)
        self.assertEqual(tuple(item.node_count for item in formal.size_cells), (30, 60, 120, 240))
        self.assertEqual(formal.basis_fingerprint, precision["precision_fingerprint"])
        self.assertNotEqual(formal.base_seed, confirmation.base_seed)
        self.assertNotEqual(formal.output_root, confirmation.output_root)
        self.assertNotEqual(formal.fingerprint, confirmation.fingerprint)
        formal_seeds = _all_seeds(formal)
        confirmation_seeds = _all_seeds(confirmation)
        self.assertEqual(len(formal_seeds), 2_000)
        self.assertEqual(len(confirmation_seeds), 2_000)
        self.assertTrue(formal_seeds.isdisjoint(confirmation_seeds))

    def test_generator_replays_sources_and_writes_a_loadable_manifest(self) -> None:
        with TemporaryDirectory(dir=_ROOT) as directory:
            target = generate_frozen_phase_manifest(
                _CALIBRATION_MANIFEST,
                _CALIBRATION_EVIDENCE,
                _PRECISION,
                phase=StudyPhase.FORMAL,
                code_revision=_CODE_REVISION,
                workspace_root=_ROOT,
                output_path=Path(directory) / "formal.json",
            )
            loaded = load_study_design_manifest(target)
            self.assertEqual(loaded.phase, StudyPhase.FORMAL)
            self.assertEqual(loaded.code_revision, _CODE_REVISION)
            self.assertEqual(loaded.parent_replicates, 20)

    def test_unfrozen_phase_or_altered_calibration_manifest_is_rejected(self) -> None:
        calibration_manifest, precision = _sources()
        with self.assertRaisesRegex(StudyManifestError, "phase"):
            build_frozen_phase_manifest(
                calibration_manifest,
                precision,
                phase=StudyPhase.PILOT,
                code_revision=_CODE_REVISION,
                environment=_ENVIRONMENT,
            )
        with self.assertRaisesRegex(StudyManifestError, "audited calibration"):
            build_frozen_phase_manifest(
                replace(calibration_manifest, base_seed=calibration_manifest.base_seed + 1),
                precision,
                phase=StudyPhase.FORMAL,
                code_revision=_CODE_REVISION,
                environment=_ENVIRONMENT,
            )


if __name__ == "__main__":
    unittest.main()
