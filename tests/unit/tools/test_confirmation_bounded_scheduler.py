"""Focused tests for the bounded confirmation singleton scheduler."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import subprocess
import sys
import unittest
from unittest import mock

from secondaryexploration.experiments import StudyManifestError
from secondaryexploration.topology import ParentGraphModel
from tools import confirmation_bounded_scheduler as target


_ROOT = Path(__file__).resolve().parents[3]


class _FakeProcess:
    next_pid = 5000

    def __init__(self, command, returncode=0):
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


class ConfirmationBoundedSchedulerTests(unittest.TestCase):
    @staticmethod
    def _identities(process_ids):
        return [
            {
                "process_id": process_id,
                "parent_process_id": os.getpid(),
                "process_creation_time": f"created-{process_id}",
                "command_line": "platform-unavailable",
            }
            for process_id in process_ids
        ]

    def test_exact_confirmation_240_singleton_partition(self) -> None:
        rows = target.canonical_singleton_schedule(
            _ROOT / "configs/confirmation/synthetic-confirmation-v1.json"
        )
        self.assertEqual(len(rows), 240)
        self.assertEqual([row["worker_index"] for row in rows], list(range(240)))
        self.assertEqual(len({row["block_key"] for row in rows}), 240)

    def test_command_binds_confirmation_manifest_and_frozen_sources(self) -> None:
        command = target._runner_command(Path(r"C:\frozen\python.exe"), 239)
        self.assertIn("configs/confirmation/synthetic-confirmation-v1.json", command)
        self.assertEqual(command[command.index("--worker-count") + 1], "240")
        self.assertEqual(command[command.index("--worker-index") + 1], "239")
        self.assertIn(target.EXECUTION_REVISION, command)

    def test_fresh_session_requires_zero_blocks_and_binds_readiness(self) -> None:
        schedule = [
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(target.LOGICAL_SHARD_COUNT)
        ]
        readiness = {"readiness_fingerprint": "a" * 64}
        with mock.patch.object(
            target,
            "_source_record",
            side_effect=lambda path: {"path": path.as_posix(), "sha256": "b" * 64},
        ):
            record = target.build_session_record(
                session_id="confirmation-session-0001",
                orchestration_revision="c" * 40,
                readiness_authorization_revision="d" * 40,
                python=Path(r"C:\frozen\python.exe"),
                environment_fingerprint=target.ENVIRONMENT_FINGERPRINT,
                schedule=schedule,
                observed_blocks={},
                readiness=readiness,
            )
        self.assertEqual(record["initial_completed_block_count"], 0)
        self.assertEqual(record["initial_block_registry_fingerprint"], target._block_registry_fingerprint({}))
        self.assertEqual(record["readiness_fingerprint"], "a" * 64)
        self.assertEqual(record["readiness_authorization_revision"], "d" * 40)
        with mock.patch.object(target, "_source_record", return_value={"path": "x", "sha256": "b" * 64}):
            with self.assertRaisesRegex(StudyManifestError, "zero blocks"):
                target.build_session_record(
                    session_id="confirmation-session-0002",
                    orchestration_revision="c" * 40,
                    readiness_authorization_revision="d" * 40,
                    python=Path(r"C:\frozen\python.exe"),
                    environment_fingerprint=target.ENVIRONMENT_FINGERPRINT,
                    schedule=schedule,
                    observed_blocks={"foreign": Path("foreign.json")},
                    readiness=readiness,
                )

    def test_validate_session_replays_readiness_and_formal_completion(self) -> None:
        schedule = [
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(target.LOGICAL_SHARD_COUNT)
        ]
        sources = [
            {"path": path, "sha256": "b" * 64} for path in target._SOURCE_PATHS
        ]
        record = {
            "schema_version": target.SCHEMA_VERSION,
            "status": "authorized-memory-only-operational-amendment",
            "session_id": "confirmation-session-0003",
            "created_at_utc": "2026-08-11T12:00:00.000Z",
            "orchestration_revision": "c" * 40,
            "execution_revision": target.EXECUTION_REVISION,
            "python_executable": str(Path(r"C:\frozen\python.exe")),
            "environment_fingerprint": target.ENVIRONMENT_FINGERPRINT,
            "manifest_fingerprint": target.CONFIRMATION_MANIFEST_FINGERPRINT,
            "logical_shard_count": target.LOGICAL_SHARD_COUNT,
            "maximum_concurrency": target.MAX_CONCURRENCY,
            "minimum_available_memory_bytes": target.MIN_AVAILABLE_MEMORY_BYTES,
            "readiness_fingerprint": "a" * 64,
            "readiness_authorization_revision": "d" * 40,
            "initial_completed_block_count": 0,
            "initial_block_registry_fingerprint": target._block_registry_fingerprint({}),
            "sources": sources,
            "schedule": schedule,
            "limitations": list(target._SESSION_LIMITATIONS),
        }
        record["fingerprint"] = target._fingerprint(record)
        readiness = {"readiness_fingerprint": "a" * 64}
        with (
            mock.patch.object(target, "_file_sha256", return_value="b" * 64),
            mock.patch.object(
                target,
                "runtime_environment_fingerprint",
                return_value=target.ENVIRONMENT_FINGERPRINT,
            ),
            mock.patch.object(target, "runtime_environment", return_value={}),
            mock.patch.object(target, "_formal_completion_gate") as formal_gate,
            mock.patch.object(target, "_readiness_gate", return_value=readiness) as ready_gate,
        ):
            target.validate_session_record(
                record, expected_schedule=schedule, verify_sources=True
            )
        formal_gate.assert_called_once()
        ready_gate.assert_called_once_with(target._ROOT, "d" * 40)

    def test_formal_completion_gate_replays_session_history_and_240_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            block_root = root / "outputs/formal/synthetic-formal-v1/blocks"
            (block_root / ".locks").mkdir(parents=True)
            (block_root.parent / "run-summary.json").write_text("{}", encoding="utf-8")
            jobs = []
            schedule = []
            observed = {}
            for index in range(target.LOGICAL_SHARD_COUNT):
                seed = SimpleNamespace(node_count=index + 1, parent_replicate=0)
                model = ParentGraphModel.ER_GNM
                key = target._block_key(seed.node_count, seed.parent_replicate, model)
                jobs.append((seed, model))
                schedule.append({"worker_index": index, "block_key": key})
                path = block_root / f"{key}.json"
                path.write_text(f"{index}\n", encoding="utf-8")
                observed[key] = path
            completion_path = root / target._SOURCE_PATHS[-1]
            completion_path.parent.mkdir(parents=True, exist_ok=True)
            formal_session = {
                "fingerprint": "a" * 64,
                "python_executable": str(Path(r"C:\frozen\python.exe")),
            }
            (completion_path.parent / "session.json").write_text(
                json.dumps(formal_session), encoding="utf-8"
            )
            completion = {
                "schema_version": "formal-bounded-scheduler-completion.v1",
                "status": "all-240-singletons-strict-child-exit-zero",
                "session_fingerprint": "a" * 64,
                "completed_at_utc": "2026-08-11T12:00:00.000Z",
                "completed_worker_indices": list(range(target.LOGICAL_SHARD_COUNT)),
                "final_batch_count": 40,
                "final_block_count": target.LOGICAL_SHARD_COUNT,
                "final_block_registry_fingerprint": target._block_registry_fingerprint(observed),
            }
            completion["fingerprint"] = target._fingerprint(completion)
            completion_path.write_text(json.dumps(completion), encoding="utf-8")
            manifest = SimpleNamespace(fingerprint=target.FORMAL_MANIFEST_FINGERPRINT)
            with (
                mock.patch.object(target, "load_study_design_manifest", return_value=manifest),
                mock.patch.object(target, "build_study_seed_ledger", return_value=object()),
                mock.patch.object(target, "_registered_block_jobs", return_value=jobs),
                mock.patch.object(
                    target.formal_scheduler,
                    "canonical_singleton_schedule",
                    return_value=tuple(schedule),
                ),
                mock.patch.object(target.formal_scheduler, "validate_session_record") as validate,
                mock.patch.object(
                    target.formal_scheduler,
                    "_validate_batch_history",
                    return_value=(set(range(target.LOGICAL_SHARD_COUNT)), 40, None),
                ) as history,
            ):
                self.assertEqual(target._formal_completion_gate(root), completion)
            validate.assert_called_once()
            history.assert_called_once()
            completion["session_fingerprint"] = "b" * 64
            completion["fingerprint"] = target._fingerprint(completion)
            completion_path.write_text(json.dumps(completion), encoding="utf-8")
            with (
                mock.patch.object(target, "load_study_design_manifest", return_value=manifest),
                mock.patch.object(target, "build_study_seed_ledger", return_value=object()),
                mock.patch.object(target, "_registered_block_jobs", return_value=jobs),
                mock.patch.object(
                    target.formal_scheduler,
                    "canonical_singleton_schedule",
                    return_value=tuple(schedule),
                ),
                mock.patch.object(target.formal_scheduler, "validate_session_record"),
                mock.patch.object(
                    target.formal_scheduler,
                    "_validate_batch_history",
                    return_value=(set(range(target.LOGICAL_SHARD_COUNT)), 40, None),
                ),
            ):
                with self.assertRaisesRegex(StudyManifestError, "completion witness"):
                    target._formal_completion_gate(root)

    def test_cross_phase_scanner_command_names_both_manifests(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="[]")
        with (
            mock.patch.object(target.os, "name", "nt"),
            mock.patch.object(target.subprocess, "run", return_value=completed) as run,
        ):
            self.assertEqual(target._cross_phase_runner_processes(), [])
        command = run.call_args.args[0][-1]
        self.assertIn("synthetic-formal-v1.json", command)
        self.assertIn("synthetic-confirmation-v1.json", command)

    def test_global_lease_uses_shared_formal_namespace_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                mock.patch.object(target, "_ROOT", root),
                mock.patch.object(
                    target, "_GLOBAL_LEASE_ROOT", Path("results/diagnostics/formal-bounded-scheduler")
                ),
            ):
                lease_path, lease = target.acquire_global_lease(
                    session_id="confirmation-session-0004",
                    orchestration_revision="c" * 40,
                    recover_stale=False,
                    process_reader=self._identities,
                    runner_reader=lambda: [],
                )
                self.assertEqual(
                    lease_path.parent,
                    root / "results/diagnostics/formal-bounded-scheduler",
                )
                self.assertEqual(
                    lease["schema_version"], "formal-bounded-scheduler-lease.v1"
                )
                with self.assertRaisesRegex(StudyManifestError, "global lease"):
                    target.acquire_global_lease(
                        session_id="confirmation-session-0005",
                        orchestration_revision="c" * 40,
                        recover_stale=False,
                        process_reader=self._identities,
                        runner_reader=lambda: [],
                    )
                self.assertFalse(
                    (root / target._SESSION_ROOT / "confirmation-session-0005").exists()
                )
                with self.assertRaisesRegex(StudyManifestError, "runners remain live"):
                    target.acquire_global_lease(
                        session_id="confirmation-session-0005",
                        orchestration_revision="c" * 40,
                        recover_stale=True,
                        process_reader=lambda process_ids: [],
                        runner_reader=lambda: [
                            {
                                "process_id": 7777,
                                "command_line": "synthetic-formal-v1.json",
                            }
                        ],
                    )
                target.validate_global_lease(
                    lease_path, lease, process_reader=self._identities
                )
                changed = dict(lease)
                changed["session_id"] = "confirmation-session-tampered"
                changed["fingerprint"] = target._fingerprint(changed)
                lease_path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaisesRegex(StudyManifestError, "changed"):
                    target.validate_global_lease(
                        lease_path, lease, process_reader=self._identities
                    )
                lease_path.write_text(json.dumps(lease), encoding="utf-8")
                target.release_global_lease(lease_path, lease)

                stale = {
                    "schema_version": "formal-bounded-scheduler-lease.v1",
                    "status": "active-global-exclusive-lease",
                    "session_id": "confirmation-crashed-session",
                    "orchestration_revision": "c" * 40,
                    "scheduler_process_id": 9999,
                    "scheduler_parent_process_id": 1,
                    "scheduler_creation_time": "crashed-owner",
                    "acquired_at_utc": "2026-08-11T00:00:00.000Z",
                }
                stale["fingerprint"] = target._fingerprint(stale)
                target._write_create_only(lease_path, stale)
                recovery = {
                    "schema_version": "formal-bounded-scheduler-lease-recovery.v1",
                    "status": "stale-global-lease-owner-proved-absent",
                    "stale_lease_fingerprint": stale["fingerprint"],
                    "stale_session_id": stale["session_id"],
                    "recovered_at_utc": "2026-08-11T00:00:01.000Z",
                }
                recovery["fingerprint"] = target._fingerprint(recovery)
                recovery_path = (
                    lease_path.parent
                    / "lease-recoveries"
                    / f"{stale['fingerprint']}.json"
                )
                target._write_create_only(recovery_path, recovery)

                def recovery_identities(process_ids):
                    return self._identities(
                        [pid for pid in process_ids if pid == os.getpid()]
                    )

                lease_path, recovered_lease = target.acquire_global_lease(
                    session_id="confirmation-session-after-crash",
                    orchestration_revision="c" * 40,
                    recover_stale=True,
                    process_reader=recovery_identities,
                    runner_reader=lambda: [],
                )
                self.assertEqual(
                    recovered_lease["session_id"], "confirmation-session-after-crash"
                )
                self.assertEqual(
                    target._load_json(recovery_path, "recovery"), recovery
                )
                target.release_global_lease(
                    lease_path,
                    recovered_lease,
                )

    def test_batch_writes_confirmation_artifact_chain_and_caps_six(self) -> None:
        rows = [
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(6)
        ]
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            workspace = session / "workspace"
            block_root = workspace / "outputs/confirmation/synthetic-confirmation-v1/blocks"
            block_root.mkdir(parents=True)

            def popen(command, **kwargs):
                index = int(command[command.index("--worker-index") + 1])
                (block_root / f"key-{index}.json").write_text(
                    f"artifact-{index}", encoding="utf-8"
                )
                return _FakeProcess(command)

            with mock.patch.object(target, "_ROOT", workspace):
                low_session = session / "low-memory"
                low_session.mkdir()
                with self.assertRaisesRegex(StudyManifestError, "memory"):
                    target.run_batch(
                        session_dir=low_session,
                        session_fingerprint="a" * 64,
                        batch_number=0,
                        rows=rows,
                        python=Path("python.exe"),
                        memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES - 1,
                        popen=popen,
                        identity_reader=self._identities,
                    )
                self.assertFalse(list(low_session.glob("batch-*")))
                result = target.run_batch(
                    session_dir=session,
                    session_fingerprint="a" * 64,
                    batch_number=0,
                    rows=rows,
                    python=Path("python.exe"),
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=popen,
                    identity_reader=self._identities,
                )
            self.assertEqual(result["status"], "batch-complete-zero-exit")
            self.assertEqual(result["launched_process_count"], 6)
            self.assertTrue(all(row["artifact_sha256"] for row in result["workers"]))

    def test_confirmation_output_gate_rejects_foreign_and_summary_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / "outputs/confirmation/synthetic-confirmation-v1"
            output.mkdir(parents=True)
            (output / "foreign.tmp").write_text("partial", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "foreign"):
                target._assert_quiescent_output(root, {"key-0"})
            (output / "foreign.tmp").unlink()
            (output / "run-summary.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "summary"):
                target._assert_quiescent_output(root, {"key-0"})

    def test_failed_batch_accepts_zero_indices_until_successful_retry(self) -> None:
        row = {"worker_index": 0, "block_key": "key-0"}
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            workspace = session / "workspace"
            block_root = workspace / "outputs/confirmation/synthetic-confirmation-v1/blocks"
            block_root.mkdir(parents=True)

            def failing(command, **kwargs):
                (block_root / "key-0.json").write_text("artifact", encoding="utf-8")
                kwargs["stderr"].write(b"failure")
                kwargs["stderr"].flush()
                return _FakeProcess(command, returncode=1)

            with mock.patch.object(target, "_ROOT", workspace):
                with self.assertRaisesRegex(StudyManifestError, "failure"):
                    target.run_batch(
                        session_dir=session,
                        session_fingerprint="a" * 64,
                        batch_number=0,
                        rows=[row],
                        python=Path("python.exe"),
                        memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                        popen=failing,
                        identity_reader=self._identities,
                    )
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={0: row},
                    expected_python=Path("python.exe"),
                )
            self.assertEqual((completed, count, incomplete), (set(), 1, None))
            with mock.patch.object(target, "_ROOT", workspace):
                target.run_batch(
                    session_dir=session,
                    session_fingerprint="a" * 64,
                    batch_number=1,
                    rows=[row],
                    python=Path("python.exe"),
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=lambda command, **kwargs: _FakeProcess(command),
                    identity_reader=self._identities,
                )
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={0: row},
                    expected_python=Path("python.exe"),
                )
            self.assertEqual((completed, count, incomplete), ({0}, 2, None))

    def test_partial_spawn_writes_exact_abort_and_remains_recoverable(self) -> None:
        rows = [
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(2)
        ]
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            workspace = session / "workspace"
            calls = 0

            def partial_popen(command, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected spawn failure")
                return _FakeProcess(command)

            with mock.patch.object(target, "_ROOT", workspace):
                with self.assertRaisesRegex(OSError, "spawn failure"):
                    target.run_batch(
                        session_dir=session,
                        session_fingerprint="a" * 64,
                        batch_number=0,
                        rows=rows,
                        python=Path("python.exe"),
                        memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                        popen=partial_popen,
                        identity_reader=self._identities,
                    )
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={index: row for index, row in enumerate(rows)},
                    expected_python=Path("python.exe"),
                )
            self.assertEqual(completed, set())
            self.assertEqual(count, 1)
            self.assertEqual(incomplete, session / "batch-000.launch.json")
            abort_path = session / "batch-000.abort.json"
            abort = target._load_json(abort_path, "abort")
            valid_abort = dict(abort)
            self.assertEqual(abort["status"], "partial-start-aborted")
            self.assertEqual(len(abort["spawned_process_ids"]), 1)
            abort["spawned_process_ids"] = [abort["spawned_process_ids"][0]] * 2
            abort["fingerprint"] = target._fingerprint(abort)
            abort_path.write_text(json.dumps(abort), encoding="utf-8")
            with mock.patch.object(target, "_ROOT", workspace):
                with self.assertRaisesRegex(StudyManifestError, "start-abort"):
                    target._validate_batch_history(
                        session,
                        session_fingerprint="a" * 64,
                        expected_rows={index: row for index, row in enumerate(rows)},
                        expected_python=Path("python.exe"),
                    )
            abort_path.write_text(json.dumps(valid_abort), encoding="utf-8")
            with (
                mock.patch.object(target, "_ROOT", workspace),
                mock.patch.object(
                    target, "_cross_phase_runner_processes", return_value=[]
                ),
            ):
                recovery_path = target.recover_incomplete_batch(
                    session,
                    session / "batch-000.launch.json",
                    session_fingerprint="a" * 64,
                    expected_keys={"key-0", "key-1"},
                    expected_rows={index: row for index, row in enumerate(rows)},
                    expected_python=Path("python.exe"),
                )
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={index: row for index, row in enumerate(rows)},
                    expected_python=Path("python.exe"),
                )
            recovery = target._load_json(recovery_path, "recovery")
            self.assertEqual(
                recovery["status"],
                "interrupted-batch-closed-without-complete-start-witness",
            )
            self.assertEqual((completed, count, incomplete), (set(), 1, None))

    def test_abort_publication_failure_still_terminates_spawned_children(self) -> None:
        rows = [
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(2)
        ]
        original_write = target._write_create_only
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            workspace = session / "workspace"
            running = _FakeProcess([], returncode=None)
            calls = 0

            def partial_popen(command, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected spawn failure")
                running.command = command
                return running

            def fail_abort(path, value, **kwargs):
                if Path(path).name.endswith(".abort.json"):
                    raise StudyManifestError("injected abort publication failure")
                return original_write(path, value, **kwargs)

            with (
                mock.patch.object(target, "_ROOT", workspace),
                mock.patch.object(
                    target, "_write_create_only", side_effect=fail_abort
                ),
            ):
                with self.assertRaisesRegex(StudyManifestError, "abort publication"):
                    target.run_batch(
                        session_dir=session,
                        session_fingerprint="a" * 64,
                        batch_number=0,
                        rows=rows,
                        python=Path("python.exe"),
                        memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                        popen=partial_popen,
                        identity_reader=self._identities,
                    )
            self.assertEqual(running.returncode, -15)
            self.assertFalse((session / "batch-000.abort.json").exists())

    def test_first_spawn_failure_without_abort_can_be_closed_and_retried(self) -> None:
        row = {"worker_index": 0, "block_key": "key-0"}
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            workspace = session / "workspace"
            with mock.patch.object(target, "_ROOT", workspace):
                with self.assertRaisesRegex(OSError, "first spawn failure"):
                    target.run_batch(
                        session_dir=session,
                        session_fingerprint="a" * 64,
                        batch_number=0,
                        rows=[row],
                        python=Path("python.exe"),
                        memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                        popen=lambda command, **kwargs: (_ for _ in ()).throw(
                            OSError("first spawn failure")
                        ),
                        identity_reader=self._identities,
                    )
            self.assertTrue((session / "batch-000.launch.json").is_file())
            self.assertFalse((session / "batch-000.abort.json").exists())
            with (
                mock.patch.object(target, "_ROOT", workspace),
                mock.patch.object(
                    target, "_cross_phase_runner_processes", return_value=[]
                ),
            ):
                recovery_path = target.recover_incomplete_batch(
                    session,
                    session / "batch-000.launch.json",
                    session_fingerprint="a" * 64,
                    expected_keys={"key-0"},
                    expected_rows={0: row},
                    expected_python=Path("python.exe"),
                )
                completed, count, incomplete = target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows={0: row},
                    expected_python=Path("python.exe"),
                )
            self.assertTrue(recovery_path.is_file())
            self.assertEqual((completed, count, incomplete), (set(), 1, None))

    def test_interrupted_published_artifact_remains_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / "session"
            session.mkdir()
            workspace = root / "workspace"
            block_root = workspace / "outputs/confirmation/synthetic-confirmation-v1/blocks"
            (block_root / ".locks").mkdir(parents=True)
            artifact = block_root / "key-0.json"
            artifact.write_text("atomic", encoding="utf-8")
            command = target._runner_command(Path("python.exe"), 0)
            command[command.index("--workspace-root") + 1] = str(workspace)
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
                            subprocess.list2cmdline(command).encode("utf-8")
                        ).hexdigest(),
                        "stdout_file": "batch-000.worker-000.stdout.txt",
                        "stderr_file": "batch-000.worker-000.stderr.txt",
                    }
                ],
            }
            launch["fingerprint"] = target._fingerprint(launch)
            launch_path = session / "batch-000.launch.json"
            target._write_create_only(launch_path, launch)
            started = {
                "schema_version": "confirmation-bounded-scheduler-started.v1",
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
                        "stdout_file": "batch-000.worker-000.stdout.txt",
                        "stderr_file": "batch-000.worker-000.stderr.txt",
                    }
                ],
            }
            started["fingerprint"] = target._fingerprint(started)
            started_path = session / "batch-000.started.json"
            target._write_create_only(started_path, started)
            malformed = dict(started)
            malformed["session_fingerprint"] = "b" * 64
            malformed["fingerprint"] = target._fingerprint(malformed)
            started_path.write_text(json.dumps(malformed), encoding="utf-8")
            with mock.patch.object(target, "_ROOT", workspace):
                with self.assertRaisesRegex(StudyManifestError, "started witness"):
                    target.recover_incomplete_batch(
                        session,
                        launch_path,
                        session_fingerprint="a" * 64,
                        expected_keys={"key-0"},
                        expected_rows={0: {"worker_index": 0, "block_key": "key-0"}},
                        expected_python=Path("python.exe"),
                    )
            self.assertFalse((session / "batch-000.recovery.json").exists())
            started_path.write_text(json.dumps(started), encoding="utf-8")

            drifted = dict(started)
            drifted["captured_at_utc"] = "2026-08-11T00:00:02.000Z"
            drifted["fingerprint"] = target._fingerprint(drifted)

            def drift_after_initial_validation():
                started_path.write_text(json.dumps(drifted), encoding="utf-8")
                return []

            with (
                mock.patch.object(target, "_ROOT", workspace),
                mock.patch.object(
                    target,
                    "_cross_phase_runner_processes",
                    side_effect=drift_after_initial_validation,
                ),
            ):
                with self.assertRaisesRegex(StudyManifestError, "drifted"):
                    target.recover_incomplete_batch(
                        session,
                        launch_path,
                        session_fingerprint="a" * 64,
                        expected_keys={"key-0"},
                        expected_rows={0: {"worker_index": 0, "block_key": "key-0"}},
                        expected_python=Path("python.exe"),
                    )
            self.assertFalse((session / "batch-000.recovery.json").exists())
            started_path.write_text(json.dumps(started), encoding="utf-8")

            with (
                mock.patch.object(target, "_ROOT", workspace),
                mock.patch.object(
                    target,
                    "_cross_phase_runner_processes",
                    side_effect=[[], [{"process_id": 9999}]],
                ),
                mock.patch.object(
                    target,
                    "_process_identities",
                    return_value=[
                        {
                            "process_id": 1234,
                            "parent_process_id": 7,
                            "process_creation_time": "reused-other",
                            "command_line": "unrelated",
                        }
                    ],
                ),
            ):
                with self.assertRaisesRegex(StudyManifestError, "appeared"):
                    target.recover_incomplete_batch(
                        session,
                        launch_path,
                        session_fingerprint="a" * 64,
                        expected_keys={"key-0"},
                        expected_rows={0: {"worker_index": 0, "block_key": "key-0"}},
                        expected_python=Path("python.exe"),
                    )
            self.assertFalse((session / "batch-000.recovery.json").exists())

            scan_count = 0

            def mutate_artifact_before_publish():
                nonlocal scan_count
                scan_count += 1
                if scan_count == 2:
                    artifact.write_text("drifted", encoding="utf-8")
                return []

            with (
                mock.patch.object(target, "_ROOT", workspace),
                mock.patch.object(
                    target,
                    "_cross_phase_runner_processes",
                    side_effect=mutate_artifact_before_publish,
                ),
                mock.patch.object(
                    target,
                    "_process_identities",
                    return_value=[
                        {
                            "process_id": 1234,
                            "parent_process_id": 7,
                            "process_creation_time": "reused-other",
                            "command_line": "unrelated",
                        }
                    ],
                ),
            ):
                with self.assertRaisesRegex(StudyManifestError, "artifact registry drifted"):
                    target.recover_incomplete_batch(
                        session,
                        launch_path,
                        session_fingerprint="a" * 64,
                        expected_keys={"key-0"},
                        expected_rows={0: {"worker_index": 0, "block_key": "key-0"}},
                        expected_python=Path("python.exe"),
                    )
            self.assertFalse((session / "batch-000.recovery.json").exists())
            artifact.write_text("atomic", encoding="utf-8")

            scan_count = 0
            late_lock = block_root / ".locks" / "key-0.lock"

            def create_lock_before_publish():
                nonlocal scan_count
                scan_count += 1
                if scan_count == 2:
                    late_lock.write_text("late", encoding="utf-8")
                return []

            with (
                mock.patch.object(target, "_ROOT", workspace),
                mock.patch.object(
                    target,
                    "_cross_phase_runner_processes",
                    side_effect=create_lock_before_publish,
                ),
                mock.patch.object(
                    target,
                    "_process_identities",
                    return_value=[
                        {
                            "process_id": 1234,
                            "parent_process_id": 7,
                            "process_creation_time": "reused-other",
                            "command_line": "unrelated",
                        }
                    ],
                ),
            ):
                with self.assertRaisesRegex(StudyManifestError, "lock"):
                    target.recover_incomplete_batch(
                        session,
                        launch_path,
                        session_fingerprint="a" * 64,
                        expected_keys={"key-0"},
                        expected_rows={0: {"worker_index": 0, "block_key": "key-0"}},
                        expected_python=Path("python.exe"),
                    )
            self.assertFalse((session / "batch-000.recovery.json").exists())
            late_lock.unlink()

            with (
                mock.patch.object(target, "_ROOT", workspace),
                mock.patch.object(target, "_cross_phase_runner_processes", return_value=[]),
                mock.patch.object(
                    target,
                    "_process_identities",
                    return_value=[
                        {
                            "process_id": 1234,
                            "parent_process_id": 7,
                            "process_creation_time": "reused-other",
                            "command_line": "unrelated",
                        }
                    ],
                ),
            ):
                recovery_path = target.recover_incomplete_batch(
                    session,
                    launch_path,
                    session_fingerprint="a" * 64,
                    expected_keys={"key-0"},
                    expected_rows={0: {"worker_index": 0, "block_key": "key-0"}},
                    expected_python=Path("python.exe"),
                )
            recovery = target._load_json(recovery_path, "recovery")
            self.assertEqual(recovery["workers"][0]["artifact_state"], "atomic-file-present")
            self.assertIn("remains-pending", recovery["limitations"][1])

    def test_history_replay_rejects_log_and_artifact_tampering(self) -> None:
        row = {"worker_index": 0, "block_key": "key-0"}
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            workspace = session / "workspace"
            block_root = workspace / "outputs/confirmation/synthetic-confirmation-v1/blocks"
            block_root.mkdir(parents=True)

            def popen(command, **kwargs):
                (block_root / "key-0.json").write_text("artifact", encoding="utf-8")
                return _FakeProcess(command)

            with mock.patch.object(target, "_ROOT", workspace):
                target.run_batch(
                    session_dir=session,
                    session_fingerprint="a" * 64,
                    batch_number=0,
                    rows=[row],
                    python=Path("python.exe"),
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=popen,
                    identity_reader=self._identities,
                )
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

    def test_history_rejects_path_traversal_and_noncanonical_pending_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            command = target._runner_command(Path("python.exe"), 239)
            launch = {
                "schema_version": target.BATCH_SCHEMA_VERSION,
                "status": "planned-before-launch",
                "session_fingerprint": "a" * 64,
                "batch_number": 0,
                "started_at_utc": "2026-08-11T00:00:00.000Z",
                "available_memory_bytes_before_launch": target.MIN_AVAILABLE_MEMORY_BYTES,
                "workers": [
                    {
                        "worker_index": 239,
                        "block_key": "key-239",
                        "command": command,
                        "command_sha256": hashlib.sha256(
                            subprocess.list2cmdline(command).encode("utf-8")
                        ).hexdigest(),
                        "stdout_file": "../../outside.txt",
                        "stderr_file": "batch-000.worker-239.stderr.txt",
                    }
                ],
            }
            launch["fingerprint"] = target._fingerprint(launch)
            path = session / "batch-000.launch.json"
            target._write_create_only(path, launch)
            rows = {
                0: {"worker_index": 0, "block_key": "key-0"},
                239: {"worker_index": 239, "block_key": "key-239"},
            }
            with self.assertRaisesRegex(StudyManifestError, "log filename"):
                target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows=rows,
                    expected_python=Path("python.exe"),
                )
            launch["workers"][0]["stdout_file"] = "batch-000.worker-239.stdout.txt"
            launch["available_memory_bytes_before_launch"] = 0
            launch["fingerprint"] = target._fingerprint(launch)
            path.write_text(json.dumps(launch), encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "launch witness"):
                target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows=rows,
                    expected_python=Path("python.exe"),
                )
            launch["available_memory_bytes_before_launch"] = (
                target.MIN_AVAILABLE_MEMORY_BYTES
            )
            launch["fingerprint"] = target._fingerprint(launch)
            path.write_text(json.dumps(launch), encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "pending prefix"):
                target._validate_batch_history(
                    session,
                    session_fingerprint="a" * 64,
                    expected_rows=rows,
                    expected_python=Path("python.exe"),
                )

    def test_plain_path_gate_rejects_simulated_windows_reparse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            redirected = root / "redirected"
            redirected.mkdir()
            real_lstat = target.os.lstat

            def lstat(path):
                result = real_lstat(path)
                if Path(path) != redirected:
                    return result
                return SimpleNamespace(
                    st_mode=result.st_mode,
                    st_file_attributes=getattr(
                        target.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024
                    ),
                )

            with mock.patch.object(target.os, "lstat", side_effect=lstat):
                with self.assertRaisesRegex(StudyManifestError, "redirected component"):
                    target._assert_plain_path(redirected / "active-session.json")

    def test_full_fresh_run_writes_40_batches_and_resume_revalidates_completion(self) -> None:
        schedule = tuple(
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(target.LOGICAL_SHARD_COUNT)
        )
        original_run_batch = target.run_batch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            lease_path = root / "active-session.json"
            lease = {"fingerprint": "e" * 64}
            source_checks = []

            def fake_popen(command, **kwargs):
                index = int(command[command.index("--worker-index") + 1])
                block_root = (
                    root
                    / "outputs/confirmation/synthetic-confirmation-v1/blocks"
                )
                block_root.mkdir(parents=True, exist_ok=True)
                (block_root / f"key-{index}.json").write_text(
                    f"artifact-{index}\n", encoding="utf-8"
                )
                return _FakeProcess(command)

            def bounded_batch(**kwargs):
                return original_run_batch(
                    **kwargs,
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=fake_popen,
                    identity_reader=self._identities,
                )

            def validate_session(record, **kwargs):
                source_checks.append(record["fingerprint"])

            common = (
                mock.patch.object(target, "_ROOT", root),
                mock.patch.object(target, "verify_source_snapshots"),
                mock.patch.object(
                    target,
                    "_readiness_gate",
                    return_value={"readiness_fingerprint": "a" * 64},
                ),
                mock.patch.object(target, "_formal_completion_gate"),
                mock.patch.object(target, "canonical_singleton_schedule", return_value=schedule),
                mock.patch.object(
                    target,
                    "preflight_synthetic_study",
                    return_value={
                        "selected_block_count": 1,
                        "environment_fingerprint": target.ENVIRONMENT_FINGERPRINT,
                    },
                ),
                mock.patch.object(
                    target,
                    "_source_record",
                    side_effect=lambda path: {
                        "path": Path(path).as_posix(),
                        "sha256": "b" * 64,
                    },
                ),
                mock.patch.object(target, "validate_session_record", side_effect=validate_session),
                mock.patch.object(target, "validate_global_lease"),
                mock.patch.object(target, "_cross_phase_runner_processes", return_value=[]),
                mock.patch.object(target, "run_batch", side_effect=bounded_batch),
            )
            with common[0], common[1], common[2], common[3], common[4], common[5], common[6], common[7], common[8], common[9], common[10]:
                completion_path = target._run_scheduler_body(
                    session_id="confirmation-integration-0001",
                    orchestration_revision="c" * 40,
                    readiness_authorization_revision="d" * 40,
                    python_executable=Path(sys.executable),
                    resume=False,
                    recover_interrupted=False,
                    lease_path=lease_path,
                    lease=lease,
                )
            completion = target._load_json(completion_path, "completion")
            self.assertEqual(completion["final_batch_count"], 40)
            self.assertEqual(completion["final_block_count"], 240)
            session_dir = completion_path.parent
            self.assertEqual(len(list(session_dir.glob("batch-*.launch.json"))), 40)
            self.assertEqual(len(list(session_dir.glob("batch-*.final.json"))), 40)
            first_source_check_count = len(source_checks)
            self.assertGreaterEqual(first_source_check_count, 42)

            with common[0], common[1], common[2], common[3], common[4], common[5], common[6], common[7], common[8], common[9], common[10]:
                resumed = target._run_scheduler_body(
                    session_id="confirmation-integration-0001",
                    orchestration_revision="c" * 40,
                    readiness_authorization_revision="d" * 40,
                    python_executable=Path(sys.executable),
                    resume=True,
                    recover_interrupted=False,
                    lease_path=lease_path,
                    lease=lease,
                )
            self.assertEqual(resumed, completion_path)
            self.assertGreater(len(source_checks), first_source_check_count)

            early_artifact = (
                root
                / "outputs/confirmation/synthetic-confirmation-v1/blocks/key-0.json"
            )
            early_artifact.write_text("tampered-after-completion\n", encoding="utf-8")
            with common[0], common[1], common[2], common[3], common[4], common[5], common[6], common[7], common[8], common[9], common[10]:
                with self.assertRaisesRegex(StudyManifestError, "artifact hash"):
                    target._run_scheduler_body(
                        session_id="confirmation-integration-0001",
                        orchestration_revision="c" * 40,
                        readiness_authorization_revision="d" * 40,
                        python_executable=Path(sys.executable),
                        resume=True,
                        recover_interrupted=False,
                        lease_path=lease_path,
                        lease=lease,
                    )
            early_artifact.write_text("artifact-0\n", encoding="utf-8")
            changed_completion = target._load_json(completion_path, "completion")
            changed_completion["final_batch_count"] = 39
            changed_completion["fingerprint"] = target._fingerprint(changed_completion)
            completion_path.write_text(json.dumps(changed_completion), encoding="utf-8")
            with common[0], common[1], common[2], common[3], common[4], common[5], common[6], common[7], common[8], common[9], common[10]:
                with self.assertRaisesRegex(StudyManifestError, "completion witness"):
                    target._run_scheduler_body(
                        session_id="confirmation-integration-0001",
                        orchestration_revision="c" * 40,
                        readiness_authorization_revision="d" * 40,
                        python_executable=Path(sys.executable),
                        resume=True,
                        recover_interrupted=False,
                        lease_path=lease_path,
                        lease=lease,
                    )

    def test_source_gate_drift_stops_before_next_batch(self) -> None:
        schedule = tuple(
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(12)
        )
        original_run_batch = target.run_batch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            validation_count = 0

            def fake_popen(command, **kwargs):
                index = int(command[command.index("--worker-index") + 1])
                block_root = (
                    root
                    / "outputs/confirmation/synthetic-confirmation-v1/blocks"
                )
                block_root.mkdir(parents=True, exist_ok=True)
                (block_root / f"key-{index}.json").write_text(
                    f"artifact-{index}\n", encoding="utf-8"
                )
                return _FakeProcess(command)

            def bounded_batch(**kwargs):
                return original_run_batch(
                    **kwargs,
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=fake_popen,
                    identity_reader=self._identities,
                )

            def validate_then_drift(record, **kwargs):
                nonlocal validation_count
                validation_count += 1
                if validation_count == 3:
                    raise StudyManifestError("source drift injected")

            with (
                mock.patch.object(target, "_ROOT", root),
                mock.patch.object(target, "verify_source_snapshots"),
                mock.patch.object(
                    target,
                    "_readiness_gate",
                    return_value={"readiness_fingerprint": "a" * 64},
                ),
                mock.patch.object(target, "_formal_completion_gate"),
                mock.patch.object(
                    target, "canonical_singleton_schedule", return_value=schedule
                ),
                mock.patch.object(
                    target,
                    "preflight_synthetic_study",
                    return_value={
                        "selected_block_count": 1,
                        "environment_fingerprint": target.ENVIRONMENT_FINGERPRINT,
                    },
                ),
                mock.patch.object(
                    target,
                    "_source_record",
                    side_effect=lambda path: {
                        "path": Path(path).as_posix(),
                        "sha256": "b" * 64,
                    },
                ),
                mock.patch.object(
                    target,
                    "validate_session_record",
                    side_effect=validate_then_drift,
                ),
                mock.patch.object(target, "validate_global_lease"),
                mock.patch.object(
                    target, "_cross_phase_runner_processes", return_value=[]
                ),
                mock.patch.object(target, "run_batch", side_effect=bounded_batch),
            ):
                with self.assertRaisesRegex(StudyManifestError, "source drift"):
                    target._run_scheduler_body(
                        session_id="confirmation-source-drift-0001",
                        orchestration_revision="c" * 40,
                        readiness_authorization_revision="d" * 40,
                        python_executable=Path(sys.executable),
                        resume=False,
                        recover_interrupted=False,
                        lease_path=root / "active-session.json",
                        lease={"fingerprint": "e" * 64},
                    )
            block_root = root / "outputs/confirmation/synthetic-confirmation-v1/blocks"
            self.assertEqual(len(list(block_root.glob("*.json"))), 6)
            session_dir = root / target._SESSION_ROOT / "confirmation-source-drift-0001"
            self.assertEqual(len(list(session_dir.glob("batch-*.launch.json"))), 1)
            self.assertFalse((session_dir / "completion.json").exists())

    def test_completion_prepublish_rejects_artifact_drift(self) -> None:
        schedule = tuple(
            {"worker_index": index, "block_key": f"key-{index}"}
            for index in range(6)
        )
        original_run_batch = target.run_batch
        original_write = target._write_create_only
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()

            def fake_popen(command, **kwargs):
                index = int(command[command.index("--worker-index") + 1])
                block_root = (
                    root
                    / "outputs/confirmation/synthetic-confirmation-v1/blocks"
                )
                block_root.mkdir(parents=True, exist_ok=True)
                (block_root / f"key-{index}.json").write_text(
                    f"artifact-{index}\n", encoding="utf-8"
                )
                return _FakeProcess(command)

            def bounded_batch(**kwargs):
                return original_run_batch(
                    **kwargs,
                    memory_reader=lambda: target.MIN_AVAILABLE_MEMORY_BYTES + 1,
                    popen=fake_popen,
                    identity_reader=self._identities,
                )

            def drift_before_completion_publish(path, value, **kwargs):
                if Path(path).name == "completion.json":
                    artifact = (
                        root
                        / "outputs/confirmation/synthetic-confirmation-v1/blocks/key-0.json"
                    )
                    artifact.write_text("drifted-before-publish\n", encoding="utf-8")
                return original_write(path, value, **kwargs)

            common = (
                mock.patch.object(target, "_ROOT", root),
                mock.patch.object(target, "LOGICAL_SHARD_COUNT", 6),
                mock.patch.object(target, "verify_source_snapshots"),
                mock.patch.object(
                    target,
                    "_readiness_gate",
                    return_value={"readiness_fingerprint": "a" * 64},
                ),
                mock.patch.object(target, "_formal_completion_gate"),
                mock.patch.object(
                    target, "canonical_singleton_schedule", return_value=schedule
                ),
                mock.patch.object(
                    target,
                    "preflight_synthetic_study",
                    return_value={
                        "selected_block_count": 1,
                        "environment_fingerprint": target.ENVIRONMENT_FINGERPRINT,
                    },
                ),
                mock.patch.object(
                    target,
                    "_source_record",
                    side_effect=lambda path: {
                        "path": Path(path).as_posix(),
                        "sha256": "b" * 64,
                    },
                ),
                mock.patch.object(target, "validate_session_record"),
                mock.patch.object(target, "validate_global_lease"),
                mock.patch.object(
                    target, "_cross_phase_runner_processes", return_value=[]
                ),
                mock.patch.object(target, "run_batch", side_effect=bounded_batch),
                mock.patch.object(
                    target,
                    "_write_create_only",
                    side_effect=drift_before_completion_publish,
                ),
            )
            with common[0], common[1], common[2], common[3], common[4], common[5], common[6], common[7], common[8], common[9], common[10], common[11], common[12]:
                with self.assertRaisesRegex(
                    StudyManifestError, "artifact hash|state drifted"
                ):
                    target._run_scheduler_body(
                        session_id="confirmation-completion-drift-0001",
                        orchestration_revision="c" * 40,
                        readiness_authorization_revision="d" * 40,
                        python_executable=Path(sys.executable),
                        resume=False,
                        recover_interrupted=False,
                        lease_path=root / "active-session.json",
                        lease={"fingerprint": "e" * 64},
                    )
            session_dir = root / target._SESSION_ROOT / "confirmation-completion-drift-0001"
            self.assertFalse((session_dir / "completion.json").exists())


if __name__ == "__main__":
    unittest.main()
