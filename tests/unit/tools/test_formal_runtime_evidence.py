"""Tests for the strict formal runtime launch-gate evidence."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from secondaryexploration.experiments import StudyManifestError
from tools import formal_runtime_evidence as target


_MANIFEST = target._FORMAL_MANIFEST_FINGERPRINT
_EVIDENCE = "d" * 40


def _launch_batch():
    processes = []
    for index, (stem, size, model, full_replay) in enumerate(target._GRID):
        suffix = "" if full_replay else " --skip-replay"
        command = (
            '"python.exe" tools\\profile_synthetic_block.py '
            "configs\\formal\\synthetic-formal-v1.json "
            f"--node-count {size} --parent-replicate 0 --model {model}{suffix} "
            f"--batch-id {target._BATCH_ID} --profile-id {stem}"
        )
        processes.append(
            {
                "profile_id": stem,
                "process_id": 100 + index,
                "parent_process_id": 42,
                "start_time_utc": "2026-08-09T07:33:14.000Z",
                "command_line": command,
                "command_line_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
            }
        )
    value = {
        "schema_version": "formal-runtime-profile-launch.v1",
        "status": "six-workers-observed-live",
        "manifest_fingerprint": _MANIFEST,
        "profiler_revision": _EVIDENCE,
        "launcher_revision": _EVIDENCE,
        "batch_id": target._BATCH_ID,
        "worker_count": 6,
        "captured_at_utc": "2026-08-09T07:40:00.000Z",
        "start_skew_milliseconds": 0,
        "machine": {
            "logical_processors": 16,
            "total_physical_memory_bytes": 10_000,
        },
        "processes": processes,
    }
    value["batch_fingerprint"] = target._fingerprint(value)
    return value


def _resume_state():
    value = {
        "output_root": "outputs/formal/synthetic-formal-v1",
        "manifest_fingerprint": _MANIFEST,
        "seed_ledger_fingerprint": "1" * 64,
        "calibration_evidence_fingerprint": "2" * 64,
        "precision_fingerprint": "3" * 64,
        "environment_fingerprint": "4" * 64,
        "retained_block_keys": list(target._RETAINED_BLOCK_KEYS),
        "artifact_fingerprints": [f"{index + 16:064x}" for index in range(15)],
        "result_fingerprints": [f"{index + 64:064x}" for index in range(15)],
        "lock_file_count": 0,
        "run_summary_present": False,
    }
    return value


def _batch_finalization(directory: Path, launch_batch):
    records = []
    for index, (stem, _, _, _) in enumerate(target._GRID):
        stdout = directory / f"{stem}.stdout.json"
        stderr = directory / f"{stem}.stderr.txt"
        records.append(
            {
                "profile_id": stem,
                "process_id": 100 + index,
                "exit_code": 0,
                "stdout_file": stdout.name,
                "stderr_file": stderr.name,
                "stdout_sha256": hashlib.sha256(stdout.read_bytes()).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr.read_bytes()).hexdigest(),
            }
        )
    value = {
        "schema_version": "formal-runtime-profile-finalization.v1",
        "status": "six-workers-exited-zero",
        "batch_id": target._BATCH_ID,
        "launcher_revision": _EVIDENCE,
        "launch_batch_fingerprint": launch_batch["batch_fingerprint"],
        "completed_at_utc": "2026-08-09T12:40:00.000Z",
        "records": records,
    }
    value["finalization_fingerprint"] = target._fingerprint(value)
    return value


def _write_grid(directory: Path, *, peak: int = 100, n240_er_ns: int = 1_000) -> None:
    for index, (stem, size, model, full_replay) in enumerate(target._GRID):
        generation = n240_er_ns if stem == "n240-er-r0-full" else 500
        record = {
            "diagnostic": "exact-synthetic-parent-block-profile.v2",
            "batch_id": target._BATCH_ID,
            "profile_id": stem,
            "process_id": 100 + index,
            "manifest_fingerprint": _MANIFEST,
            "environment_fingerprint": "4" * 64,
            "node_count": size,
            "parent_replicate": 0,
            "parent_model": model,
            "result_fingerprint": hashlib.sha256(stem.encode("utf-8")).hexdigest(),
            "generation_ns": generation,
            "validation_ns": 600 if full_replay else None,
            "peak_working_set_bytes": peak,
            "wrote_formal_artifacts": False,
        }
        (directory / f"{stem}.stdout.json").write_text(
            json.dumps(record) + "\n", encoding="utf-8"
        )
        (directory / f"{stem}.stderr.txt").write_bytes(b"")


class FormalRuntimeEvidenceTests(unittest.TestCase):
    def _build(self, directory: Path, *, memory: int = 10_000):
        launch_batch = _launch_batch()
        return target._build_runtime_profile_evidence(
            SimpleNamespace(
                study_id="synthetic-formal-v1",
                fingerprint=_MANIFEST,
                code_revision=target._EXECUTION_REVISION,
            ),
            directory,
            evidence_revision=_EVIDENCE,
            total_physical_memory_bytes=memory,
            logical_processors=16,
            launch_batch=launch_batch,
            batch_finalization=_batch_finalization(directory, launch_batch),
            formal_resume_state=_resume_state(),
        )

    def test_exact_grid_builds_and_replays_the_six_worker_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root)
            evidence = self._build(root)
        target.validate_runtime_profile_evidence(evidence)
        self.assertEqual(len(evidence["records"]), 6)
        self.assertEqual(
            evidence["resource_envelope"]["six_worker_memory_ceiling_bytes"], 600
        )
        self.assertEqual(
            evidence["records"][0]["mode"], "generation-plus-exact-replay"
        )
        self.assertEqual(evidence["records"][1]["mode"], "generation-only")

    def test_public_builder_strict_loads_paths_snapshot_and_machine(self) -> None:
        manifest = SimpleNamespace(
            study_id="synthetic-formal-v1",
            fingerprint=_MANIFEST,
            code_revision=target._EXECUTION_REVISION,
        )
        expected = {"strict": True}
        with patch.object(
            target, "load_study_design_manifest", return_value=manifest
        ) as load_manifest, patch.object(
            target, "_verify_snapshot"
        ) as verify, patch.object(
            target, "_machine_resources", return_value=(10_000, 16)
        ), patch.object(
            target, "_load_launch_batch", return_value=_launch_batch()
        ), patch.object(
            target,
            "_load_batch_finalization",
            return_value={"finalized": True},
        ), patch.object(
            target, "_load_formal_resume_state", return_value=_resume_state()
        ), patch.object(
            target, "_build_runtime_profile_evidence", return_value=expected
        ) as private_build:
            observed = target.build_runtime_profile_evidence(
                Path("formal.json"),
                Path("profiles"),
                calibration_manifest_path=Path("calibration.json"),
                calibration_evidence_path=Path("calibration-evidence.json"),
                precision_path=Path("precision.json"),
                evidence_revision=_EVIDENCE,
            )
        self.assertIs(observed, expected)
        load_manifest.assert_called_once_with(Path("formal.json"))
        verify.assert_called_once_with(target._ROOT, _EVIDENCE)
        private_build.assert_called_once()

    def test_nonempty_stderr_and_wrong_replay_mode_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root)
            (root / "n120-er-r0-full.stderr.txt").write_text("warning", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "stderr"):
                self._build(root)

            (root / "n120-er-r0-full.stderr.txt").write_bytes(b"")
            path = root / "n120-ba-r0-generation.stdout.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["validation_ns"] = 1
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "generation-only"):
                self._build(root)

    def test_batch_pid_and_finalized_stdout_hash_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root)
            path = root / "n120-er-r0-full.stdout.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["process_id"] += 1
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "identity"):
                self._build(root)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root)
            launch = _launch_batch()
            finalization = _batch_finalization(root, launch)
            finalization["records"][0]["stdout_sha256"] = "f" * 64
            finalization["finalization_fingerprint"] = target._fingerprint(
                {
                    key: value
                    for key, value in finalization.items()
                    if key != "finalization_fingerprint"
                }
            )
            with self.assertRaisesRegex(StudyManifestError, "finalization"):
                target._build_runtime_profile_evidence(
                    SimpleNamespace(
                        study_id="synthetic-formal-v1",
                        fingerprint=_MANIFEST,
                        code_revision=target._EXECUTION_REVISION,
                    ),
                    root,
                    evidence_revision=_EVIDENCE,
                    total_physical_memory_bytes=10_000,
                    logical_processors=16,
                    launch_batch=launch,
                    batch_finalization=finalization,
                    formal_resume_state=_resume_state(),
                )

    def test_extra_profile_pair_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root)
            (root / "extra.stdout.json").write_text("{}", encoding="utf-8")
            (root / "extra.stderr.txt").write_bytes(b"")
            with self.assertRaisesRegex(StudyManifestError, "file registry"):
                self._build(root)

    def test_memory_and_throughput_gates_reject_before_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root, peak=1_000)
            with self.assertRaisesRegex(StudyManifestError, "50 percent"):
                self._build(root, memory=10_000)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root, n240_er_ns=target._THROUGHPUT_CEILING_NS + 1)
            with self.assertRaisesRegex(StudyManifestError, "190 minutes"):
                self._build(root)

    def test_rehashed_nested_envelope_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root)
            evidence = self._build(root)
        forged = deepcopy(evidence)
        forged["resource_envelope"]["six_worker_memory_ceiling_bytes"] += 1
        forged["evidence_fingerprint"] = target._fingerprint(
            {key: value for key, value in forged.items() if key != "evidence_fingerprint"}
        )
        with self.assertRaisesRegex(StudyManifestError, "arithmetic"):
            target.validate_runtime_profile_evidence(forged)

    def test_rehashed_formal_resume_state_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root)
            evidence = self._build(root)
        forged = deepcopy(evidence)
        forged["formal_resume_state"]["lock_file_count"] = 1
        forged["evidence_fingerprint"] = target._fingerprint(
            {key: value for key, value in forged.items() if key != "evidence_fingerprint"}
        )
        with self.assertRaisesRegex(StudyManifestError, "resume state"):
            target.validate_runtime_profile_evidence(forged)

    def test_strict_loader_requires_complete_raw_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_grid(root)
            evidence = self._build(root)
            path = root / "evidence.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            kwargs = {
                "manifest_path": Path("formal.json"),
                "profile_dir": root,
                "calibration_manifest_path": Path("calibration.json"),
                "calibration_evidence_path": Path("calibration-evidence.json"),
                "precision_path": Path("precision.json"),
                "evidence_revision": _EVIDENCE,
            }
            with patch.object(
                target, "build_runtime_profile_evidence", return_value=evidence
            ):
                self.assertEqual(
                    target.load_runtime_profile_evidence(path, **kwargs), evidence
                )
            rebuilt = deepcopy(evidence)
            rebuilt["records"][0]["generation_ns"] += 1
            with patch.object(
                target, "build_runtime_profile_evidence", return_value=rebuilt
            ):
                with self.assertRaisesRegex(StudyManifestError, "raw replay"):
                    target.load_runtime_profile_evidence(path, **kwargs)

    def test_machine_resource_probe_returns_positive_values(self) -> None:
        memory, processors = target._machine_resources()
        self.assertGreater(memory, 0)
        self.assertGreaterEqual(processors, 6)

    def test_snapshot_rejects_revision_without_evidence_tool(self) -> None:
        completed = [
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=1),
        ]
        with patch.object(target.subprocess, "run", side_effect=completed):
            with self.assertRaisesRegex(StudyManifestError, "absent"):
                target._verify_snapshot(Path("."), _EVIDENCE)

    def test_pre_resume_layout_rejects_any_lock_directory_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocks = root / "blocks"
            blocks.mkdir()
            for key in target._RETAINED_BLOCK_KEYS:
                (blocks / f"{key}.json").write_text("{}", encoding="utf-8")
            locks = blocks / ".locks"
            locks.mkdir()
            target._validate_pre_resume_layout(root)
            (locks / "nested-entry").mkdir()
            with self.assertRaisesRegex(StudyManifestError, "lock directory"):
                target._validate_pre_resume_layout(root)

    def test_pre_resume_layout_rejects_extra_non_json_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocks = root / "blocks"
            blocks.mkdir()
            for key in target._RETAINED_BLOCK_KEYS:
                (blocks / f"{key}.json").write_text("{}", encoding="utf-8")
            (blocks / ".interrupted.tmp").write_text("partial", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "registry"):
                target._validate_pre_resume_layout(root)


if __name__ == "__main__":
    unittest.main()
