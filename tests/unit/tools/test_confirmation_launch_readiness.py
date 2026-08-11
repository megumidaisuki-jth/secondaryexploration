"""Tests for the result-blind confirmation launch-readiness witness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from secondaryexploration.experiments import StudyManifestError
from tools import confirmation_launch_readiness as target


class ConfirmationLaunchReadinessTests(unittest.TestCase):
    def _source_paths(self, root: Path, *, canonical: bool = False) -> dict[str, Path]:
        paths = {}
        for role in target._SOURCE_ROLES:
            path = (
                root / target._CANONICAL_SOURCE_PATHS[role]
                if canonical
                else root / "inputs" / f"{role}.json"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
            paths[role] = path.resolve()
        return paths

    def _record(self, root: Path, paths: dict[str, Path]) -> dict[str, object]:
        record = {
            "schema_version": target.SCHEMA_VERSION,
            "status": target.STATUS,
            "created_at_utc": "2026-08-11T12:00:00.000Z",
            "readiness_revision": "a" * 40,
            "analysis_revision": "b" * 40,
            "execution_revision": target.EXECUTION_REVISION,
            "environment_fingerprint": target.ENVIRONMENT_FINGERPRINT,
            "formal_manifest_fingerprint": target.FORMAL_MANIFEST_FINGERPRINT,
            "formal_summary_fingerprint": "c" * 64,
            "formal_phase_evidence_fingerprint": "d" * 64,
            "formal_block_registry_fingerprint": "e" * 64,
            "source_records": target._source_records(root, paths),
            "limitations": list(target._LIMITATIONS),
        }
        record["readiness_fingerprint"] = target._mapping_fingerprint(record)
        return record

    def _minimal_build_fixture(self, root: Path, *, output: str | None = None):
        paths = self._source_paths(root, canonical=True)
        manifest = SimpleNamespace(
            phase=SimpleNamespace(value="formal"),
            fingerprint=target.FORMAL_MANIFEST_FINGERPRINT,
            output_root="outputs/formal/synthetic-formal-v1",
        )
        summary = {
            "summary_fingerprint": "c" * 64,
            "environment": {"test": True},
            "blocks": [],
        }
        evidence = {
            "phase": "formal",
            "block_registry": [{} for _ in range(target.BLOCK_COUNT)],
            "evidence_fingerprint": "d" * 64,
        }
        args = SimpleNamespace(
            formal_manifest=paths["formal_manifest"],
            formal_summary=paths["formal_summary"],
            formal_evidence=paths["formal_phase_evidence"],
            finalization_witness=paths["formal_finalization_witness"],
            calibration_manifest=paths["calibration_manifest"],
            calibration_evidence=paths["calibration_evidence"],
            precision=paths["precision_evidence"],
            analysis_revision="b" * 40,
            readiness_revision="a" * 40,
            workspace_root=root,
            output=output or target._CANONICAL_OUTPUT,
        )
        sources = (manifest, object(), summary, object(), object(), object())
        return paths, args, sources, evidence

    def test_result_blind_validator_never_calls_phase_loader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = self._source_paths(root, canonical=True)
            record = self._record(root, paths)
            with mock.patch.object(
                target,
                "load_phase_evidence",
                side_effect=AssertionError("result-bearing loader was accessed"),
            ):
                target.validate_readiness_record(
                    record, root=root, expected_paths=paths
                )

    def test_git_pinned_result_blind_loader_never_parses_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = self._source_paths(root, canonical=True)
            keys = tuple(f"block-{index:03d}" for index in range(target.BLOCK_COUNT))
            block_root = root / "outputs/formal/synthetic-formal-v1/blocks"
            (block_root / ".locks").mkdir(parents=True)
            registry = []
            for index, key in enumerate(keys):
                block = block_root / f"{key}.json"
                block.write_text(f"{index}\n", encoding="utf-8")
                registry.append({"block_key": key, "file_sha256": target._sha256_file(block)})
            finalization = {
                "schema_version": "formal-streaming-finalization-witness.v1",
                "status": "complete-memory-bounded-strict-replay",
                "phase": "formal",
                "analysis_revision": "b" * 40,
                "execution_revision": target.EXECUTION_REVISION,
                "manifest_fingerprint": target.FORMAL_MANIFEST_FINGERPRINT,
                "summary_fingerprint": "c" * 64,
                "block_count": target.BLOCK_COUNT,
                "block_byte_registry": registry,
                "limitations": list(target._FINALIZATION_LIMITATIONS),
            }
            finalization["witness_fingerprint"] = target._mapping_fingerprint(finalization)
            paths["formal_finalization_witness"].write_text(
                json.dumps(finalization, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            record = self._record(root, paths)
            record["formal_block_registry_fingerprint"] = target._registry_fingerprint(registry)
            record["readiness_fingerprint"] = target._mapping_fingerprint(
                {key: value for key, value in record.items() if key != "readiness_fingerprint"}
            )
            witness = root / target._CANONICAL_OUTPUT
            witness.parent.mkdir(parents=True, exist_ok=True)
            witness.write_text(
                json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            completed = SimpleNamespace(returncode=0, stdout="")
            with (
                mock.patch.object(target, "_git", return_value=completed),
                mock.patch.object(
                    target,
                    "_git_blob_sha256",
                    return_value=target._sha256_file(witness),
                ),
                mock.patch.object(target, "verify_source_snapshots"),
                mock.patch.object(target, "_canonical_formal_block_keys", return_value=keys),
                mock.patch.object(
                    target,
                    "load_phase_evidence",
                    side_effect=AssertionError("phase evidence was parsed"),
                ),
            ):
                loaded = target.load_readiness_result_blind(
                    witness,
                    root=root,
                    authorization_revision="f" * 40,
                    readiness_revision="a" * 40,
                    analysis_revision="b" * 40,
                )
            self.assertEqual(loaded, record)
            (block_root / f"{keys[-1]}.json").write_text("tampered\n", encoding="utf-8")
            with (
                mock.patch.object(target, "_git", return_value=completed),
                mock.patch.object(
                    target,
                    "_git_blob_sha256",
                    return_value=target._sha256_file(witness),
                ),
                mock.patch.object(target, "verify_source_snapshots"),
                mock.patch.object(target, "_canonical_formal_block_keys", return_value=keys),
            ):
                with self.assertRaisesRegex(StudyManifestError, "block bytes"):
                    target.load_readiness_result_blind(
                        witness,
                        root=root,
                        authorization_revision="f" * 40,
                        readiness_revision="a" * 40,
                        analysis_revision="b" * 40,
                    )

    def test_raw_git_blob_hash_detects_autocrlf_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(("git", "init", "-q"), cwd=root, check=True)
            subprocess.run(("git", "config", "user.name", "Readiness Test"), cwd=root, check=True)
            subprocess.run(("git", "config", "user.email", "test@example.invalid"), cwd=root, check=True)
            subprocess.run(("git", "config", "core.autocrlf", "true"), cwd=root, check=True)
            relative = target._CANONICAL_OUTPUT
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b'{"ready":true}\n')
            subprocess.run(("git", "add", "--", relative), cwd=root, check=True)
            subprocess.run(("git", "commit", "-q", "-m", "pin"), cwd=root, check=True)
            revision = subprocess.run(
                ("git", "rev-parse", "HEAD"),
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            path.write_bytes(b'{"ready":true}\r\n')
            self.assertNotEqual(
                target._git_blob_sha256(root, revision, relative),
                target._sha256_file(path),
            )
            with self.assertRaisesRegex(StudyManifestError, "raw bytes"):
                target.load_readiness_result_blind(
                    path,
                    root=root,
                    authorization_revision=revision,
                    readiness_revision="a" * 40,
                    analysis_revision="b" * 40,
                )

    def test_inside_rejects_redirected_path_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            real = root / "real"
            real.mkdir()
            redirected = root / "redirected"
            try:
                redirected.symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(StudyManifestError, "redirected component"):
                target._inside(root, "redirected/formal-ready.json", must_exist=False)

    def test_inside_rejects_simulated_windows_reparse_component(self) -> None:
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
                    st_file_attributes=getattr(target.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024),
                )

            with mock.patch.object(target.os, "lstat", side_effect=lstat):
                with self.assertRaisesRegex(StudyManifestError, "redirected component"):
                    target._inside(root, "redirected/formal-ready.json", must_exist=False)

    def test_build_rechecks_source_snapshots_after_full_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths, args, sources, evidence = self._minimal_build_fixture(root)
            stable_registry = [
                {"block_key": f"block-{index:03d}", "file_sha256": "f" * 64}
                for index in range(target.BLOCK_COUNT)
            ]
            with (
                mock.patch.object(
                    target,
                    "verify_source_snapshots",
                    side_effect=[None, StudyManifestError("source drift")],
                ) as snapshots,
                mock.patch.object(target, "load_phase_sources", return_value=sources),
                mock.patch.object(target, "load_phase_evidence", return_value=evidence),
                mock.patch.object(
                    target, "_validate_finalization_witness", return_value=stable_registry
                ),
            ):
                with self.assertRaisesRegex(StudyManifestError, "source drift"):
                    target.build_readiness(args)
            self.assertEqual(snapshots.call_count, 2)
            self.assertFalse((root / target._CANONICAL_OUTPUT).exists())

    def test_build_rejects_noncanonical_input_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths, args, sources, evidence = self._minimal_build_fixture(root)
            alternate = root / "alternate-summary.json"
            alternate.write_text("{}\n", encoding="utf-8")
            args.formal_summary = alternate
            with self.assertRaisesRegex(StudyManifestError, "canonical source"):
                target.build_readiness(args)
            args.formal_summary = paths["formal_summary"]
            args.output = "results/diagnostics/confirmation-launch-readiness/other.json"
            stable_registry = [
                {"block_key": f"block-{index:03d}", "file_sha256": "f" * 64}
                for index in range(target.BLOCK_COUNT)
            ]
            with (
                mock.patch.object(target, "verify_source_snapshots"),
                mock.patch.object(target, "load_phase_sources", return_value=sources),
                mock.patch.object(target, "load_phase_evidence", return_value=evidence),
                mock.patch.object(
                    target, "_validate_finalization_witness", return_value=stable_registry
                ),
            ):
                with self.assertRaisesRegex(StudyManifestError, "canonical path"):
                    target.build_readiness(args)

    def test_create_only_and_git_revision_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / target._CANONICAL_OUTPUT
            target._atomic_create(path, {"first": True})
            with self.assertRaisesRegex(StudyManifestError, "already exists"):
                target._atomic_create(path, {"second": True})
            failed = SimpleNamespace(returncode=1, stdout="")
            with mock.patch.object(target, "_git", return_value=failed):
                with self.assertRaisesRegex(StudyManifestError, "revision"):
                    target.load_readiness_result_blind(
                        path,
                        root=root,
                        authorization_revision="f" * 40,
                        readiness_revision="a" * 40,
                        analysis_revision="b" * 40,
                    )

    def test_exact_schema_rejects_rehashed_result_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = self._source_paths(root)
            record = self._record(root, paths)
            record["formal_interval_direction"] = "beneficial"
            record["readiness_fingerprint"] = target._mapping_fingerprint(
                {key: value for key, value in record.items() if key != "readiness_fingerprint"}
            )
            with self.assertRaisesRegex(StudyManifestError, "fields"):
                target.validate_readiness_record(record, root=root)

    def test_result_blind_validator_rejects_source_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = self._source_paths(root)
            record = self._record(root, paths)
            paths["formal_phase_evidence"].write_text("{\"changed\":true}\n", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "bytes changed"):
                target.validate_readiness_record(record, root=root)

    def test_finalization_witness_replays_all_block_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / "outputs/formal/synthetic-formal-v1"
            block_root = output / "blocks"
            block_root.mkdir(parents=True)
            blocks = []
            registry = []
            for index in range(target.BLOCK_COUNT):
                key = f"block-{index:03d}"
                path = block_root / f"{key}.json"
                path.write_text(f"{index}\n", encoding="utf-8")
                blocks.append({"block_key": key})
                registry.append({"block_key": key, "file_sha256": target._sha256_file(path)})
            summary = {"summary_fingerprint": "c" * 64, "blocks": blocks}
            manifest = SimpleNamespace(output_root="outputs/formal/synthetic-formal-v1")
            witness = {
                "schema_version": "formal-streaming-finalization-witness.v1",
                "status": "complete-memory-bounded-strict-replay",
                "phase": "formal",
                "analysis_revision": "b" * 40,
                "execution_revision": target.EXECUTION_REVISION,
                "manifest_fingerprint": target.FORMAL_MANIFEST_FINGERPRINT,
                "summary_fingerprint": "c" * 64,
                "block_count": target.BLOCK_COUNT,
                "block_byte_registry": registry,
                "limitations": list(target._FINALIZATION_LIMITATIONS),
            }
            witness["witness_fingerprint"] = target._mapping_fingerprint(witness)
            self.assertEqual(
                target._validate_finalization_witness(
                    witness,
                    root=root,
                    summary=summary,
                    manifest=manifest,
                    analysis_revision="b" * 40,
                ),
                registry,
            )
            (block_root / "block-239.json").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(StudyManifestError, "byte registry"):
                target._validate_finalization_witness(
                    witness,
                    root=root,
                    summary=summary,
                    manifest=manifest,
                    analysis_revision="b" * 40,
                )

    def test_build_requires_full_replay_and_emits_no_result_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = self._source_paths(root, canonical=True)
            output_root = root / "outputs/formal/synthetic-formal-v1"
            block_root = output_root / "blocks"
            block_root.mkdir(parents=True)
            blocks = []
            registry = []
            for index in range(target.BLOCK_COUNT):
                key = f"block-{index:03d}"
                path = block_root / f"{key}.json"
                path.write_text(f"{index}\n", encoding="utf-8")
                blocks.append({"block_key": key})
                registry.append({"block_key": key, "file_sha256": target._sha256_file(path)})
            summary = {
                "summary_fingerprint": "c" * 64,
                "code_revision": target.EXECUTION_REVISION,
                "environment": {"test": True},
                "blocks": blocks,
            }
            manifest = SimpleNamespace(
                phase=SimpleNamespace(value="formal"),
                fingerprint=target.FORMAL_MANIFEST_FINGERPRINT,
                output_root="outputs/formal/synthetic-formal-v1",
            )
            finalization = {
                "schema_version": "formal-streaming-finalization-witness.v1",
                "status": "complete-memory-bounded-strict-replay",
                "phase": "formal",
                "analysis_revision": "b" * 40,
                "execution_revision": target.EXECUTION_REVISION,
                "manifest_fingerprint": target.FORMAL_MANIFEST_FINGERPRINT,
                "summary_fingerprint": "c" * 64,
                "block_count": target.BLOCK_COUNT,
                "block_byte_registry": registry,
                "limitations": list(target._FINALIZATION_LIMITATIONS),
            }
            finalization["witness_fingerprint"] = target._mapping_fingerprint(finalization)
            paths["formal_finalization_witness"].write_text(
                json.dumps(finalization, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            evidence = {
                "phase": "formal",
                "block_registry": [{} for _ in range(target.BLOCK_COUNT)],
                "evidence_fingerprint": "d" * 64,
            }
            args = SimpleNamespace(
                formal_manifest=paths["formal_manifest"],
                formal_summary=paths["formal_summary"],
                formal_evidence=paths["formal_phase_evidence"],
                finalization_witness=paths["formal_finalization_witness"],
                calibration_manifest=paths["calibration_manifest"],
                calibration_evidence=paths["calibration_evidence"],
                precision=paths["precision_evidence"],
                analysis_revision="b" * 40,
                readiness_revision="a" * 40,
                workspace_root=root,
                output="results/diagnostics/confirmation-launch-readiness/formal-ready.json",
            )
            sources = (manifest, object(), summary, object(), object(), object())
            with (
                mock.patch.object(target, "verify_source_snapshots"),
                mock.patch.object(target, "load_phase_sources", return_value=sources),
                mock.patch.object(target, "load_phase_evidence", return_value=evidence) as replay,
                mock.patch.object(
                    target,
                    "runtime_environment_fingerprint",
                    return_value=target.ENVIRONMENT_FINGERPRINT,
                ),
            ):
                created = target.build_readiness(args)
                target.build_readiness(args)
            self.assertEqual(replay.call_count, 2)
            record = json.loads(created.read_text(encoding="utf-8"))
            target.validate_readiness_record(record, root=root, expected_paths=paths)
            banned = {"interval", "lower", "upper", "gate", "estimate", "direction", "point"}
            self.assertTrue(all(not any(word in key for word in banned) for key in record))


if __name__ == "__main__":
    unittest.main()
