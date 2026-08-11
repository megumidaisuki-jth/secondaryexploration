"""Tests for non-inferential formal execution progress checkpoints."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from secondaryexploration.experiments import StudyManifestError
from secondaryexploration.topology import ParentGraphModel
from tools import formal_progress_checkpoint as target


def _checkpoint(keys=None):
    if keys is None:
        keys = target._EXPECTED_KEYS[:2]
    blocks = [
        {
            "block_key": key,
            "artifact_fingerprint": f"{index + 1:064x}",
            "result_fingerprint": f"{index + 101:064x}",
            "file_sha256": f"{index + 201:064x}",
        }
        for index, key in enumerate(keys)
    ]
    value = {
        "schema_version": target.SCHEMA_VERSION,
        "status": target._STATUS,
        "manifest_fingerprint": target._FORMAL_MANIFEST_FINGERPRINT,
        "seed_ledger_fingerprint": "1" * 64,
        "calibration_evidence_fingerprint": "2" * 64,
        "precision_fingerprint": "3" * 64,
        "code_revision": target._EXECUTION_REVISION,
        "environment_fingerprint": "4" * 64,
        "expected_block_count": target._EXPECTED_BLOCK_COUNT,
        "completed_block_count": len(blocks),
        "completed_by_cell": target._cell_counts(blocks),
        "blocks": blocks,
        "limitations": list(target._LIMITATIONS),
    }
    value["checkpoint_fingerprint"] = target._fingerprint(value)
    return value


class FormalProgressCheckpointTests(unittest.TestCase):
    def test_validator_accepts_canonical_noninferential_registry(self):
        target.validate_formal_progress_checkpoint(_checkpoint())

    def test_validator_rejects_tamper_reordering_and_unknown_fields(self):
        cases = []
        tampered = _checkpoint()
        tampered["blocks"][0]["file_sha256"] = "f" * 64
        cases.append(tampered)
        reordered = _checkpoint()
        reordered["blocks"].reverse()
        reordered["checkpoint_fingerprint"] = target._fingerprint(
            {k: v for k, v in reordered.items() if k != "checkpoint_fingerprint"}
        )
        cases.append(reordered)
        outcome = _checkpoint()
        outcome["effect_estimate"] = 0.5
        cases.append(outcome)
        cell_tamper = _checkpoint()
        cell_tamper["completed_by_cell"][0]["completed_parent_count"] += 1
        cell_tamper["checkpoint_fingerprint"] = target._fingerprint(
            {k: v for k, v in cell_tamper.items() if k != "checkpoint_fingerprint"}
        )
        cases.append(cell_tamper)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(StudyManifestError):
                    target.validate_formal_progress_checkpoint(value)

    def test_historical_loader_accepts_current_valid_superset(self):
        first_key, second_key = target._EXPECTED_KEYS[:2]
        first_bytes = b"first-artifact\n"
        checkpoint = _checkpoint([first_key])
        checkpoint["blocks"][0].update(
            {
                "artifact_fingerprint": "a" * 64,
                "result_fingerprint": "b" * 64,
                "file_sha256": hashlib.sha256(first_bytes).hexdigest(),
            }
        )
        checkpoint["checkpoint_fingerprint"] = target._fingerprint(
            {k: v for k, v in checkpoint.items() if k != "checkpoint_fingerprint"}
        )
        manifest = SimpleNamespace(
            fingerprint=target._FORMAL_MANIFEST_FINGERPRINT,
            output_root="outputs/formal/synthetic-formal-v1",
        )
        ledger = SimpleNamespace(fingerprint="1" * 64)
        seed1, seed2 = object(), object()
        jobs = (
            (first_key, seed1, ParentGraphModel.ER_GNM),
            (second_key, seed2, ParentGraphModel.BARABASI_ALBERT),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            block_root = root / manifest.output_root / "blocks"
            block_root.mkdir(parents=True)
            (block_root / f"{first_key}.json").write_bytes(first_bytes)
            (block_root / f"{second_key}.json").write_bytes(b"later-valid-superset\n")
            checkpoint_path = root / "checkpoint.json"
            checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
            context = (
                manifest,
                ledger,
                {"python_version": "3.12.13"},
                {"evidence_fingerprint": "2" * 64},
                {"precision_fingerprint": "3" * 64},
            )
            with (
                patch.object(target, "_load_context", return_value=context),
                patch.object(target, "_canonical_jobs", return_value=jobs),
                patch.object(
                    target,
                    "runtime_environment_fingerprint",
                    return_value="4" * 64,
                ),
                patch.object(
                    target,
                    "load_synthetic_block_artifact",
                    return_value={
                        "artifact_fingerprint": "a" * 64,
                        "result_fingerprint": "b" * 64,
                    },
                ) as loader,
            ):
                loaded = target.load_formal_progress_checkpoint(
                    checkpoint_path,
                    manifest_path=root / "manifest.json",
                    calibration_manifest_path=root / "calibration.json",
                    calibration_evidence_path=root / "calibration-evidence.json",
                    precision_path=root / "precision.json",
                    code_revision=target._EXECUTION_REVISION,
                    workspace_root=root,
                )
                (block_root / f"{first_key}.json").write_bytes(b"changed\n")
                with self.assertRaises(StudyManifestError):
                    target.load_formal_progress_checkpoint(
                        checkpoint_path,
                        manifest_path=root / "manifest.json",
                        calibration_manifest_path=root / "calibration.json",
                        calibration_evidence_path=root / "calibration-evidence.json",
                        precision_path=root / "precision.json",
                        code_revision=target._EXECUTION_REVISION,
                        workspace_root=root,
                    )
                (block_root / f"{first_key}.json").unlink()
                with self.assertRaises(StudyManifestError):
                    target.load_formal_progress_checkpoint(
                        checkpoint_path,
                        manifest_path=root / "manifest.json",
                        calibration_manifest_path=root / "calibration.json",
                        calibration_evidence_path=root / "calibration-evidence.json",
                        precision_path=root / "precision.json",
                        code_revision=target._EXECUTION_REVISION,
                        workspace_root=root,
                    )
        self.assertEqual(loaded, checkpoint)
        self.assertEqual(loader.call_count, 2)

    def test_active_atomic_temporary_retries_but_unknown_entry_rejects(self):
        key = target._EXPECTED_KEYS[0]
        with tempfile.TemporaryDirectory() as directory:
            block_root = Path(directory) / "blocks"
            lock_root = block_root / ".locks"
            lock_root.mkdir(parents=True)
            (lock_root / f"{key}.lock").write_bytes(b"")
            temporary = block_root / f".{key}.json.abcd.tmp"
            temporary.write_bytes(b"partial")

            def remove_temporary(_seconds):
                temporary.unlink()

            with patch.object(target.time, "sleep", side_effect=remove_temporary):
                observed = target._observed_block_paths(block_root, {key})
            self.assertEqual(observed, {})
            unknown = block_root / ".unknown.json.abcd.tmp"
            unknown.write_bytes(b"partial")
            with self.assertRaises(StudyManifestError):
                target._observed_block_paths(block_root, {key})

    def test_vanished_active_atomic_temporary_retries(self):
        key = target._EXPECTED_KEYS[0]
        with tempfile.TemporaryDirectory() as directory:
            block_root = Path(directory) / "blocks"
            lock_root = block_root / ".locks"
            lock_root.mkdir(parents=True)
            (lock_root / f"{key}.lock").write_bytes(b"")
            temporary = block_root / f".{key}.json.abcd.tmp"
            temporary.write_bytes(b"partial")
            original_lstat = Path.lstat
            vanished = False

            def vanish_during_lstat(path):
                nonlocal vanished
                if path == temporary and not vanished:
                    vanished = True
                    temporary.unlink()
                    raise FileNotFoundError(path)
                return original_lstat(path)

            with (
                patch.object(Path, "lstat", new=vanish_during_lstat),
                patch.object(target.time, "sleep", return_value=None),
            ):
                observed = target._observed_block_paths(block_root, {key})
            self.assertTrue(vanished)
            self.assertEqual(observed, {})

    def test_vanished_canonical_lock_retries_whole_snapshot(self):
        key = target._EXPECTED_KEYS[0]
        with tempfile.TemporaryDirectory() as directory:
            block_root = Path(directory) / "blocks"
            lock_root = block_root / ".locks"
            lock_root.mkdir(parents=True)
            lock = lock_root / f"{key}.lock"
            lock.write_bytes(b"")
            original_lstat = Path.lstat
            vanished = False

            def vanish_lock_during_lstat(path):
                nonlocal vanished
                if path == lock and not vanished:
                    vanished = True
                    lock.unlink()
                    raise FileNotFoundError(path)
                return original_lstat(path)

            with (
                patch.object(Path, "lstat", new=vanish_lock_during_lstat),
                patch.object(target.time, "sleep", return_value=None),
            ):
                observed = target._observed_block_paths(block_root, {key})
            self.assertTrue(vanished)
            self.assertEqual(observed, {})

    def test_temp_and_lock_vanish_between_enumerations_retries(self):
        key = target._EXPECTED_KEYS[0]
        with tempfile.TemporaryDirectory() as directory:
            block_root = Path(directory) / "blocks"
            lock_root = block_root / ".locks"
            lock_root.mkdir(parents=True)
            lock = lock_root / f"{key}.lock"
            lock.write_bytes(b"")
            temporary = block_root / f".{key}.json.abcd.tmp"
            temporary.write_bytes(b"partial")
            original_active_locks = target._active_lock_keys
            completed = False

            def finish_before_lock_scan(path, expected):
                nonlocal completed
                if not completed:
                    completed = True
                    temporary.unlink()
                    lock.unlink()
                    return set()
                return original_active_locks(path, expected)

            with (
                patch.object(
                    target, "_active_lock_keys", side_effect=finish_before_lock_scan
                ),
                patch.object(target.time, "sleep", return_value=None),
            ):
                observed = target._observed_block_paths(block_root, {key})
            self.assertTrue(completed)
            self.assertEqual(observed, {})

    def test_checkpoint_writer_is_count_addressed_and_create_only(self):
        checkpoint = _checkpoint()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = (
                root
                / target._CHECKPOINT_ROOT
                / f"checkpoint-{checkpoint['completed_block_count']:06d}.json"
            )
            with self.assertRaises(StudyManifestError):
                target._write_new_checkpoint(
                    root / "manifest.json", checkpoint, workspace_root=root
                )
            written = target._write_new_checkpoint(
                expected.parent, checkpoint, workspace_root=root
            )
            self.assertEqual(written, expected)
            target.validate_formal_progress_checkpoint(
                json.loads(expected.read_text(encoding="utf-8"))
            )
            with self.assertRaises(StudyManifestError):
                target._write_new_checkpoint(
                    expected.parent, checkpoint, workspace_root=root
                )

    def test_main_rejects_file_output_before_expensive_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = SimpleNamespace(
                manifest=root / "manifest.json",
                calibration_manifest=root / "calibration-manifest.json",
                calibration_evidence=root / "calibration-evidence.json",
                precision=root / "precision.json",
                code_revision=target._EXECUTION_REVISION,
                workspace_root=root,
                output=(
                    root
                    / target._CHECKPOINT_ROOT
                    / "checkpoint-000174.json"
                ),
                verify_existing=False,
            )
            parser = SimpleNamespace(parse_args=lambda argv: arguments)
            with (
                patch.object(target, "_parser", return_value=parser),
                patch.object(target, "build_formal_progress_checkpoint") as build,
            ):
                with self.assertRaisesRegex(StudyManifestError, "directory is not frozen"):
                    target.main([])
            build.assert_not_called()

    def test_verify_existing_rejects_redirect_before_expensive_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / target._CHECKPOINT_ROOT
            parent.mkdir(parents=True)
            checkpoint_path = parent / "checkpoint-000174.json"
            checkpoint_path.write_text("{}", encoding="utf-8")
            arguments = SimpleNamespace(
                manifest=root / "manifest.json",
                calibration_manifest=root / "calibration-manifest.json",
                calibration_evidence=root / "calibration-evidence.json",
                precision=root / "precision.json",
                code_revision=target._EXECUTION_REVISION,
                workspace_root=root,
                output=checkpoint_path,
                verify_existing=True,
            )
            parser = SimpleNamespace(parse_args=lambda argv: arguments)
            real_lstat = target.os.lstat

            def lstat(path):
                result = real_lstat(path)
                if Path(path) != parent:
                    return result
                return SimpleNamespace(
                    st_mode=result.st_mode,
                    st_file_attributes=getattr(
                        target.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024
                    ),
                )

            with (
                patch.object(target, "_parser", return_value=parser),
                patch.object(target.os, "lstat", side_effect=lstat),
                patch.object(target, "load_formal_progress_checkpoint") as load,
            ):
                with self.assertRaisesRegex(StudyManifestError, "redirected component"):
                    target.main([])
            load.assert_not_called()

    def test_expected_checkpoint_path_rejects_dangling_leaf_symlink(self):
        checkpoint = _checkpoint()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf = (
                root
                / target._CHECKPOINT_ROOT
                / f"checkpoint-{checkpoint['completed_block_count']:06d}.json"
            )
            original_is_symlink = Path.is_symlink

            def report_leaf_symlink(path):
                if path == leaf:
                    return True
                return original_is_symlink(path)

            with patch.object(Path, "is_symlink", new=report_leaf_symlink):
                with self.assertRaises(StudyManifestError):
                    target._expected_checkpoint_path(
                        root, checkpoint["completed_block_count"]
                    )


if __name__ == "__main__":
    unittest.main()
