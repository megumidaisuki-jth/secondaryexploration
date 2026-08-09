"""Resumable exact execution of every synthetic study parent block."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter_ns

from secondaryexploration.topology import ParentGraphModel
from secondaryexploration.analysis.precision import (
    load_audited_calibration_evidence,
    load_formal_precision_evidence,
)

from .artifacts import (
    atomic_write_json,
    build_study_run_summary,
    build_synthetic_block_artifact,
    load_synthetic_block_artifact,
    validate_code_revision,
)
from .pipeline import (
    run_synthetic_parent_block,
    validate_synthetic_parent_block_result,
)
from .study import (
    StudyManifestError,
    StudyDesignManifest,
    StudyPhase,
    build_study_seed_ledger,
    load_study_design_manifest,
)


ProgressCallback = Callable[[str], None]
_REGISTERED_PARENT_MODELS = (
    ParentGraphModel.ER_GNM,
    ParentGraphModel.BARABASI_ALBERT,
    ParentGraphModel.SBM_FIXED_COUNT,
)


def execute_synthetic_study(
    manifest_path: str | Path,
    *,
    workspace_root: str | Path,
    code_revision: str,
    precision_path: str | Path | None = None,
    calibration_evidence_path: str | Path | None = None,
    resume: bool = True,
    progress: ProgressCallback | None = None,
) -> Path:
    """Execute, exactly replay, checkpoint, and index every declared block."""

    (
        manifest,
        ledger,
        output_root,
        environment,
        _precision,
        expected_count,
    ) = _prepare_synthetic_study(
        manifest_path,
        workspace_root=workspace_root,
        code_revision=code_revision,
        precision_path=precision_path,
        calibration_evidence_path=calibration_evidence_path,
    )
    block_root = output_root / "blocks"
    completed_artifacts: list[dict[str, object]] = []

    for parent_seed in ledger.parent_seeds:
        for parent_model in _REGISTERED_PARENT_MODELS:
            block_key = _block_key(parent_seed.node_count, parent_seed.parent_replicate, parent_model)
            artifact_path = block_root / f"{block_key}.json"
            if artifact_path.exists():
                if not resume:
                    raise StudyManifestError(
                        f"block artifact already exists with resume disabled: {artifact_path}"
                    )
                _notify(progress, f"resume {block_key}")
                artifact = load_synthetic_block_artifact(
                    artifact_path,
                    manifest=manifest,
                    ledger=ledger,
                    parent_seed=parent_seed,
                    parent_model=parent_model.value,
                    code_revision=code_revision,
                    environment=environment,
                )
            else:
                _notify(progress, f"generate {block_key}")
                started = perf_counter_ns()
                result = run_synthetic_parent_block(
                    manifest,
                    parent_seed,
                    parent_model,
                )
                generation_ns = perf_counter_ns() - started
                _notify(progress, f"validate {block_key}")
                validation_started = perf_counter_ns()
                validate_synthetic_parent_block_result(
                    result,
                    manifest,
                    parent_seed,
                    parent_model,
                )
                validation_ns = perf_counter_ns() - validation_started
                artifact = build_synthetic_block_artifact(
                    result,
                    code_revision=code_revision,
                    environment=environment,
                    generation_ns=generation_ns,
                    validation_ns=validation_ns,
                )
                atomic_write_json(artifact_path, artifact)
                _notify(progress, f"checkpoint {block_key}")
            completed_artifacts.append(artifact)
            summary = build_study_run_summary(
                manifest,
                ledger,
                code_revision=code_revision,
                environment=environment,
                block_artifacts=completed_artifacts,
            )
            atomic_write_json(output_root / "run-summary.json", summary)

    _notify(progress, f"complete {len(completed_artifacts)}/{expected_count}")
    return output_root / "run-summary.json"


def preflight_synthetic_study(
    manifest_path: str | Path,
    *,
    workspace_root: str | Path,
    code_revision: str,
    precision_path: str | Path | None = None,
    calibration_evidence_path: str | Path | None = None,
) -> dict[str, object]:
    """Replay every launch gate without creating an output directory or block."""

    (
        manifest,
        _ledger,
        output_root,
        environment,
        precision,
        expected_count,
    ) = _prepare_synthetic_study(
        manifest_path,
        workspace_root=workspace_root,
        code_revision=code_revision,
        precision_path=precision_path,
        calibration_evidence_path=calibration_evidence_path,
    )
    return {
        "status": "preflight-valid-no-execution",
        "study_id": manifest.study_id,
        "phase": manifest.phase.value,
        "manifest_fingerprint": manifest.fingerprint,
        "precision_fingerprint": (
            None if precision is None else precision["precision_fingerprint"]
        ),
        "code_revision": code_revision,
        "environment": dict(environment),
        "environment_fingerprint": runtime_environment_fingerprint(environment),
        "expected_block_count": expected_count,
        "output_root": manifest.output_root,
        "output_already_exists": output_root.exists(),
    }


def _prepare_synthetic_study(
    manifest_path: str | Path,
    *,
    workspace_root: str | Path,
    code_revision: str,
    precision_path: str | Path | None,
    calibration_evidence_path: str | Path | None,
):
    manifest = load_study_design_manifest(manifest_path)
    validate_code_revision(code_revision)
    if manifest.code_revision is not None and code_revision != manifest.code_revision:
        raise StudyManifestError(
            "code_revision does not match the frozen study manifest"
        )
    ledger = build_study_seed_ledger(manifest)
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise StudyManifestError("workspace_root must be an existing directory")
    environment = runtime_environment()
    precision = None
    if manifest.phase is StudyPhase.PILOT:
        if precision_path is not None or calibration_evidence_path is not None:
            raise StudyManifestError(
                "pilot execution cannot consume a formal precision freeze"
            )
    else:
        if precision_path is None or calibration_evidence_path is None:
            raise StudyManifestError(
                "formal and confirmation execution require precision and calibration evidence"
            )
        resolved_precision = _resolve_read_path(root, precision_path, "precision_path")
        resolved_calibration = _resolve_read_path(
            root,
            calibration_evidence_path,
            "calibration_evidence_path",
        )
        calibration = load_audited_calibration_evidence(resolved_calibration)
        precision = load_formal_precision_evidence(
            resolved_precision,
            calibration_evidence=calibration,
        )
    validate_frozen_execution_context(
        manifest,
        code_revision=code_revision,
        environment=environment,
        precision_evidence=precision,
    )
    output_root = (root / manifest.output_root).resolve()
    try:
        output_root.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("manifest output_root escapes workspace_root") from exc
    expected_count = len(ledger.parent_seeds) * len(_REGISTERED_PARENT_MODELS)
    return manifest, ledger, output_root, environment, precision, expected_count


def runtime_environment() -> dict[str, object]:
    """Return the minimal exact runtime identity bound to resumable artifacts."""

    return {
        "python_implementation": sys.implementation.name,
        "python_version": platform.python_version(),
        "platform_system": platform.system() or "unknown",
        "machine": platform.machine() or "unknown",
    }


def runtime_environment_fingerprint(environment: Mapping[str, object]) -> str:
    """Return the canonical SHA-256 identity frozen by non-pilot manifests."""

    expected = {
        "python_implementation",
        "python_version",
        "platform_system",
        "machine",
    }
    if not isinstance(environment, Mapping) or set(environment) != expected:
        raise StudyManifestError("runtime environment fields differ")
    if any(type(value) is not str or not value for value in environment.values()):
        raise StudyManifestError("runtime environment values must be nonempty strings")
    payload = json.dumps(
        dict(environment),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_frozen_execution_context(
    manifest: StudyDesignManifest,
    *,
    code_revision: str,
    environment: Mapping[str, object],
    precision_evidence: Mapping[str, object] | None,
) -> None:
    """Fail closed unless a non-pilot run matches every precision freeze field."""

    if not isinstance(manifest, StudyDesignManifest):
        raise StudyManifestError("execution manifest is malformed")
    validate_code_revision(code_revision)
    environment_fingerprint = runtime_environment_fingerprint(environment)
    if manifest.phase is StudyPhase.PILOT:
        if precision_evidence is not None:
            raise StudyManifestError("pilot execution cannot use formal precision evidence")
        return
    if precision_evidence is None:
        raise StudyManifestError("non-pilot execution requires formal precision evidence")
    if manifest.code_revision != code_revision:
        raise StudyManifestError("code_revision does not match the frozen study manifest")
    if manifest.environment_fingerprint != environment_fingerprint:
        raise StudyManifestError("runtime environment does not match the frozen manifest")
    if manifest.basis_fingerprint != precision_evidence.get("precision_fingerprint"):
        raise StudyManifestError("manifest basis does not match formal precision evidence")
    expected_seed_field = (
        "formal_base_seed"
        if manifest.phase is StudyPhase.FORMAL
        else "confirmation_base_seed"
    )
    expected_seed = precision_evidence.get("execution_seed_families", {}).get(
        expected_seed_field
    )
    if manifest.base_seed != expected_seed:
        raise StudyManifestError("manifest seed does not match its frozen phase family")
    horizon = precision_evidence.get("precision_targets", {}).get(
        "endpoint_horizon",
        {},
    )
    if manifest.requests_per_node != horizon.get("requests_per_node"):
        raise StudyManifestError("manifest horizon differs from formal precision evidence")
    counts = precision_evidence.get("planned_parent_count_per_size_model")
    if not isinstance(counts, list):
        raise StudyManifestError("formal precision parent counts are malformed")
    count_field = (
        "formal_parent_count"
        if manifest.phase is StudyPhase.FORMAL
        else "confirmation_parent_count"
    )
    expected_rows = {
        (cell.node_count, model, manifest.parent_replicates)
        for cell in manifest.size_cells
        for model in ("barabasi_albert", "er_gnm", "sbm_fixed_count")
    }
    observed_rows = set()
    for item in counts:
        if not isinstance(item, Mapping):
            raise StudyManifestError("formal precision parent count row is malformed")
        observed_rows.add(
            (item.get("node_count"), item.get("parent_model"), item.get(count_field))
        )
    if observed_rows != expected_rows:
        raise StudyManifestError("manifest parent counts differ from formal precision evidence")


def _resolve_read_path(root: Path, value: str | Path, label: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError(f"{label} escapes workspace_root") from exc
    return resolved


def _block_key(
    node_count: int,
    parent_replicate: int,
    parent_model: ParentGraphModel,
) -> str:
    return f"n{node_count:04d}-r{parent_replicate:04d}-{parent_model.value}"


def _notify(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run every registered synthetic block with exact replay checkpoints.",
    )
    parser.add_argument("manifest", help="strict study manifest JSON path")
    parser.add_argument(
        "--workspace-root",
        default=".",
        help="repository root used to resolve the manifest output_root",
    )
    parser.add_argument(
        "--code-revision",
        required=True,
        help="full 40-character Git revision containing the runner",
    )
    parser.add_argument(
        "--precision",
        default=None,
        help="frozen precision JSON required for formal or confirmation execution",
    )
    parser.add_argument(
        "--calibration-evidence",
        default=None,
        help="audited calibration JSON required to replay the precision freeze",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="fail if any expected block artifact already exists",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="validate every launch gate and exit without writing or running blocks",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.preflight_only:
        result = preflight_synthetic_study(
            arguments.manifest,
            workspace_root=arguments.workspace_root,
            code_revision=arguments.code_revision,
            precision_path=arguments.precision,
            calibration_evidence_path=arguments.calibration_evidence,
        )
        print(
            json.dumps(
                result,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    summary_path = execute_synthetic_study(
        arguments.manifest,
        workspace_root=arguments.workspace_root,
        code_revision=arguments.code_revision,
        precision_path=arguments.precision,
        calibration_evidence_path=arguments.calibration_evidence,
        resume=not arguments.no_resume,
        progress=lambda message: print(message, flush=True),
    )
    print(summary_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "execute_synthetic_study",
    "main",
    "preflight_synthetic_study",
    "runtime_environment",
    "runtime_environment_fingerprint",
    "validate_frozen_execution_context",
]
