"""Tests for formal runner precision and environment gates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from secondaryexploration.analysis.precision import (
    load_audited_calibration_evidence,
    load_formal_precision_evidence,
)
from secondaryexploration.experiments import (
    StudyManifestError,
    StudyPhase,
    SyntheticSizeCell,
    build_study_seed_ledger,
    load_study_design_manifest,
)
from secondaryexploration.experiments.artifacts import load_study_run_summary
from secondaryexploration.experiments.runner import (
    execute_synthetic_study,
    finalize_synthetic_study,
    runtime_environment,
    runtime_environment_fingerprint,
    preflight_synthetic_study,
    validate_frozen_execution_context,
)
from secondaryexploration.experiments import runner as runner_module


_ROOT = Path(__file__).resolve().parents[3]
_CALIBRATION_MANIFEST = (
    _ROOT / "configs" / "pilot" / "synthetic-calibration-v1.json"
)
_CALIBRATION_EVIDENCE = (
    _ROOT / "results" / "pilot" / "synthetic-calibration-v1" / "evidence.json"
)
_PRECISION = _ROOT / "results" / "planning" / "formal-precision-v1.json"
_SMALL_PIPELINE = _ROOT / "configs" / "pilot" / "synthetic-pipeline-v1.json"
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
    def test_code_snapshot_rejects_old_or_missing_revision(self) -> None:
        ok = Mock(returncode=0, stdout="", stderr="")
        differs = Mock(returncode=1, stdout="", stderr="")
        missing = Mock(returncode=128, stdout="", stderr="")

        with patch.object(runner_module.subprocess, "run", side_effect=(ok, ok, ok)):
            runner_module._verify_execution_code_snapshot(_ROOT, "a" * 40)
        with patch.object(runner_module.subprocess, "run", side_effect=(ok, differs)):
            with self.assertRaisesRegex(StudyManifestError, "does not match"):
                runner_module._verify_execution_code_snapshot(_ROOT, "b" * 40)
        with patch.object(runner_module.subprocess, "run", return_value=missing):
            with self.assertRaisesRegex(StudyManifestError, "does not match"):
                runner_module._verify_execution_code_snapshot(_ROOT, "c" * 40)

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
        self.assertEqual(result["selected_block_count"], 240)
        self.assertEqual(result["worker_count"], 1)
        self.assertEqual(result["worker_index"], 0)
        self.assertEqual(result["manifest_fingerprint"], manifest.fingerprint)
        self.assertEqual(output_root.exists(), existed_before)

    def test_worker_partitions_are_exhaustive_disjoint_and_canonical(self) -> None:
        ledger = build_study_seed_ledger(_formal_manifest())
        all_jobs = runner_module._registered_block_jobs(ledger)
        for worker_count in (1, 2, 3, 7, 241):
            with self.subTest(worker_count=worker_count):
                shards = tuple(
                    runner_module._select_worker_jobs(ledger, worker_count, index)
                    for index in range(worker_count)
                )
                self.assertEqual(
                    tuple(job for shard in shards for job in shard),
                    tuple(
                        job
                        for index in range(worker_count)
                        for job in all_jobs[index::worker_count]
                    ),
                )
                self.assertEqual(
                    {job for shard in shards for job in shard},
                    set(all_jobs),
                )
                self.assertEqual(
                    sum(len(shard) for shard in shards),
                    len(all_jobs),
                )
        for worker_count, worker_index in ((0, 0), (1, -1), (2, 2), (True, 0)):
            with self.subTest(worker_count=worker_count, worker_index=worker_index):
                with self.assertRaises(StudyManifestError):
                    runner_module._select_worker_jobs(
                        ledger,
                        worker_count,
                        worker_index,
                    )

    def test_finalization_of_missing_artifact_does_not_create_summary(self) -> None:
        pilot = load_study_design_manifest(_CALIBRATION_MANIFEST)
        manifest = replace(
            pilot,
            study_id="finalization-missing-artifact-test",
            output_root="outputs/finalization-missing-artifact-test",
            size_cells=(pilot.size_cells[0],),
            parent_replicates=1,
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "pilot.json"
            manifest_path.write_text(manifest.canonical_json, encoding="utf-8")
            summary_path = root / manifest.output_root / "run-summary.json"
            with self.assertRaisesRegex(StudyManifestError, "every registered block"):
                finalize_synthetic_study(
                    manifest_path,
                    workspace_root=root,
                    code_revision=_CODE_REVISION,
                )
            self.assertFalse(summary_path.exists())

    def test_exclusive_block_lock_rejects_duplicate_worker_and_releases(self) -> None:
        with TemporaryDirectory() as directory:
            block_root = Path(directory) / "blocks"
            first = runner_module._acquire_block_lock(block_root, "n0030-r0000-er_gnm")
            with self.assertRaisesRegex(StudyManifestError, "exclusively locked"):
                runner_module._acquire_block_lock(block_root, "n0030-r0000-er_gnm")
            first.unlink()
            second = runner_module._acquire_block_lock(block_root, "n0030-r0000-er_gnm")
            self.assertTrue(second.exists())
            second.unlink()

    def test_shards_publish_no_summary_until_strict_finalization(self) -> None:
        tracked = load_study_design_manifest(_SMALL_PIPELINE)
        manifest = replace(
            tracked,
            study_id="sharded-runner-integration",
            output_root="outputs/sharded-runner-integration",
            size_cells=(tracked.size_cells[0],),
            parent_replicates=1,
            requests_per_node=1,
            topology_search=replace(
                tracked.topology_search,
                proposal_budget=12,
                maximum_rounds=1,
            ),
            capacity_search=replace(
                tracked.capacity_search,
                evaluation_budget=2,
            ),
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "sharded.json"
            manifest_path.write_text(manifest.canonical_json, encoding="utf-8")
            summary_path = root / manifest.output_root / "run-summary.json"
            block_root = root / manifest.output_root / "blocks"
            for worker_index in (0, 1):
                execute_synthetic_study(
                    manifest_path,
                    workspace_root=root,
                    code_revision=_CODE_REVISION,
                    worker_count=2,
                    worker_index=worker_index,
                )
                self.assertFalse(summary_path.exists())
            self.assertEqual(len(tuple(block_root.glob("*.json"))), 3)

            finalized = finalize_synthetic_study(
                manifest_path,
                workspace_root=root,
                code_revision=_CODE_REVISION,
            )
            self.assertEqual(finalized, summary_path)
            summary = load_study_run_summary(
                summary_path,
                manifest=manifest,
                ledger=build_study_seed_ledger(manifest),
                code_revision=_CODE_REVISION,
                environment=runtime_environment(),
            )
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["completed_block_count"], 3)

            before = summary_path.read_text(encoding="utf-8")
            next(block_root.glob("*.json")).write_text("{}", encoding="utf-8")
            with self.assertRaises(StudyManifestError):
                finalize_synthetic_study(
                    manifest_path,
                    workspace_root=root,
                    code_revision=_CODE_REVISION,
                )
            self.assertEqual(summary_path.read_text(encoding="utf-8"), before)

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
