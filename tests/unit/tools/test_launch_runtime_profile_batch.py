"""Tests for the bound six-worker runtime profiler launcher."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from secondaryexploration.experiments import StudyManifestError
from tools import formal_runtime_evidence as evidence
from tools import launch_runtime_profile_batch as target


class LaunchRuntimeProfileBatchTests(unittest.TestCase):
    def test_commands_bind_batch_profile_and_replay_mode(self) -> None:
        for stem, size, model, full_replay in evidence._GRID:
            command = target._command(stem, size, model, full_replay)
            joined = " ".join(command)
            self.assertIn(evidence._BATCH_ID, joined)
            self.assertIn(stem, joined)
            self.assertEqual("--skip-replay" in command, not full_replay)

    def test_finalization_binds_pid_exit_code_and_file_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            processes = []
            for index, (stem, size, model, full_replay) in enumerate(evidence._GRID):
                stdout = root / f"{stem}.stdout.json"
                stderr = root / f"{stem}.stderr.txt"
                stdout.write_text(f"record-{stem}", encoding="utf-8")
                stderr.write_bytes(b"")
                processes.append(
                    {
                        "profile_id": stem,
                        "process": SimpleNamespace(pid=100 + index),
                        "exit_code": 0,
                        "stdout_path": stdout,
                        "stderr_path": stderr,
                    }
                )
            launch = {
                "batch_fingerprint": "a" * 64,
                "captured_at_utc": "2026-08-09T07:40:00.000Z",
                "processes": [
                    {"profile_id": stem, "process_id": 100 + index}
                    for index, (stem, _, _, _) in enumerate(evidence._GRID)
                ],
            }
            record = target._finalization_record(
                processes, launch, launcher_revision="d" * 40
            )
        self.assertEqual(record["status"], "six-workers-exited-zero")
        self.assertTrue(all(item["exit_code"] == 0 for item in record["records"]))

    def test_launch_record_rejects_start_skew_above_two_seconds(self) -> None:
        base = datetime(2026, 8, 9, 7, 33, 14, tzinfo=timezone.utc)
        processes = []
        for index, (stem, size, model, full_replay) in enumerate(evidence._GRID):
            started = base if index < 5 else base.replace(second=17)
            processes.append(
                {
                    "profile_id": stem,
                    "command": target._command(stem, size, model, full_replay),
                    "process": SimpleNamespace(pid=100 + index),
                    "start_datetime": started,
                    "start_time_utc": started.isoformat(timespec="milliseconds").replace(
                        "+00:00", "Z"
                    ),
                }
            )
        with self.assertRaisesRegex(StudyManifestError, "skew"):
            target._launch_record(
                processes,
                launcher_revision="d" * 40,
                memory=10_000,
                processors=16,
            )

    def test_live_witness_rejects_an_exited_worker(self) -> None:
        processes = [
            {"process": SimpleNamespace(poll=lambda: None)} for _ in evidence._GRID
        ]
        target._assert_workers_live(processes)
        processes[-1] = {"process": SimpleNamespace(poll=lambda: 1)}
        with self.assertRaisesRegex(StudyManifestError, "not all live"):
            target._assert_workers_live(processes)

    def test_launcher_environment_must_match_frozen_manifest(self) -> None:
        manifest = SimpleNamespace(
            fingerprint=evidence._FORMAL_MANIFEST_FINGERPRINT,
            environment_fingerprint="a" * 64,
        )
        with unittest.mock.patch.object(
            target, "load_study_design_manifest", return_value=manifest
        ), unittest.mock.patch.object(
            target, "runtime_environment", return_value={"runtime": "test"}
        ), unittest.mock.patch.object(
            target, "runtime_environment_fingerprint", return_value="b" * 64
        ):
            with self.assertRaisesRegex(StudyManifestError, "environment"):
                target._verify_launcher_environment()


if __name__ == "__main__":
    unittest.main()
