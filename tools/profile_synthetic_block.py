"""Profile one exact synthetic parent-model block without writing artifacts.

This diagnostic uses a registered frozen manifest, parent seed, and model.
It deliberately calls the same generation and optional complete replay used by
the runner, but it never invokes the artifact writer or creates an output
directory.  It is therefore suitable for profiling the large-size path before
launching a formal phase.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
from time import perf_counter_ns

# The script lives outside the package so it cannot alter the frozen execution
# snapshot.  Add its repository root explicitly when launched by file path.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from secondaryexploration.experiments import (
    build_study_seed_ledger,
    load_study_design_manifest,
)
from secondaryexploration.experiments.pipeline import (
    run_synthetic_parent_block,
    validate_synthetic_parent_block_result,
)
from secondaryexploration.experiments.runner import (
    runtime_environment,
    runtime_environment_fingerprint,
)
from secondaryexploration.topology import ParentGraphModel


def _peak_working_set_bytes() -> int | None:
    """Return the process peak working set on Windows when available."""

    if sys.platform != "win32":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = wintypes.HANDLE
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    )
    get_process_memory_info.restype = wintypes.BOOL
    success = get_process_memory_info(
        get_current_process(),
        ctypes.byref(counters),
        counters.cb,
    )
    return int(counters.PeakWorkingSetSize) if success else None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--node-count", required=True, type=int)
    parser.add_argument("--parent-replicate", default=0, type=int)
    parser.add_argument(
        "--model",
        required=True,
        choices=tuple(item.value for item in ParentGraphModel),
    )
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        help="profile generation only; by default the complete exact replay also runs",
    )
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--profile-id", required=True)
    return parser.parse_args()


def _validate_batch_identity(args: argparse.Namespace) -> None:
    if (
        len(args.batch_id) != 64
        or any(character not in "0123456789abcdef" for character in args.batch_id)
    ):
        raise SystemExit("batch-id must be a lowercase SHA-256 value")
    model_labels = {
        "er_gnm": "er",
        "barabasi_albert": "ba",
        "sbm_fixed_count": "sbm",
    }
    mode = "generation" if args.skip_replay else "full"
    expected = (
        f"n{args.node_count}-{model_labels[args.model]}-"
        f"r{args.parent_replicate}-{mode}"
    )
    if args.profile_id != expected:
        raise SystemExit("profile-id differs from the requested diagnostic cell")


def main() -> None:
    args = _parse_args()
    _validate_batch_identity(args)
    manifest = load_study_design_manifest(args.manifest)
    environment_fingerprint = runtime_environment_fingerprint(runtime_environment())
    if environment_fingerprint != manifest.environment_fingerprint:
        raise SystemExit("runtime environment differs from the frozen manifest")
    ledger = build_study_seed_ledger(manifest)
    matching_seeds = tuple(
        seed
        for seed in ledger.parent_seeds
        if seed.node_count == args.node_count
        and seed.parent_replicate == args.parent_replicate
    )
    if len(matching_seeds) != 1:
        raise SystemExit("requested node count and replicate are not registered uniquely")
    parent_seed = matching_seeds[0]
    model = ParentGraphModel(args.model)

    generation_start = perf_counter_ns()
    result = run_synthetic_parent_block(manifest, parent_seed, model)
    generation_ns = perf_counter_ns() - generation_start
    validation_ns: int | None = None
    if not args.skip_replay:
        validation_start = perf_counter_ns()
        validate_synthetic_parent_block_result(result, manifest, parent_seed, model)
        validation_ns = perf_counter_ns() - validation_start

    print(
        json.dumps(
            {
                "diagnostic": "exact-synthetic-parent-block-profile.v2",
                "batch_id": args.batch_id,
                "profile_id": args.profile_id,
                "process_id": os.getpid(),
                "manifest_fingerprint": manifest.fingerprint,
                "environment_fingerprint": environment_fingerprint,
                "node_count": args.node_count,
                "parent_replicate": args.parent_replicate,
                "parent_model": model.value,
                "result_fingerprint": result.fingerprint,
                "generation_ns": generation_ns,
                "validation_ns": validation_ns,
                "peak_working_set_bytes": _peak_working_set_bytes(),
                "wrote_formal_artifacts": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
