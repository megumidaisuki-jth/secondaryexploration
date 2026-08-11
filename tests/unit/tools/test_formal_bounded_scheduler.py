"""Tests for the memory-bounded formal singleton scheduler."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from secondaryexploration.experiments import StudyManifestError
from tools import formal_bounded_scheduler as target


_ROOT = Path(__file__).resolve().parents[3]


class _FakeProcess:
    next_pid = 1000

    def __init__(self, command, *, returncode=0):
        self.command = command
        self.returncode = returncode
        self.pid = _FakeProcess.next_pid
        _FakeProcess.next_pid += 1

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class FormalBoundedSchedulerTests(unittest.TestCase):
    @staticmethod
    def _fake_identities(process_ids):
        return [
            {
                "process_id": pid,
                "parent_process_id": os.getpid(),
                "process_creation_time": f"time-{pid}",
                "command_line": "platform-unavailable",
            }
            for pid in process_ids
        ]

    def test_exact_240_singleton_partition(self) -> None:
        rows = target.canonical_singleton_schedule(
            _ROOT / "configs/formal/synthetic-formal-v1.json"
        )
        self.assertEqual(len(rows), 240)
        self.assertEqual([row["worker_index"] for row in rows], list(range(240)))
        self.assertEqual(len({row["block_key"] for row in rows}), 240)

    def test_commands_bind_frozen_sources_and_singleton_indices(self) -> None:
        python = Path(r"C:\frozen\python.exe")
        command = target._runner_command(python, 173)
        self.assertEqual(command[0], str(python))
        self.assertIn(target.EXECUTION_REVISION, command)
        self.assertEqual(command[command.index("--worker-count") + 1], "240")
        self.assertEqual(command[command.index("--worker-index") + 1], "173")
        self.assertIn("--precision", command)
        self.assertIn("--calibration-evidence", command)
        self.assertIn("--calibration-manifest", command)

    def test_batch_rejects_more_than_six_duplicate_and_low_memory(self) -> None:
        rows = [
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(7)
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(StudyManifestError, "batch size"):
                target.run_batch(
                    session_dir=root,
                    session_fingerprint="a" * 64,
                    batch_number=0,
                    rows=rows,
                    python=Path("python.exe"),
                )
            with self.assertRaisesRegex(StudyManifestError, "duplicate"):
                target.run_batch(
                    session_dir=root,
                    session_fingerprint="a" * 64,
                    batch_number=0,
                    rows=[rows[0], rows[0]],
                    python=Path("python.exe"),
                )
            with self.assertRaisesRegex(StudyManifestError, "memory"):
                target.run_batch(
                    session_dir=root,
                    session_fingerprint="a" * 64,
                    batch_number=0,
                    rows=rows[:1],
                    python=Path("python.exe"),
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES - 1,
                )

    def test_session_validation_rejects_duplicate_index_and_fingerprint_tamper(self) -> None:
        schedule = [
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(240)
        ]
        record = {
            "schema_version": target.SCHEMA_VERSION,
            "status": "authorized-memory-only-operational-amendment",
            "session_id": "session-0001",
            "created_at_utc": "2026-08-11T00:00:00.000Z",
            "orchestration_revision": "b" * 40,
            "execution_revision": target.EXECUTION_REVISION,
            "python_executable": str(Path("C:/frozen/python.exe")),
            "manifest_fingerprint": target.FORMAL_MANIFEST_FINGERPRINT,
            "logical_shard_count": 240,
            "maximum_concurrency": 6,
            "minimum_available_memory_bytes": target.MIN_AVAILABLE_MEMORY_BYTES,
            "initial_checkpoint_fingerprint": target.CHECKPOINT_166_FINGERPRINT,
            "initial_completed_block_count": 166,
            "initial_block_registry_fingerprint": "c" * 64,
            "sources": [
                {"path": path, "sha256": "d" * 64}
                for path in target._SOURCE_PATHS
            ],
            "schedule": schedule,
            "limitations": list(target._SESSION_LIMITATIONS),
        }
        record["fingerprint"] = target._fingerprint(record)
        canonical_schedule = [dict(row) for row in schedule]
        target.validate_session_record(
            record, verify_sources=False, expected_schedule=canonical_schedule
        )
        missing = dict(record)
        missing.pop("sources")
        missing["fingerprint"] = target._fingerprint(missing)
        with self.assertRaisesRegex(StudyManifestError, "fields"):
            target.validate_session_record(missing, verify_sources=False)
        schedule[0]["block_key"], schedule[1]["block_key"] = (
            schedule[1]["block_key"],
            schedule[0]["block_key"],
        )
        record["fingerprint"] = target._fingerprint(record)
        with self.assertRaisesRegex(StudyManifestError, "index-to-key"):
            target.validate_session_record(
                record,
                verify_sources=False,
                expected_schedule=canonical_schedule,
            )
        schedule[0]["block_key"], schedule[1]["block_key"] = (
            schedule[1]["block_key"],
            schedule[0]["block_key"],
        )
        schedule[-1]["worker_index"] = 238
        record["fingerprint"] = target._fingerprint(record)
        with self.assertRaisesRegex(StudyManifestError, "canonical"):
            target.validate_session_record(record, verify_sources=False)
        schedule[-1]["worker_index"] = 239
        record["fingerprint"] = "f" * 64
        with self.assertRaisesRegex(StudyManifestError, "mismatch"):
            target.validate_session_record(record, verify_sources=False)

    def test_quiescent_gate_rejects_lock_temp_foreign_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            block_root = root / "outputs/formal/synthetic-formal-v1/blocks"
            lock_root = block_root / ".locks"
            lock_root.mkdir(parents=True)
            (lock_root / "x.lock").write_text("pid=1", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "locks"):
                target._assert_quiescent_output(root, {"x"})
            (lock_root / "x.lock").unlink()
            (block_root / ".x.json.tmp").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "unknown"):
                target._assert_quiescent_output(root, {"x"})
            (block_root / ".x.json.tmp").unlink()
            (block_root / "foreign.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "foreign"):
                target._assert_quiescent_output(root, {"x"})
            (block_root / "foreign.json").unlink()
            summary = block_root.parent / "run-summary.json"
            summary.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "summary"):
                target._assert_quiescent_output(root, {"x"})

    def test_run_batch_caps_concurrency_and_closes_hash_chain(self) -> None:
        rows = [
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            fake_root = session / "workspace"
            block_root = fake_root / "outputs/formal/synthetic-formal-v1/blocks"
            block_root.mkdir(parents=True)
            processes = []

            def popen(command, **kwargs):
                index = int(command[command.index("--worker-index") + 1])
                (block_root / f"key-{index}.json").write_text(
                    f"artifact-{index}", encoding="utf-8"
                )
                process = _FakeProcess(command)
                processes.append(process)
                return process

            with mock.patch.object(target, "_ROOT", fake_root):
                result = target.run_batch(
                    session_dir=session,
                    session_fingerprint="a" * 64,
                    batch_number=0,
                    rows=rows,
                    python=Path("python.exe"),
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=popen,
                    identity_reader=self._fake_identities,
                )
            self.assertEqual(result["status"], "batch-complete-zero-exit")
            self.assertEqual(result["launched_process_count"], 6)
            self.assertEqual(result["configured_concurrency_ceiling"], 6)
            self.assertEqual(len(processes), 6)
            self.assertTrue(all(row["artifact_sha256"] for row in result["workers"]))
            self.assertEqual(result["fingerprint"], target._fingerprint(result))

    def test_nonzero_or_nonempty_stderr_stops_batch(self) -> None:
        row = {"worker_index": 0, "block_key": "key-0"}
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            fake_root = session / "workspace"
            block_root = fake_root / "outputs/formal/synthetic-formal-v1/blocks"
            block_root.mkdir(parents=True)

            def failing_popen(command, **kwargs):
                (block_root / "key-0.json").write_text("artifact", encoding="utf-8")
                kwargs["stderr"].write(b"failure")
                kwargs["stderr"].flush()
                return _FakeProcess(command, returncode=1)

            with mock.patch.object(target, "_ROOT", fake_root):
                with self.assertRaisesRegex(StudyManifestError, "failure"):
                    target.run_batch(
                        session_dir=session,
                        session_fingerprint="a" * 64,
                        batch_number=0,
                        rows=[row],
                        python=Path("python.exe"),
                        memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                        popen=failing_popen,
                        identity_reader=self._fake_identities,
                    )
            final = target._load_json(
                session / "batch-000.final.json", "failed finalization"
            )
            self.assertEqual(final["status"], "batch-failed-stop")
            with mock.patch.object(target, "_ROOT", fake_root):
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={0: row},
                    expected_python=Path("python.exe"),
                )
            self.assertEqual((completed, count, incomplete), (set(), 1, None))

            def succeeding_popen(command, **kwargs):
                return _FakeProcess(command)

            with mock.patch.object(target, "_ROOT", fake_root):
                target.run_batch(
                    session_dir=session,
                    session_fingerprint="a" * 64,
                    batch_number=1,
                    rows=[row],
                    python=Path("python.exe"),
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=succeeding_popen,
                    identity_reader=self._fake_identities,
                )
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={0: row},
                    expected_python=Path("python.exe"),
                )
            self.assertEqual((completed, count, incomplete), ({0}, 2, None))

    def test_launch_without_started_can_close_and_retry_all_indices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / "session"
            session.mkdir()
            fake_workspace = root / "workspace"
            block_root = fake_workspace / "outputs/formal/synthetic-formal-v1/blocks"
            (block_root / ".locks").mkdir(parents=True)
            row = {"worker_index": 0, "block_key": "key-0"}
            command = target._runner_command(Path("python.exe"), 0)
            command[command.index("--workspace-root") + 1] = str(fake_workspace)
            launch = {
                "schema_version": target.BATCH_SCHEMA_VERSION,
                "status": "planned-before-launch",
                "session_fingerprint": "a" * 64,
                "batch_number": 0,
                "started_at_utc": "2026-08-11T00:00:00.000Z",
                "available_memory_bytes_before_launch": target.MIN_AVAILABLE_MEMORY_BYTES,
                "workers": [
                    {
                        "worker_index": 0,
                        "block_key": "key-0",
                        "command": command,
                        "command_sha256": hashlib.sha256(
                            __import__("subprocess").list2cmdline(command).encode("utf-8")
                        ).hexdigest(),
                        "stdout_file": "out.txt",
                        "stderr_file": "err.txt",
                    }
                ],
            }
            launch["fingerprint"] = target._fingerprint(launch)
            launch_path = session / "batch-000.launch.json"
            target._write_create_only(launch_path, launch)
            with mock.patch.object(target, "_ROOT", fake_workspace), mock.patch.object(
                target, "_formal_runner_processes", return_value=[]
            ):
                recovery_path = target.recover_incomplete_batch(
                    session,
                    launch_path,
                    session_fingerprint="a" * 64,
                    expected_keys={"key-0"},
                )
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={0: row},
                    expected_python=Path("python.exe"),
                )
            recovery = target._load_json(recovery_path, "no-start recovery")
            self.assertIsNone(recovery["started_fingerprint"])
            self.assertIn("without-complete-start", recovery["status"])
            self.assertEqual((completed, count, incomplete), (set(), 1, None))

    def test_create_only_witness_rejects_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "witness.json"
            target._write_create_only(path, {"value": 1})
            before = path.read_bytes()
            with self.assertRaisesRegex(StudyManifestError, "already exists"):
                target._write_create_only(path, {"value": 2})
            self.assertEqual(path.read_bytes(), before)

    def test_interrupted_batch_recovery_keeps_indices_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / "session"
            session.mkdir()
            fake_workspace = root / "workspace"
            block_root = fake_workspace / "outputs/formal/synthetic-formal-v1/blocks"
            (block_root / ".locks").mkdir(parents=True)
            artifact = block_root / "key-0.json"
            artifact.write_text("atomic", encoding="utf-8")
            command = target._runner_command(Path("python.exe"), 0)
            launch = {
                "schema_version": target.BATCH_SCHEMA_VERSION,
                "status": "planned-before-launch",
                "session_fingerprint": "a" * 64,
                "batch_number": 0,
                "workers": [
                    {
                        "worker_index": 0,
                        "block_key": "key-0",
                        "command": command,
                        "command_sha256": hashlib.sha256(
                            __import__("subprocess").list2cmdline(command).encode("utf-8")
                        ).hexdigest(),
                        "stdout_file": "out.txt",
                        "stderr_file": "err.txt",
                    }
                ],
            }
            launch["fingerprint"] = target._fingerprint(launch)
            launch_path = session / "batch-000.launch.json"
            target._write_create_only(launch_path, launch)
            started = {
                "schema_version": "formal-bounded-scheduler-started.v1",
                "status": "all-planned-children-started",
                "session_fingerprint": "a" * 64,
                "batch_number": 0,
                "launch_fingerprint": launch["fingerprint"],
                "captured_at_utc": "2026-08-11T00:00:01.000Z",
                "scheduler_process_id": os.getpid(),
                "workers": [
                    {
                        "worker_index": 0,
                        "block_key": "key-0",
                        "process_id": 1234,
                        "parent_process_id": os.getpid(),
                        "process_creation_time": "creation-1234",
                        "command_line": "platform-unavailable",
                        "command_line_sha256": launch["workers"][0]["command_sha256"],
                        "stdout_file": "out.txt",
                        "stderr_file": "err.txt",
                    }
                ],
            }
            started["fingerprint"] = target._fingerprint(started)
            target._write_create_only(session / "batch-000.started.json", started)
            with mock.patch.object(target, "_ROOT", fake_workspace), mock.patch.object(
                target, "_formal_runner_processes", return_value=[]
            ), mock.patch.object(
                target,
                "_process_identities",
                return_value=[
                    {
                        "process_id": 1234,
                        "parent_process_id": 7,
                        "process_creation_time": "reused-different-identity",
                        "command_line": "unrelated",
                    }
                ],
            ):
                recovery_path = target.recover_incomplete_batch(
                    session,
                    launch_path,
                    session_fingerprint="a" * 64,
                    expected_keys={"key-0"},
                )
            recovery = target._load_json(recovery_path, "recovery")
            self.assertEqual(recovery["workers"][0]["artifact_state"], "atomic-file-present")
            self.assertIn("remains-pending", recovery["limitations"][1])

    def test_global_lease_rejects_a_second_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_root = Path(directory)

            def identities(process_ids):
                return [
                    {
                        "process_id": pid,
                        "parent_process_id": 99,
                        "process_creation_time": f"creation-{pid}",
                        "command_line": "scheduler",
                    }
                    for pid in process_ids
                ]

            with mock.patch.object(target, "_ROOT", fake_root):
                lease_path, lease = target.acquire_global_lease(
                    session_id="session-0001",
                    orchestration_revision="b" * 40,
                    recover_stale=False,
                    process_reader=identities,
                    runner_reader=lambda: [],
                )
                with self.assertRaisesRegex(StudyManifestError, "global lease"):
                    target.acquire_global_lease(
                        session_id="session-0002",
                        orchestration_revision="b" * 40,
                        recover_stale=False,
                        process_reader=identities,
                        runner_reader=lambda: [],
                    )
                target.release_global_lease(lease_path, lease)
                self.assertFalse(lease_path.exists())

    def test_global_lease_rejects_legacy_or_external_formal_runner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_root = Path(directory)

            def identities(process_ids):
                return [
                    {
                        "process_id": pid,
                        "parent_process_id": 99,
                        "process_creation_time": f"creation-{pid}",
                        "command_line": "scheduler",
                    }
                    for pid in process_ids
                ]

            with mock.patch.object(target, "_ROOT", fake_root):
                with self.assertRaisesRegex(StudyManifestError, "formal runner"):
                    target.acquire_global_lease(
                        session_id="session-0001",
                        orchestration_revision="b" * 40,
                        recover_stale=False,
                        process_reader=identities,
                        runner_reader=lambda: [
                            {"ProcessId": 123, "CommandLine": "--worker-count 6"}
                        ],
                    )

    def test_history_replay_rejects_log_or_artifact_tampering(self) -> None:
        row = {"worker_index": 0, "block_key": "key-0"}
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            fake_root = session / "workspace"
            block_root = fake_root / "outputs/formal/synthetic-formal-v1/blocks"
            block_root.mkdir(parents=True)

            def popen(command, **kwargs):
                (block_root / "key-0.json").write_text("artifact", encoding="utf-8")
                return _FakeProcess(command)

            with mock.patch.object(target, "_ROOT", fake_root):
                target.run_batch(
                    session_dir=session,
                    session_fingerprint="a" * 64,
                    batch_number=0,
                    rows=[row],
                    python=Path("python.exe"),
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=popen,
                    identity_reader=self._fake_identities,
                )
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={0: row},
                    expected_python=Path("python.exe"),
                )
                self.assertEqual((completed, count, incomplete), ({0}, 1, None))
                (session / "batch-000.worker-000.stdout.txt").write_text(
                    "tamper", encoding="utf-8"
                )
                with self.assertRaisesRegex(StudyManifestError, "log hash"):
                    target._validate_batch_history(
                        session,
                        session_fingerprint="a" * 64,
                        expected_rows={0: row},
                        expected_python=Path("python.exe"),
                    )
                (session / "batch-000.worker-000.stdout.txt").write_bytes(b"")
                (block_root / "key-0.json").write_text("tampered", encoding="utf-8")
                with self.assertRaisesRegex(StudyManifestError, "artifact hash"):
                    target._validate_batch_history(
                        session,
                        session_fingerprint="a" * 64,
                        expected_rows={0: row},
                        expected_python=Path("python.exe"),
                    )


if __name__ == "__main__":
    unittest.main()
