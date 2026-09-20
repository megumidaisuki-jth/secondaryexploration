"""Bounded parallel executor for the frozen descriptive projection.

This is an execution-topology change only.  It preserves the frozen
projection's schema and uses its exact per-block validator/projector.  Before
it may be used for a new phase, ``--equivalence-reference`` must have produced
an exact mapping match against a completed sequential projection of the same
phase.  It does not replace the later independent scientific replay audit.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

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
    load_study_run_summary,
    load_synthetic_block_artifact,
)
from secondaryexploration.experiments.runner import validate_frozen_execution_context
from tools import formal_descriptive_projection as frozen
from tools import formal_inference as primary


FROZEN_PROJECTION_REVISION = "a85c952afa120f86a9ace96a031819c0d131d2b4"
_TOOL_PATHS = (
    "tools/parallel_descriptive_projection.py",
    "docs/plans/2026-09-19-parallel-descriptive-executor.md",
)
_WORKER: dict[str, object] = {}
CHECKPOINT_SCHEMA = "parallel-descriptive-block-checkpoint.v1"


def _digest(path: Path) -> str:
    return primary._sha256_file(path)


def _verify_executor_snapshot(root: Path, revision: str) -> None:
    primary._validate_digest(revision, "executor_revision", length=40)
    frozen._verify_projection_snapshot(root, FROZEN_PROJECTION_REVISION)
    for path in _TOOL_PATHS:
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}:{path}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if exists.returncode != 0:
            raise StudyManifestError("parallel executor source is absent from declared revision")
    clean = subprocess.run(
        ["git", "diff", "--quiet", revision, "--", *_TOOL_PATHS],
        cwd=root,
        check=False,
    )
    if clean.returncode != 0:
        raise StudyManifestError("parallel executor source differs from declared revision")


def _worker_initializer(manifest_path: str) -> None:
    manifest = load_study_design_manifest(Path(manifest_path))
    ledger = build_study_seed_ledger(manifest)
    _WORKER.clear()
    _WORKER.update(
        manifest=manifest,
        ledger=ledger,
        seeds={(item.node_count, item.parent_replicate): item for item in ledger.parent_seeds},
    )


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checkpoint_context(manifest, ledger, summary, calibration, precision, workers: int, executor_revision: str) -> dict[str, object]:
    return {
        "schema_version": CHECKPOINT_SCHEMA,
        "executor_revision": executor_revision,
        "frozen_projection_revision": FROZEN_PROJECTION_REVISION,
        "phase": manifest.phase.value,
        "workers": workers,
        "manifest": manifest.fingerprint,
        "seed_ledger": ledger.fingerprint,
        "run_summary": summary["summary_fingerprint"],
        "calibration": calibration["evidence_fingerprint"],
        "precision": precision["precision_fingerprint"],
    }


def _load_checkpoint(path: Path, *, index: int, key: str, context_sha256: str, expected_record: Mapping[str, object]) -> dict[str, object]:
    value = primary._load_strict_json(path, "parallel block checkpoint")
    required = {"schema_version", "context_sha256", "index", "block_key", "rebuilt", "registry", "rows"}
    if set(value) != required or value["schema_version"] != CHECKPOINT_SCHEMA:
        raise StudyManifestError("parallel block checkpoint schema differs")
    if value["context_sha256"] != context_sha256 or value["index"] != index or value["block_key"] != key:
        raise StudyManifestError("parallel block checkpoint identity differs")
    if value["rebuilt"] != expected_record:
        raise StudyManifestError("parallel block checkpoint summary record differs")
    registry = value["registry"]
    if not isinstance(registry, Mapping) or registry.get("block_key") != key:
        raise StudyManifestError("parallel block checkpoint registry differs")
    if not isinstance(value["rows"], list):
        raise StudyManifestError("parallel block checkpoint rows differ")
    return value


def _write_progress(path: Path, *, context_sha256: str, phase: str, completed: int, total: int, last_key: str | None) -> None:
    atomic_write_json(path, {
        "schema_version": "parallel-descriptive-progress.v1",
        "context_sha256": context_sha256,
        "phase": phase,
        "completed_block_count": completed,
        "total_block_count": total,
        "last_completed_block_key": last_key,
        "updated_at": _utc(),
        "status": "complete" if completed == total else "running",
    })


def _project_one(task: tuple[int, str, str, int, int, str, str, Mapping[str, object], str, str]):
    index, key, path_text, node_count, replicate, parent_model, code_revision, environment, checkpoint_text, context_sha256 = task
    manifest = _WORKER["manifest"]
    ledger = _WORKER["ledger"]
    seeds = _WORKER["seeds"]
    if not isinstance(manifest, object) or not isinstance(ledger, object) or not isinstance(seeds, dict):
        raise StudyManifestError("parallel worker context is unavailable")
    path = Path(path_text)
    before = _digest(path)
    artifact = load_synthetic_block_artifact(
        path,
        manifest=manifest,
        ledger=ledger,
        parent_seed=seeds[(node_count, replicate)],
        parent_model=parent_model,
        code_revision=code_revision,
        environment=environment,
    )
    timing = artifact["timing_ns"]
    rebuilt = {
        "block_key": key,
        "path": f"blocks/{key}.json",
        "artifact_fingerprint": artifact["artifact_fingerprint"],
        "result_fingerprint": artifact["result_fingerprint"],
        "generation_ns": timing["generation"],
        "validation_ns": timing["exact_validation"],
    }
    registry = {
        "block_key": key,
        "path": f"blocks/{key}.json",
        "artifact_fingerprint": artifact["artifact_fingerprint"],
        "result_fingerprint": artifact["result_fingerprint"],
        "file_sha256": before,
    }
    rows = frozen._project_block(manifest, artifact)
    checkpoint = Path(checkpoint_text)
    atomic_write_json(checkpoint, {
        "schema_version": CHECKPOINT_SCHEMA,
        "context_sha256": context_sha256,
        "index": index,
        "block_key": key,
        "rebuilt": rebuilt,
        "registry": registry,
        "rows": rows,
    })
    return index, key


def build_parallel_projection(
    manifest,
    ledger,
    summary,
    calibration,
    precision,
    *,
    manifest_path: Path,
    output_root: Path,
    workers: int,
    checkpoint_root: Path,
    executor_revision: str,
):
    if workers < 1 or workers > 4:
        raise StudyManifestError("parallel worker count must be in [1, 4]")
    if summary["status"] != "complete" or summary["completed_block_count"] != 240:
        raise StudyManifestError("parallel projection requires complete 240 blocks")
    expected_keys = tuple(item["block_key"] for item in summary["blocks"])
    if expected_keys != primary._expected_block_keys():
        raise StudyManifestError("summary block registry is not canonical")
    paths = primary._exact_phase_block_paths(output_root, expected_keys)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    context = _checkpoint_context(manifest, ledger, summary, calibration, precision, workers, executor_revision)
    context_sha256 = primary._mapping_fingerprint(context)
    context_path = checkpoint_root / "context.json"
    if context_path.exists():
        if primary._load_strict_json(context_path, "parallel checkpoint context") != context:
            raise StudyManifestError("parallel checkpoint context differs; refusing resume")
    else:
        atomic_write_json(context_path, context)
    progress_path = checkpoint_root / "progress.json"
    tasks = []
    completed_keys: list[str] = []
    for index, record in enumerate(summary["blocks"]):
        key = record["block_key"]
        parts = key.split("-", 2)
        checkpoint = checkpoint_root / f"{index:03d}-{key}.json"
        if checkpoint.exists():
            _load_checkpoint(checkpoint, index=index, key=key, context_sha256=context_sha256, expected_record=record)
            completed_keys.append(key)
            continue
        tasks.append((
            index,
            key,
            str(paths[key]),
            int(parts[0][1:]),
            int(parts[1][1:]),
            parts[2],
            summary["code_revision"],
            summary["environment"],
            str(checkpoint),
            context_sha256,
        ))
    _write_progress(progress_path, context_sha256=context_sha256, phase=manifest.phase.value,
                    completed=len(completed_keys), total=len(summary["blocks"]),
                    last_key=completed_keys[-1] if completed_keys else None)
    if tasks:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_initializer,
            initargs=(str(manifest_path),),
        ) as pool:
            futures = [pool.submit(_project_one, task) for task in tasks]
            for future in as_completed(futures):
                _, key = future.result()
                completed_keys.append(key)
                _write_progress(progress_path, context_sha256=context_sha256, phase=manifest.phase.value,
                                completed=len(completed_keys), total=len(summary["blocks"]), last_key=key)
    rows = []
    rebuilt_records = []
    byte_registry = []
    artifact_fingerprints = []
    for index, record in enumerate(summary["blocks"]):
        key = record["block_key"]
        checkpoint = checkpoint_root / f"{index:03d}-{key}.json"
        saved = _load_checkpoint(checkpoint, index=index, key=key, context_sha256=context_sha256, expected_record=record)
        rows.extend(saved["rows"])
        rebuilt_records.append(saved["rebuilt"])
        byte_registry.append(saved["registry"])
        artifact_fingerprints.append(saved["registry"]["artifact_fingerprint"])
    if rebuilt_records != summary["blocks"]:
        raise StudyManifestError("summary differs from parallel source artifacts")
    rebuilt_summary = primary._summary_from_stream_records(
        manifest,
        ledger,
        code_revision=summary["code_revision"],
        environment=summary["environment"],
        records=rebuilt_records,
    )
    if rebuilt_summary != summary:
        raise StudyManifestError("complete summary does not replay for parallel projection")
    final_paths = primary._exact_phase_block_paths(output_root, expected_keys)
    if final_paths != paths:
        raise StudyManifestError("phase registry changed during parallel projection")
    for record in byte_registry:
        if _digest(final_paths[record["block_key"]]) != record["file_sha256"]:
            raise StudyManifestError("phase block changed during parallel projection")
    rows.sort(key=frozen._parent_sort_key)
    evidence = {
        "schema_version": frozen.SCHEMA_VERSION,
        "status": frozen.STATUS,
        "phase": manifest.phase.value,
        "study_id": manifest.study_id,
        "projection_revision": FROZEN_PROJECTION_REVISION,
        "execution_revision": summary["code_revision"],
        "base_analysis_revision": frozen.BASE_ANALYSIS_REVISION,
        "source_fingerprints": {
            "manifest": manifest.fingerprint,
            "seed_ledger": ledger.fingerprint,
            "run_summary": summary["summary_fingerprint"],
            "calibration_evidence": calibration["evidence_fingerprint"],
            "formal_precision": precision["precision_fingerprint"],
            "block_artifacts": artifact_fingerprints,
        },
        "metric_registry": frozen._metric_registry(),
        "block_registry": byte_registry,
        "parent_contrasts": rows,
        "summaries": frozen._build_summaries(manifest.phase.value, rows),
        "limitations": list(frozen._LIMITATIONS),
    }
    evidence["projection_fingerprint"] = primary._mapping_fingerprint(evidence)
    frozen.validate_phase_projection(evidence)
    return evidence


def _load_inputs(args):
    root = Path(args.workspace_root).resolve()
    paths = [
        primary._inside(root, value)
        for value in (
            args.manifest,
            args.summary,
            args.calibration_manifest,
            args.calibration_evidence,
            args.precision,
        )
    ]
    _verify_executor_snapshot(root, args.executor_revision)
    manifest = load_study_design_manifest(paths[0])
    ledger = build_study_seed_ledger(manifest)
    summary = load_study_run_summary(paths[1], manifest=manifest, ledger=ledger)
    calibration_manifest = load_study_design_manifest(paths[2])
    calibration = load_audited_calibration_evidence(paths[3])
    precision = load_formal_precision_evidence(paths[4], calibration_evidence=calibration)
    validate_frozen_execution_context(
        manifest,
        code_revision=summary["code_revision"],
        environment=summary["environment"],
        precision_evidence=precision,
        calibration_manifest=calibration_manifest,
    )
    return root, paths, manifest, ledger, summary, calibration, precision


def run(args) -> Path:
    root, paths, manifest, ledger, summary, calibration, precision = _load_inputs(args)
    checkpoint_base = (root / args.checkpoint_root).resolve()
    try:
        checkpoint_base.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("checkpoint root escapes workspace") from exc
    checkpoint_base.mkdir(parents=True, exist_ok=True)
    checkpoint_root = checkpoint_base / manifest.phase.value
    evidence = build_parallel_projection(
        manifest,
        ledger,
        summary,
        calibration,
        precision,
        manifest_path=paths[0],
        output_root=paths[1].parent.resolve(),
        workers=args.workers,
        checkpoint_root=checkpoint_root,
        executor_revision=args.executor_revision,
    )
    target = primary._evidence_target(root, args.output, paths)
    if args.equivalence_reference:
        reference_path = primary._inside(root, args.equivalence_reference)
        reference = primary._load_strict_json(reference_path, "sequential equivalence reference")
        frozen.validate_phase_projection(reference)
        if reference != evidence:
            raise StudyManifestError("parallel projection differs from sequential reference")
        receipt = {
            "schema_version": "parallel-descriptive-equivalence-audit.v1",
            "status": "exact-mapping-match",
            "phase": manifest.phase.value,
            "executor_revision": args.executor_revision,
            "frozen_projection_revision": FROZEN_PROJECTION_REVISION,
            "worker_count": args.workers,
            "reference_sha256": _digest(reference_path),
            "reference_projection_fingerprint": reference["projection_fingerprint"],
            "candidate_projection_fingerprint": evidence["projection_fingerprint"],
            "source_summary_fingerprint": summary["summary_fingerprint"],
        }
        primary._write_new_or_identical(target, receipt, "parallel descriptive equivalence receipt")
    else:
        primary._write_new_or_identical(target, evidence, "parallel descriptive projection")
    return target


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("summary")
    parser.add_argument("calibration_manifest")
    parser.add_argument("calibration_evidence")
    parser.add_argument("precision")
    parser.add_argument("--executor-revision", required=True)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--workers", type=int, default=min(4, max(1, (os.cpu_count() or 1) // 2)))
    parser.add_argument("--checkpoint-root", default="results/diagnostics/parallel-descriptive")
    parser.add_argument("--equivalence-reference")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    target = run(_parser().parse_args(argv))
    print(target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
