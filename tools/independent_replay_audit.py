"""Run a resumable, result-blind replay audit of the final evidence package.

Each stage invokes the frozen public analysis command against its canonical
output.  The frozen writers refuse a non-identical existing output, so a zero
exit means that the fresh replay reconstructed exactly the archived artifact.
This wrapper adds only operational receipts and never parses scientific
endpoints.
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
PROJECTION_REVISION = "a85c952afa120f86a9ace96a031819c0d131d2b4"


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
                "tools/formal_descriptive_projection.py",
                "configs/formal/synthetic-formal-v1.json",
                "outputs/formal/synthetic-formal-v1/run-summary.json",
                *common,
                "--projection-revision", PROJECTION_REVISION,
                "--workspace-root", str(ROOT),
                "--output", "results/inference/formal-descriptive-mechanism-v1.json",
            ],
            "results/inference/formal-descriptive-mechanism-v1.json",
        ),
        (
            "confirmation-descriptive",
            [
                "tools/formal_descriptive_projection.py",
                "configs/confirmation/synthetic-confirmation-v1.json",
                "outputs/confirmation/synthetic-confirmation-v1/run-summary.json",
                *common,
                "--projection-revision", PROJECTION_REVISION,
                "--workspace-root", str(ROOT),
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


def main() -> int:
    DIAG.mkdir(parents=True, exist_ok=True)
    with (DIAG / "audit.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            for name, arguments, output in plan():
                run_stage(name, arguments, output)
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
