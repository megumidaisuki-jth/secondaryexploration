"""Parent-stratified evidence for the second synthetic calibration pilot."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from secondaryexploration.experiments.artifacts import (
    atomic_write_json,
    load_study_run_summary,
    load_synthetic_block_artifact,
)
from secondaryexploration.experiments.study import (
    StudyDesignManifest,
    StudyManifestError,
    StudySeedLedger,
    TrafficRegimeRole,
    build_study_seed_ledger,
    load_study_design_manifest,
)

from .pilot import build_pilot_evidence, _trace_observation


CALIBRATION_EVIDENCE_SCHEMA_VERSION = "synthetic-calibration-evidence.v1"
_CALIBRATION_STUDY_ID = "synthetic-calibration-pilot-v1"
_CALIBRATION_MANIFEST_FINGERPRINT = (
    "cd15e32990c65b8737105f660e592525b2fc347ff7a51f2eb991e02ac023da89"
)
_PARENT_MODELS = ("barabasi_albert", "er_gnm", "sbm_fixed_count")
_SERVICE_METRICS = (
    "normalized_restricted_tau_nopath",
    "failure_risk",
    "success_rate",
    "accepted_value",
)
_DYNAMIC_COST_FIELDS = (
    "traversed_hyperedge_count",
    "signaled_participant_slots",
    "unique_signaled_participants",
    "quadratic_coordination_exposure",
)
_DISPERSION_METRICS = _SERVICE_METRICS + tuple(
    f"dynamic_cost_per_attempt.{field}" for field in _DYNAMIC_COST_FIELDS
) + tuple(
    f"dynamic_cost_per_accepted.{field}" for field in _DYNAMIC_COST_FIELDS
)
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "study_id",
    "status",
    "manifest_fingerprint",
    "seed_ledger_fingerprint",
    "run_summary_fingerprint",
    "base_pilot_evidence_fingerprint",
    "code_revision",
    "environment",
    "analysis_contract",
    "counts",
    "event_coverage",
    "parent_dispersion",
    "demand_aware_search",
    "runtime",
    "censoring_gate",
    "formal_precision_gate",
    "limitations",
    "evidence_fingerprint",
}
_ANALYSIS_CONTRACT = {
    "independent_unit": "parent_graph_within_node_count_and_parent_model",
    "binary_bracket_rule": "equal_mean_within_trace",
    "trace_rule": "equal_mean_by_scope_within_parent_graph",
    "dispersion_rule": "within_exact_size_model_family_scope_cell",
    "model_pooling": "forbidden",
    "inference_status": "calibration-planning-only",
}
_LIMITATIONS = (
    "three_parent_replicates_per_model_size_are_preliminary_not_powered",
    "traffic_regimes_are_nested_measurements_not_independent_parent_graphs",
    "no_confirmatory_intervals_hypothesis_tests_or_superiority_claims",
    "runtime_projection_repeats_observed_30_to_60_scaling_and_is_not_a_benchmark_guarantee",
)


def build_calibration_evidence(
    manifest: StudyDesignManifest,
    ledger: StudySeedLedger,
    run_summary: Mapping[str, object],
    block_artifacts: list[Mapping[str, object]],
) -> dict[str, object]:
    """Build exact planning evidence from a complete calibration run."""

    evidence = _build_calibration_evidence(
        manifest,
        ledger,
        run_summary,
        block_artifacts,
    )
    validate_calibration_evidence(evidence)
    return evidence


def _build_calibration_evidence(
    manifest: StudyDesignManifest,
    ledger: StudySeedLedger,
    run_summary: Mapping[str, object],
    block_artifacts: list[Mapping[str, object]],
) -> dict[str, object]:
    if not isinstance(manifest, StudyDesignManifest):
        raise StudyManifestError("calibration manifest is invalid")
    if not isinstance(ledger, StudySeedLedger):
        raise StudyManifestError("calibration seed ledger is invalid")
    _validate_frozen_calibration_inputs(manifest, block_artifacts)
    base = build_pilot_evidence(manifest, ledger, run_summary, block_artifacts)
    observations = _extract_observations(manifest, block_artifacts)
    parent_cells = _aggregate_parent_cells(observations)
    event_coverage = _event_coverage(observations)
    dispersion = _parent_dispersion(parent_cells)
    runtime = _runtime_evidence(block_artifacts)
    gate_rows = _censoring_gate(observations, manifest.lower_quantile)
    all_identified = all(
        row["all_parents_source_and_binary_lower_quantiles_identified"]
        for row in gate_rows
    )
    result: dict[str, object] = {
        "schema_version": CALIBRATION_EVIDENCE_SCHEMA_VERSION,
        "study_id": manifest.study_id,
        "status": "calibration-planning-only-not-formal-evidence",
        "manifest_fingerprint": manifest.fingerprint,
        "seed_ledger_fingerprint": ledger.fingerprint,
        "run_summary_fingerprint": run_summary["summary_fingerprint"],
        "base_pilot_evidence_fingerprint": base["evidence_fingerprint"],
        "code_revision": run_summary["code_revision"],
        "environment": dict(run_summary["environment"]),
        "analysis_contract": dict(_ANALYSIS_CONTRACT),
        "counts": {
            "block_count": len(block_artifacts),
            "parent_cell_count": len(parent_cells),
            "trace_contrast_count": len(observations),
            "dispersion_cell_count": len(dispersion),
        },
        "event_coverage": event_coverage,
        "parent_dispersion": dispersion,
        "demand_aware_search": base["demand_aware_search"],
        "runtime": runtime,
        "censoring_gate": {
            "registered_lower_quantile": _fraction_payload(manifest.lower_quantile),
            "cells": gate_rows,
            "all_cells_lower_quantile_identified": all_identified,
            "formal_endpoint_route": (
                "lower-quantile-eligible-subject-to-precision-freeze"
                if all_identified
                else "restricted-time-and-fixed-horizon-risk-primary"
            ),
        },
        "formal_precision_gate": {
            "status": "not-frozen",
            "smallest_effect_of_scientific_interest": "AUTHOR_INPUT_NEEDED",
            "target_simultaneous_interval_half_width": "AUTHOR_INPUT_NEEDED",
            "confidence_family": "AUTHOR_INPUT_NEEDED",
            "bootstrap_resamples": "AUTHOR_INPUT_NEEDED",
            "planned_parent_count_per_size_model": "AUTHOR_INPUT_NEEDED",
        },
        "limitations": list(_LIMITATIONS),
    }
    result["evidence_fingerprint"] = _mapping_fingerprint(result)
    return result


def validate_calibration_evidence(
    evidence: object,
    *,
    manifest: StudyDesignManifest | None = None,
    ledger: StudySeedLedger | None = None,
    run_summary: Mapping[str, object] | None = None,
    block_artifacts: list[Mapping[str, object]] | None = None,
) -> None:
    """Validate identity and optionally rebuild from all complete sources."""

    if not isinstance(evidence, Mapping) or set(evidence) != _TOP_LEVEL_FIELDS:
        raise StudyManifestError("calibration evidence top-level fields differ")
    if evidence["schema_version"] != CALIBRATION_EVIDENCE_SCHEMA_VERSION:
        raise StudyManifestError("unsupported calibration evidence schema")
    if evidence["study_id"] != _CALIBRATION_STUDY_ID:
        raise StudyManifestError("calibration evidence study id differs")
    if evidence["status"] != "calibration-planning-only-not-formal-evidence":
        raise StudyManifestError("calibration evidence cannot be relabelled as formal")
    if evidence["analysis_contract"] != _ANALYSIS_CONTRACT:
        raise StudyManifestError("calibration analysis contract differs")
    if evidence["limitations"] != list(_LIMITATIONS):
        raise StudyManifestError("calibration limitations differ")
    _validate_digest(evidence["evidence_fingerprint"], "evidence_fingerprint")
    content = dict(evidence)
    supplied = content.pop("evidence_fingerprint")
    if supplied != _mapping_fingerprint(content):
        raise StudyManifestError("calibration evidence fingerprint mismatch")
    contexts = (manifest, ledger, run_summary, block_artifacts)
    if any(value is not None for value in contexts):
        if any(value is None for value in contexts):
            raise StudyManifestError("all calibration replay sources are required")
        expected = _build_calibration_evidence(
            manifest,
            ledger,
            run_summary,
            block_artifacts,
        )
        if dict(evidence) != expected:
            raise StudyManifestError("calibration evidence source replay mismatch")


def _extract_observations(
    manifest: StudyDesignManifest,
    artifacts: list[Mapping[str, object]],
) -> list[dict[str, object]]:
    regimes = {
        item.regime_id: item
        for item in manifest.regimes
        if item.role is TrafficRegimeRole.TEST
    }
    observations: list[dict[str, object]] = []
    for artifact in artifacts:
        block = artifact["block"]
        parent_id = _parent_id(block)
        panels = artifact["resource_panels"]
        for held_out in artifact["held_out"]:
            regime_id = held_out["trace_seed"]["regime_id"]
            regime = regimes[regime_id]
            variants = {item["variant_id"]: item for item in held_out["variants"]}
            for panel in panels:
                source = variants[panel["source_variant_id"]]
                binary = [variants[item] for item in panel["binary_variant_ids"]]
                horizon = source["horizon"]
                if any(item["horizon"] != horizon for item in binary):
                    raise StudyManifestError("calibration panel horizons differ")
                observation = _trace_observation(
                    node_count=block["node_count"],
                    parent_graph_id=parent_id,
                    regime_id=regime_id,
                    scope=(
                        "same_distribution"
                        if regime.shift.value == "same_distribution"
                        else "distribution_shift"
                    ),
                    source_variant_id=panel["source_variant_id"],
                    binary_arm_count=len(binary),
                    horizon=horizon,
                    source=source,
                    binary=binary,
                )
                observation["parent_model"] = block["parent_model"]
                observation["parent_replicate"] = block["parent_replicate"]
                observation["binary_tau_nopath_observations"] = tuple(
                    (item["variant_id"], bool(item["tau_nopath"]["observed"]))
                    for item in binary
                )
                observations.append(observation)
    observations.sort(
        key=lambda item: (
            item["node_count"],
            item["parent_model"],
            item["parent_replicate"],
            item["source_variant_id"],
            item["scope"],
            item["regime_id"],
        )
    )
    return observations


def _aggregate_parent_cells(
    observations: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for item in observations:
        key = (
            item["node_count"],
            item["parent_model"],
            item["parent_replicate"],
            item["parent_graph_id"],
            item["source_variant_id"],
            item["scope"],
        )
        grouped[key].append(item)
    rows = []
    for key in sorted(grouped):
        items = grouped[key]
        values = {
            metric: _parent_metric_mean(items, metric) for metric in _DISPERSION_METRICS
        }
        rows.append(
            {
                "node_count": key[0],
                "parent_model": key[1],
                "parent_replicate": key[2],
                "parent_graph_id": key[3],
                "source_variant_id": key[4],
                "scope": key[5],
                "nested_trace_count": len(items),
                "values": values,
            }
        )
    return rows


def _parent_metric_mean(
    items: list[dict[str, object]],
    metric: str,
) -> Fraction | None:
    values = [_metric_difference(item, metric) for item in items]
    if any(value is None for value in values):
        return None
    return sum(values, Fraction(0)) / len(values)


def _metric_difference(item: Mapping[str, object], metric: str) -> Fraction | None:
    if metric in _SERVICE_METRICS:
        return item["metrics"][metric][2]
    section, field = metric.split(".", 1)
    value = item[section][field]
    return None if value is None else value[2]


def _event_coverage(
    observations: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for item in observations:
        grouped[
            (
                item["node_count"],
                item["parent_model"],
                item["source_variant_id"],
                item["scope"],
            )
        ].append(item)
    rows = []
    for key in sorted(grouped):
        items = grouped[key]
        source_events = sum(bool(item["source_tau_nopath_observed"]) for item in items)
        binary_equivalent = sum(
            (item["binary_tau_nopath_event_mean"] for item in items),
            Fraction(0),
        )
        binary_arm_count = sum(item["binary_arm_count"] for item in items)
        binary_event_count = sum(
            item["binary_tau_nopath_event_mean"] * item["binary_arm_count"]
            for item in items
        )
        if binary_event_count.denominator != 1:
            raise StudyManifestError("binary event arm count is not integral")
        rows.append(
            {
                "node_count": key[0],
                "parent_model": key[1],
                "source_variant_id": key[2],
                "scope": key[3],
                "parent_graph_count": len({item["parent_graph_id"] for item in items}),
                "nested_trace_count": len(items),
                "source_event_count": source_events,
                "source_censored_count": len(items) - source_events,
                "binary_arm_observation_count": binary_arm_count,
                "binary_event_arm_count": binary_event_count.numerator,
                "binary_event_equivalent": _fraction_payload(binary_equivalent),
            }
        )
    return rows


def _censoring_gate(
    observations: list[dict[str, object]],
    lower_quantile: Fraction,
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for item in observations:
        grouped[
            (
                item["node_count"],
                item["parent_model"],
                item["source_variant_id"],
                item["scope"],
            )
        ].append(item)
    cells = []
    for key in sorted(grouped):
        by_parent: dict[str, list[dict[str, object]]] = defaultdict(list)
        for item in grouped[key]:
            by_parent[item["parent_graph_id"]].append(item)
        parent_rows = []
        for parent_id in sorted(by_parent):
            items = by_parent[parent_id]
            trace_count = len(items)
            source_events = sum(
                bool(item["source_tau_nopath_observed"]) for item in items
            )
            source_fraction = Fraction(source_events, trace_count)
            binary_events: dict[str, int] = defaultdict(int)
            binary_counts: dict[str, int] = defaultdict(int)
            for item in items:
                for variant_id, observed in item["binary_tau_nopath_observations"]:
                    binary_counts[variant_id] += 1
                    binary_events[variant_id] += int(observed)
            if any(count != trace_count for count in binary_counts.values()):
                raise StudyManifestError(
                    "binary bracket arms differ across traces within a parent cell"
                )
            binary_rows = []
            for variant_id in sorted(binary_counts):
                fraction = Fraction(binary_events[variant_id], binary_counts[variant_id])
                binary_rows.append(
                    {
                        "variant_id": variant_id,
                        "event_count": binary_events[variant_id],
                        "trace_count": binary_counts[variant_id],
                        "event_fraction": _fraction_payload(fraction),
                        "lower_quantile_identified": fraction >= lower_quantile,
                    }
                )
            source_identified = source_fraction >= lower_quantile
            binary_identified = bool(binary_rows) and all(
                row["lower_quantile_identified"] for row in binary_rows
            )
            parent_rows.append(
                {
                    "parent_graph_id": parent_id,
                    "nested_trace_count": trace_count,
                    "source_event_count": source_events,
                    "source_event_fraction": _fraction_payload(source_fraction),
                    "source_lower_quantile_identified": source_identified,
                    "binary_arms": binary_rows,
                    "all_binary_lower_quantiles_identified": binary_identified,
                    "source_and_binary_lower_quantiles_identified": (
                        source_identified and binary_identified
                    ),
                }
            )
        cells.append(
            {
                "node_count": key[0],
                "parent_model": key[1],
                "source_variant_id": key[2],
                "scope": key[3],
                "parent_graph_count": len(parent_rows),
                "parents": parent_rows,
                "all_parents_source_and_binary_lower_quantiles_identified": all(
                    row["source_and_binary_lower_quantiles_identified"]
                    for row in parent_rows
                ),
            }
        )
    return cells


def _parent_dispersion(parent_cells: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in parent_cells:
        grouped[
            (
                row["node_count"],
                row["parent_model"],
                row["source_variant_id"],
                row["scope"],
            )
        ].append(row)
    result = []
    for key in sorted(grouped):
        parents = sorted(grouped[key], key=lambda item: item["parent_graph_id"])
        metrics = {}
        for metric in _DISPERSION_METRICS:
            defined = [
                (item["parent_graph_id"], item["values"][metric])
                for item in parents
                if item["values"][metric] is not None
            ]
            values = [value for _, value in defined]
            mean = None if not values else sum(values, Fraction(0)) / len(values)
            variance = None
            if len(values) >= 2:
                variance = sum((value - mean) ** 2 for value in values) / (
                    len(values) - 1
                )
            metrics[metric] = {
                "defined_parent_count": len(values),
                "parent_values": [
                    {"parent_graph_id": parent_id, "value": _fraction_payload(value)}
                    for parent_id, value in defined
                ],
                "mean": None if mean is None else _fraction_payload(mean),
                "sample_variance": (
                    None if variance is None else _fraction_payload(variance)
                ),
                "minimum": None if not values else _fraction_payload(min(values)),
                "maximum": None if not values else _fraction_payload(max(values)),
            }
        result.append(
            {
                "node_count": key[0],
                "parent_model": key[1],
                "source_variant_id": key[2],
                "scope": key[3],
                "parent_graph_count": len(parents),
                "metrics": metrics,
            }
        )
    return result


def _runtime_evidence(
    artifacts: list[Mapping[str, object]],
) -> dict[str, object]:
    grouped: dict[tuple[int, str], list[tuple[int, int]]] = defaultdict(list)
    blocks = []
    for artifact in artifacts:
        block = artifact["block"]
        generation = artifact["timing_ns"]["generation"]
        validation = artifact["timing_ns"]["exact_validation"]
        grouped[(block["node_count"], block["parent_model"])].append(
            (generation, validation)
        )
        blocks.append(
            {
                "parent_graph_id": _parent_id(block),
                "generation_ns": generation,
                "validation_ns": validation,
                "total_ns": generation + validation,
            }
        )
    medians = {}
    cells = []
    for key in sorted(grouped):
        values = grouped[key]
        if len(values) != 3:
            raise StudyManifestError(
                "runtime evidence requires three blocks per size/model cell"
            )
        generation = _integer_median([item[0] for item in values])
        validation = _integer_median([item[1] for item in values])
        total = _integer_median([sum(item) for item in values])
        medians[key] = total
        cells.append(
            {
                "node_count": key[0],
                "parent_model": key[1],
                "block_count": len(values),
                "median_generation_ns": generation,
                "median_validation_ns": validation,
                "median_total_ns": total,
            }
        )
    projections = []
    for model in sorted({key[1] for key in medians}):
        if (30, model) not in medians or (60, model) not in medians:
            raise StudyManifestError("runtime projection requires sizes 30 and 60")
        ratio = Fraction(medians[(60, model)], medians[(30, model)])
        for node_count, powers in ((120, 1), (240, 2)):
            projected_ns = Fraction(medians[(60, model)], 1) * ratio**powers
            projections.append(
                {
                    "node_count": node_count,
                    "parent_model": model,
                    "observed_doubling_ratio": _fraction_payload(ratio),
                    "projected_total_seconds_per_block_ceiling": _ceil_fraction(
                        projected_ns / 1_000_000_000
                    ),
                }
            )
    return {
        "projection_rule": "repeat-model-specific-observed-30-to-60-median-total-ratio",
        "blocks": sorted(blocks, key=lambda item: item["parent_graph_id"]),
        "observed_cells": cells,
        "projected_cells": projections,
    }


def _validate_frozen_calibration_inputs(
    manifest: StudyDesignManifest,
    artifacts: list[Mapping[str, object]],
) -> None:
    if manifest.study_id != _CALIBRATION_STUDY_ID:
        raise StudyManifestError("calibration evidence requires the frozen study id")
    if manifest.fingerprint != _CALIBRATION_MANIFEST_FINGERPRINT:
        raise StudyManifestError("calibration manifest fingerprint is not frozen v1")
    if manifest.parent_replicates != 3 or tuple(
        cell.node_count for cell in manifest.size_cells
    ) != (30, 60):
        raise StudyManifestError("calibration design is not the frozen 30/60 contract")
    expected = tuple(
        sorted(
            f"n{node_count:04d}-r{replicate:04d}-{model}"
            for node_count in (30, 60)
            for replicate in range(3)
            for model in _PARENT_MODELS
        )
    )
    observed = tuple(sorted(_parent_id(artifact["block"]) for artifact in artifacts))
    if observed != expected:
        raise StudyManifestError("calibration evidence requires the exact frozen 18 blocks")


def generate_calibration_evidence(
    manifest_path: str | Path,
    *,
    workspace_root: str | Path,
    summary_path: str | Path | None = None,
    output_path: str | Path,
) -> Path:
    """Load all exact artifacts and atomically write calibration evidence."""

    manifest = load_study_design_manifest(manifest_path)
    ledger = build_study_seed_ledger(manifest)
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise StudyManifestError("workspace_root must be an existing directory")
    resolved_summary = (
        (root / manifest.output_root / "run-summary.json").resolve()
        if summary_path is None
        else Path(summary_path).resolve()
    )
    try:
        resolved_summary.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("summary_path escapes workspace_root") from exc
    run_summary = load_study_run_summary(
        resolved_summary,
        manifest=manifest,
        ledger=ledger,
    )
    if run_summary["status"] != "complete":
        raise StudyManifestError(
            "calibration evidence requires a complete 18-block run summary"
        )
    artifacts = []
    parent_seeds = {
        (item.node_count, item.parent_replicate): item for item in ledger.parent_seeds
    }
    for record in run_summary["blocks"]:
        artifact_path = (resolved_summary.parent / record["path"]).resolve()
        try:
            artifact_path.relative_to(resolved_summary.parent)
        except ValueError as exc:
            raise StudyManifestError("summary block path escapes output root") from exc
        parts = record["block_key"].split("-", 2)
        node_count = int(parts[0][1:])
        parent_replicate = int(parts[1][1:])
        parent_model = parts[2]
        try:
            parent_seed = parent_seeds[(node_count, parent_replicate)]
        except KeyError as exc:
            raise StudyManifestError("summary block is absent from the seed ledger") from exc
        artifacts.append(
            load_synthetic_block_artifact(
                artifact_path,
                manifest=manifest,
                ledger=ledger,
                parent_seed=parent_seed,
                parent_model=parent_model,
                code_revision=run_summary["code_revision"],
                environment=run_summary["environment"],
            )
        )
    evidence = build_calibration_evidence(manifest, ledger, run_summary, artifacts)
    validate_calibration_evidence(
        evidence,
        manifest=manifest,
        ledger=ledger,
        run_summary=run_summary,
        block_artifacts=artifacts,
    )
    target = Path(output_path)
    if not target.is_absolute():
        target = (root / target).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("output_path escapes workspace_root") from exc
    atomic_write_json(target, evidence)
    return target


def load_calibration_evidence(
    path: str | Path,
    *,
    manifest: StudyDesignManifest,
    ledger: StudySeedLedger,
    run_summary: Mapping[str, object],
    block_artifacts: list[Mapping[str, object]],
) -> dict[str, object]:
    """Load strict JSON and fully replay calibration evidence."""

    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except StudyManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StudyManifestError(f"cannot load calibration evidence: {path}") from exc
    validate_calibration_evidence(
        raw,
        manifest=manifest,
        ledger=ledger,
        run_summary=run_summary,
        block_artifacts=block_artifacts,
    )
    return dict(raw)


def _parent_id(block: Mapping[str, object]) -> str:
    return (
        f"n{block['node_count']:04d}-r{block['parent_replicate']:04d}-"
        f"{block['parent_model']}"
    )


def _integer_median(values: list[int]) -> int:
    if not values or any(type(value) is not int or value < 0 for value in values):
        raise StudyManifestError("runtime values must be nonnegative integers")
    ordered = sorted(values)
    if len(ordered) % 2:
        return ordered[len(ordered) // 2]
    return (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) // 2


def _ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def _fraction_payload(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _mapping_fingerprint(mapping: Mapping[str, object]) -> str:
    payload = json.dumps(
        mapping,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_digest(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError(f"{label} must be lowercase SHA-256 hexadecimal")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise StudyManifestError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise StudyManifestError(f"non-finite JSON constant {value!r} is not allowed")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build exact parent-stratified calibration evidence"
    )
    parser.add_argument("manifest")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--summary", default=None)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    target = generate_calibration_evidence(
        args.manifest,
        workspace_root=args.workspace_root,
        summary_path=args.summary,
        output_path=args.output,
    )
    print(target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CALIBRATION_EVIDENCE_SCHEMA_VERSION",
    "build_calibration_evidence",
    "generate_calibration_evidence",
    "load_calibration_evidence",
    "validate_calibration_evidence",
]
