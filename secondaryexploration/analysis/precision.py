"""Frozen formal-precision evidence derived from the audited calibration."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from secondaryexploration.experiments.artifacts import atomic_write_json
from secondaryexploration.experiments.study import StudyManifestError

from .calibration import validate_calibration_evidence


FORMAL_PRECISION_SCHEMA_VERSION = "formal-precision-freeze.v1"
_CALIBRATION_EVIDENCE_FINGERPRINT = (
    "7c5c8bc98939b5b9f3fa602b3b3f3986fd531004c06b1cb8277d6b52d653c0ff"
)
_PARENT_MODELS = ("barabasi_albert", "er_gnm", "sbm_fixed_count")
_TOPOLOGY_FAMILIES = ("demand-aware", "fhs3", "fhs5", "nch")
_PRIMARY_SIZES = (30, 60, 120, 240)
_CALIBRATION_SIZES = (30, 60)
_ENDPOINTS = (
    ("failure_risk", "negative"),
    ("normalized_restricted_tau_nopath", "positive"),
)
_STUDYWISE_CONFIDENCE = Fraction(19, 20)
_LOCAL_FAMILY_CONFIDENCE = Fraction(159, 160)
_BONFERRONI_TAIL = Fraction(1, 1600)
_NORMAL_CRITICAL_HEX = "0x1.9d157e4e47baap+1"
_BOOTSTRAP_ROOT_SEED = 2026081003
_BOOTSTRAP_RESAMPLES = 20_000
_PLANNED_PARENTS = 20
_FORMAL_BASE_SEED = 2026081001
_CONFIRMATION_BASE_SEED = 2026081002
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "status",
    "calibration_evidence_fingerprint",
    "decision",
    "analysis_contract",
    "confirmatory_families",
    "precision_targets",
    "bootstrap",
    "execution_seed_families",
    "planning_method",
    "planning_cells",
    "planned_parent_count_per_size_model",
    "runtime_allocation",
    "limitations",
    "precision_fingerprint",
}


def build_formal_precision_evidence(
    calibration_evidence: Mapping[str, object],
) -> dict[str, object]:
    """Build recommended-A precision evidence from the exact audited pilot."""

    evidence = _build_formal_precision_evidence(calibration_evidence)
    validate_formal_precision_evidence(evidence)
    return evidence


def _build_formal_precision_evidence(
    calibration_evidence: Mapping[str, object],
) -> dict[str, object]:
    _validate_calibration_source(calibration_evidence)
    confirmatory_families = _confirmatory_families()
    planning_cells = _planning_cells(calibration_evidence)
    maximum_global = max(
        item["required_parents_per_model"]
        for item in planning_cells
        if item["tier"] == "global"
    )
    maximum_secondary = max(
        item["required_parents_per_model"]
        for item in planning_cells
        if item["tier"] == "secondary"
    )
    if maximum_global != 19 or maximum_secondary != 12:
        raise StudyManifestError("calibration no longer replays recommended-A counts")
    if _PLANNED_PARENTS < max(maximum_global, maximum_secondary):
        raise StudyManifestError("planned parent count is below the precision envelope")
    runtime = _runtime_allocation(calibration_evidence)
    result: dict[str, object] = {
        "schema_version": FORMAL_PRECISION_SCHEMA_VERSION,
        "status": "frozen-before-formal-outcomes",
        "calibration_evidence_fingerprint": _CALIBRATION_EVIDENCE_FINGERPRINT,
        "decision": {
            "selection": "recommended-a",
            "selection_rule": "user-authorized-one-minute-default",
            "decision_date": "2026-08-09",
        },
        "analysis_contract": {
            "independent_unit": "parent_graph_within_node_count_and_parent_model",
            "nested_measurement": "traffic_trace",
            "trace_aggregation": "equal_trace_mean_within_parent",
            "traffic_scope_weights": {
                "same_distribution": 4,
                "distribution_shift": 3,
            },
            "model_aggregation": "equal_weight_across_three_named_strata",
            "parent_pooling_across_models": "forbidden",
            "size_pooling": "forbidden",
            "binary_bracket_rule": "equal_mean_within_trace",
        },
        "confirmatory_families": confirmatory_families,
        "precision_targets": {
            "smallest_effect_of_scientific_interest": [
                {
                    "metric": metric,
                    "reported_units": (
                        "absolute_probability_difference"
                        if metric == "failure_risk"
                        else "fraction_of_registered_horizon"
                    ),
                    "value": [1, 10],
                    "beneficial_direction": direction,
                }
                for metric, direction in _ENDPOINTS
            ],
            "simultaneous_interval_half_width": {
                "global": [1, 20],
                "secondary": [1, 10],
            },
            "endpoint_horizon": {
                "requests_per_node": 12,
                "horizon_rule": "node_count-times-requests_per_node",
                "administrative_censoring_retained": True,
            },
            "lower_tau_nopath_quantile": "exploratory-censored-not-confirmatory",
        },
        "bootstrap": {
            "root_seed": _BOOTSTRAP_ROOT_SEED,
            "resamples": _BOOTSTRAP_RESAMPLES,
            "studywise_confidence_level": _fraction_payload(_STUDYWISE_CONFIDENCE),
            "local_hierarchy_count": len(confirmatory_families),
            "local_hierarchy_confidence_level": _fraction_payload(
                _LOCAL_FAMILY_CONFIDENCE
            ),
            "confirmatory_contrast_count": sum(
                len(item["registrations"]) for item in confirmatory_families
            ),
            "bonferroni_tail_probability": _fraction_payload(_BONFERRONI_TAIL),
            "expected_resamples_in_each_adjusted_tail": _fraction_payload(
                _BOOTSTRAP_RESAMPLES * _BONFERRONI_TAIL
            ),
        },
        "execution_seed_families": {
            "formal_base_seed": _FORMAL_BASE_SEED,
            "confirmation_base_seed": _CONFIRMATION_BASE_SEED,
            "bootstrap_root_seed": _BOOTSTRAP_ROOT_SEED,
            "all_three_roots_distinct": len(
                {_FORMAL_BASE_SEED, _CONFIRMATION_BASE_SEED, _BOOTSTRAP_ROOT_SEED}
            )
            == 3,
        },
        "planning_method": {
            "status": "normal-approximation-for-sample-size-planning-only",
            "normal_critical_value_hex": _NORMAL_CRITICAL_HEX,
            "variance_rule": (
                "sum-model-sample-variances-divided-by-nine-for-one-parent-per-stratum"
            ),
            "required_count_rule": "ceiling(z_squared_times_variance_coefficient_over_half_width_squared)",
            "calibration_sizes": list(_CALIBRATION_SIZES),
            "extension_rule": (
                "maximum-required-count-over-all-30-and-60-calibration-cells-applied-to-all-primary-sizes"
            ),
            "maximum_raw_required_global": maximum_global,
            "maximum_raw_required_secondary": maximum_secondary,
            "rounding_rule": "round-up-to-20-parents-per-model-size",
        },
        "planning_cells": planning_cells,
        "planned_parent_count_per_size_model": [
            {
                "node_count": node_count,
                "parent_model": model,
                "formal_parent_count": _PLANNED_PARENTS,
                "confirmation_parent_count": _PLANNED_PARENTS,
            }
            for node_count in _PRIMARY_SIZES
            for model in _PARENT_MODELS
        ],
        "runtime_allocation": runtime,
        "limitations": [
            "calibration-variance-estimates-use-only-three-parents-per-exact-cell",
            "sizes-120-and-240-use-a-conservative-extension-from-30-and-60-not-direct-variance-estimates",
            "normal-approximation-counts-are-planning-inputs-not-achieved-power-or-finite-sample-coverage",
            "formal-inference-remains-the-registered-stratified-parent-bootstrap",
            "runtime-values-for-120-and-240-are-extrapolated-budget-ceilings-not-performance-guarantees",
            "demand-aware-topology-was-unchanged-in-ten-of-eighteen-calibration-blocks-and-requires-activity-sensitivity-reporting",
        ],
    }
    result["precision_fingerprint"] = _mapping_fingerprint(result)
    return result


def validate_formal_precision_evidence(
    evidence: object,
    *,
    calibration_evidence: Mapping[str, object] | None = None,
) -> None:
    """Validate the artifact, optionally rebuilding it from calibration evidence."""

    if not isinstance(evidence, Mapping) or set(evidence) != _TOP_LEVEL_FIELDS:
        raise StudyManifestError("formal precision top-level fields differ")
    if evidence["schema_version"] != FORMAL_PRECISION_SCHEMA_VERSION:
        raise StudyManifestError("unsupported formal precision schema")
    if evidence["status"] != "frozen-before-formal-outcomes":
        raise StudyManifestError("formal precision evidence status differs")
    _validate_digest(evidence["precision_fingerprint"], "precision_fingerprint")
    content = dict(evidence)
    supplied = content.pop("precision_fingerprint")
    if supplied != _mapping_fingerprint(content):
        raise StudyManifestError("formal precision fingerprint mismatch")
    if calibration_evidence is not None:
        expected = _build_formal_precision_evidence(calibration_evidence)
        if dict(evidence) != expected:
            raise StudyManifestError("formal precision calibration replay mismatch")


def load_formal_precision_evidence(
    path: str | Path,
    *,
    calibration_evidence: Mapping[str, object],
) -> dict[str, object]:
    """Strictly load and replay a formal precision artifact."""

    raw = _load_strict_json(path, "formal precision evidence")
    validate_formal_precision_evidence(raw, calibration_evidence=calibration_evidence)
    return raw


def load_audited_calibration_evidence(path: str | Path) -> dict[str, object]:
    """Strictly load the one audited calibration accepted by this freeze."""

    raw = _load_strict_json(path, "calibration evidence")
    _validate_calibration_source(raw)
    return raw


def generate_formal_precision_evidence(
    calibration_path: str | Path,
    *,
    workspace_root: str | Path,
    output_path: str | Path,
) -> Path:
    """Write the frozen precision artifact only after exact source replay."""

    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise StudyManifestError("workspace_root must be an existing directory")
    calibration = _load_strict_json(calibration_path, "calibration evidence")
    _validate_calibration_source(calibration)
    evidence = build_formal_precision_evidence(calibration)
    target = Path(output_path)
    if not target.is_absolute():
        target = (root / target).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("output_path escapes workspace_root") from exc
    atomic_write_json(target, evidence)
    return target


def _confirmatory_families() -> list[dict[str, object]]:
    result = []
    for metric, direction in _ENDPOINTS:
        for node_count in _PRIMARY_SIZES:
            family_id = f"{metric}.n{node_count:04d}"
            registrations = [
                {
                    "contrast_id": f"{family_id}.global",
                    "tier": "global",
                    "source_family": "equal-mean-of-four-topology-families",
                    "beneficial_direction": direction,
                }
            ]
            registrations.extend(
                {
                    "contrast_id": f"{family_id}.{source_family}",
                    "tier": "secondary",
                    "source_family": source_family,
                    "beneficial_direction": direction,
                }
                for source_family in _TOPOLOGY_FAMILIES
            )
            result.append(
                {
                    "family_id": family_id,
                    "metric": metric,
                    "node_count": node_count,
                    "registrations": registrations,
                }
            )
    return result


def _planning_cells(calibration: Mapping[str, object]) -> list[dict[str, object]]:
    values = _parent_values(calibration)
    z = Fraction.from_float(float.fromhex(_NORMAL_CRITICAL_HEX))
    result = []
    for node_count in _CALIBRATION_SIZES:
        for metric, _ in _ENDPOINTS:
            for source_family in ("global",) + _TOPOLOGY_FAMILIES:
                stratum_variances = []
                for model in _PARENT_MODELS:
                    parent_ids = sorted(
                        {
                            key[5]
                            for key in values
                            if key[0] == node_count
                            and key[1] == model
                            and key[4] == metric
                        }
                    )
                    if len(parent_ids) != 3:
                        raise StudyManifestError("planning cells require three parents")
                    parent_values = []
                    for parent_id in parent_ids:
                        families = (
                            _TOPOLOGY_FAMILIES
                            if source_family == "global"
                            else (source_family,)
                        )
                        family_values = []
                        for family in families:
                            same = values[
                                (
                                    node_count,
                                    model,
                                    family,
                                    "same_distribution",
                                    metric,
                                    parent_id,
                                )
                            ]
                            shifted = values[
                                (
                                    node_count,
                                    model,
                                    family,
                                    "distribution_shift",
                                    metric,
                                    parent_id,
                                )
                            ]
                            family_values.append((4 * same + 3 * shifted) / 7)
                        parent_values.append(
                            sum(family_values, Fraction(0)) / len(family_values)
                        )
                    mean = sum(parent_values, Fraction(0)) / len(parent_values)
                    variance = sum((item - mean) ** 2 for item in parent_values) / 2
                    stratum_variances.append(
                        {
                            "parent_model": model,
                            "sample_variance": _fraction_payload(variance),
                        }
                    )
                coefficient = sum(
                    (_fraction(item["sample_variance"]) for item in stratum_variances),
                    Fraction(0),
                ) / 9
                tier = "global" if source_family == "global" else "secondary"
                half_width = Fraction(1, 20) if tier == "global" else Fraction(1, 10)
                required = _ceil_fraction(z**2 * coefficient / half_width**2)
                result.append(
                    {
                        "node_count": node_count,
                        "metric": metric,
                        "tier": tier,
                        "source_family": source_family,
                        "target_half_width": _fraction_payload(half_width),
                        "stratum_variances": stratum_variances,
                        "equal_stratum_variance_coefficient": _fraction_payload(
                            coefficient
                        ),
                        "required_parents_per_model": required,
                    }
                )
    return result


def _parent_values(
    calibration: Mapping[str, object],
) -> dict[tuple[object, ...], Fraction]:
    result = {}
    for row in calibration["parent_dispersion"]:
        for metric, _ in _ENDPOINTS:
            for item in row["metrics"][metric]["parent_values"]:
                key = (
                    row["node_count"],
                    row["parent_model"],
                    row["source_variant_id"],
                    row["scope"],
                    metric,
                    item["parent_graph_id"],
                )
                if key in result:
                    raise StudyManifestError("duplicate parent planning value")
                result[key] = _fraction(item["value"])
    return result


def _runtime_allocation(calibration: Mapping[str, object]) -> dict[str, object]:
    observed_ns = sum(
        item["median_total_ns"] for item in calibration["runtime"]["observed_cells"]
    )
    projected_seconds = sum(
        item["projected_total_seconds_per_block_ceiling"]
        for item in calibration["runtime"]["projected_cells"]
    )
    per_replicate = Fraction(observed_ns, 1_000_000_000) + projected_seconds
    per_phase = per_replicate * _PLANNED_PARENTS
    combined = per_phase * 2
    return {
        "block_count_per_phase": (
            len(_PRIMARY_SIZES) * len(_PARENT_MODELS) * _PLANNED_PARENTS
        ),
        "formal_and_confirmation_use_disjoint_seed_families": True,
        "estimated_sequential_seconds_per_one-parent-across-all-cells": _fraction_payload(
            per_replicate
        ),
        "formal_estimated_sequential_seconds_ceiling": _ceil_fraction(per_phase),
        "confirmation_estimated_sequential_seconds_ceiling": _ceil_fraction(per_phase),
        "combined_estimated_sequential_seconds_ceiling": _ceil_fraction(combined),
        "launch_gate": "profile-and-verify-parallel-resource-envelope-before-formal-execution",
    }


def _validate_calibration_source(calibration: Mapping[str, object]) -> None:
    validate_calibration_evidence(calibration)
    if calibration["evidence_fingerprint"] != _CALIBRATION_EVIDENCE_FINGERPRINT:
        raise StudyManifestError("formal precision requires the audited calibration")
    if calibration["censoring_gate"]["formal_endpoint_route"] != (
        "restricted-time-and-fixed-horizon-risk-primary"
    ):
        raise StudyManifestError("calibration endpoint route differs")


def _load_strict_json(path: str | Path, label: str) -> dict[str, object]:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except StudyManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StudyManifestError(f"cannot load {label}: {path}") from exc
    if not isinstance(raw, dict):
        raise StudyManifestError(f"{label} must be a JSON object")
    return raw


def _fraction(value: object) -> Fraction:
    if (
        type(value) is not list
        or len(value) != 2
        or any(type(item) is not int for item in value)
        or value[1] <= 0
    ):
        raise StudyManifestError("fraction payload is malformed")
    return Fraction(value[0], value[1])


def _fraction_payload(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


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
    parser = argparse.ArgumentParser(description="Freeze formal precision evidence")
    parser.add_argument("calibration")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    target = generate_formal_precision_evidence(
        args.calibration,
        workspace_root=args.workspace_root,
        output_path=args.output,
    )
    print(target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FORMAL_PRECISION_SCHEMA_VERSION",
    "build_formal_precision_evidence",
    "generate_formal_precision_evidence",
    "load_audited_calibration_evidence",
    "load_formal_precision_evidence",
    "validate_formal_precision_evidence",
]
