"""Launch, witness, and finalize the frozen six-worker runtime profile batch."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from secondaryexploration.experiments import (
    StudyManifestError,
    load_study_design_manifest,
)
from secondaryexploration.experiments.artifacts import atomic_write_json
from secondaryexploration.experiments.runner import (
    runtime_environment,
    runtime_environment_fingerprint,
)
from tools.formal_runtime_evidence import (
    _BATCH_ID,
    _FORMAL_MANIFEST_FINGERPRINT,
    _GRID,
    _fingerprint,
    _machine_resources,
    _validate_batch_finalization,
    _validate_launch_batch,
    _verify_snapshot,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _command(stem: str, size: int, model: str, full_replay: bool) -> list[str]:
    command = [
        sys.executable,
        "tools\\profile_synthetic_block.py",
        "configs\\formal\\synthetic-formal-v1.json",
        "--node-count",
        str(size),
        "--parent-replicate",
        "0",
        "--model",
        model,
    ]
    if not full_replay:
        command.append("--skip-replay")
    command.extend(("--batch-id", _BATCH_ID, "--profile-id", stem))
    return command


def _launch_record(processes, *, launcher_revision, memory, processors):
    starts = [item["start_datetime"] for item in processes]
    skew_ms = round((max(starts) - min(starts)).total_seconds() * 1000)
    captured_at = _utc_now()
    rows = []
    for item in processes:
        command_line = subprocess.list2cmdline(item["command"])
        rows.append(
            {
                "profile_id": item["profile_id"],
                "process_id": item["process"].pid,
                "parent_process_id": os.getpid(),
                "start_time_utc": item["start_time_utc"],
                "command_line": command_line,
                "command_line_sha256": hashlib.sha256(
                    command_line.encode("utf-8")
                ).hexdigest(),
            }
        )
    record: dict[str, object] = {
        "schema_version": "formal-runtime-profile-launch.v1",
        "status": "six-workers-observed-live",
        "manifest_fingerprint": _FORMAL_MANIFEST_FINGERPRINT,
        "profiler_revision": launcher_revision,
        "launcher_revision": launcher_revision,
        "batch_id": _BATCH_ID,
        "worker_count": len(_GRID),
        "captured_at_utc": captured_at,
        "start_skew_milliseconds": skew_ms,
        "machine": {
            "logical_processors": processors,
            "total_physical_memory_bytes": memory,
        },
        "processes": rows,
    }
    record["batch_fingerprint"] = _fingerprint(record)
    _validate_launch_batch(
        record,
        evidence_revision=launcher_revision,
        manifest_fingerprint=_FORMAL_MANIFEST_FINGERPRINT,
        total_physical_memory_bytes=memory,
        logical_processors=processors,
    )
    return record


def _finalization_record(processes, launch_record, *, launcher_revision):
    records = []
    for item in processes:
        stdout_path = item["stdout_path"]
        stderr_path = item["stderr_path"]
        records.append(
            {
                "profile_id": item["profile_id"],
                "process_id": item["process"].pid,
                "exit_code": item["exit_code"],
                "stdout_file": stdout_path.name,
                "stderr_file": stderr_path.name,
                "stdout_sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr_path.read_bytes()).hexdigest(),
            }
        )
    record: dict[str, object] = {
        "schema_version": "formal-runtime-profile-finalization.v1",
        "status": "six-workers-exited-zero",
        "batch_id": _BATCH_ID,
        "launcher_revision": launcher_revision,
        "launch_batch_fingerprint": launch_record["batch_fingerprint"],
        "completed_at_utc": _utc_now(),
        "records": records,
    }
    record["finalization_fingerprint"] = _fingerprint(record)
    _validate_batch_finalization(
        record,
        evidence_revision=launcher_revision,
        launch_batch=launch_record,
    )
    return record


def _verify_launcher_snapshot(revision: str) -> None:
    _verify_snapshot(_ROOT, revision)


def _assert_workers_live(processes) -> None:
    if len(processes) != len(_GRID) or any(
        item["process"].poll() is not None for item in processes
    ):
        raise StudyManifestError("six runtime profiler workers were not all live")


def _verify_launcher_environment() -> None:
    manifest = load_study_design_manifest(
        _ROOT / "configs" / "formal" / "synthetic-formal-v1.json"
    )
    environment_fingerprint = runtime_environment_fingerprint(runtime_environment())
    if (
        manifest.fingerprint != _FORMAL_MANIFEST_FINGERPRINT
        or environment_fingerprint != manifest.environment_fingerprint
    ):
        raise StudyManifestError("launcher environment differs from frozen manifest")


def launch(profile_dir: Path, *, launcher_revision: str) -> tuple[Path, Path]:
    """Run the exact concurrent grid and persist launch/finalization witnesses."""

    _verify_launcher_snapshot(launcher_revision)
    _verify_launcher_environment()
    profile_dir = profile_dir.resolve()
    if profile_dir != (_ROOT / "tmp" / "profiling").resolve():
        raise StudyManifestError("runtime profiles must use the frozen tmp directory")
    profile_dir.mkdir(parents=True, exist_ok=True)
    expected_paths = [
        profile_dir / name
        for stem, _, _, _ in _GRID
        for name in (f"{stem}.stdout.json", f"{stem}.stderr.txt")
    ]
    launch_path = profile_dir / "six-worker-launch.json"
    finalization_path = profile_dir / "six-worker-finalization.json"
    if any(path.exists() for path in (*expected_paths, launch_path, finalization_path)):
        raise StudyManifestError("runtime batch output already exists")
    processes = []
    handles = []
    try:
        for stem, size, model, full_replay in _GRID:
            stdout_path = profile_dir / f"{stem}.stdout.json"
            stderr_path = profile_dir / f"{stem}.stderr.txt"
            stdout_handle = stdout_path.open("wb")
            stderr_handle = stderr_path.open("wb")
            handles.extend((stdout_handle, stderr_handle))
            command = _command(stem, size, model, full_replay)
            started = datetime.now(timezone.utc)
            process = subprocess.Popen(
                command,
                cwd=_ROOT,
                stdout=stdout_handle,
                stderr=stderr_handle,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            processes.append(
                {
                    "profile_id": stem,
                    "command": command,
                    "process": process,
                    "start_datetime": started,
                    "start_time_utc": started.isoformat(timespec="milliseconds").replace(
                        "+00:00", "Z"
                    ),
                    "stdout_path": stdout_path,
                    "stderr_path": stderr_path,
                }
            )
        _assert_workers_live(processes)
        memory, processors = _machine_resources()
        launch_record = _launch_record(
            processes,
            launcher_revision=launcher_revision,
            memory=memory,
            processors=processors,
        )
        atomic_write_json(launch_path, launch_record)
        for item in processes:
            item["exit_code"] = item["process"].wait()
        for handle in handles:
            handle.close()
        handles.clear()
        if any(item["exit_code"] != 0 for item in processes):
            raise StudyManifestError("one or more runtime profiler workers failed")
        finalization = _finalization_record(
            processes, launch_record, launcher_revision=launcher_revision
        )
        atomic_write_json(finalization_path, finalization)
        return launch_path, finalization_path
    except BaseException:
        for item in processes:
            if item["process"].poll() is None:
                item["process"].terminate()
        for item in processes:
            if item["process"].poll() is None:
                try:
                    item["process"].wait(timeout=10)
                except subprocess.TimeoutExpired:
                    item["process"].kill()
                    item["process"].wait()
        raise
    finally:
        for handle in handles:
            handle.close()


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-dir", required=True, type=Path)
    parser.add_argument("--launcher-revision", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    launch_path, finalization_path = launch(
        args.profile_dir, launcher_revision=args.launcher_revision
    )
    print(launch_path, flush=True)
    print(finalization_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
