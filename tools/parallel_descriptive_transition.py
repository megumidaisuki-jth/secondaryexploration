"""Continue post-confirmation analysis after a verified parallel-equivalence gate.

The caller must first pause the legacy sequential supervisor at the successful
Formal descriptive receipt.  This transition then proves the bounded parallel
executor exactly reproduces that Formal artifact before it uses the executor
for the independent Confirmation projection.  It remains result-blind and
does not replace the later independent scientific replay audit.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from secondaryexploration.experiments.artifacts import atomic_write_json
from tools import formal_inference as analysis
from tools import post_confirmation_pipeline as legacy


ROOT = _ROOT
DIAG = ROOT / "results/diagnostics/post-confirmation/20260917-v1"
EXECUTOR_REVISION = "c636cad28403c82113bdce8dcc0103ffa8c89ff9"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    return analysis._sha256_file(path)


def command_plan():
    shared = [
        "configs/pilot/synthetic-calibration-v1.json",
        "results/pilot/synthetic-calibration-v1/evidence.json",
        "results/planning/formal-precision-v1.json",
    ]
    parallel_prefix = ["tools/parallel_descriptive_projection.py"]
    formal = [
        *parallel_prefix,
        "configs/formal/synthetic-formal-v1.json",
        "outputs/formal/synthetic-formal-v1/run-summary.json",
        *shared,
        "--executor-revision", EXECUTOR_REVISION,
        "--workspace-root", str(ROOT),
        "--workers", "4",
        "--checkpoint-root", "results/diagnostics/parallel-descriptive",
        "--output", "results/inference/formal-descriptive-mechanism-v1.json",
    ]
    confirmation = [
        *parallel_prefix,
        "configs/confirmation/synthetic-confirmation-v1.json",
        "outputs/confirmation/synthetic-confirmation-v1/run-summary.json",
        *shared,
        "--executor-revision", EXECUTOR_REVISION,
        "--workspace-root", str(ROOT),
        "--workers", "4",
        "--checkpoint-root", "results/diagnostics/parallel-descriptive",
        "--output", "results/inference/confirmation-descriptive-mechanism-v1.json",
    ]
    replication = next(arguments for name, arguments, _ in legacy.plan() if name == "replication")
    return (
        ("formal-descriptive-parallel", formal, "results/inference/formal-descriptive-mechanism-v1.json"),
        ("confirmation-descriptive", confirmation, "results/inference/confirmation-descriptive-mechanism-v1.json"),
        ("replication", replication, "results/inference/formal-confirmation-replication-evidence.json"),
    )


def _run_stage(name: str, arguments: list[str], output: str, context_hash: str) -> None:
    receipt_path = DIAG / f"{name}.success.json"
    command = [sys.executable, *arguments]
    if receipt_path.exists():
        prior = analysis._load_strict_json(receipt_path, "transition receipt")
        if (
            prior.get("context_sha256") != context_hash
            or prior.get("command") != command
            or not (ROOT / output).is_file()
            or digest(ROOT / output) != prior.get("output_sha256")
        ):
            raise RuntimeError("completed transition stage identity drift")
        return
    attempt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    started = utc()
    base = DIAG / f"{name}.{attempt}"
    with Path(str(base) + ".stdout.log").open("xb") as out, Path(str(base) + ".stderr.log").open("xb") as err:
        child = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err)
        atomic_write_json(
            DIAG / "status.json",
            {
                "status": "running",
                "stage": name,
                "pid": os.getpid(),
                "child_pid": child.pid,
                "started_at": started,
                "command": command,
            },
        )
        code = child.wait()
    record = {
        "stage": name,
        "command": command,
        "started_at": started,
        "completed_at": utc(),
        "exit_code": code,
        "context_sha256": context_hash,
        "stdout_sha256": digest(Path(str(base) + ".stdout.log")),
        "stderr_sha256": digest(Path(str(base) + ".stderr.log")),
        "output": output,
    }
    if code != 0 or not (ROOT / output).is_file():
        atomic_write_json(Path(str(base) + ".failure.json"), record)
        raise RuntimeError(f"{name} failed; recorded exit {code}")
    record["output_sha256"] = digest(ROOT / output)
    record["output_bytes"] = (ROOT / output).stat().st_size
    atomic_write_json(receipt_path, record)


def run() -> None:
    DIAG.mkdir(parents=True, exist_ok=True)
    with (DIAG / "supervisor.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            atomic_write_json(DIAG / "status.json", {"status": "parallel-transition-preflight", "pid": os.getpid(), "at": utc()})
            context = legacy.preflight()
            context_hash = analysis._mapping_fingerprint(context)
            atomic_write_json(
                DIAG / "parallel-transition-preflight.json",
                {
                    "status": "byte-bindings-verified",
                    "at": utc(),
                    "executor_revision": EXECUTOR_REVISION,
                    "context_sha256": context_hash,
                    "serial_formal_status": "intentionally-stopped-without-output",
                },
            )
            for name, arguments, output in command_plan():
                _run_stage(name, arguments, output, context_hash)
            atomic_write_json(DIAG / "status.json", {"status": "generated-pending-independent-replay", "at": utc()})
        except Exception as error:
            atomic_write_json(DIAG / "status.json", {"status": "stopped-on-error", "at": utc(), "error": str(error)})
            raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
