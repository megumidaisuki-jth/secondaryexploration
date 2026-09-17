"""Pause an operational supervisor once a named stage has a verified receipt.

This utility is intentionally endpoint-free.  It watches only the supervisor's
execution receipt and process tree, so it can be used to honor a requested
stage boundary without inspecting analysis outputs or raw blocks.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"expected object: {path}")
    return value


def children_of(pid: int) -> list[int]:
    # WMIC is unavailable on newer Windows; PowerShell is part of the OS.
    import subprocess

    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        f"(Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}').ProcessId",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        return []
    found: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            found.append(int(line))
    return found


def terminate_tree(pid: int) -> list[int]:
    descendants = children_of(pid)
    stopped: list[int] = []
    for child in descendants:
        stopped.extend(terminate_tree(child))
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return stopped
    stopped.append(pid)
    return stopped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostics", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--poll-seconds", type=float, default=0.2)
    args = parser.parse_args()
    diagnostics = (ROOT / args.diagnostics).resolve()
    receipt = diagnostics / f"{args.stage}.success.json"
    status_path = diagnostics / "status.json"
    while not receipt.exists():
        time.sleep(args.poll_seconds)
    evidence = load_json(receipt)
    if evidence.get("stage") != args.stage or evidence.get("exit_code") != 0:
        raise RuntimeError("stage receipt is not a successful requested stage")
    status = load_json(status_path)
    supervisor = status.get("pid")
    if not isinstance(supervisor, int) or supervisor <= 0:
        raise RuntimeError("supervisor PID unavailable at requested boundary")
    stopped = terminate_tree(supervisor)
    record = {
        "status": "paused-after-requested-stage",
        "stage": args.stage,
        "receipt": receipt.name,
        "stopped_pids": stopped,
        "at_unix": time.time(),
    }
    temporary = status_path.with_suffix(".pause.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, status_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
