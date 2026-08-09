"""Generate formal and confirmation manifests from the frozen precision plan."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from secondaryexploration.experiments.artifacts import atomic_write_json
from secondaryexploration.experiments.runner import (
    runtime_environment,
    runtime_environment_fingerprint,
    validate_frozen_execution_context,
)
from secondaryexploration.experiments.study import (
    StudyDesignManifest,
    StudyManifestError,
    StudyPhase,
    SyntheticSizeCell,
    load_study_design_manifest,
)

from .precision import (
    load_audited_calibration_evidence,
    load_formal_precision_evidence,
    validate_formal_precision_evidence,
)


_CALIBRATION_MANIFEST_FINGERPRINT = (
    "cd15e32990c65b8737105f660e592525b2fc347ff7a51f2eb991e02ac023da89"
)
_FORMAL_PRECISION_FINGERPRINT = (
    "c2083ff1762ec7407412e702f99bf2c58ef244e4702accc90553112fb876a2d1"
)
_SIZE_CELLS = (
    SyntheticSizeCell(30, 3, 4, 60),
    SyntheticSizeCell(60, 3, 4, 128),
    SyntheticSizeCell(120, 3, 4, 263),
    SyntheticSizeCell(240, 3, 4, 533),
)


def build_frozen_phase_manifest(
    calibration_manifest: StudyDesignManifest,
    precision_evidence: Mapping[str, object],
    *,
    phase: StudyPhase,
    code_revision: str,
    environment: Mapping[str, object],
) -> StudyDesignManifest:
    """Build one non-pilot manifest and validate it against the precision freeze."""

    if not isinstance(calibration_manifest, StudyDesignManifest):
        raise StudyManifestError("calibration manifest is malformed")
    if calibration_manifest.fingerprint != _CALIBRATION_MANIFEST_FINGERPRINT:
        raise StudyManifestError("formal freeze requires the audited calibration manifest")
    if phase not in (StudyPhase.FORMAL, StudyPhase.CONFIRMATION):
        raise StudyManifestError("phase must be formal or confirmation")
    if not isinstance(precision_evidence, Mapping):
        raise StudyManifestError("precision evidence is malformed")
    validate_formal_precision_evidence(precision_evidence)
    if precision_evidence["precision_fingerprint"] != _FORMAL_PRECISION_FINGERPRINT:
        raise StudyManifestError("formal freeze requires the audited precision artifact")
    seeds = precision_evidence.get("execution_seed_families")
    if not isinstance(seeds, Mapping):
        raise StudyManifestError("precision seed families are malformed")
    if phase is StudyPhase.FORMAL:
        study_id = "synthetic-formal-v1"
        base_seed = seeds.get("formal_base_seed")
        output_root = "outputs/formal/synthetic-formal-v1"
    else:
        study_id = "synthetic-confirmation-v1"
        base_seed = seeds.get("confirmation_base_seed")
        output_root = "outputs/confirmation/synthetic-confirmation-v1"
    counts = precision_evidence.get("planned_parent_count_per_size_model")
    if not isinstance(counts, list) or not counts:
        raise StudyManifestError("precision parent counts are malformed")
    count_field = (
        "formal_parent_count"
        if phase is StudyPhase.FORMAL
        else "confirmation_parent_count"
    )
    planned_counts = {item.get(count_field) for item in counts if isinstance(item, Mapping)}
    if len(planned_counts) != 1:
        raise StudyManifestError("precision parent counts are not uniform")
    parent_replicates = next(iter(planned_counts))
    manifest = replace(
        calibration_manifest,
        study_id=study_id,
        phase=phase,
        base_seed=base_seed,
        output_root=output_root,
        basis_fingerprint=precision_evidence.get("precision_fingerprint"),
        code_revision=code_revision,
        environment_fingerprint=runtime_environment_fingerprint(environment),
        size_cells=_SIZE_CELLS,
        parent_replicates=parent_replicates,
    )
    validate_frozen_execution_context(
        manifest,
        code_revision=code_revision,
        environment=environment,
        precision_evidence=precision_evidence,
        calibration_manifest=calibration_manifest,
    )
    return manifest


def generate_frozen_phase_manifest(
    calibration_manifest_path: str | Path,
    calibration_evidence_path: str | Path,
    precision_path: str | Path,
    *,
    phase: StudyPhase,
    code_revision: str,
    workspace_root: str | Path,
    output_path: str | Path,
) -> Path:
    """Strictly replay all freeze sources before atomically writing a manifest."""

    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise StudyManifestError("workspace_root must be an existing directory")
    calibration_manifest = load_study_design_manifest(
        _resolve_read_path(root, calibration_manifest_path, "calibration_manifest_path")
    )
    calibration = load_audited_calibration_evidence(
        _resolve_read_path(root, calibration_evidence_path, "calibration_evidence_path")
    )
    precision = load_formal_precision_evidence(
        _resolve_read_path(root, precision_path, "precision_path"),
        calibration_evidence=calibration,
    )
    manifest = build_frozen_phase_manifest(
        calibration_manifest,
        precision,
        phase=phase,
        code_revision=code_revision,
        environment=runtime_environment(),
    )
    target = Path(output_path)
    if not target.is_absolute():
        target = (root / target).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("output_path escapes workspace_root") from exc
    atomic_write_json(target, manifest.to_canonical_mapping())
    return target


def _resolve_read_path(root: Path, value: str | Path, label: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError(f"{label} escapes workspace_root") from exc
    return resolved


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze a formal study phase manifest")
    parser.add_argument("calibration_manifest")
    parser.add_argument("calibration_evidence")
    parser.add_argument("precision")
    parser.add_argument("--phase", choices=("formal", "confirmation"), required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    target = generate_frozen_phase_manifest(
        args.calibration_manifest,
        args.calibration_evidence,
        args.precision,
        phase=StudyPhase(args.phase),
        code_revision=args.code_revision,
        workspace_root=args.workspace_root,
        output_path=args.output,
    )
    print(target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_frozen_phase_manifest", "generate_frozen_phase_manifest"]
