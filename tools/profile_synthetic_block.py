"""Profile one exact synthetic parent-model block without writing artifacts.

This diagnostic uses a registered frozen manifest, parent seed, and model.
It deliberately calls the same generation and optional complete replay used by
the runner, but it never invokes the artifact writer or creates an output
directory.  It is therefore suitable for profiling the large-size path before
launching a formal phase.
"""

from __future__ import annotations

import argparse
import json
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
from secondaryexploration.topology import ParentGraphModel


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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = load_study_design_manifest(args.manifest)
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
                "diagnostic": "exact-synthetic-parent-block-profile.v1",
                "manifest_fingerprint": manifest.fingerprint,
                "node_count": args.node_count,
                "parent_replicate": args.parent_replicate,
                "parent_model": model.value,
                "result_fingerprint": result.fingerprint,
                "generation_ns": generation_ns,
                "validation_ns": validation_ns,
                "wrote_formal_artifacts": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
