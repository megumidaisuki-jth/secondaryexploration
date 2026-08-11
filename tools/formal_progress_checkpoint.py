"""Build and replay non-inferential progress checkpoints for the formal phase."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from secondaryexploration.analysis.precision import (
    load_audited_calibration_evidence,
    load_formal_precision_evidence,
)
from secondaryexploration.experiments import (
    StudyManifestError,
    build_study_seed_ledger,
    load_study_design_manifest,
)
from secondaryexploration.experiments.artifacts import load_synthetic_block_artifact
from secondaryexploration.experiments.runner import (
    runtime_environment,
    runtime_environment_fingerprint,
    validate_frozen_execution_context,
)
from secondaryexploration.topology import ParentGraphModel


SCHEMA_VERSION = "formal-execution-progress.v1"
_STATUS = "in-progress-no-inferential-readout"
_EXECUTION_REVISION = "425710a418b1b28e6c5cd813dff18aeeaa6303c3"
_FORMAL_MANIFEST_FINGERPRINT = (
    "ac7152fc11b79c61b1ec14dc24b26d0ee60d159b00ddaa396e166651212191a6"
)
_EXPECTED_BLOCK_COUNT = 240
_SIZES = (30, 60, 120, 240)
_MODELS = (
    ParentGraphModel.ER_GNM,
    ParentGraphModel.BARABASI_ALBERT,
    ParentGraphModel.SBM_FIXED_COUNT,
)
_EXPECTED_KEYS = tuple(
    f"n{size:04d}-r{replicate:04d}-{model.value}"
    for size in _SIZES
    for replicate in range(20)
    for model in _MODELS
)
_LIMITATIONS = [
    "checkpoint-records-identities-and-completion-only-not-scientific-endpoints",
    "nested-traffic-traces-are-not-promoted-to-independent-units",
    "current-output-may-be-a-strict-superset-of-a-replayed-checkpoint",
    "checkpoint-does-not-replace-complete-phase-finalization-or-inference-gates",
]
_CHECKPOINT_ROOT = Path("results/diagnostics/formal-progress-checkpoints")
_ATOMIC_TEMP = re.compile(
    r"^\.(n\d{4}-r\d{4}-(?:er_gnm|barabasi_albert|sbm_fixed_count))"
    r"\.json\.[^.]+\.tmp$"
)
_STABILITY_ATTEMPTS = 20
_STABILITY_INTERVAL_SECONDS = 0.05
_FIELDS = {
    "schema_version",
    "status",
    "manifest_fingerprint",
    "seed_ledger_fingerprint",
    "calibration_evidence_fingerprint",
    "precision_fingerprint",
    "code_revision",
    "environment_fingerprint",
    "expected_block_count",
    "completed_block_count",
    "completed_by_cell",
    "blocks",
    "limitations",
    "checkpoint_fingerprint",
}


class _TransientSnapshotRace(Exception):
    """Signal a legitimate atomic-writer transition that requires re-enumeration."""


def build_formal_progress_checkpoint(
    manifest_path: Path,
    *,
    calibration_manifest_path: Path,
    calibration_evidence_path: Path,
    precision_path: Path,
    code_revision: str,
    workspace_root: Path = _ROOT,
) -> dict[str, object]:
    """Strict-load every completed artifact without exposing endpoint values."""

    manifest, ledger, environment, calibration, precision = _load_context(
        manifest_path,
        calibration_manifest_path=calibration_manifest_path,
        calibration_evidence_path=calibration_evidence_path,
        precision_path=precision_path,
        code_revision=code_revision,
    )
    root = workspace_root.resolve()
    output_root = (root / manifest.output_root).resolve()
    try:
        output_root.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("formal output root escapes workspace") from exc
    block_root = output_root / "blocks"
    jobs = _canonical_jobs(ledger)
    job_by_key = {key: (seed, model) for key, seed, model in jobs}
    observed = _observed_block_paths(block_root, set(job_by_key))

    rows = []
    for key, parent_seed, parent_model in jobs:
        path = observed.get(key)
        if path is None:
            continue
        raw_bytes = path.read_bytes()
        artifact = load_synthetic_block_artifact(
            path,
            manifest=manifest,
            ledger=ledger,
            parent_seed=parent_seed,
            parent_model=parent_model.value,
            code_revision=code_revision,
            environment=environment,
        )
        rows.append(
            {
                "block_key": key,
                "artifact_fingerprint": artifact["artifact_fingerprint"],
                "result_fingerprint": artifact["result_fingerprint"],
                "file_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            }
        )

    checkpoint: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": _STATUS,
        "manifest_fingerprint": manifest.fingerprint,
        "seed_ledger_fingerprint": ledger.fingerprint,
        "calibration_evidence_fingerprint": calibration["evidence_fingerprint"],
        "precision_fingerprint": precision["precision_fingerprint"],
        "code_revision": code_revision,
        "environment_fingerprint": runtime_environment_fingerprint(environment),
        "expected_block_count": len(jobs),
        "completed_block_count": len(rows),
        "completed_by_cell": _cell_counts(rows),
        "blocks": rows,
        "limitations": list(_LIMITATIONS),
    }
    checkpoint["checkpoint_fingerprint"] = _fingerprint(checkpoint)
    validate_formal_progress_checkpoint(checkpoint)
    return checkpoint


def load_formal_progress_checkpoint(
    path: Path,
    *,
    manifest_path: Path,
    calibration_manifest_path: Path,
    calibration_evidence_path: Path,
    precision_path: Path,
    code_revision: str,
    workspace_root: Path = _ROOT,
) -> dict[str, object]:
    """Replay a historical checkpoint while allowing later valid blocks."""

    try:
        raw = _load_one_json(path.read_bytes(), "formal progress checkpoint")
    except OSError as exc:
        raise StudyManifestError("cannot read formal progress checkpoint") from exc
    validate_formal_progress_checkpoint(raw)
    manifest, ledger, environment, calibration, precision = _load_context(
        manifest_path,
        calibration_manifest_path=calibration_manifest_path,
        calibration_evidence_path=calibration_evidence_path,
        precision_path=precision_path,
        code_revision=code_revision,
    )
    expected_sources = {
        "manifest_fingerprint": manifest.fingerprint,
        "seed_ledger_fingerprint": ledger.fingerprint,
        "calibration_evidence_fingerprint": calibration["evidence_fingerprint"],
        "precision_fingerprint": precision["precision_fingerprint"],
        "code_revision": code_revision,
        "environment_fingerprint": runtime_environment_fingerprint(environment),
    }
    if any(raw[field] != value for field, value in expected_sources.items()):
        raise StudyManifestError("formal progress source identity differs")

    root = workspace_root.resolve()
    block_root = (root / manifest.output_root / "blocks").resolve()
    jobs = _canonical_jobs(ledger)
    job_by_key = {key: (seed, model) for key, seed, model in jobs}
    observed = _observed_block_paths(block_root, set(job_by_key))
    for row in raw["blocks"]:
        key = row["block_key"]
        path = observed.get(key)
        if path is None:
            raise StudyManifestError("checkpointed formal block is missing")
        parent_seed, parent_model = job_by_key[key]
        raw_bytes = path.read_bytes()
        artifact = load_synthetic_block_artifact(
            path,
            manifest=manifest,
            ledger=ledger,
            parent_seed=parent_seed,
            parent_model=parent_model.value,
            code_revision=code_revision,
            environment=environment,
        )
        expected = {
            "block_key": key,
            "artifact_fingerprint": artifact["artifact_fingerprint"],
            "result_fingerprint": artifact["result_fingerprint"],
            "file_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        }
        if row != expected:
            raise StudyManifestError("checkpointed formal block replay differs")
    return raw


def validate_formal_progress_checkpoint(value: object) -> None:
    """Validate schema, canonical ordering, counts, and the outer fingerprint."""

    top = _mapping(value, _FIELDS, "formal progress checkpoint")
    if top["schema_version"] != SCHEMA_VERSION or top["status"] != _STATUS:
        raise StudyManifestError("formal progress schema or status differs")
    if (
        top["manifest_fingerprint"] != _FORMAL_MANIFEST_FINGERPRINT
        or top["code_revision"] != _EXECUTION_REVISION
        or top["expected_block_count"] != _EXPECTED_BLOCK_COUNT
        or top["limitations"] != _LIMITATIONS
    ):
        raise StudyManifestError("formal progress frozen identity differs")
    for field in (
        "manifest_fingerprint",
        "seed_ledger_fingerprint",
        "calibration_evidence_fingerprint",
        "precision_fingerprint",
        "environment_fingerprint",
        "checkpoint_fingerprint",
    ):
        _digest(top[field], field)
    _digest(top["code_revision"], "code_revision", 40)
    content = dict(top)
    supplied = content.pop("checkpoint_fingerprint")
    if supplied != _fingerprint(content):
        raise StudyManifestError("formal progress fingerprint mismatch")

    blocks = top["blocks"]
    if type(blocks) is not list or type(top["completed_block_count"]) is not int:
        raise StudyManifestError("formal progress block registry is invalid")
    if not 0 <= top["completed_block_count"] <= _EXPECTED_BLOCK_COUNT:
        raise StudyManifestError("formal progress completed count is invalid")
    if len(blocks) != top["completed_block_count"]:
        raise StudyManifestError("formal progress completed count differs")
    positions = []
    expected_position = {key: index for index, key in enumerate(_EXPECTED_KEYS)}
    for row in blocks:
        item = _mapping(
            row,
            {"block_key", "artifact_fingerprint", "result_fingerprint", "file_sha256"},
            "formal progress block",
        )
        key = item["block_key"]
        if type(key) is not str or key not in expected_position:
            raise StudyManifestError("formal progress block key is not registered")
        positions.append(expected_position[key])
        for field in ("artifact_fingerprint", "result_fingerprint", "file_sha256"):
            _digest(item[field], field)
    if positions != sorted(set(positions)):
        raise StudyManifestError("formal progress block order or uniqueness differs")
    if top["completed_by_cell"] != _cell_counts(blocks):
        raise StudyManifestError("formal progress cell counts differ")


def _load_context(
    manifest_path: Path,
    *,
    calibration_manifest_path: Path,
    calibration_evidence_path: Path,
    precision_path: Path,
    code_revision: str,
):
    manifest = load_study_design_manifest(manifest_path)
    calibration = load_audited_calibration_evidence(calibration_evidence_path)
    precision = load_formal_precision_evidence(
        precision_path, calibration_evidence=calibration
    )
    calibration_manifest = load_study_design_manifest(calibration_manifest_path)
    environment = runtime_environment()
    validate_frozen_execution_context(
        manifest,
        code_revision=code_revision,
        environment=environment,
        precision_evidence=precision,
        calibration_manifest=calibration_manifest,
    )
    ledger = build_study_seed_ledger(manifest)
    if (
        manifest.study_id != "synthetic-formal-v1"
        or manifest.fingerprint != _FORMAL_MANIFEST_FINGERPRINT
        or code_revision != _EXECUTION_REVISION
        or len(_canonical_jobs(ledger)) != _EXPECTED_BLOCK_COUNT
    ):
        raise StudyManifestError("progress checkpoint requires the frozen formal study")
    return manifest, ledger, environment, calibration, precision


def _canonical_jobs(ledger):
    return tuple(
        (
            f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model.value}",
            seed,
            model,
        )
        for seed in ledger.parent_seeds
        for model in _MODELS
    )


def _observed_block_paths(block_root: Path, expected_keys: set[str]):
    """Return one stable atomic snapshot, retrying only active writer temps."""

    for _attempt in range(_STABILITY_ATTEMPTS):
        try:
            entries = tuple(block_root.iterdir())
        except OSError as exc:
            raise StudyManifestError("cannot inspect formal block directory") from exc
        try:
            active_locks = _active_lock_keys(block_root / ".locks", expected_keys)
        except _TransientSnapshotRace:
            time.sleep(_STABILITY_INTERVAL_SECONDS)
            continue
        observed = {}
        transient = False
        for entry in entries:
            if entry.name == ".locks":
                continue
            match = _ATOMIC_TEMP.fullmatch(entry.name)
            if match is not None:
                try:
                    mode = entry.lstat().st_mode
                except FileNotFoundError:
                    transient = True
                    continue
                if (
                    match.group(1) not in active_locks
                    or stat.S_ISLNK(mode)
                    or not stat.S_ISREG(mode)
                ):
                    raise StudyManifestError("formal atomic temporary entry is invalid")
                transient = True
                continue
            if entry.is_symlink() or not entry.is_file() or entry.suffix != ".json":
                raise StudyManifestError(
                    "formal block directory contains an unknown entry"
                )
            key = entry.stem
            if key not in expected_keys or key in observed:
                raise StudyManifestError("formal block registry contains an unknown key")
            observed[key] = entry
        if not transient:
            return observed
        time.sleep(_STABILITY_INTERVAL_SECONDS)
    raise StudyManifestError("formal block directory did not reach a stable snapshot")


def _active_lock_keys(lock_root: Path, expected_keys: set[str]) -> set[str]:
    if not lock_root.exists():
        return set()
    if lock_root.is_symlink() or not lock_root.is_dir():
        raise StudyManifestError("formal lock entry is invalid")
    active = set()
    try:
        entries = tuple(lock_root.iterdir())
    except OSError as exc:
        raise StudyManifestError("cannot inspect formal lock directory") from exc
    for entry in entries:
        if entry.suffix != ".lock":
            raise StudyManifestError("formal lock directory contains an unknown entry")
        key = entry.stem
        if key not in expected_keys or key in active:
            raise StudyManifestError("formal lock registry contains an unknown key")
        try:
            mode = entry.lstat().st_mode
        except FileNotFoundError as exc:
            raise _TransientSnapshotRace from exc
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise StudyManifestError("formal lock directory contains an unknown entry")
        active.add(key)
    return active


def _cell_counts(blocks):
    counts = {(size, model.value): 0 for size in _SIZES for model in _MODELS}
    for row in blocks:
        size_part, _replicate_part, model = row["block_key"].split("-", 2)
        key = (int(size_part[1:]), model)
        if key not in counts:
            raise StudyManifestError("formal progress cell is not registered")
        counts[key] += 1
    return [
        {
            "node_count": size,
            "parent_model": model.value,
            "completed_parent_count": counts[(size, model.value)],
        }
        for size in _SIZES
        for model in _MODELS
    ]


def _mapping(value, fields, label):
    if not isinstance(value, Mapping) or set(value) != fields:
        raise StudyManifestError(f"{label} fields differ")
    return value


def _digest(value, label, length=64):
    if (
        type(value) is not str
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError(f"{label} must be lowercase hexadecimal")


def _fingerprint(mapping):
    return hashlib.sha256(
        json.dumps(
            mapping,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _load_one_json(raw: bytes, label: str):
    try:
        text = raw.decode("utf-8")
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise StudyManifestError(f"{label} must be strict JSON") from exc


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"non-finite JSON constant {value!r}")


def _write_new_checkpoint(
    output_directory: Path,
    checkpoint: Mapping[str, object],
    *,
    workspace_root: Path,
) -> Path:
    """Atomically create one count-addressed checkpoint without replacement."""

    validate_formal_progress_checkpoint(checkpoint)
    expected = _expected_checkpoint_path(
        workspace_root, checkpoint["completed_block_count"]
    )
    parent = _validate_checkpoint_output_directory(
        output_directory, workspace_root=workspace_root
    )
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise StudyManifestError("formal progress output directory is invalid")
    if expected.exists():
        raise StudyManifestError("formal progress checkpoint already exists")
    payload = (
        json.dumps(
            checkpoint,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    temporary_name = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=parent,
            prefix=f".{expected.name}.",
            suffix=".tmp",
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_name, expected)
        except FileExistsError as exc:
            raise StudyManifestError("formal progress checkpoint already exists") from exc
    finally:
        if temporary_name is not None:
            temporary = Path(temporary_name)
            if temporary.exists():
                temporary.unlink()
    return expected


def _validate_checkpoint_output_directory(
    output_directory: Path, *, workspace_root: Path
) -> Path:
    """Reject a non-canonical output argument before any expensive replay."""

    expected_parent = _expected_checkpoint_path(workspace_root, 0).parent
    if output_directory.is_symlink() or output_directory.resolve() != expected_parent:
        raise StudyManifestError("formal progress output directory is not frozen")
    if output_directory.exists() and not output_directory.is_dir():
        raise StudyManifestError("formal progress output directory is invalid")
    return expected_parent


def _expected_checkpoint_path(workspace_root: Path, completed_count: int) -> Path:
    root = workspace_root.resolve()
    raw = root / _CHECKPOINT_ROOT / f"checkpoint-{completed_count:06d}.json"
    if raw.is_symlink():
        raise StudyManifestError("formal progress checkpoint path is a symlink")
    current = root
    for part in raw.relative_to(root).parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise StudyManifestError("formal progress output path contains a symlink")
    expected = raw.resolve()
    try:
        expected.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("formal progress output path escapes workspace") from exc
    return expected


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--calibration-manifest", required=True, type=Path)
    parser.add_argument("--calibration-evidence", required=True, type=Path)
    parser.add_argument("--precision", required=True, type=Path)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--workspace-root", default=_ROOT, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    kwargs = {
        "manifest_path": arguments.manifest,
        "calibration_manifest_path": arguments.calibration_manifest,
        "calibration_evidence_path": arguments.calibration_evidence,
        "precision_path": arguments.precision,
        "code_revision": arguments.code_revision,
        "workspace_root": arguments.workspace_root,
    }
    if arguments.verify_existing:
        checkpoint = load_formal_progress_checkpoint(arguments.output, **kwargs)
        expected = _expected_checkpoint_path(
            arguments.workspace_root, checkpoint["completed_block_count"]
        )
        if arguments.output.resolve() != expected:
            raise StudyManifestError(
                "formal progress output path is not count-addressed"
            )
    else:
        _validate_checkpoint_output_directory(
            arguments.output, workspace_root=arguments.workspace_root
        )
        checkpoint = build_formal_progress_checkpoint(**kwargs)
        checkpoint_path = _write_new_checkpoint(
            arguments.output,
            checkpoint,
            workspace_root=arguments.workspace_root,
        )
    print(
        json.dumps(
            {
                "status": checkpoint["status"],
                "completed_block_count": checkpoint["completed_block_count"],
                "checkpoint_fingerprint": checkpoint["checkpoint_fingerprint"],
                "checkpoint_path": str(
                    arguments.output if arguments.verify_existing else checkpoint_path
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SCHEMA_VERSION",
    "build_formal_progress_checkpoint",
    "load_formal_progress_checkpoint",
    "main",
    "validate_formal_progress_checkpoint",
]
