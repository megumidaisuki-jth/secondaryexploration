"""Build a strict, write-free formal runtime launch-gate evidence artifact."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from collections.abc import Mapping, Sequence

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
from secondaryexploration.experiments.artifacts import (
    atomic_write_json,
    load_synthetic_block_artifact,
)
from secondaryexploration.experiments.runner import (
    runtime_environment,
    runtime_environment_fingerprint,
    validate_frozen_execution_context,
)


SCHEMA_VERSION = "formal-runtime-profile-evidence.v1"
_STATUS = "launch-gate-pass-six-workers"
_WORKER_COUNT = 6
_THROUGHPUT_CEILING_NS = 190 * 60 * 1_000_000_000
_FORMAL_MANIFEST_FINGERPRINT = "ac7152fc11b79c61b1ec14dc24b26d0ee60d159b00ddaa396e166651212191a6"
_EXECUTION_REVISION = "425710a418b1b28e6c5cd813dff18aeeaa6303c3"
_BATCH_ID = "3abb46668ce27037c792230f610188828bec6f88e8d244b61353f865b81c8ec1"
_RETAINED_BLOCK_KEYS = tuple(
    f"n0030-r{replicate:04d}-{model}"
    for replicate in range(5)
    for model in ("barabasi_albert", "er_gnm", "sbm_fixed_count")
)
_GRID = (
    ("n120-er-r0-full", 120, "er_gnm", True),
    ("n120-ba-r0-generation", 120, "barabasi_albert", False),
    ("n120-sbm-r0-generation", 120, "sbm_fixed_count", False),
    ("n240-er-r0-full", 240, "er_gnm", True),
    ("n240-ba-r0-generation", 240, "barabasi_albert", False),
    ("n240-sbm-r0-generation", 240, "sbm_fixed_count", False),
)
_PROFILE_FIELDS = {
    "diagnostic",
    "batch_id",
    "profile_id",
    "process_id",
    "manifest_fingerprint",
    "environment_fingerprint",
    "node_count",
    "parent_replicate",
    "parent_model",
    "result_fingerprint",
    "generation_ns",
    "validation_ns",
    "peak_working_set_bytes",
    "wrote_formal_artifacts",
}
_EVIDENCE_FIELDS = {
    "schema_version",
    "status",
    "manifest_fingerprint",
    "evidence_revision",
    "profiler_revision",
    "execution_revision",
    "machine",
    "concurrent_worker_count",
    "throughput_ceiling_ns",
    "launch_batch",
    "batch_finalization",
    "records",
    "resource_envelope",
    "formal_resume_state",
    "limitations",
    "evidence_fingerprint",
}
_LIMITATIONS = [
    "profiles-are-write-free-diagnostics-not-formal-study-blocks",
    "barabasi-albert-and-sbm-records-measure-generation-only",
    "six-worker-authorization-does-not-authorize-eight-workers",
    "resource-envelope-does-not-change-the-independent-parent-unit",
    "earlier-cprofile-files-are-auxiliary-hotspot-diagnostics-not-launch-gate-inputs",
    "strict-raw-replay-freezes-the-pre-resume-15-block-state-and-is-timepoint-specific",
]


def build_runtime_profile_evidence(
    manifest_path: Path,
    profile_dir: Path,
    *,
    calibration_manifest_path: Path,
    calibration_evidence_path: Path,
    precision_path: Path,
    evidence_revision: str,
) -> dict[str, object]:
    """Strict-load frozen paths and machine resources before building evidence."""

    manifest = load_study_design_manifest(manifest_path)
    _verify_snapshot(_ROOT, evidence_revision)
    total_memory, processors = _machine_resources()
    launch_batch = _load_launch_batch(
        profile_dir / "six-worker-launch.json",
        evidence_revision=evidence_revision,
        total_physical_memory_bytes=total_memory,
        logical_processors=processors,
    )
    batch_finalization = _load_batch_finalization(
        profile_dir / "six-worker-finalization.json",
        evidence_revision=evidence_revision,
        launch_batch=launch_batch,
    )
    formal_resume_state = _load_formal_resume_state(
        manifest,
        calibration_manifest_path=calibration_manifest_path,
        calibration_evidence_path=calibration_evidence_path,
        precision_path=precision_path,
    )
    return _build_runtime_profile_evidence(
        manifest,
        profile_dir,
        evidence_revision=evidence_revision,
        total_physical_memory_bytes=total_memory,
        logical_processors=processors,
        launch_batch=launch_batch,
        batch_finalization=batch_finalization,
        formal_resume_state=formal_resume_state,
    )


def _build_runtime_profile_evidence(
    manifest,
    profile_dir: Path,
    *,
    evidence_revision: str,
    total_physical_memory_bytes: int,
    logical_processors: int,
    launch_batch: Mapping[str, object],
    batch_finalization: Mapping[str, object],
    formal_resume_state: Mapping[str, object],
) -> dict[str, object]:
    """Strict-load the frozen six-record grid and apply the launch gate."""

    _digest(evidence_revision, "evidence_revision", 40)
    if (
        manifest.study_id != "synthetic-formal-v1"
        or manifest.fingerprint != _FORMAL_MANIFEST_FINGERPRINT
        or manifest.code_revision != _EXECUTION_REVISION
    ):
        raise StudyManifestError("runtime evidence requires the frozen formal study")
    if type(total_physical_memory_bytes) is not int or total_physical_memory_bytes <= 0:
        raise StudyManifestError("total physical memory must be positive")
    if type(logical_processors) is not int or logical_processors < _WORKER_COUNT:
        raise StudyManifestError("machine has fewer logical processors than workers")
    _validate_launch_batch(
        launch_batch,
        evidence_revision=evidence_revision,
        manifest_fingerprint=manifest.fingerprint,
        total_physical_memory_bytes=total_physical_memory_bytes,
        logical_processors=logical_processors,
    )
    _validate_batch_finalization(
        batch_finalization,
        evidence_revision=evidence_revision,
        launch_batch=launch_batch,
    )
    _validate_formal_resume_state(formal_resume_state, manifest.fingerprint)

    expected_profile_files = {
        f"{stem}.{suffix}"
        for stem, _, _, _ in _GRID
        for suffix in ("stdout.json", "stderr.txt")
    }
    observed_profile_files = {
        path.name
        for pattern in ("*.stdout.json", "*.stderr.txt")
        for path in profile_dir.glob(pattern)
        if path.is_file()
    }
    if observed_profile_files != expected_profile_files:
        raise StudyManifestError("runtime profile file registry differs")

    launch_processes = {
        item["profile_id"]: item for item in launch_batch["processes"]
    }
    finalized = {
        item["profile_id"]: item for item in batch_finalization["records"]
    }
    records = []
    for stem, size, model, full_replay in _GRID:
        stdout_path = profile_dir / f"{stem}.stdout.json"
        stderr_path = profile_dir / f"{stem}.stderr.txt"
        try:
            stderr_bytes = stderr_path.read_bytes()
            stdout_bytes = stdout_path.read_bytes()
        except OSError as exc:
            raise StudyManifestError(f"cannot read runtime profile {stem}") from exc
        if stderr_bytes:
            raise StudyManifestError(f"runtime profile stderr is nonempty: {stem}")
        raw = _load_one_json_line(stdout_bytes, stem)
        _validate_profile_record(
            raw,
            manifest_fingerprint=manifest.fingerprint,
            node_count=size,
            parent_model=model,
            full_replay=full_replay,
            profile_id=stem,
            batch_id=_BATCH_ID,
            process_id=launch_processes[stem]["process_id"],
            environment_fingerprint=formal_resume_state["environment_fingerprint"],
        )
        stdout_sha = hashlib.sha256(stdout_bytes).hexdigest()
        stderr_sha = hashlib.sha256(stderr_bytes).hexdigest()
        final = finalized[stem]
        if (
            final["process_id"] != raw["process_id"]
            or final["stdout_file"] != stdout_path.name
            or final["stderr_file"] != stderr_path.name
            or final["stdout_sha256"] != stdout_sha
            or final["stderr_sha256"] != stderr_sha
            or final["exit_code"] != 0
        ):
            raise StudyManifestError("profile files differ from batch finalization")
        records.append(
            {
                "profile_id": stem,
                "mode": "generation-plus-exact-replay" if full_replay else "generation-only",
                "node_count": size,
                "parent_model": model,
                "parent_replicate": 0,
                "result_fingerprint": raw["result_fingerprint"],
                "environment_fingerprint": raw["environment_fingerprint"],
                "generation_ns": raw["generation_ns"],
                "validation_ns": raw["validation_ns"],
                "peak_working_set_bytes": raw["peak_working_set_bytes"],
                "stdout_sha256": stdout_sha,
                "stderr_sha256": stderr_sha,
            }
        )

    max_peak = max(item["peak_working_set_bytes"] for item in records)
    memory_ceiling = max_peak * _WORKER_COUNT
    if memory_ceiling * 2 > total_physical_memory_bytes:
        raise StudyManifestError("six-worker peak-memory envelope exceeds 50 percent")
    n240_er = next(item for item in records if item["profile_id"] == "n240-er-r0-full")
    if n240_er["generation_ns"] > _THROUGHPUT_CEILING_NS:
        raise StudyManifestError("concurrent n240 ER generation exceeds 190 minutes")

    evidence: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": _STATUS,
        "manifest_fingerprint": manifest.fingerprint,
        "evidence_revision": evidence_revision,
        "profiler_revision": evidence_revision,
        "execution_revision": _EXECUTION_REVISION,
        "machine": {
            "logical_processors": logical_processors,
            "total_physical_memory_bytes": total_physical_memory_bytes,
        },
        "concurrent_worker_count": _WORKER_COUNT,
        "throughput_ceiling_ns": _THROUGHPUT_CEILING_NS,
        "launch_batch": dict(launch_batch),
        "batch_finalization": dict(batch_finalization),
        "records": records,
        "resource_envelope": {
            "max_recorded_peak_working_set_bytes": max_peak,
            "six_worker_memory_ceiling_bytes": memory_ceiling,
            "minimum_memory_reserve_bytes": total_physical_memory_bytes - memory_ceiling,
            "n240_er_concurrent_generation_ns": n240_er["generation_ns"],
        },
        "formal_resume_state": dict(formal_resume_state),
        "limitations": list(_LIMITATIONS),
    }
    evidence["evidence_fingerprint"] = _fingerprint(evidence)
    validate_runtime_profile_evidence(evidence)
    return evidence


def validate_runtime_profile_evidence(value: object) -> None:
    """Validate the complete nested evidence schema and all gate arithmetic."""

    top = _mapping(value, _EVIDENCE_FIELDS, "runtime evidence")
    if top["schema_version"] != SCHEMA_VERSION or top["status"] != _STATUS:
        raise StudyManifestError("runtime evidence schema or status differs")
    _digest(top["manifest_fingerprint"], "manifest_fingerprint")
    _digest(top["evidence_revision"], "evidence_revision", 40)
    _digest(top["profiler_revision"], "profiler_revision", 40)
    _digest(top["execution_revision"], "execution_revision", 40)
    _digest(top["evidence_fingerprint"], "evidence_fingerprint")
    content = dict(top)
    supplied = content.pop("evidence_fingerprint")
    if supplied != _fingerprint(content):
        raise StudyManifestError("runtime evidence fingerprint mismatch")
    if top["concurrent_worker_count"] != _WORKER_COUNT or top[
        "throughput_ceiling_ns"
    ] != _THROUGHPUT_CEILING_NS:
        raise StudyManifestError("runtime gate constants differ")
    if (
        top["manifest_fingerprint"] != _FORMAL_MANIFEST_FINGERPRINT
        or top["profiler_revision"] != top["evidence_revision"]
        or top["execution_revision"] != _EXECUTION_REVISION
    ):
        raise StudyManifestError("runtime frozen source identity differs")

    machine = _mapping(
        top["machine"],
        {"logical_processors", "total_physical_memory_bytes"},
        "machine",
    )
    if type(machine["logical_processors"]) is not int or machine[
        "logical_processors"
    ] < _WORKER_COUNT or type(machine["total_physical_memory_bytes"]) is not int or machine[
        "total_physical_memory_bytes"
    ] <= 0:
        raise StudyManifestError("runtime machine record is invalid")
    _validate_launch_batch(
        top["launch_batch"],
        evidence_revision=top["evidence_revision"],
        manifest_fingerprint=top["manifest_fingerprint"],
        total_physical_memory_bytes=machine["total_physical_memory_bytes"],
        logical_processors=machine["logical_processors"],
    )
    _validate_batch_finalization(
        top["batch_finalization"],
        evidence_revision=top["evidence_revision"],
        launch_batch=top["launch_batch"],
    )
    _validate_formal_resume_state(
        top["formal_resume_state"], top["manifest_fingerprint"]
    )

    rows = top["records"]
    if type(rows) is not list or len(rows) != len(_GRID):
        raise StudyManifestError("runtime evidence record count differs")
    for row, (stem, size, model, full_replay) in zip(rows, _GRID):
        item = _mapping(
            row,
            {
                "profile_id",
                "mode",
                "node_count",
                "parent_model",
                "parent_replicate",
                "result_fingerprint",
                "environment_fingerprint",
                "generation_ns",
                "validation_ns",
                "peak_working_set_bytes",
                "stdout_sha256",
                "stderr_sha256",
            },
            "runtime record",
        )
        expected_mode = "generation-plus-exact-replay" if full_replay else "generation-only"
        if (
            item["profile_id"] != stem
            or item["mode"] != expected_mode
            or item["node_count"] != size
            or item["parent_model"] != model
            or item["parent_replicate"] != 0
        ):
            raise StudyManifestError("runtime record registry differs")
        for field in (
            "result_fingerprint",
            "environment_fingerprint",
            "stdout_sha256",
            "stderr_sha256",
        ):
            _digest(item[field], field)
        if item["environment_fingerprint"] != top["formal_resume_state"][
            "environment_fingerprint"
        ]:
            raise StudyManifestError("runtime record environment differs")
        if item["stderr_sha256"] != hashlib.sha256(b"").hexdigest():
            raise StudyManifestError("runtime stderr hash is not the empty-file hash")
        if type(item["generation_ns"]) is not int or item["generation_ns"] <= 0:
            raise StudyManifestError("runtime generation time is invalid")
        if full_replay:
            if type(item["validation_ns"]) is not int or item["validation_ns"] <= 0:
                raise StudyManifestError("full runtime replay time is invalid")
        elif item["validation_ns"] is not None:
            raise StudyManifestError("generation-only validation time must be null")
        if type(item["peak_working_set_bytes"]) is not int or item[
            "peak_working_set_bytes"
        ] <= 0:
            raise StudyManifestError("runtime peak working set is invalid")

    envelope = _mapping(
        top["resource_envelope"],
        {
            "max_recorded_peak_working_set_bytes",
            "six_worker_memory_ceiling_bytes",
            "minimum_memory_reserve_bytes",
            "n240_er_concurrent_generation_ns",
        },
        "resource envelope",
    )
    max_peak = max(item["peak_working_set_bytes"] for item in rows)
    expected_ceiling = max_peak * _WORKER_COUNT
    n240_generation = next(
        item["generation_ns"] for item in rows if item["profile_id"] == "n240-er-r0-full"
    )
    if envelope != {
        "max_recorded_peak_working_set_bytes": max_peak,
        "six_worker_memory_ceiling_bytes": expected_ceiling,
        "minimum_memory_reserve_bytes": machine["total_physical_memory_bytes"] - expected_ceiling,
        "n240_er_concurrent_generation_ns": n240_generation,
    }:
        raise StudyManifestError("runtime resource envelope arithmetic differs")
    if expected_ceiling * 2 > machine["total_physical_memory_bytes"]:
        raise StudyManifestError("runtime evidence violates the memory gate")
    if n240_generation > _THROUGHPUT_CEILING_NS:
        raise StudyManifestError("runtime evidence violates the throughput gate")
    if top["limitations"] != _LIMITATIONS:
        raise StudyManifestError("runtime evidence limitations differ")


def _load_launch_batch(
    path: Path,
    *,
    evidence_revision: str,
    total_physical_memory_bytes: int,
    logical_processors: int,
):
    try:
        raw = _load_one_json_line(path.read_bytes(), "six-worker-launch")
    except OSError as exc:
        raise StudyManifestError("cannot read six-worker launch record") from exc
    _validate_launch_batch(
        raw,
        evidence_revision=evidence_revision,
        manifest_fingerprint=_FORMAL_MANIFEST_FINGERPRINT,
        total_physical_memory_bytes=total_physical_memory_bytes,
        logical_processors=logical_processors,
    )
    return raw


def _validate_launch_batch(
    value,
    *,
    evidence_revision,
    manifest_fingerprint,
    total_physical_memory_bytes,
    logical_processors,
):
    fields = {
        "schema_version",
        "status",
        "manifest_fingerprint",
        "profiler_revision",
        "launcher_revision",
        "batch_id",
        "worker_count",
        "captured_at_utc",
        "start_skew_milliseconds",
        "machine",
        "processes",
        "batch_fingerprint",
    }
    top = _mapping(value, fields, "launch batch")
    if (
        top["schema_version"] != "formal-runtime-profile-launch.v1"
        or top["status"] != "six-workers-observed-live"
        or top["manifest_fingerprint"] != manifest_fingerprint
        or top["profiler_revision"] != evidence_revision
        or top["launcher_revision"] != evidence_revision
        or top["batch_id"] != _BATCH_ID
        or top["worker_count"] != _WORKER_COUNT
    ):
        raise StudyManifestError("launch batch frozen identity differs")
    for field, length in (
        ("manifest_fingerprint", 64),
        ("profiler_revision", 40),
        ("launcher_revision", 40),
        ("batch_id", 64),
        ("batch_fingerprint", 64),
    ):
        _digest(top[field], field, length)
    content = dict(top)
    supplied = content.pop("batch_fingerprint")
    if supplied != _fingerprint(content):
        raise StudyManifestError("launch batch fingerprint mismatch")
    captured_at = _utc_time(top["captured_at_utc"], "launch capture time")
    if type(top["start_skew_milliseconds"]) is not int or not 0 <= top[
        "start_skew_milliseconds"
    ] <= 2_000:
        raise StudyManifestError("launch start skew exceeds two seconds")
    machine = _mapping(
        top["machine"],
        {"logical_processors", "total_physical_memory_bytes"},
        "launch machine",
    )
    if machine != {
        "logical_processors": logical_processors,
        "total_physical_memory_bytes": total_physical_memory_bytes,
    }:
        raise StudyManifestError("launch machine differs from evidence machine")
    processes = top["processes"]
    if type(processes) is not list or len(processes) != len(_GRID):
        raise StudyManifestError("launch process count differs")
    observed_ids = []
    process_ids = []
    parent_ids = set()
    start_times = []
    for item, (stem, size, model, full_replay) in zip(processes, _GRID):
        row = _mapping(
            item,
            {
                "profile_id",
                "process_id",
                "parent_process_id",
                "start_time_utc",
                "command_line",
                "command_line_sha256",
            },
            "launch process",
        )
        if row["profile_id"] != stem:
            raise StudyManifestError("launch process registry differs")
        if type(row["process_id"]) is not int or row["process_id"] <= 0 or type(
            row["parent_process_id"]
        ) is not int or row["parent_process_id"] <= 0:
            raise StudyManifestError("launch process identifier is invalid")
        start_time = _utc_time(row["start_time_utc"], "launch process start time")
        command = row["command_line"]
        if type(command) is not str or not command:
            raise StudyManifestError("launch command line is invalid")
        _digest(row["command_line_sha256"], "command_line_sha256")
        if row["command_line_sha256"] != hashlib.sha256(command.encode("utf-8")).hexdigest():
            raise StudyManifestError("launch command-line fingerprint mismatch")
        normalized = command.replace("/", "\\")
        required = (
            "tools\\profile_synthetic_block.py",
            "configs\\formal\\synthetic-formal-v1.json",
            f"--node-count {size}",
            "--parent-replicate 0",
            f"--model {model}",
            f"--batch-id {_BATCH_ID}",
            f"--profile-id {stem}",
        )
        if any(token not in normalized for token in required) or (
            ("--skip-replay" in normalized) is full_replay
        ):
            raise StudyManifestError("launch command differs from registered profile")
        observed_ids.append(stem)
        process_ids.append(row["process_id"])
        parent_ids.add(row["parent_process_id"])
        start_times.append(start_time)
    if observed_ids != [item[0] for item in _GRID] or len(set(process_ids)) != len(
        process_ids
    ) or len(parent_ids) != 1:
        raise StudyManifestError("launch processes are not one concurrent batch")
    actual_skew = round((max(start_times) - min(start_times)).total_seconds() * 1000)
    if top["start_skew_milliseconds"] != actual_skew or captured_at < max(start_times):
        raise StudyManifestError("launch start-time skew is inconsistent")


def _utc_time(value, label):
    if type(value) is not str or not value.endswith("Z"):
        raise StudyManifestError(f"{label} is invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise StudyManifestError(f"{label} is malformed") from exc
    return parsed


def _load_batch_finalization(
    path: Path,
    *,
    evidence_revision: str,
    launch_batch: Mapping[str, object],
):
    try:
        raw = _load_one_json_line(path.read_bytes(), "six-worker-finalization")
    except OSError as exc:
        raise StudyManifestError("cannot read six-worker finalization record") from exc
    _validate_batch_finalization(
        raw,
        evidence_revision=evidence_revision,
        launch_batch=launch_batch,
    )
    return raw


def _validate_batch_finalization(
    value,
    *,
    evidence_revision,
    launch_batch,
):
    top = _mapping(
        value,
        {
            "schema_version",
            "status",
            "batch_id",
            "launcher_revision",
            "launch_batch_fingerprint",
            "completed_at_utc",
            "records",
            "finalization_fingerprint",
        },
        "batch finalization",
    )
    if (
        top["schema_version"] != "formal-runtime-profile-finalization.v1"
        or top["status"] != "six-workers-exited-zero"
        or top["batch_id"] != _BATCH_ID
        or top["launcher_revision"] != evidence_revision
        or top["launch_batch_fingerprint"] != launch_batch["batch_fingerprint"]
    ):
        raise StudyManifestError("batch finalization identity differs")
    for field, length in (
        ("batch_id", 64),
        ("launcher_revision", 40),
        ("launch_batch_fingerprint", 64),
        ("finalization_fingerprint", 64),
    ):
        _digest(top[field], field, length)
    content = dict(top)
    supplied = content.pop("finalization_fingerprint")
    if supplied != _fingerprint(content):
        raise StudyManifestError("batch finalization fingerprint mismatch")
    completed = _utc_time(top["completed_at_utc"], "batch completion time")
    launched = _utc_time(launch_batch["captured_at_utc"], "launch capture time")
    if completed <= launched:
        raise StudyManifestError("batch completion precedes launch capture")
    records = top["records"]
    if type(records) is not list or len(records) != len(_GRID):
        raise StudyManifestError("batch finalization record count differs")
    launch_processes = {
        item["profile_id"]: item for item in launch_batch["processes"]
    }
    for item, (stem, _, _, _) in zip(records, _GRID):
        row = _mapping(
            item,
            {
                "profile_id",
                "process_id",
                "exit_code",
                "stdout_file",
                "stderr_file",
                "stdout_sha256",
                "stderr_sha256",
            },
            "batch finalization record",
        )
        if (
            row["profile_id"] != stem
            or row["process_id"] != launch_processes[stem]["process_id"]
            or row["exit_code"] != 0
            or row["stdout_file"] != f"{stem}.stdout.json"
            or row["stderr_file"] != f"{stem}.stderr.txt"
        ):
            raise StudyManifestError("batch finalization process differs")
        _digest(row["stdout_sha256"], "stdout_sha256")
        _digest(row["stderr_sha256"], "stderr_sha256")
        if row["stderr_sha256"] != hashlib.sha256(b"").hexdigest():
            raise StudyManifestError("batch finalization stderr is not empty")


def _load_formal_resume_state(
    manifest,
    *,
    calibration_manifest_path: Path,
    calibration_evidence_path: Path,
    precision_path: Path,
):
    calibration = load_audited_calibration_evidence(calibration_evidence_path)
    precision = load_formal_precision_evidence(
        precision_path, calibration_evidence=calibration
    )
    calibration_manifest = load_study_design_manifest(calibration_manifest_path)
    environment = runtime_environment()
    validate_frozen_execution_context(
        manifest,
        code_revision=_EXECUTION_REVISION,
        environment=environment,
        precision_evidence=precision,
        calibration_manifest=calibration_manifest,
    )
    ledger = build_study_seed_ledger(manifest)
    output_root = (_ROOT / manifest.output_root).resolve()
    _validate_pre_resume_layout(output_root)
    block_root = output_root / "blocks"
    seeds = {(seed.node_count, seed.parent_replicate): seed for seed in ledger.parent_seeds}
    artifact_fingerprints = []
    result_fingerprints = []
    for key in _RETAINED_BLOCK_KEYS:
        size_part, replicate_part, model = key.split("-", 2)
        size = int(size_part[1:])
        replicate = int(replicate_part[1:])
        artifact = load_synthetic_block_artifact(
            block_root / f"{key}.json",
            manifest=manifest,
            ledger=ledger,
            parent_seed=seeds[(size, replicate)],
            parent_model=model,
            code_revision=_EXECUTION_REVISION,
            environment=environment,
        )
        artifact_fingerprints.append(artifact["artifact_fingerprint"])
        result_fingerprints.append(artifact["result_fingerprint"])
    state = {
        "output_root": manifest.output_root,
        "manifest_fingerprint": manifest.fingerprint,
        "seed_ledger_fingerprint": ledger.fingerprint,
        "calibration_evidence_fingerprint": calibration["evidence_fingerprint"],
        "precision_fingerprint": precision["precision_fingerprint"],
        "environment_fingerprint": runtime_environment_fingerprint(environment),
        "retained_block_keys": list(_RETAINED_BLOCK_KEYS),
        "artifact_fingerprints": artifact_fingerprints,
        "result_fingerprints": result_fingerprints,
        "lock_file_count": 0,
        "run_summary_present": False,
    }
    _validate_formal_resume_state(state, manifest.fingerprint)
    return state


def _validate_pre_resume_layout(output_root: Path) -> None:
    """Require exactly the frozen retained-block timepoint before formal resume."""

    block_root = output_root / "blocks"
    expected_names = {f"{key}.json" for key in _RETAINED_BLOCK_KEYS}
    try:
        entries = tuple(block_root.iterdir())
    except OSError as exc:
        raise StudyManifestError("cannot inspect retained formal block directory") from exc
    observed_names = {path.name for path in entries}
    allowed_names = expected_names | {".locks"}
    if not expected_names.issubset(observed_names) or not observed_names.issubset(
        allowed_names
    ):
        raise StudyManifestError("retained formal block registry differs")
    if any(not (block_root / name).is_file() for name in expected_names):
        raise StudyManifestError("retained formal block entry is not a file")
    lock_root = block_root / ".locks"
    if lock_root.exists() and (
        lock_root.is_symlink()
        or not lock_root.is_dir()
        or any(lock_root.iterdir())
    ):
        raise StudyManifestError("formal lock directory is not empty")
    if (output_root / "run-summary.json").exists():
        raise StudyManifestError("partial formal run summary must be absent")


def _validate_formal_resume_state(value, manifest_fingerprint):
    top = _mapping(
        value,
        {
            "output_root",
            "manifest_fingerprint",
            "seed_ledger_fingerprint",
            "calibration_evidence_fingerprint",
            "precision_fingerprint",
            "environment_fingerprint",
            "retained_block_keys",
            "artifact_fingerprints",
            "result_fingerprints",
            "lock_file_count",
            "run_summary_present",
        },
        "formal resume state",
    )
    if (
        top["output_root"] != "outputs/formal/synthetic-formal-v1"
        or top["manifest_fingerprint"] != manifest_fingerprint
        or top["retained_block_keys"] != list(_RETAINED_BLOCK_KEYS)
        or top["lock_file_count"] != 0
        or top["run_summary_present"] is not False
    ):
        raise StudyManifestError("formal resume state differs from frozen gate")
    for field in (
        "manifest_fingerprint",
        "seed_ledger_fingerprint",
        "calibration_evidence_fingerprint",
        "precision_fingerprint",
        "environment_fingerprint",
    ):
        _digest(top[field], field)
    for field in ("artifact_fingerprints", "result_fingerprints"):
        values = top[field]
        if type(values) is not list or len(values) != len(_RETAINED_BLOCK_KEYS):
            raise StudyManifestError(f"formal resume {field} count differs")
        for digest in values:
            _digest(digest, field)
        if len(set(values)) != len(values):
            raise StudyManifestError(f"formal resume {field} must be unique")


def _validate_profile_record(
    raw,
    *,
    manifest_fingerprint,
    node_count,
    parent_model,
    full_replay,
    profile_id,
    batch_id,
    process_id,
    environment_fingerprint,
) -> None:
    item = _mapping(raw, _PROFILE_FIELDS, "profile record")
    if item["diagnostic"] != "exact-synthetic-parent-block-profile.v2":
        raise StudyManifestError("runtime diagnostic schema differs")
    if (
        item["batch_id"] != batch_id
        or item["profile_id"] != profile_id
        or item["process_id"] != process_id
        or item["manifest_fingerprint"] != manifest_fingerprint
        or item["environment_fingerprint"] != environment_fingerprint
        or item["node_count"] != node_count
        or item["parent_model"] != parent_model
        or item["parent_replicate"] != 0
    ):
        raise StudyManifestError("runtime profile identity differs")
    _digest(item["manifest_fingerprint"], "manifest_fingerprint")
    _digest(item["environment_fingerprint"], "environment_fingerprint")
    _digest(item["batch_id"], "batch_id")
    if type(item["profile_id"]) is not str or type(item["process_id"]) is not int or item[
        "process_id"
    ] <= 0:
        raise StudyManifestError("profile batch identity is invalid")
    _digest(item["result_fingerprint"], "result_fingerprint")
    if type(item["generation_ns"]) is not int or item["generation_ns"] <= 0:
        raise StudyManifestError("profile generation time is invalid")
    if full_replay:
        if type(item["validation_ns"]) is not int or item["validation_ns"] <= 0:
            raise StudyManifestError("profile exact replay time is invalid")
    elif item["validation_ns"] is not None:
        raise StudyManifestError("generation-only profile has replay time")
    if type(item["peak_working_set_bytes"]) is not int or item[
        "peak_working_set_bytes"
    ] <= 0:
        raise StudyManifestError("profile peak working set is invalid")
    if item["wrote_formal_artifacts"] is not False:
        raise StudyManifestError("profile is not write-free")


def _load_one_json_line(data: bytes, label: str):
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise StudyManifestError(f"runtime profile is not UTF-8: {label}") from exc
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise StudyManifestError(f"runtime profile must contain one JSON line: {label}")
    try:
        value = json.loads(
            lines[0],
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, StudyManifestError) as exc:
        raise StudyManifestError(f"runtime profile JSON is invalid: {label}") from exc
    return value


def _machine_resources():
    processors = os.cpu_count()
    if type(processors) is not int or processors <= 0:
        raise StudyManifestError("logical processor count is unavailable")
    if sys.platform != "win32":
        raise StudyManifestError("formal runtime evidence currently requires Windows")

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise StudyManifestError("total physical memory is unavailable")
    return int(status.ullTotalPhys), processors


def _verify_snapshot(root: Path, evidence_revision: str) -> None:
    _digest(evidence_revision, "evidence_revision", 40)
    for revision, path, label in (
        (evidence_revision, "tools/formal_runtime_evidence.py", "runtime evidence tool"),
        (evidence_revision, "tools/profile_synthetic_block.py", "profiler"),
        (
            evidence_revision,
            "tools/launch_runtime_profile_batch.py",
            "runtime batch launcher",
        ),
        (_EXECUTION_REVISION, "secondaryexploration", "execution package"),
    ):
        completed = subprocess.run(
            ["git", "diff", "--quiet", revision, "--", path], cwd=root, check=False
        )
        if completed.returncode != 0:
            raise StudyManifestError(f"{label} differs from declared revision")
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}:{path}"],
            cwd=root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if exists.returncode != 0:
            raise StudyManifestError(f"{label} is absent from declared revision")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "secondaryexploration"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if untracked.returncode != 0 or untracked.stdout.strip():
        raise StudyManifestError("untracked execution-package files prevent verification")


def load_runtime_profile_evidence(
    path: Path,
    *,
    manifest_path: Path,
    profile_dir: Path,
    calibration_manifest_path: Path,
    calibration_evidence_path: Path,
    precision_path: Path,
    evidence_revision: str,
):
    """Strict-load evidence only through complete raw-source reconstruction."""

    try:
        raw = _load_one_json_line(path.read_bytes(), "runtime-evidence")
    except OSError as exc:
        raise StudyManifestError("cannot read runtime evidence") from exc
    validate_runtime_profile_evidence(raw)
    expected = build_runtime_profile_evidence(
        manifest_path,
        profile_dir,
        calibration_manifest_path=calibration_manifest_path,
        calibration_evidence_path=calibration_evidence_path,
        precision_path=precision_path,
        evidence_revision=evidence_revision,
    )
    if raw != expected:
        raise StudyManifestError("runtime evidence complete raw replay mismatch")
    return raw


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


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StudyManifestError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    raise StudyManifestError(f"non-finite JSON constant {value!r} is unsupported")


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile-dir", required=True, type=Path)
    parser.add_argument("--calibration-manifest", required=True, type=Path)
    parser.add_argument("--calibration-evidence", required=True, type=Path)
    parser.add_argument("--precision", required=True, type=Path)
    parser.add_argument("--evidence-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    evidence = build_runtime_profile_evidence(
        args.manifest,
        args.profile_dir,
        calibration_manifest_path=args.calibration_manifest,
        calibration_evidence_path=args.calibration_evidence,
        precision_path=args.precision,
        evidence_revision=args.evidence_revision,
    )
    output = args.output.resolve()
    allowed_root = (_ROOT / "results" / "diagnostics").resolve()
    try:
        output.relative_to(allowed_root)
    except ValueError as exc:
        raise StudyManifestError("runtime evidence output must be in results/diagnostics") from exc
    if output.exists():
        raise StudyManifestError("runtime evidence output already exists")
    atomic_write_json(output, evidence)
    print(output, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
