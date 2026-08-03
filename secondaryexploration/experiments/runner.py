"""Resumable exact execution of every synthetic study parent block."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
import platform
import sys
from time import perf_counter_ns

from secondaryexploration.topology import ParentGraphModel

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
    resume: bool = True,
    progress: ProgressCallback | None = None,
) -> Path:
    """Execute, exactly replay, checkpoint, and index every declared block."""

    manifest = load_study_design_manifest(manifest_path)
    validate_code_revision(code_revision)
    if (
        manifest.code_revision is not None
        and code_revision != manifest.code_revision
    ):
        raise StudyManifestError(
            "code_revision does not match the frozen study manifest"
        )
    ledger = build_study_seed_ledger(manifest)
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise StudyManifestError("workspace_root must be an existing directory")
    output_root = (root / manifest.output_root).resolve()
    try:
        output_root.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("manifest output_root escapes workspace_root") from exc
    block_root = output_root / "blocks"
    environment = runtime_environment()
    expected_count = len(ledger.parent_seeds) * len(_REGISTERED_PARENT_MODELS)
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


def runtime_environment() -> dict[str, object]:
    """Return the minimal exact runtime identity bound to resumable artifacts."""

    return {
        "python_implementation": sys.implementation.name,
        "python_version": platform.python_version(),
        "platform_system": platform.system() or "unknown",
        "machine": platform.machine() or "unknown",
    }


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
        "--no-resume",
        action="store_true",
        help="fail if any expected block artifact already exists",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    summary_path = execute_synthetic_study(
        arguments.manifest,
        workspace_root=arguments.workspace_root,
        code_revision=arguments.code_revision,
        resume=not arguments.no_resume,
        progress=lambda message: print(message, flush=True),
    )
    print(summary_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["execute_synthetic_study", "main", "runtime_environment"]
