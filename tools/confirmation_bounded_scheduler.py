"""Run frozen confirmation blocks as memory-bounded singleton child processes.

This is an operational wrapper around the frozen scientific runner.  It never
imports endpoint values, changes a seed, or writes a scientific artifact.  A
logical worker count of 240 makes every child own exactly one canonical block;
the wrapper permits at most six such children to be live at once.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Callable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from secondaryexploration.experiments import (
    StudyManifestError,
    build_study_seed_ledger,
    load_study_design_manifest,
)
from secondaryexploration.experiments.runner import (
    _block_key,
    _registered_block_jobs,
    _select_worker_jobs,
    preflight_synthetic_study,
    runtime_environment,
    runtime_environment_fingerprint,
)
from tools.confirmation_launch_readiness import load_readiness_result_blind
from tools import formal_bounded_scheduler as formal_scheduler


SCHEMA_VERSION = "confirmation-bounded-scheduler-session.v1"
BATCH_SCHEMA_VERSION = "confirmation-bounded-scheduler-batch.v1"
FINAL_SCHEMA_VERSION = "confirmation-bounded-scheduler-finalization.v1"
EXECUTION_REVISION = "425710a418b1b28e6c5cd813dff18aeeaa6303c3"
CONFIRMATION_MANIFEST_FINGERPRINT = (
    "dd3caac05a77e89ff69f24dde32930365334b39d4b6cdd5b5d773f5380c3fb5a"
)
FORMAL_MANIFEST_FINGERPRINT = (
    "ac7152fc11b79c61b1ec14dc24b26d0ee60d159b00ddaa396e166651212191a6"
)
ENVIRONMENT_FINGERPRINT = (
    "0a499b6a1334446fa6bf02a02b25e80934a22689168d6282a2ccb067ac6216c3"
)
LOGICAL_SHARD_COUNT = 240
MAX_CONCURRENCY = 6
SIX_SINGLE_BLOCK_ENVELOPE_BYTES = 2_243_665_920
MIN_AVAILABLE_MEMORY_BYTES = 2 * SIX_SINGLE_BLOCK_ENVELOPE_BYTES
_SESSION_ROOT = Path("results/diagnostics/confirmation-bounded-scheduler")
_GLOBAL_LEASE_ROOT = Path("results/diagnostics/formal-bounded-scheduler")
READINESS_REVISION = "04356260731e2ac330d59a777490813a41322c94"
ANALYSIS_REVISION = "9ecaadec84f8bebe799fb507969de8e0a0947b66"
_SESSION_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{7,79}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_TOOL_PATHS = (
    "tools/confirmation_bounded_scheduler.py",
    "tools/confirmation_launch_readiness.py",
    "tools/formal_bounded_scheduler.py",
    "docs/plans/2026-08-11-confirmation-memory-operational-amendment.md",
)
_SESSION_FIELDS = {
    "schema_version",
    "status",
    "session_id",
    "created_at_utc",
    "orchestration_revision",
    "execution_revision",
    "python_executable",
    "environment_fingerprint",
    "manifest_fingerprint",
    "logical_shard_count",
    "maximum_concurrency",
    "minimum_available_memory_bytes",
    "readiness_fingerprint",
    "readiness_authorization_revision",
    "initial_completed_block_count",
    "initial_block_registry_fingerprint",
    "sources",
    "schedule",
    "limitations",
    "fingerprint",
}
_LAUNCH_FIELDS = {
    "schema_version",
    "status",
    "session_fingerprint",
    "batch_number",
    "started_at_utc",
    "available_memory_bytes_before_launch",
    "workers",
    "fingerprint",
}
_LAUNCH_WORKER_FIELDS = {
    "worker_index",
    "block_key",
    "command",
    "command_sha256",
    "stdout_file",
    "stderr_file",
}
_STARTED_FIELDS = {
    "schema_version",
    "status",
    "session_fingerprint",
    "batch_number",
    "launch_fingerprint",
    "captured_at_utc",
    "scheduler_process_id",
    "workers",
    "fingerprint",
}
_STARTED_WORKER_FIELDS = {
    "worker_index",
    "block_key",
    "process_id",
    "parent_process_id",
    "process_creation_time",
    "command_line",
    "command_line_sha256",
    "stdout_file",
    "stderr_file",
}
_ABORT_FIELDS = {
    "schema_version",
    "status",
    "session_fingerprint",
    "batch_number",
    "launch_fingerprint",
    "captured_at_utc",
    "spawned_process_ids",
    "fingerprint",
}
_FINAL_FIELDS = {
    "schema_version",
    "status",
    "session_fingerprint",
    "batch_number",
    "launch_fingerprint",
    "started_fingerprint",
    "completed_at_utc",
    "launched_process_count",
    "configured_concurrency_ceiling",
    "available_memory_bytes_after_exit",
    "workers",
    "fingerprint",
}
_FINAL_WORKER_FIELDS = {
    "worker_index",
    "block_key",
    "process_id",
    "started_at_utc",
    "completed_at_utc",
    "exit_code",
    "stdout_file",
    "stdout_sha256",
    "stderr_file",
    "stderr_sha256",
    "artifact_file",
    "artifact_sha256",
}
_RECOVERY_FIELDS = {
    "schema_version",
    "status",
    "session_fingerprint",
    "batch_number",
    "launch_fingerprint",
    "started_fingerprint",
    "recovered_at_utc",
    "workers",
    "limitations",
    "fingerprint",
}
_RECOVERY_WORKER_FIELDS = {
    "worker_index",
    "block_key",
    "artifact_state",
    "artifact_sha256",
}
_COMPLETION_FIELDS = {
    "schema_version",
    "status",
    "session_fingerprint",
    "completed_at_utc",
    "completed_worker_indices",
    "final_batch_count",
    "final_block_count",
    "final_block_registry_fingerprint",
    "fingerprint",
}
_SOURCE_PATHS = (
    "configs/confirmation/synthetic-confirmation-v1.json",
    "configs/pilot/synthetic-calibration-v1.json",
    "results/pilot/synthetic-calibration-v1/evidence.json",
    "results/planning/formal-precision-v1.json",
    "results/diagnostics/confirmation-launch-readiness/formal-ready.json",
    (
        "results/diagnostics/formal-bounded-scheduler/"
        "formal-20260811-memory-v1/completion.json"
    ),
)
_SESSION_LIMITATIONS = [
    "operational-memory-amendment-only-no-scientific-contract-change",
    "scheduler-does-not-read-or-aggregate-scientific-endpoints",
    "legacy-whole-phase-finalizer-and-loader-disabled-revision-bound-streaming-paths-required",
]
_RECOVERY_LIMITATIONS_STARTED = [
    "recovery-does-not-accept-artifact-validity",
    "each-index-remains-pending-for-frozen-child-strict-replay",
]
_RECOVERY_LIMITATIONS_NO_START = [
    "complete-child-pid-witness-was-not-published-before-interruption",
    "global-cross-phase-runner-scan-and-quiescent-filesystem-proved-before-recovery",
    "recovery-does-not-accept-artifact-validity",
    "each-index-remains-pending-for-frozen-child-strict-replay",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _fingerprint(value: Mapping[str, object]) -> str:
    payload = dict(value)
    payload.pop("fingerprint", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    _assert_plain_path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_plain_path(path: Path) -> None:
    candidate = Path(os.path.abspath(str(path)))
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or (
            attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise StudyManifestError("scheduler path contains a redirected component")


def _block_registry_fingerprint(observed: Mapping[str, Path]) -> str:
    rows = [
        {"block_key": key, "file_sha256": _file_sha256(observed[key])}
        for key in sorted(observed)
    ]
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, object]:
    _assert_plain_path(path)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise StudyManifestError(f"{label} contains a duplicate JSON key")
            result[key] = value
        return result

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            value = json.load(handle, object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StudyManifestError(f"cannot load {label}") from exc
    if not isinstance(value, dict):
        raise StudyManifestError(f"{label} must be a JSON object")
    return value


def _write_create_only(
    path: Path,
    value: Mapping[str, object],
    *,
    prepublish: Callable[[], None] | None = None,
) -> None:
    """Atomically publish canonical JSON without replacing an existing witness."""

    _assert_plain_path(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_plain_path(path.parent)
    if path.exists() or path.is_symlink():
        raise StudyManifestError(f"scheduler witness already exists: {path.name}")
    payload = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    descriptor, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if prepublish is not None:
            prepublish()
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise StudyManifestError(
                f"scheduler witness already exists: {path.name}"
            ) from exc
    finally:
        temp.unlink(missing_ok=True)


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ("git", "-C", str(root), *arguments),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise StudyManifestError("Git is required for scheduler attestation") from exc


def verify_source_snapshots(root: Path, orchestration_revision: str) -> None:
    """Bind frozen execution source and the operational wrapper independently."""

    if not _REVISION.fullmatch(orchestration_revision):
        raise StudyManifestError("orchestration revision must be a full Git SHA")
    for revision in (EXECUTION_REVISION, orchestration_revision):
        if _git(root, "rev-parse", "--verify", f"{revision}^{{commit}}").returncode:
            raise StudyManifestError("declared Git revision does not exist")
    for path in _TOOL_PATHS:
        if _git(root, "cat-file", "-e", f"{orchestration_revision}:{path}").returncode:
            raise StudyManifestError("orchestration revision does not contain its contract")
    if _git(root, "diff", "--quiet", orchestration_revision, "--", *_TOOL_PATHS).returncode:
        raise StudyManifestError("scheduler or operational amendment is dirty")
    if _git(
        root,
        "diff",
        "--quiet",
        EXECUTION_REVISION,
        "--",
        "secondaryexploration",
        ":(exclude)secondaryexploration/analysis/formal_freeze.py",
    ).returncode:
        raise StudyManifestError("scientific execution source differs from its freeze")
    untracked = _git(
        root, "ls-files", "--others", "--exclude-standard", "--", "secondaryexploration"
    )
    if untracked.returncode or untracked.stdout.strip():
        raise StudyManifestError("untracked scientific execution source is present")


def canonical_singleton_schedule(manifest_path: Path) -> tuple[dict[str, object], ...]:
    """Return the exact 240 canonical ordinal/key singleton assignments."""

    manifest = load_study_design_manifest(manifest_path)
    if manifest.fingerprint != CONFIRMATION_MANIFEST_FINGERPRINT:
        raise StudyManifestError("scheduler accepts only the frozen confirmation manifest")
    ledger = build_study_seed_ledger(manifest)
    jobs = _registered_block_jobs(ledger)
    if len(jobs) != LOGICAL_SHARD_COUNT:
        raise StudyManifestError("confirmation registry is not exactly 240 blocks")
    rows = []
    for index, (seed, model) in enumerate(jobs):
        selected = _select_worker_jobs(ledger, LOGICAL_SHARD_COUNT, index)
        if len(selected) != 1 or selected[0] != (seed, model):
            raise StudyManifestError("logical singleton partition is not exact")
        rows.append(
            {
                "worker_index": index,
                "block_key": _block_key(seed.node_count, seed.parent_replicate, model),
            }
        )
    if len({row["block_key"] for row in rows}) != LOGICAL_SHARD_COUNT:
        raise StudyManifestError("confirmation singleton keys are not unique")
    return tuple(rows)


def available_physical_memory_bytes() -> int:
    """Return Windows available physical memory without an optional dependency."""

    if os.name != "nt":
        try:
            pages = os.sysconf("SC_AVPHYS_PAGES")
            size = os.sysconf("SC_PAGE_SIZE")
        except (AttributeError, OSError, ValueError) as exc:
            raise StudyManifestError("cannot inspect available physical memory") from exc
        return int(pages * size)
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise StudyManifestError("cannot inspect available physical memory")
    return int(status.available_physical)


def _assert_quiescent_output(root: Path, expected_keys: set[str]) -> dict[str, Path]:
    output = root / "outputs" / "confirmation" / "synthetic-confirmation-v1"
    _assert_plain_path(output)
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise StudyManifestError("confirmation output root is invalid or redirected")
    output.mkdir(parents=True, exist_ok=True)
    summary = output / "run-summary.json"
    if summary.exists() or summary.is_symlink():
        raise StudyManifestError("confirmation run summary already exists")
    block_root = output / "blocks"
    if block_root.is_symlink():
        raise StudyManifestError("confirmation block root cannot be a symlink")
    block_root.mkdir(parents=True, exist_ok=True)
    for entry in output.iterdir():
        if entry != block_root:
            raise StudyManifestError("foreign confirmation output entry is present")
    locks = block_root / ".locks"
    if locks.is_symlink():
        raise StudyManifestError("confirmation lock root cannot be a symlink")
    locks.mkdir(parents=True, exist_ok=True)
    if any(locks.iterdir()):
        raise StudyManifestError("confirmation block locks must be empty before a batch")
    observed = {}
    for entry in block_root.iterdir():
        if entry.name == ".locks" and entry.is_dir() and not entry.is_symlink():
            continue
        if entry.is_symlink() or not entry.is_file() or entry.suffix != ".json":
            raise StudyManifestError("unknown or transient confirmation block entry is present")
        if entry.stem not in expected_keys:
            raise StudyManifestError("foreign confirmation block artifact is present")
        observed[entry.stem] = entry
    return observed


def _runner_command(python: Path, worker_index: int) -> list[str]:
    return [
        str(python),
        "-m",
        "secondaryexploration.experiments.runner",
        "configs/confirmation/synthetic-confirmation-v1.json",
        "--workspace-root",
        str(_ROOT),
        "--code-revision",
        EXECUTION_REVISION,
        "--precision",
        "results/planning/formal-precision-v1.json",
        "--calibration-evidence",
        "results/pilot/synthetic-calibration-v1/evidence.json",
        "--calibration-manifest",
        "configs/pilot/synthetic-calibration-v1.json",
        "--worker-count",
        str(LOGICAL_SHARD_COUNT),
        "--worker-index",
        str(worker_index),
    ]


def _source_record(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(_ROOT).as_posix(), "sha256": _file_sha256(path)}


def _formal_completion_gate(root: Path) -> Mapping[str, object]:
    manifest_path = root / "configs/formal/synthetic-formal-v1.json"
    manifest = load_study_design_manifest(manifest_path)
    if manifest.fingerprint != FORMAL_MANIFEST_FINGERPRINT:
        raise StudyManifestError("formal manifest differs at confirmation launch")
    ledger = build_study_seed_ledger(manifest)
    expected_keys = {
        _block_key(seed.node_count, seed.parent_replicate, model)
        for seed, model in _registered_block_jobs(ledger)
    }
    if len(expected_keys) != LOGICAL_SHARD_COUNT:
        raise StudyManifestError("formal completion registry is not 240 blocks")
    output = root / "outputs/formal/synthetic-formal-v1"
    _assert_plain_path(output)
    block_root = output / "blocks"
    lock_root = block_root / ".locks"
    if (
        output.is_symlink()
        or block_root.is_symlink()
        or not block_root.is_dir()
        or lock_root.is_symlink()
        or not lock_root.is_dir()
        or any(lock_root.iterdir())
    ):
        raise StudyManifestError("formal output is not quiescent at confirmation launch")
    allowed_output_names = {"blocks", "run-summary.json"}
    for entry in output.iterdir():
        if entry.name not in allowed_output_names:
            raise StudyManifestError("foreign formal output entry at confirmation launch")
    formal_summary = output / "run-summary.json"
    if formal_summary.is_symlink() or not formal_summary.is_file():
        raise StudyManifestError("formal run summary is missing or redirected")
    observed: dict[str, Path] = {}
    for entry in block_root.iterdir():
        if entry.name == ".locks" and entry.is_dir() and not entry.is_symlink():
            continue
        if entry.is_symlink() or not entry.is_file() or entry.suffix != ".json":
            raise StudyManifestError("unknown formal block entry at confirmation launch")
        if entry.stem not in expected_keys:
            raise StudyManifestError("foreign formal block at confirmation launch")
        observed[entry.stem] = entry
    if set(observed) != expected_keys:
        raise StudyManifestError("formal 240-block registry is incomplete")
    completion_path = root / _SOURCE_PATHS[-1]
    completion = _load_json(completion_path, "formal scheduler completion")
    formal_session_dir = completion_path.parent
    formal_session = _load_json(
        formal_session_dir / "session.json", "formal scheduler session"
    )
    formal_schedule = formal_scheduler.canonical_singleton_schedule(manifest_path)
    formal_scheduler.validate_session_record(
        formal_session,
        root=root,
        expected_schedule=formal_schedule,
    )
    formal_rows = {int(row["worker_index"]): row for row in formal_schedule}
    formal_completed, formal_batch_count, formal_incomplete = (
        formal_scheduler._validate_batch_history(
            formal_session_dir,
            session_fingerprint=str(formal_session["fingerprint"]),
            expected_rows=formal_rows,
            expected_python=Path(str(formal_session["python_executable"])),
        )
    )
    if (
        set(completion) != _COMPLETION_FIELDS
        or completion.get("schema_version") != "formal-bounded-scheduler-completion.v1"
        or completion.get("status") != "all-240-singletons-strict-child-exit-zero"
        or completion.get("session_fingerprint") != formal_session["fingerprint"]
        or completion.get("completed_worker_indices") != list(range(LOGICAL_SHARD_COUNT))
        or formal_completed != set(range(LOGICAL_SHARD_COUNT))
        or formal_incomplete is not None
        or completion.get("final_batch_count") != formal_batch_count
        or completion.get("final_block_count") != LOGICAL_SHARD_COUNT
        or completion.get("final_block_registry_fingerprint")
        != _block_registry_fingerprint(observed)
        or completion.get("fingerprint") != _fingerprint(completion)
    ):
        raise StudyManifestError("formal scheduler completion witness differs")
    return completion


def build_session_record(
    *,
    session_id: str,
    orchestration_revision: str,
    readiness_authorization_revision: str,
    python: Path,
    environment_fingerprint: str,
    schedule: Sequence[Mapping[str, object]],
    observed_blocks: Mapping[str, Path],
    readiness: Mapping[str, object],
) -> dict[str, object]:
    if observed_blocks:
        raise StudyManifestError("fresh confirmation must start from zero blocks")
    if environment_fingerprint != ENVIRONMENT_FINGERPRINT:
        raise StudyManifestError("confirmation environment fingerprint differs")
    if readiness.get("readiness_fingerprint") is None:
        raise StudyManifestError("confirmation readiness fingerprint is missing")
    sources = [_source_record(_ROOT / path) for path in _SOURCE_PATHS]
    record: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "authorized-memory-only-operational-amendment",
        "session_id": session_id,
        "created_at_utc": _utc_now(),
        "orchestration_revision": orchestration_revision,
        "execution_revision": EXECUTION_REVISION,
        "python_executable": str(python),
        "environment_fingerprint": environment_fingerprint,
        "manifest_fingerprint": CONFIRMATION_MANIFEST_FINGERPRINT,
        "logical_shard_count": LOGICAL_SHARD_COUNT,
        "maximum_concurrency": MAX_CONCURRENCY,
        "minimum_available_memory_bytes": MIN_AVAILABLE_MEMORY_BYTES,
        "readiness_fingerprint": readiness["readiness_fingerprint"],
        "readiness_authorization_revision": readiness_authorization_revision,
        "initial_completed_block_count": 0,
        "initial_block_registry_fingerprint": _block_registry_fingerprint({}),
        "sources": sources,
        "schedule": [dict(row) for row in schedule],
        "limitations": list(_SESSION_LIMITATIONS),
    }
    record["fingerprint"] = _fingerprint(record)
    return record


def _readiness_gate(root: Path, authorization_revision: str) -> Mapping[str, object]:
    return load_readiness_result_blind(
        root / "results/diagnostics/confirmation-launch-readiness/formal-ready.json",
        root=root,
        authorization_revision=authorization_revision,
        readiness_revision=READINESS_REVISION,
        analysis_revision=ANALYSIS_REVISION,
    )


def validate_session_record(
    record: Mapping[str, object],
    *,
    root: Path = _ROOT,
    verify_sources: bool = True,
    expected_schedule: Sequence[Mapping[str, object]] | None = None,
) -> None:
    if set(record) != _SESSION_FIELDS:
        raise StudyManifestError("scheduler session fields differ")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise StudyManifestError("unsupported scheduler session schema")
    if record.get("status") != "authorized-memory-only-operational-amendment":
        raise StudyManifestError("scheduler session status is invalid")
    if record.get("execution_revision") != EXECUTION_REVISION:
        raise StudyManifestError("scheduler execution revision drift")
    if record.get("manifest_fingerprint") != CONFIRMATION_MANIFEST_FINGERPRINT:
        raise StudyManifestError("scheduler manifest fingerprint drift")
    if record.get("environment_fingerprint") != ENVIRONMENT_FINGERPRINT:
        raise StudyManifestError("scheduler environment fingerprint drift")
    if record.get("logical_shard_count") != LOGICAL_SHARD_COUNT:
        raise StudyManifestError("scheduler logical shard count drift")
    if record.get("maximum_concurrency") != MAX_CONCURRENCY:
        raise StudyManifestError("scheduler concurrency drift")
    if record.get("minimum_available_memory_bytes") != MIN_AVAILABLE_MEMORY_BYTES:
        raise StudyManifestError("scheduler memory gate drift")
    readiness_fingerprint = record.get("readiness_fingerprint")
    if not isinstance(readiness_fingerprint, str) or not _DIGEST.fullmatch(
        readiness_fingerprint
    ):
        raise StudyManifestError("scheduler readiness fingerprint is malformed")
    readiness_authorization = record.get("readiness_authorization_revision")
    if not isinstance(readiness_authorization, str) or not _REVISION.fullmatch(
        readiness_authorization
    ):
        raise StudyManifestError("scheduler readiness authorization is malformed")
    if record.get("initial_completed_block_count") != 0:
        raise StudyManifestError("scheduler initial block count drift")
    registry_fingerprint = record.get("initial_block_registry_fingerprint")
    if not isinstance(registry_fingerprint, str) or not _DIGEST.fullmatch(
        registry_fingerprint
    ):
        raise StudyManifestError("scheduler initial registry fingerprint is malformed")
    session_id = record.get("session_id")
    if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
        raise StudyManifestError("scheduler session id is malformed")
    revision = record.get("orchestration_revision")
    if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
        raise StudyManifestError("scheduler orchestration revision is malformed")
    python = record.get("python_executable")
    if not isinstance(python, str) or not Path(python).is_absolute():
        raise StudyManifestError("scheduler interpreter path is not absolute")
    if record.get("limitations") != _SESSION_LIMITATIONS:
        raise StudyManifestError("scheduler session limitations drift")
    sources = record.get("sources")
    if not isinstance(sources, list) or len(sources) != len(_SOURCE_PATHS):
        raise StudyManifestError("scheduler source registry is malformed")
    for expected_path, source in zip(_SOURCE_PATHS, sources, strict=True):
        if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
            raise StudyManifestError("scheduler source row fields differ")
        if source.get("path") != expected_path:
            raise StudyManifestError("scheduler source path drift")
        digest = source.get("sha256")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise StudyManifestError("scheduler source hash is malformed")
        if verify_sources and digest != _file_sha256(root / expected_path):
            raise StudyManifestError("scheduler source bytes drift")
    schedule = record.get("schedule")
    if not isinstance(schedule, list) or len(schedule) != LOGICAL_SHARD_COUNT:
        raise StudyManifestError("scheduler schedule must contain 240 rows")
    if any(
        not isinstance(row, dict) or set(row) != {"worker_index", "block_key"}
        for row in schedule
    ):
        raise StudyManifestError("scheduler schedule row fields differ")
    indices = [row.get("worker_index") for row in schedule]
    keys = [row.get("block_key") for row in schedule]
    if indices != list(range(LOGICAL_SHARD_COUNT)) or len(set(keys)) != LOGICAL_SHARD_COUNT:
        raise StudyManifestError("scheduler schedule is not canonical and unique")
    if expected_schedule is None and verify_sources:
        expected_schedule = canonical_singleton_schedule(
            root / "configs/confirmation/synthetic-confirmation-v1.json"
        )
    if expected_schedule is not None and [dict(row) for row in schedule] != [
        dict(row) for row in expected_schedule
    ]:
        raise StudyManifestError("scheduler index-to-key mapping is not canonical")
    if verify_sources:
        current_environment = runtime_environment_fingerprint(runtime_environment())
        if current_environment != ENVIRONMENT_FINGERPRINT:
            raise StudyManifestError("current scheduler environment differs")
        if registry_fingerprint != _block_registry_fingerprint({}):
            raise StudyManifestError("scheduler initial registry fingerprint mismatch")
        _formal_completion_gate(root)
        readiness = _readiness_gate(root, readiness_authorization)
        if readiness.get("readiness_fingerprint") != readiness_fingerprint:
            raise StudyManifestError("scheduler readiness witness differs")
    supplied = record.get("fingerprint")
    if not isinstance(supplied, str) or not _DIGEST.fullmatch(supplied):
        raise StudyManifestError("scheduler session fingerprint is malformed")
    if supplied != _fingerprint(record):
        raise StudyManifestError("scheduler session fingerprint mismatch")


def _validate_batch_history(
    session_dir: Path,
    *,
    session_fingerprint: str,
    expected_rows: Mapping[int, Mapping[str, object]],
    expected_python: Path,
) -> tuple[set[int], int, Path | None]:
    """Replay the complete operational hash chain without endpoint parsing."""

    launches = sorted(session_dir.glob("batch-*.launch.json"))
    completed: set[int] = set()
    incomplete: Path | None = None
    for expected_number, launch_path in enumerate(launches):
        expected_stem = f"batch-{expected_number:03d}"
        if launch_path.name != f"{expected_stem}.launch.json":
            raise StudyManifestError("scheduler batch numbering is not contiguous")
        launch = _load_json(launch_path, "scheduler batch launch")
        if (
            set(launch) != _LAUNCH_FIELDS
            or
            launch.get("schema_version") != BATCH_SCHEMA_VERSION
            or launch.get("status") != "planned-before-launch"
            or launch.get("session_fingerprint") != session_fingerprint
            or launch.get("batch_number") != expected_number
            or type(launch.get("available_memory_bytes_before_launch")) is not int
            or launch.get("available_memory_bytes_before_launch")
            < MIN_AVAILABLE_MEMORY_BYTES
            or launch.get("fingerprint") != _fingerprint(launch)
        ):
            raise StudyManifestError("scheduler launch witness mismatch")
        launch_workers = launch.get("workers")
        if not isinstance(launch_workers, list) or not 1 <= len(launch_workers) <= 6:
            raise StudyManifestError("scheduler launch worker registry is malformed")
        launch_indices = []
        for worker in launch_workers:
            if not isinstance(worker, dict) or set(worker) != _LAUNCH_WORKER_FIELDS:
                raise StudyManifestError("scheduler launch worker is malformed")
            index = worker.get("worker_index")
            if type(index) is not int or index not in expected_rows:
                raise StudyManifestError("scheduler launch index is foreign")
            expected = expected_rows[index]
            if worker.get("block_key") != expected["block_key"]:
                raise StudyManifestError("scheduler launch key/index mismatch")
            command = worker.get("command")
            if not isinstance(command, list) or command != _runner_command(
                expected_python, index
            ):
                raise StudyManifestError("scheduler launch command drift")
            command_hash = hashlib.sha256(
                subprocess.list2cmdline(command).encode("utf-8")
            ).hexdigest()
            if worker.get("command_sha256") != command_hash:
                raise StudyManifestError("scheduler launch command hash mismatch")
            expected_stdout = f"{expected_stem}.worker-{index:03d}.stdout.txt"
            expected_stderr = f"{expected_stem}.worker-{index:03d}.stderr.txt"
            if (
                worker.get("stdout_file") != expected_stdout
                or worker.get("stderr_file") != expected_stderr
            ):
                raise StudyManifestError("scheduler launch log filename is not canonical")
            launch_indices.append(index)
        if len(set(launch_indices)) != len(launch_indices):
            raise StudyManifestError("scheduler launch duplicates an index")
        pending_indices = [index for index in sorted(expected_rows) if index not in completed]
        expected_indices = pending_indices[: min(MAX_CONCURRENCY, len(pending_indices))]
        if launch_indices != expected_indices:
            raise StudyManifestError("scheduler launch is not the canonical pending prefix")
        final_path = session_dir / f"{expected_stem}.final.json"
        recovery_path = session_dir / f"{expected_stem}.recovery.json"
        started_path = session_dir / f"{expected_stem}.started.json"
        abort_path = session_dir / f"{expected_stem}.abort.json"
        for witness_path in (final_path, recovery_path, started_path, abort_path):
            _assert_plain_path(witness_path)
        if final_path.exists() and recovery_path.exists():
            raise StudyManifestError("scheduler batch has both final and recovery records")
        started = None
        started_workers: list[dict[str, object]] = []
        if started_path.exists():
            if not started_path.is_file() or started_path.is_symlink():
                raise StudyManifestError("scheduler started witness is redirected")
            started = _load_json(started_path, "scheduler batch started witness")
            if (
                set(started) != _STARTED_FIELDS
                or started.get("schema_version")
                != "confirmation-bounded-scheduler-started.v1"
                or started.get("status") != "all-planned-children-started"
                or started.get("session_fingerprint") != session_fingerprint
                or started.get("batch_number") != expected_number
                or started.get("launch_fingerprint") != launch["fingerprint"]
                or type(started.get("scheduler_process_id")) is not int
                or started.get("fingerprint") != _fingerprint(started)
            ):
                raise StudyManifestError("scheduler started witness mismatch")
            raw_started_workers = started.get("workers")
            if not isinstance(raw_started_workers, list) or len(
                raw_started_workers
            ) != len(launch_workers):
                raise StudyManifestError("scheduler started worker registry mismatch")
            started_workers = raw_started_workers
            pids = [row.get("process_id") for row in started_workers if isinstance(row, dict)]
            if len(set(pids)) != len(started_workers):
                raise StudyManifestError("scheduler started PIDs are not unique")
            for launch_worker, worker in zip(
                launch_workers, started_workers, strict=True
            ):
                expected_command_line = subprocess.list2cmdline(
                    launch_worker["command"]
                )
                if (
                    not isinstance(worker, dict)
                    or set(worker) != _STARTED_WORKER_FIELDS
                    or worker.get("worker_index") != launch_worker["worker_index"]
                    or worker.get("block_key") != launch_worker["block_key"]
                    or worker.get("stdout_file") != launch_worker["stdout_file"]
                    or worker.get("stderr_file") != launch_worker["stderr_file"]
                    or worker.get("command_line_sha256")
                    != launch_worker["command_sha256"]
                    or worker.get("command_line")
                    not in {expected_command_line, "platform-unavailable"}
                    or type(worker.get("process_id")) is not int
                    or worker.get("parent_process_id")
                    != started["scheduler_process_id"]
                    or not isinstance(worker.get("process_creation_time"), str)
                    or not worker["process_creation_time"]
                ):
                    raise StudyManifestError("scheduler started worker identity mismatch")
        elif final_path.exists():
            raise StudyManifestError("finalized scheduler batch lacks a started witness")
        abort = None
        if abort_path.exists():
            abort = _load_json(abort_path, "scheduler batch start-abort witness")
            spawned = abort.get("spawned_process_ids")
            if (
                set(abort) != _ABORT_FIELDS
                or abort.get("schema_version")
                != "confirmation-bounded-scheduler-start-abort.v1"
                or abort.get("status") != "partial-start-aborted"
                or abort.get("session_fingerprint") != session_fingerprint
                or abort.get("batch_number") != expected_number
                or abort.get("launch_fingerprint") != launch["fingerprint"]
                or not isinstance(abort.get("captured_at_utc"), str)
                or not abort["captured_at_utc"]
                or not isinstance(spawned, list)
                or not 1 <= len(spawned) <= len(launch_workers)
                or any(type(process_id) is not int for process_id in spawned)
                or len(set(spawned)) != len(spawned)
                or abort.get("fingerprint") != _fingerprint(abort)
            ):
                raise StudyManifestError("scheduler start-abort witness mismatch")
            if started is not None or final_path.exists():
                raise StudyManifestError(
                    "scheduler start-abort conflicts with started or final witness"
                )
        if not final_path.exists() and not recovery_path.exists():
            if expected_number != len(launches) - 1:
                raise StudyManifestError("only the last scheduler batch may be incomplete")
            incomplete = launch_path
            continue
        if recovery_path.exists():
            recovery = _load_json(recovery_path, "scheduler batch recovery")
            expected_recovery_status = (
                "interrupted-batch-closed-no-live-worker"
                if started is not None
                else "interrupted-batch-closed-without-complete-start-witness"
            )
            expected_started_fingerprint = (
                started["fingerprint"] if started is not None else None
            )
            expected_limitations = (
                _RECOVERY_LIMITATIONS_STARTED
                if started is not None
                else _RECOVERY_LIMITATIONS_NO_START
            )
            if (
                set(recovery) != _RECOVERY_FIELDS
                or
                recovery.get("schema_version")
                != "confirmation-bounded-scheduler-recovery.v1"
                or recovery.get("status") != expected_recovery_status
                or recovery.get("session_fingerprint") != session_fingerprint
                or recovery.get("batch_number") != expected_number
                or recovery.get("launch_fingerprint") != launch["fingerprint"]
                or recovery.get("started_fingerprint")
                != expected_started_fingerprint
                or recovery.get("limitations") != expected_limitations
                or recovery.get("fingerprint") != _fingerprint(recovery)
            ):
                raise StudyManifestError("scheduler recovery witness mismatch")
            recovery_workers = recovery.get("workers")
            if not isinstance(recovery_workers, list) or len(recovery_workers) != len(
                launch_workers
            ):
                raise StudyManifestError("scheduler recovery worker registry mismatch")
            for launch_worker, worker in zip(
                launch_workers, recovery_workers, strict=True
            ):
                if (
                    not isinstance(worker, dict)
                    or set(worker) != _RECOVERY_WORKER_FIELDS
                    or worker.get("worker_index") != launch_worker["worker_index"]
                    or worker.get("block_key") != launch_worker["block_key"]
                    or worker.get("artifact_state")
                    not in {"atomic-file-present", "absent"}
                ):
                    raise StudyManifestError("scheduler recovery worker mismatch")
                digest = worker.get("artifact_sha256")
                if worker["artifact_state"] == "atomic-file-present":
                    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
                        raise StudyManifestError("scheduler recovery artifact hash is malformed")
                elif digest is not None:
                    raise StudyManifestError("absent recovery artifact cannot have a hash")
            continue
        record = _load_json(final_path, "scheduler batch finalization")
        batch_succeeded = record.get("status") == "batch-complete-zero-exit"
        if (
            record.get("schema_version") != FINAL_SCHEMA_VERSION
            or set(record) != _FINAL_FIELDS
            or record.get("status")
            not in {"batch-complete-zero-exit", "batch-failed-stop"}
            or record.get("session_fingerprint") != session_fingerprint
            or record.get("batch_number") != expected_number
            or record.get("launch_fingerprint") != launch["fingerprint"]
            or record.get("started_fingerprint") != started["fingerprint"]
            or type(record.get("available_memory_bytes_after_exit")) is not int
            or record.get("available_memory_bytes_after_exit") < 0
            or record.get("fingerprint") != _fingerprint(record)
        ):
            raise StudyManifestError("scheduler finalization witness mismatch")
        if (
            record.get("launched_process_count") != len(launch_workers)
            or record.get("configured_concurrency_ceiling") != MAX_CONCURRENCY
        ):
            raise StudyManifestError("scheduler recorded concurrency mismatch")
        final_workers = record.get("workers")
        if not isinstance(final_workers, list) or len(final_workers) != len(launch_workers):
            raise StudyManifestError("scheduler final worker registry mismatch")
        for position, (launch_worker, worker) in enumerate(
            zip(launch_workers, final_workers, strict=True)
        ):
            index = worker.get("worker_index") if isinstance(worker, dict) else None
            stdout_digest = worker.get("stdout_sha256") if isinstance(worker, dict) else None
            stderr_digest = worker.get("stderr_sha256") if isinstance(worker, dict) else None
            artifact_digest = worker.get("artifact_sha256") if isinstance(worker, dict) else None
            if (
                not isinstance(worker, dict)
                or set(worker) != _FINAL_WORKER_FIELDS
                or index != launch_worker["worker_index"]
                or worker.get("block_key") != launch_worker["block_key"]
                or worker.get("process_id")
                != started_workers[position]["process_id"]
                or type(worker.get("exit_code")) is not int
                or not isinstance(worker.get("started_at_utc"), str)
                or not worker["started_at_utc"]
                or not isinstance(worker.get("completed_at_utc"), str)
                or not worker["completed_at_utc"]
                or not isinstance(stdout_digest, str)
                or not _DIGEST.fullmatch(stdout_digest)
                or not isinstance(stderr_digest, str)
                or not _DIGEST.fullmatch(stderr_digest)
                or (
                    artifact_digest is not None
                    and (
                        not isinstance(artifact_digest, str)
                        or not _DIGEST.fullmatch(artifact_digest)
                    )
                )
                or index in completed
            ):
                raise StudyManifestError("scheduler finalized worker identity mismatch")
            for kind in ("stdout", "stderr"):
                file_field = f"{kind}_file"
                hash_field = f"{kind}_sha256"
                if worker.get(file_field) != launch_worker[file_field]:
                    raise StudyManifestError("scheduler log filename mismatch")
                log_path = session_dir / str(worker[file_field])
                if not log_path.is_file() or log_path.is_symlink():
                    raise StudyManifestError("scheduler log is missing or redirected")
                if worker.get(hash_field) != _file_sha256(log_path):
                    raise StudyManifestError("scheduler log hash mismatch")
            stderr_path = session_dir / str(worker["stderr_file"])
            if batch_succeeded and stderr_path.stat().st_size:
                raise StudyManifestError("successful scheduler stderr is nonempty")
            artifact = _ROOT / str(worker.get("artifact_file"))
            expected_artifact = (
                _ROOT
                / "outputs/confirmation/synthetic-confirmation-v1/blocks"
                / f"{worker['block_key']}.json"
            )
            if artifact.resolve() != expected_artifact.resolve():
                raise StudyManifestError("scheduler artifact path mismatch")
            if artifact_digest is not None:
                if not artifact.is_file() or artifact_digest != _file_sha256(artifact):
                    raise StudyManifestError("scheduler artifact hash mismatch")
            if batch_succeeded:
                if worker.get("exit_code") != 0 or artifact_digest is None:
                    raise StudyManifestError("successful batch worker is incomplete")
                completed.add(index)
    return completed, len(launches), incomplete


def _process_identities(process_ids: Sequence[int]) -> list[dict[str, object]]:
    """Capture PID, parent, creation identity, and command line for live children."""

    wanted = sorted(set(process_ids))
    if not wanted:
        return []
    if os.name != "nt":
        return [
            {
                "process_id": pid,
                "parent_process_id": os.getpid(),
                "process_creation_time": "platform-unavailable",
                "command_line": "platform-unavailable",
            }
            for pid in wanted
        ]
    ids = ",".join(str(pid) for pid in wanted)
    script = (
        f"$wanted = @({ids}); "
        "$rows = Get-CimInstance Win32_Process | Where-Object { "
        "$wanted -contains [int]$_.ProcessId }; "
        "@($rows | ForEach-Object { [pscustomobject]@{"
        "process_id=[int]$_.ProcessId;"
        "parent_process_id=[int]$_.ParentProcessId;"
        "process_creation_time=[string]$_.CreationDate;"
        "command_line=[string]$_.CommandLine}}) | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ("powershell", "-NoProfile", "-Command", script),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise StudyManifestError("cannot capture child process identities")
    payload = result.stdout.strip()
    if not payload:
        return []
    value = json.loads(payload)
    rows = value if isinstance(value, list) else [value]
    return sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: row["process_id"],
    )


def _cross_phase_runner_processes() -> list[dict[str, object]]:
    """Return any live formal or confirmation runner, including superseded six-shard commands."""

    if os.name != "nt":
        return []
    script = (
        "$rows = Get-CimInstance Win32_Process | Where-Object { "
        "$_.CommandLine -like '*secondaryexploration*experiments*runner*' -and "
        "($_.CommandLine -like '*synthetic-formal-v1.json*' -or "
        "$_.CommandLine -like '*synthetic-confirmation-v1.json*') -and "
        "$_.ProcessId -ne $PID }; "
        "@($rows | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ("powershell", "-NoProfile", "-Command", script),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise StudyManifestError("cannot inspect live confirmation singleton processes")
    payload = result.stdout.strip()
    if not payload:
        return []
    value = json.loads(payload)
    rows = value if isinstance(value, list) else [value]
    return [row for row in rows if isinstance(row, dict)]


def acquire_global_lease(
    *,
    session_id: str,
    orchestration_revision: str,
    recover_stale: bool,
    process_reader: Callable[[Sequence[int]], list[dict[str, object]]] = _process_identities,
    runner_reader: Callable[[], list[dict[str, object]]] = _cross_phase_runner_processes,
) -> tuple[Path, dict[str, object]]:
    """Exclusively authorize one scheduler across every session."""

    raw_root = _ROOT / _GLOBAL_LEASE_ROOT
    _assert_plain_path(raw_root)
    root = raw_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    _assert_plain_path(root)
    lease_path = root / "active-session.json"
    if lease_path.is_symlink():
        raise StudyManifestError("global scheduler lease cannot be a symlink")
    if lease_path.exists():
        if not recover_stale:
            raise StudyManifestError("another scheduler holds the global lease")
        stale = _load_json(lease_path, "stale global scheduler lease")
        expected_fields = {
            "schema_version",
            "status",
            "session_id",
            "orchestration_revision",
            "scheduler_process_id",
            "scheduler_parent_process_id",
            "scheduler_creation_time",
            "acquired_at_utc",
            "fingerprint",
        }
        if (
            set(stale) != expected_fields
            or stale.get("schema_version") != "formal-bounded-scheduler-lease.v1"
            or stale.get("status") != "active-global-exclusive-lease"
            or stale.get("fingerprint") != _fingerprint(stale)
        ):
            raise StudyManifestError("stale global scheduler lease is malformed")
        stale_pid = stale.get("scheduler_process_id")
        if type(stale_pid) is not int:
            raise StudyManifestError("stale global scheduler PID is malformed")
        live_identity = process_reader([stale_pid])
        if any(
            row.get("process_id") == stale_pid
            and row.get("process_creation_time") == stale.get("scheduler_creation_time")
            for row in live_identity
        ):
            raise StudyManifestError("recorded scheduler lease owner remains live")
        if runner_reader():
            raise StudyManifestError("formal or confirmation runners remain live during lease recovery")
        recovery: dict[str, object] = {
            "schema_version": "formal-bounded-scheduler-lease-recovery.v1",
            "status": "stale-global-lease-owner-proved-absent",
            "stale_lease_fingerprint": stale["fingerprint"],
            "stale_session_id": stale["session_id"],
            "recovered_at_utc": _utc_now(),
        }
        recovery["fingerprint"] = _fingerprint(recovery)
        recovery_path = root / "lease-recoveries" / f"{stale['fingerprint']}.json"
        if recovery_path.exists():
            existing_recovery = _load_json(
                recovery_path, "existing stale global lease recovery"
            )
            if (
                set(existing_recovery)
                != {
                    "schema_version",
                    "status",
                    "stale_lease_fingerprint",
                    "stale_session_id",
                    "recovered_at_utc",
                    "fingerprint",
                }
                or existing_recovery.get("schema_version")
                != "formal-bounded-scheduler-lease-recovery.v1"
                or existing_recovery.get("status")
                != "stale-global-lease-owner-proved-absent"
                or existing_recovery.get("stale_lease_fingerprint")
                != stale["fingerprint"]
                or existing_recovery.get("stale_session_id") != stale["session_id"]
                or not isinstance(existing_recovery.get("recovered_at_utc"), str)
                or not existing_recovery["recovered_at_utc"]
                or existing_recovery.get("fingerprint")
                != _fingerprint(existing_recovery)
            ):
                raise StudyManifestError(
                    "existing stale global lease recovery witness mismatch"
                )
        else:
            _write_create_only(recovery_path, recovery)
        if any(
            row.get("process_id") == stale_pid
            and row.get("process_creation_time") == stale.get("scheduler_creation_time")
            for row in process_reader([stale_pid])
        ):
            raise StudyManifestError("recorded scheduler lease owner reappeared")
        if runner_reader():
            raise StudyManifestError(
                "formal or confirmation runner appeared before lease recovery commit"
            )
        current_stale = _load_json(lease_path, "stale global scheduler lease before unlink")
        if current_stale != stale:
            raise StudyManifestError("stale global scheduler lease changed before unlink")
        lease_path.unlink()
    elif recover_stale:
        raise StudyManifestError("no stale global scheduler lease exists")
    if runner_reader():
        raise StudyManifestError("a formal or confirmation runner is live before lease acquisition")
    identities = process_reader([os.getpid()])
    if len(identities) != 1 or identities[0].get("process_id") != os.getpid():
        raise StudyManifestError("cannot attest scheduler process identity")
    identity = identities[0]
    lease: dict[str, object] = {
        "schema_version": "formal-bounded-scheduler-lease.v1",
        "status": "active-global-exclusive-lease",
        "session_id": session_id,
        "orchestration_revision": orchestration_revision,
        "scheduler_process_id": os.getpid(),
        "scheduler_parent_process_id": int(identity["parent_process_id"]),
        "scheduler_creation_time": str(identity["process_creation_time"]),
        "acquired_at_utc": _utc_now(),
    }
    lease["fingerprint"] = _fingerprint(lease)
    _write_create_only(lease_path, lease)
    return lease_path, lease


def release_global_lease(
    lease_path: Path, lease: Mapping[str, object]
) -> None:
    """Release only the unchanged lease owned by this exact scheduler process."""

    observed = _load_json(lease_path, "active global scheduler lease")
    if (
        observed != dict(lease)
        or observed.get("scheduler_process_id") != os.getpid()
        or observed.get("fingerprint") != _fingerprint(observed)
    ):
        raise StudyManifestError("global scheduler lease identity changed")
    lease_path.unlink()


def validate_global_lease(
    lease_path: Path,
    lease: Mapping[str, object],
    *,
    process_reader: Callable[[Sequence[int]], list[dict[str, object]]] = _process_identities,
) -> None:
    observed = _load_json(lease_path, "active cross-phase scheduler lease")
    if observed != dict(lease) or observed.get("fingerprint") != _fingerprint(observed):
        raise StudyManifestError("global scheduler lease changed during session")
    if observed.get("scheduler_process_id") != os.getpid():
        raise StudyManifestError("global scheduler lease PID differs")
    identities = process_reader([os.getpid()])
    if not any(
        row.get("process_id") == os.getpid()
        and row.get("process_creation_time") == observed.get("scheduler_creation_time")
        for row in identities
    ):
        raise StudyManifestError("global scheduler lease process identity differs")


def recover_incomplete_batch(
    session_dir: Path,
    launch_path: Path,
    *,
    session_fingerprint: str,
    expected_keys: set[str],
    expected_rows: Mapping[int, Mapping[str, object]],
    expected_python: Path,
) -> Path:
    """Close one interrupted batch after external stale-lock recovery."""

    _completed, _count, incomplete = _validate_batch_history(
        session_dir,
        session_fingerprint=session_fingerprint,
        expected_rows=expected_rows,
        expected_python=expected_python,
    )
    if incomplete != launch_path:
        raise StudyManifestError("recovery target is not the strictly replayed incomplete batch")
    started_path = launch_path.with_name(
        launch_path.name.replace(".launch.json", ".started.json")
    )

    def recovery_source_snapshot() -> tuple[str, str | None]:
        _assert_plain_path(launch_path)
        _assert_plain_path(started_path)
        launch_sha256 = _file_sha256(launch_path)
        started_sha256 = _file_sha256(started_path) if started_path.exists() else None
        return launch_sha256, started_sha256

    validated_snapshot = recovery_source_snapshot()
    if _cross_phase_runner_processes():
        raise StudyManifestError("cannot recover while a formal or confirmation runner is live")
    observed = _assert_quiescent_output(_ROOT, expected_keys)
    observed_snapshot = {
        key: _file_sha256(path) for key, path in sorted(observed.items())
    }
    _completed, _count, replayed_incomplete = _validate_batch_history(
        session_dir,
        session_fingerprint=session_fingerprint,
        expected_rows=expected_rows,
        expected_python=expected_python,
    )
    if replayed_incomplete != launch_path:
        raise StudyManifestError("recovery target changed during quiescence checks")
    if recovery_source_snapshot() != validated_snapshot:
        raise StudyManifestError("recovery launch or started witness drifted after validation")
    launch = _load_json(launch_path, "interrupted scheduler launch")
    started = None
    started_rows: list[dict[str, object]] = []
    if started_path.exists():
        if not started_path.is_file() or started_path.is_symlink():
            raise StudyManifestError("interrupted started witness is redirected")
        started = _load_json(started_path, "interrupted scheduler started witness")
        started_rows = started.get("workers", [])
        started_pids = [
            int(row["process_id"])
            for row in started_rows
            if isinstance(row, dict) and type(row.get("process_id")) is int
        ]
        if len(started_pids) != len(launch.get("workers", [])):
            raise StudyManifestError("interrupted PID registry is incomplete")
    def assert_started_children_not_live() -> None:
        if not started_rows:
            return
        started_pids = [int(row["process_id"]) for row in started_rows]
        live_by_pid = {
            int(row["process_id"]): row for row in _process_identities(started_pids)
        }
        for row in started_rows:
            live = live_by_pid.get(int(row["process_id"]))
            if live is not None and live.get("process_creation_time") == row.get(
                "process_creation_time"
            ):
                raise StudyManifestError("an interrupted child identity remains live")

    assert_started_children_not_live()
    workers = []
    for row in launch["workers"]:
        key = row["block_key"]
        artifact = observed.get(key)
        workers.append(
            {
                "worker_index": row["worker_index"],
                "block_key": key,
                "artifact_state": "atomic-file-present" if artifact else "absent",
                "artifact_sha256": _file_sha256(artifact) if artifact else None,
            }
        )
    record: dict[str, object] = {
        "schema_version": "confirmation-bounded-scheduler-recovery.v1",
        "status": (
            "interrupted-batch-closed-no-live-worker"
            if started is not None
            else "interrupted-batch-closed-without-complete-start-witness"
        ),
        "session_fingerprint": session_fingerprint,
        "batch_number": launch["batch_number"],
        "launch_fingerprint": launch["fingerprint"],
        "started_fingerprint": (
            started["fingerprint"] if started is not None else None
        ),
        "recovered_at_utc": _utc_now(),
        "workers": workers,
        "limitations": list(
            _RECOVERY_LIMITATIONS_STARTED
            if started is not None
            else _RECOVERY_LIMITATIONS_NO_START
        ),
    }
    record["fingerprint"] = _fingerprint(record)
    path = launch_path.with_name(launch_path.name.replace(".launch.json", ".recovery.json"))

    def verify_recovery_sources_before_publish() -> None:
        if _cross_phase_runner_processes():
            raise StudyManifestError(
                "formal or confirmation runner appeared before recovery publication"
            )
        current_observed = _assert_quiescent_output(_ROOT, expected_keys)
        current_snapshot = {
            key: _file_sha256(path)
            for key, path in sorted(current_observed.items())
        }
        if current_snapshot != observed_snapshot:
            raise StudyManifestError(
                "confirmation artifact registry drifted before recovery publication"
            )
        assert_started_children_not_live()
        _completed, _count, final_incomplete = _validate_batch_history(
            session_dir,
            session_fingerprint=session_fingerprint,
            expected_rows=expected_rows,
            expected_python=expected_python,
        )
        if final_incomplete != launch_path or recovery_source_snapshot() != validated_snapshot:
            raise StudyManifestError(
                "recovery launch or started witness drifted before publication"
            )

    _write_create_only(path, record, prepublish=verify_recovery_sources_before_publish)
    return path


def run_batch(
    *,
    session_dir: Path,
    session_fingerprint: str,
    batch_number: int,
    rows: Sequence[Mapping[str, object]],
    python: Path,
    memory_reader: Callable[[], int] = available_physical_memory_bytes,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    identity_reader: Callable[[Sequence[int]], list[dict[str, object]]] = _process_identities,
) -> dict[str, object]:
    """Run one at-most-six singleton micro-batch and publish closed provenance."""

    if not rows or len(rows) > MAX_CONCURRENCY:
        raise StudyManifestError("scheduler batch size is outside [1, 6]")
    indices = [row["worker_index"] for row in rows]
    if len(set(indices)) != len(indices):
        raise StudyManifestError("scheduler batch contains duplicate indices")
    available = memory_reader()
    if available < MIN_AVAILABLE_MEMORY_BYTES:
        raise StudyManifestError("available physical memory is below the frozen safety gate")
    prefix = f"batch-{batch_number:03d}"
    commands = [_runner_command(python, int(row["worker_index"])) for row in rows]
    launch: dict[str, object] = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "status": "planned-before-launch",
        "session_fingerprint": session_fingerprint,
        "batch_number": batch_number,
        "started_at_utc": _utc_now(),
        "available_memory_bytes_before_launch": available,
        "workers": [
            {
                "worker_index": row["worker_index"],
                "block_key": row["block_key"],
                "command": command,
                "command_sha256": hashlib.sha256(
                    subprocess.list2cmdline(command).encode("utf-8")
                ).hexdigest(),
                "stdout_file": f"{prefix}.worker-{int(row['worker_index']):03d}.stdout.txt",
                "stderr_file": f"{prefix}.worker-{int(row['worker_index']):03d}.stderr.txt",
            }
            for row, command in zip(rows, commands, strict=True)
        ],
    }
    launch["fingerprint"] = _fingerprint(launch)
    launch_path = session_dir / f"{prefix}.launch.json"
    _write_create_only(launch_path, launch)
    processes = []
    handles = []
    started: dict[str, object] | None = None
    try:
        for worker, command in zip(launch["workers"], commands, strict=True):
            stdout_path = session_dir / worker["stdout_file"]
            stderr_path = session_dir / worker["stderr_file"]
            if stdout_path.exists() or stderr_path.exists():
                raise StudyManifestError("scheduler log collision")
            stdout_handle = stdout_path.open("xb")
            stderr_handle = stderr_path.open("xb")
            handles.extend((stdout_handle, stderr_handle))
            started_at = _utc_now()
            process = popen(
                command,
                cwd=_ROOT,
                stdout=stdout_handle,
                stderr=stderr_handle,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            processes.append((worker, process, stdout_path, stderr_path, started_at))
        identities = identity_reader([process.pid for _, process, _, _, _ in processes])
        identity_by_pid = {int(row["process_id"]): row for row in identities}
        if set(identity_by_pid) != {
            process.pid for _, process, _, _, _ in processes
        }:
            raise StudyManifestError("not every singleton child has a live process identity")
        started_workers = []
        for worker, process, _, _, _ in processes:
            identity = identity_by_pid[process.pid]
            command_line = str(identity["command_line"])
            expected_command_line = subprocess.list2cmdline(
                commands[len(started_workers)]
            )
            if command_line not in {expected_command_line, "platform-unavailable"}:
                raise StudyManifestError("live singleton command line differs")
            started_workers.append(
                {
                    "worker_index": worker["worker_index"],
                    "block_key": worker["block_key"],
                    "process_id": process.pid,
                    "parent_process_id": int(identity["parent_process_id"]),
                    "process_creation_time": str(identity["process_creation_time"]),
                    "command_line": command_line,
                    "command_line_sha256": worker["command_sha256"],
                    "stdout_file": worker["stdout_file"],
                    "stderr_file": worker["stderr_file"],
                }
            )
        started = {
            "schema_version": "confirmation-bounded-scheduler-started.v1",
            "status": "all-planned-children-started",
            "session_fingerprint": session_fingerprint,
            "batch_number": batch_number,
            "launch_fingerprint": launch["fingerprint"],
            "captured_at_utc": _utc_now(),
            "scheduler_process_id": os.getpid(),
            "workers": started_workers,
        }
        started["fingerprint"] = _fingerprint(started)
        _write_create_only(session_dir / f"{prefix}.started.json", started)
        completed_times = {}
        for _, process, _, _, _ in processes:
            process.wait()
            completed_times[process.pid] = _utc_now()
        for handle in handles:
            handle.close()
        handles.clear()
        final_workers = []
        failed = False
        for worker, process, stdout_path, stderr_path, started_at in processes:
            stderr_size = stderr_path.stat().st_size
            if process.returncode != 0 or stderr_size:
                failed = True
            block_path = (
                _ROOT
                / "outputs/confirmation/synthetic-confirmation-v1/blocks"
                / f"{worker['block_key']}.json"
            )
            final_workers.append(
                {
                    "worker_index": worker["worker_index"],
                    "block_key": worker["block_key"],
                    "process_id": process.pid,
                    "started_at_utc": started_at,
                    "completed_at_utc": completed_times[process.pid],
                    "exit_code": process.returncode,
                    "stdout_file": worker["stdout_file"],
                    "stdout_sha256": _file_sha256(stdout_path),
                    "stderr_file": worker["stderr_file"],
                    "stderr_sha256": _file_sha256(stderr_path),
                    "artifact_file": block_path.relative_to(_ROOT).as_posix(),
                    "artifact_sha256": _file_sha256(block_path) if block_path.is_file() else None,
                }
            )
        final: dict[str, object] = {
            "schema_version": FINAL_SCHEMA_VERSION,
            "status": "batch-failed-stop" if failed else "batch-complete-zero-exit",
            "session_fingerprint": session_fingerprint,
            "batch_number": batch_number,
            "launch_fingerprint": launch["fingerprint"],
            "started_fingerprint": started["fingerprint"],
            "completed_at_utc": _utc_now(),
            "launched_process_count": len(processes),
            "configured_concurrency_ceiling": MAX_CONCURRENCY,
            "available_memory_bytes_after_exit": memory_reader(),
            "workers": final_workers,
        }
        if not failed and any(row["artifact_sha256"] is None for row in final_workers):
            final["status"] = "batch-failed-stop"
            failed = True
        final["fingerprint"] = _fingerprint(final)
        _write_create_only(session_dir / f"{prefix}.final.json", final)
        if failed:
            raise StudyManifestError("singleton child failure stopped the scheduler")
        return final
    except BaseException:
        try:
            if processes and started is None:
                abort = {
                    "schema_version": "confirmation-bounded-scheduler-start-abort.v1",
                    "status": "partial-start-aborted",
                    "session_fingerprint": session_fingerprint,
                    "batch_number": batch_number,
                    "launch_fingerprint": launch["fingerprint"],
                    "captured_at_utc": _utc_now(),
                    "spawned_process_ids": [
                        process.pid for _, process, _, _, _ in processes
                    ],
                }
                abort["fingerprint"] = _fingerprint(abort)
                abort_path = session_dir / f"{prefix}.abort.json"
                if not abort_path.exists():
                    _write_create_only(abort_path, abort)
        finally:
            for _, process, _, _, _ in processes:
                if process.poll() is None:
                    process.terminate()
            for _, process, _, _, _ in processes:
                if process.poll() is None:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        raise
    finally:
        for handle in handles:
            handle.close()


def _run_scheduler_body(
    *,
    session_id: str,
    orchestration_revision: str,
    readiness_authorization_revision: str,
    python_executable: Path,
    resume: bool,
    recover_interrupted: bool,
    lease_path: Path,
    lease: Mapping[str, object],
) -> Path:
    root = _ROOT.resolve()
    if recover_interrupted and not resume:
        raise StudyManifestError("--recover-interrupted requires --resume")
    if not _SESSION_ID.fullmatch(session_id):
        raise StudyManifestError("session id is malformed")
    python = python_executable.resolve()
    if python != Path(sys.executable).resolve():
        raise StudyManifestError("scheduler and child interpreter must be identical")
    verify_source_snapshots(root, orchestration_revision)
    readiness = _readiness_gate(root, readiness_authorization_revision)
    _formal_completion_gate(root)
    manifest_path = root / "configs/confirmation/synthetic-confirmation-v1.json"
    schedule = canonical_singleton_schedule(manifest_path)
    preflight = preflight_synthetic_study(
        manifest_path,
        workspace_root=root,
        code_revision=EXECUTION_REVISION,
        precision_path=root / "results/planning/formal-precision-v1.json",
        calibration_evidence_path=root / "results/pilot/synthetic-calibration-v1/evidence.json",
        calibration_manifest_path=root / "configs/pilot/synthetic-calibration-v1.json",
        worker_count=LOGICAL_SHARD_COUNT,
        worker_index=0,
    )
    if preflight.get("selected_block_count") != 1:
        raise StudyManifestError("frozen runner preflight is not singleton")
    if preflight.get("environment_fingerprint") != ENVIRONMENT_FINGERPRINT:
        raise StudyManifestError("confirmation preflight environment differs")
    expected_keys = {str(row["block_key"]) for row in schedule}
    observed_at_start = _assert_quiescent_output(root, expected_keys)
    raw_session_parent = root / _SESSION_ROOT
    raw_session_dir = raw_session_parent / session_id
    _assert_plain_path(raw_session_parent)
    _assert_plain_path(raw_session_dir)
    if raw_session_parent.is_symlink() or raw_session_dir.is_symlink():
        raise StudyManifestError("scheduler session path cannot be a symlink")
    session_dir = raw_session_dir.resolve()
    expected_parent = raw_session_parent.resolve()
    if session_dir.parent != expected_parent:
        raise StudyManifestError("scheduler session path escapes its frozen root")
    session_path = session_dir / "session.json"
    if resume:
        session = _load_json(session_path, "scheduler session")
        validate_session_record(session)
        if session.get("orchestration_revision") != orchestration_revision:
            raise StudyManifestError("resume orchestration revision drift")
        if (
            session.get("readiness_authorization_revision")
            != readiness_authorization_revision
        ):
            raise StudyManifestError("resume readiness authorization drift")
        if Path(str(session.get("python_executable"))).resolve() != python:
            raise StudyManifestError("resume interpreter drift")
    else:
        if session_dir.exists() or session_dir.is_symlink():
            raise StudyManifestError("fresh scheduler session already exists")
        session_dir.mkdir(parents=True)
        _assert_plain_path(session_dir)
        session = build_session_record(
            session_id=session_id,
            orchestration_revision=orchestration_revision,
            readiness_authorization_revision=readiness_authorization_revision,
            python=python,
            environment_fingerprint=preflight["environment_fingerprint"],
            schedule=schedule,
            observed_blocks=observed_at_start,
            readiness=readiness,
        )
        validate_session_record(session)
        _write_create_only(session_path, session)
    expected_by_index = {int(row["worker_index"]): row for row in schedule}
    completed, batch_number, incomplete = _validate_batch_history(
        session_dir,
        session_fingerprint=str(session["fingerprint"]),
        expected_rows=expected_by_index,
        expected_python=python,
    )
    if incomplete is not None:
        if not recover_interrupted:
            raise StudyManifestError(
                "incomplete scheduler batch requires --recover-interrupted after lock recovery"
            )
        recover_incomplete_batch(
            session_dir,
            incomplete,
            session_fingerprint=str(session["fingerprint"]),
            expected_keys=expected_keys,
            expected_rows=expected_by_index,
            expected_python=python,
        )
        completed, batch_number, incomplete = _validate_batch_history(
            session_dir,
            session_fingerprint=str(session["fingerprint"]),
            expected_rows=expected_by_index,
            expected_python=python,
        )
        if incomplete is not None:
            raise StudyManifestError("scheduler recovery did not close interrupted batch")
    elif recover_interrupted:
        raise StudyManifestError("no interrupted scheduler batch exists to recover")
    pending = [row for row in schedule if row["worker_index"] not in completed]
    completion_path = session_dir / "completion.json"
    if completion_path.exists():
        validate_global_lease(lease_path, lease)
        if _cross_phase_runner_processes():
            raise StudyManifestError("formal or confirmation runner remains after completion")
        verify_source_snapshots(root, orchestration_revision)
        validate_session_record(session)
        completion = _load_json(completion_path, "scheduler completion")
        if (
            pending
            or set(observed_at_start) != expected_keys
            or len(observed_at_start) != LOGICAL_SHARD_COUNT
            or set(completion) != _COMPLETION_FIELDS
            or completion.get("schema_version")
            != "confirmation-bounded-scheduler-completion.v1"
            or completion.get("status")
            != "all-240-singletons-strict-child-exit-zero"
            or completion.get("session_fingerprint") != session["fingerprint"]
            or completion.get("completed_worker_indices")
            != list(range(LOGICAL_SHARD_COUNT))
            or completion.get("final_block_count") != LOGICAL_SHARD_COUNT
            or type(completion.get("final_batch_count")) is not int
            or completion.get("final_batch_count") != batch_number
            or not isinstance(
                completion.get("final_block_registry_fingerprint"), str
            )
            or not _DIGEST.fullmatch(completion["final_block_registry_fingerprint"])
            or completion.get("final_block_registry_fingerprint")
            != _block_registry_fingerprint(observed_at_start)
            or completion.get("fingerprint") != _fingerprint(completion)
        ):
            raise StudyManifestError("scheduler completion witness mismatch")
        return completion_path
    while pending:
        validate_global_lease(lease_path, lease)
        verify_source_snapshots(root, orchestration_revision)
        validate_session_record(session)
        _assert_quiescent_output(root, expected_keys)
        if _cross_phase_runner_processes():
            raise StudyManifestError("another formal or confirmation runner appeared")
        rows = pending[:MAX_CONCURRENCY]
        run_batch(
            session_dir=session_dir,
            session_fingerprint=str(session["fingerprint"]),
            batch_number=batch_number,
            rows=rows,
            python=python,
        )
        completed.update(int(row["worker_index"]) for row in rows)
        pending = [row for row in schedule if row["worker_index"] not in completed]
        batch_number += 1
    validate_global_lease(lease_path, lease)
    if _cross_phase_runner_processes():
        raise StudyManifestError("formal or confirmation runner remains at completion")
    verify_source_snapshots(root, orchestration_revision)
    validate_session_record(session)
    final_observed = _assert_quiescent_output(root, expected_keys)
    final_completed, final_batch_count, final_incomplete = _validate_batch_history(
        session_dir,
        session_fingerprint=str(session["fingerprint"]),
        expected_rows=expected_by_index,
        expected_python=python,
    )
    if (
        final_completed != set(range(LOGICAL_SHARD_COUNT))
        or final_incomplete is not None
        or set(final_observed) != expected_keys
        or len(final_observed) != LOGICAL_SHARD_COUNT
    ):
        raise StudyManifestError("final scheduler history or 240-block registry is incomplete")
    completion = {
        "schema_version": "confirmation-bounded-scheduler-completion.v1",
        "status": "all-240-singletons-strict-child-exit-zero",
        "session_fingerprint": session["fingerprint"],
        "completed_at_utc": _utc_now(),
        "completed_worker_indices": list(range(LOGICAL_SHARD_COUNT)),
        "final_batch_count": final_batch_count,
        "final_block_count": len(final_observed),
        "final_block_registry_fingerprint": _block_registry_fingerprint(
            final_observed
        ),
    }
    completion["fingerprint"] = _fingerprint(completion)
    if completion["final_block_count"] != LOGICAL_SHARD_COUNT:
        raise StudyManifestError("scheduler completed indices without 240 artifacts")

    def verify_completion_before_publish() -> None:
        validate_global_lease(lease_path, lease)
        if _cross_phase_runner_processes():
            raise StudyManifestError(
                "formal or confirmation runner appeared before completion publication"
            )
        verify_source_snapshots(root, orchestration_revision)
        validate_session_record(session)
        current_observed = _assert_quiescent_output(root, expected_keys)
        current_completed, current_batch_count, current_incomplete = (
            _validate_batch_history(
                session_dir,
                session_fingerprint=str(session["fingerprint"]),
                expected_rows=expected_by_index,
                expected_python=python,
            )
        )
        if (
            current_completed != set(range(LOGICAL_SHARD_COUNT))
            or current_incomplete is not None
            or current_batch_count != final_batch_count
            or set(current_observed) != expected_keys
            or len(current_observed) != LOGICAL_SHARD_COUNT
            or _block_registry_fingerprint(current_observed)
            != completion["final_block_registry_fingerprint"]
        ):
            raise StudyManifestError(
                "scheduler state drifted before completion publication"
            )

    _write_create_only(
        completion_path,
        completion,
        prepublish=verify_completion_before_publish,
    )
    return completion_path


def run_scheduler(
    *,
    session_id: str,
    orchestration_revision: str,
    readiness_authorization_revision: str,
    python_executable: Path,
    resume: bool,
    recover_interrupted: bool,
    recover_global_lease: bool,
) -> Path:
    """Run one globally exclusive bounded scheduler session."""

    lease_path, lease = acquire_global_lease(
        session_id=session_id,
        orchestration_revision=orchestration_revision,
        recover_stale=recover_global_lease,
    )
    try:
        return _run_scheduler_body(
            session_id=session_id,
            orchestration_revision=orchestration_revision,
            readiness_authorization_revision=readiness_authorization_revision,
            python_executable=python_executable,
            resume=resume,
            recover_interrupted=recover_interrupted,
            lease_path=lease_path,
            lease=lease,
        )
    finally:
        release_global_lease(lease_path, lease)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--orchestration-revision", required=True)
    parser.add_argument("--readiness-authorization-revision", required=True)
    parser.add_argument("--python-executable", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--recover-interrupted", action="store_true")
    parser.add_argument("--recover-global-lease", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    completion = run_scheduler(
        session_id=arguments.session_id,
        orchestration_revision=arguments.orchestration_revision,
        readiness_authorization_revision=arguments.readiness_authorization_revision,
        python_executable=arguments.python_executable,
        resume=arguments.resume,
        recover_interrupted=arguments.recover_interrupted,
        recover_global_lease=arguments.recover_global_lease,
    )
    print(completion, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
