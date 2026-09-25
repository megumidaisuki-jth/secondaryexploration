"""Pause the independent replay task while preserving atomic block checkpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "results" / "diagnostics" / "independent-replay" / "20260922-v1"
TASK_NAME = "SecondaryExploration-IndependentReplay-20260925"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict[str, object]) -> None:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def stop_process_tree() -> None:
    script = rf"""
$task = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue
if ($task -and $task.State -eq 'Running') {{ Stop-ScheduledTask -TaskName '{TASK_NAME}' }}
$all = @(Get-CimInstance Win32_Process)
$ids = [System.Collections.Generic.HashSet[int]]::new()
foreach ($process in $all) {{
  if ($process.CommandLine -match 'independent_replay_audit\.py|parallel_descriptive_projection\.py') {{
    [void]$ids.Add([int]$process.ProcessId)
  }}
}}
do {{
  $changed = $false
  foreach ($process in $all) {{
    if ($ids.Contains([int]$process.ParentProcessId) -and $ids.Add([int]$process.ProcessId)) {{ $changed = $true }}
  }}
}} while ($changed)
foreach ($processId in @($ids) | Sort-Object -Descending) {{
  Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}}
"""
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "failed to stop replay process tree")


def checkpoint_state() -> dict[str, object]:
    states = []
    for phase in ("formal", "confirmation"):
        directory = DIAG / "checkpoints" / phase
        progress_path = directory / "progress.json"
        progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.is_file() else None
        count = sum(1 for path in directory.glob("*.json") if len(path.name) > 4 and path.name[:3].isdigit() and path.name[3] == "-") if directory.is_dir() else 0
        states.append({"phase": phase, "checkpoint_file_count": count, "progress": progress})
    return {"phases": states}


def main() -> int:
    DIAG.mkdir(parents=True, exist_ok=True)
    stop_process_tree()
    now = datetime.now(timezone.utc)
    receipt = {
        "schema_version": "independent-replay-pause.v2",
        "status": "paused-by-user",
        "paused_at": now.isoformat(),
        **checkpoint_state(),
    }
    write_json(DIAG / f"pause-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json", receipt)
    write_json(DIAG / "status.json", receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
