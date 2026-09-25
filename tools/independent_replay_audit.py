"""Run a resumable, result-blind replay audit of the final evidence package.

Each stage invokes a frozen public analysis command against its canonical
output.  The descriptive stages use four bounded workers with a fresh audit
checkpoint root.  The frozen writers refuse a non-identical existing output,
so a zero exit means that the fresh replay reconstructed exactly the archived
artifact.  This wrapper adds only operational receipts and never parses
scientific endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import msvcrt
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "results" / "diagnostics" / "independent-replay" / "20260922-v1"
ANALYSIS_REVISION = "9ecaadec84f8bebe799fb507969de8e0a0947b66"
PARALLEL_EXECUTOR_REVISION = "c636cad28403c82113bdce8dcc0103ffa8c89ff9"
AUDIT_CHECKPOINT_ROOT = "results/diagnostics/independent-replay/20260922-v1/checkpoints"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_json(path: Path, value: dict[str, object]) -> None:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def plan() -> tuple[tuple[str, list[str], str], ...]:
    common = [
        "configs/pilot/synthetic-calibration-v1.json",
        "results/pilot/synthetic-calibration-v1/evidence.json",
        "results/planning/formal-precision-v1.json",
    ]
    return (
        (
            "formal-phase",
            [
                "tools/formal_inference.py", "phase",
                "configs/formal/synthetic-formal-v1.json",
                "outputs/formal/synthetic-formal-v1/run-summary.json",
                *common,
                "--analysis-revision", ANALYSIS_REVISION,
                "--workspace-root", str(ROOT),
                "--output", "results/inference/formal-phase-evidence.json",
            ],
            "results/inference/formal-phase-evidence.json",
        ),
        (
            "confirmation-phase",
            [
                "tools/formal_inference.py", "phase",
                "configs/confirmation/synthetic-confirmation-v1.json",
                "outputs/confirmation/synthetic-confirmation-v1/run-summary.json",
                *common,
                "--analysis-revision", ANALYSIS_REVISION,
                "--workspace-root", str(ROOT),
                "--output", "results/inference/confirmation-phase-evidence.json",
            ],
            "results/inference/confirmation-phase-evidence.json",
        ),
        (
            "formal-descriptive",
            [
                "tools/parallel_descriptive_projection.py",
                "configs/formal/synthetic-formal-v1.json",
                "outputs/formal/synthetic-formal-v1/run-summary.json",
                *common,
                "--executor-revision", PARALLEL_EXECUTOR_REVISION,
                "--workspace-root", str(ROOT),
                "--workers", "4",
                "--checkpoint-root", AUDIT_CHECKPOINT_ROOT,
                "--output", "results/inference/formal-descriptive-mechanism-v1.json",
            ],
            "results/inference/formal-descriptive-mechanism-v1.json",
        ),
        (
            "confirmation-descriptive",
            [
                "tools/parallel_descriptive_projection.py",
                "configs/confirmation/synthetic-confirmation-v1.json",
                "outputs/confirmation/synthetic-confirmation-v1/run-summary.json",
                *common,
                "--executor-revision", PARALLEL_EXECUTOR_REVISION,
                "--workspace-root", str(ROOT),
                "--workers", "4",
                "--checkpoint-root", AUDIT_CHECKPOINT_ROOT,
                "--output", "results/inference/confirmation-descriptive-mechanism-v1.json",
            ],
            "results/inference/confirmation-descriptive-mechanism-v1.json",
        ),
        (
            "replication",
            [
                "tools/formal_inference.py", "replication",
                "--formal-manifest", "configs/formal/synthetic-formal-v1.json",
                "--formal-summary", "outputs/formal/synthetic-formal-v1/run-summary.json",
                "--formal-evidence", "results/inference/formal-phase-evidence.json",
                "--confirmation-manifest", "configs/confirmation/synthetic-confirmation-v1.json",
                "--confirmation-summary", "outputs/confirmation/synthetic-confirmation-v1/run-summary.json",
                "--confirmation-evidence", "results/inference/confirmation-phase-evidence.json",
                "--calibration-manifest", common[0],
                "--calibration-evidence", common[1],
                "--precision", common[2],
                "--analysis-revision", ANALYSIS_REVISION,
                "--workspace-root", str(ROOT),
                "--output", "results/inference/formal-confirmation-replication-evidence.json",
            ],
            "results/inference/formal-confirmation-replication-evidence.json",
        ),
    )


def run_stage(name: str, arguments: list[str], output: str) -> None:
    receipt = DIAG / f"{name}.success.json"
    command = [sys.executable, *arguments]
    target = ROOT / output
    if receipt.exists():
        prior = json.loads(receipt.read_text(encoding="utf-8"))
        if prior.get("command") == command and target.is_file() and prior.get("output_sha256") == digest(target):
            return
        raise RuntimeError(f"prior audit receipt drift for {name}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stdout = DIAG / f"{name}.{stamp}.stdout.log"
    stderr = DIAG / f"{name}.{stamp}.stderr.log"
    write_json(DIAG / "status.json", {"status": "running", "stage": name, "started_at": utc()})
    started = utc()
    with stdout.open("xb") as out, stderr.open("xb") as err:
        completed = subprocess.run(command, cwd=ROOT, stdout=out, stderr=err, check=False)
    record: dict[str, object] = {
        "stage": name, "command": command, "started_at": started,
        "completed_at": utc(), "exit_code": completed.returncode,
        "stdout_sha256": digest(stdout), "stderr_sha256": digest(stderr), "output": output,
    }
    if completed.returncode != 0 or not target.is_file():
        write_json(DIAG / f"{name}.{stamp}.failure.json", record)
        raise RuntimeError(f"{name} replay failed with exit {completed.returncode}")
    record["output_sha256"] = digest(target)
    record["output_bytes"] = target.stat().st_size
    write_json(receipt, record)


def _stage_is_reusable(name: str, arguments: list[str], output: str) -> bool:
    receipt = DIAG / f"{name}.success.json"
    command = [sys.executable, *arguments]
    target = ROOT / output
    if not receipt.exists():
        return False
    prior = json.loads(receipt.read_text(encoding="utf-8"))
    if prior.get("command") == command and target.is_file() and prior.get("output_sha256") == digest(target):
        return True
    raise RuntimeError(f"prior audit receipt drift for {name}")


def run_parallel_stages(stages: tuple[tuple[str, list[str], str], ...]) -> None:
    """Run up to two independent immutable-output replays concurrently."""

    pending = [stage for stage in stages if not _stage_is_reusable(*stage)]
    if not pending:
        return
    if len(pending) > 2:
        raise RuntimeError("parallel audit group exceeds its two-process memory bound")
    started = utc()
    write_json(
        DIAG / "status.json",
        {
            "status": "running",
            "stage": "parallel-group",
            "active_stages": [name for name, _arguments, _output in pending],
            "started_at": started,
            "workers": len(pending),
        },
    )
    jobs = []
    try:
        for name, arguments, output in pending:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            stdout = DIAG / f"{name}.{stamp}.stdout.log"
            stderr = DIAG / f"{name}.{stamp}.stderr.log"
            out = stdout.open("xb")
            err = stderr.open("xb")
            child = subprocess.Popen([sys.executable, *arguments], cwd=ROOT, stdout=out, stderr=err)
            jobs.append((name, arguments, output, stamp, stdout, stderr, out, err, child))
        failures = []
        for name, arguments, output, stamp, stdout, stderr, out, err, child in jobs:
            code = child.wait()
            out.close()
            err.close()
            target = ROOT / output
            record: dict[str, object] = {
                "stage": name,
                "command": [sys.executable, *arguments],
                "started_at": started,
                "completed_at": utc(),
                "exit_code": code,
                "stdout_sha256": digest(stdout),
                "stderr_sha256": digest(stderr),
                "output": output,
            }
            if code == 0 and target.is_file():
                record["output_sha256"] = digest(target)
                record["output_bytes"] = target.stat().st_size
                write_json(DIAG / f"{name}.success.json", record)
            else:
                write_json(DIAG / f"{name}.{stamp}.failure.json", record)
                failures.append(f"{name} exited {code}")
        if failures:
            raise RuntimeError("; ".join(failures))
    finally:
        for _name, _arguments, _output, _stamp, _stdout, _stderr, out, err, _child in jobs:
            if not out.closed:
                out.close()
            if not err.closed:
                err.close()


def main() -> int:
    DIAG.mkdir(parents=True, exist_ok=True)
    with (DIAG / "audit.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            stages = plan()
            run_parallel_stages(stages[:2])
            run_stage(*stages[2])
            run_stage(*stages[3])
            run_stage(*stages[4])
        except Exception as error:
            write_json(DIAG / "status.json", {"status": "stopped-on-error", "at": utc(), "error": str(error)})
            raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    write_json(DIAG / "status.json", {"status": "complete-independent-replay", "at": utc()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
