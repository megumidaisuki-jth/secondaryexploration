"""Build strict phase and cross-phase inference evidence after finalization.

This tool is intentionally outside ``secondaryexploration`` so freezing the
analysis route cannot alter the already-running simulation-code snapshot.
It accepts only complete, strictly replayed formal or confirmation sources.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction
import hashlib
import json
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
    StudyPhase,
    build_study_seed_ledger,
    load_study_design_manifest,
)
from secondaryexploration.experiments.artifacts import (
    STUDY_RUN_SUMMARY_SCHEMA_VERSION,
    atomic_write_json,
    load_study_run_summary,
    load_synthetic_block_artifact,
    validate_study_run_summary,
)
from secondaryexploration.experiments.runner import (
    runtime_environment,
    validate_frozen_execution_context,
)
from secondaryexploration.metrics import (
    BeneficialDirection,
    BlockContrastObservation,
    BootstrapPlan,
    ConfirmatoryHierarchy,
    ContrastMetric,
    ContrastRegistration,
    InferenceTier,
    StratifiedContrastSample,
    StratumContrastSample,
    apply_stratified_confirmatory_hierarchy,
    empirical_quantile,
    hierarchical_contrast_sample,
    stratified_hierarchical_percentile_intervals,
)


PHASE_EVIDENCE_SCHEMA = "formal-phase-inference-evidence.v1"
REPLICATION_EVIDENCE_SCHEMA = "formal-replication-evidence.v1"
_STATUS = "complete-strict-replay"
_MODELS = ("barabasi_albert", "er_gnm", "sbm_fixed_count")
_SOURCES = ("demand-aware", "fhs3", "fhs5", "nch")
_METRICS = (
    "failure_risk",
    "normalized_restricted_tau_nopath",
)
_PHASE_FIELDS = {
    "schema_version",
    "status",
    "phase",
    "study_id",
    "source_fingerprints",
    "analysis_revision",
    "analysis_contract",
    "block_registry",
    "trace_contrasts",
    "parent_contrasts",
    "hierarchies",
    "event_coverage",
    "activity_sensitivity",
    "limitations",
    "evidence_fingerprint",
}
_REPLICATION_FIELDS = {
    "schema_version",
    "status",
    "formal_evidence_fingerprint",
    "confirmation_evidence_fingerprint",
    "analysis_revision",
    "contrast_results",
    "limitations",
    "replication_fingerprint",
}
_TRACE_FIELDS = {
    "node_count",
    "parent_model",
    "parent_replicate",
    "parent_graph_id",
    "regime_id",
    "scope",
    "paired_manifest_fingerprint",
    "source_family",
    "metric",
    "horizon",
    "binary_arm_count",
    "binary_arm_events",
    "source_event",
    "value",
}
_PARENT_FIELDS = {
    "node_count",
    "parent_model",
    "parent_replicate",
    "parent_graph_id",
    "source_family",
    "metric",
    "horizon",
    "same_distribution_trace_count",
    "same_distribution_mean",
    "distribution_shift_trace_count",
    "distribution_shift_mean",
    "scope_weights",
    "combined_parent_value",
}
_INTERVAL_FIELDS = {
    "contrast_id",
    "metric",
    "node_count",
    "tier",
    "beneficial_direction",
    "estimate",
    "lower",
    "upper",
    "confidence_level",
    "tail_probability",
    "parent_count",
    "stratum_parent_counts",
    "bootstrap_values",
    "inference_status",
    "beneficial_effect_supported",
    "gate_state",
}
_PHASE_LIMITATIONS = [
    "each-phase-40-contrast-family-is-separate-not-one-joint-80-interval-family",
    "lower-q0.10-is-identifiability-coverage-only-without-a-quantile-estimate",
    "demand-aware-changed-unchanged-sensitivity-is-descriptive-only",
    "post-launch-pre-inferential-analysis-amendment-after-15-formal-blocks",
]
_REPLICATION_LIMITATIONS = [
    "phases-are-not-pooled",
    "confirmation-cannot-rescue-a-failed-formal-phase",
    "the-two-phase-80-interval-set-is-not-one-joint-95-percent-family",
]


def build_phase_evidence(
    manifest,
    ledger,
    summary: Mapping[str, object],
    artifacts: list[Mapping[str, object]],
    calibration: Mapping[str, object],
    precision: Mapping[str, object],
    *,
    analysis_revision: str,
) -> dict[str, object]:
    """Build all 40 registered intervals from exact phase sources."""

    trace_rows = _extract_trace_contrasts(manifest, artifacts)
    projection = {
        "stream_projection_version": 1,
        "trace_contrasts": trace_rows,
        "activity_flags": _artifact_activity_flags(artifacts),
        "artifact_fingerprints": [
            item["artifact_fingerprint"]
            for item in sorted(artifacts, key=_artifact_sort_key)
        ],
    }
    return build_phase_evidence_from_projection(
        manifest,
        ledger,
        summary,
        projection,
        calibration,
        precision,
        analysis_revision=analysis_revision,
    )


def build_phase_evidence_from_projection(
    manifest,
    ledger,
    summary: Mapping[str, object],
    projection: Mapping[str, object],
    calibration: Mapping[str, object],
    precision: Mapping[str, object],
    *,
    analysis_revision: str,
) -> dict[str, object]:
    """Build the exact phase evidence from a bounded-memory raw projection."""

    _validate_digest(analysis_revision, "analysis_revision", length=40)
    if manifest.phase not in {StudyPhase.FORMAL, StudyPhase.CONFIRMATION}:
        raise StudyManifestError("phase evidence requires formal or confirmation")
    if summary["status"] != "complete" or summary["completed_block_count"] != 240:
        raise StudyManifestError("phase evidence requires the complete 240 blocks")
    if set(projection) != {
        "stream_projection_version",
        "trace_contrasts",
        "activity_flags",
        "artifact_fingerprints",
    } or projection["stream_projection_version"] != 1:
        raise StudyManifestError("phase stream projection fields differ")
    trace_rows = projection["trace_contrasts"]
    if not isinstance(trace_rows, list):
        raise StudyManifestError("phase trace projection must be a list")
    activity_flags = projection["activity_flags"]
    if not isinstance(activity_flags, Mapping) or len(activity_flags) != 240:
        raise StudyManifestError("phase activity projection must contain 240 blocks")
    artifact_fingerprints = projection["artifact_fingerprints"]
    if not isinstance(artifact_fingerprints, list) or len(artifact_fingerprints) != 240:
        raise StudyManifestError("phase artifact projection must contain 240 digests")
    parent_rows = _aggregate_parent_contrasts(trace_rows)
    hierarchies = _build_hierarchies(manifest, precision, trace_rows)
    event_coverage = _build_event_coverage(trace_rows)
    activity = _build_activity_sensitivity_from_flags(
        manifest, activity_flags, parent_rows
    )
    source_fingerprints = {
        "manifest": manifest.fingerprint,
        "seed_ledger": ledger.fingerprint,
        "run_summary": summary["summary_fingerprint"],
        "calibration_evidence": calibration["evidence_fingerprint"],
        "formal_precision": precision["precision_fingerprint"],
        "block_artifacts": list(artifact_fingerprints),
        "paired_manifests": sorted(
            {row["paired_manifest_fingerprint"] for row in trace_rows}
        ),
    }
    evidence: dict[str, object] = {
        "schema_version": PHASE_EVIDENCE_SCHEMA,
        "status": _STATUS,
        "phase": manifest.phase.value,
        "study_id": manifest.study_id,
        "source_fingerprints": source_fingerprints,
        "analysis_revision": analysis_revision,
        "analysis_contract": _analysis_contract(),
        "block_registry": [
            {
                "block_key": item["block_key"],
                "path": item["path"],
                "artifact_fingerprint": item["artifact_fingerprint"],
                "result_fingerprint": item["result_fingerprint"],
            }
            for item in summary["blocks"]
        ],
        "trace_contrasts": trace_rows,
        "parent_contrasts": parent_rows,
        "hierarchies": hierarchies,
        "event_coverage": event_coverage,
        "activity_sensitivity": activity,
        "limitations": list(_PHASE_LIMITATIONS),
    }
    evidence["evidence_fingerprint"] = _mapping_fingerprint(evidence)
    validate_phase_evidence(evidence)
    return evidence


def validate_phase_evidence(
    evidence: object,
    *,
    sources: tuple[object, object, Mapping[str, object], object, Mapping[str, object], Mapping[str, object], str]
    | None = None,
) -> None:
    """Validate structure and optionally replay the complete phase evidence."""

    top = _expect_mapping(evidence, _PHASE_FIELDS, "phase evidence")
    if top["schema_version"] != PHASE_EVIDENCE_SCHEMA or top["status"] != _STATUS:
        raise StudyManifestError("unsupported phase evidence schema or status")
    if top["phase"] not in {"formal", "confirmation"}:
        raise StudyManifestError("phase evidence phase is invalid")
    _validate_digest(top["analysis_revision"], "analysis_revision", length=40)
    _validate_digest(top["evidence_fingerprint"], "evidence_fingerprint")
    content = dict(top)
    supplied = content.pop("evidence_fingerprint")
    if supplied != _mapping_fingerprint(content):
        raise StudyManifestError("phase evidence fingerprint mismatch")
    if len(_expect_list(top["block_registry"], "block_registry")) != 240:
        raise StudyManifestError("phase evidence block registry must contain 240 blocks")
    _validate_phase_nested(top)
    if sources is not None:
        manifest, ledger, summary, raw_source, calibration, precision, revision = sources
        if not isinstance(summary, Mapping) or "code_revision" not in summary:
            raise StudyManifestError("strict phase replay summary context is missing")
        _verify_analysis_snapshot(_ROOT, revision, summary["code_revision"])
        if isinstance(raw_source, Mapping) and raw_source.get(
            "stream_projection_version"
        ) == 1:
            expected = build_phase_evidence_from_projection(
                manifest,
                ledger,
                summary,
                raw_source,
                calibration,
                precision,
                analysis_revision=revision,
            )
        else:
            expected = build_phase_evidence(
                manifest,
                ledger,
                summary,
                raw_source,
                calibration,
                precision,
                analysis_revision=revision,
            )
        if dict(top) != expected:
            raise StudyManifestError("phase evidence complete replay mismatch")


def _validate_phase_nested(top: Mapping[str, object]) -> None:
    expected_study = f"synthetic-{top['phase']}-v1"
    if top["study_id"] != expected_study:
        raise StudyManifestError("phase evidence study_id differs from phase")
    if top["analysis_contract"] != _analysis_contract():
        raise StudyManifestError("phase analysis contract differs")
    if top["limitations"] != _PHASE_LIMITATIONS:
        raise StudyManifestError("phase limitations differ")

    source = _expect_mapping(
        top["source_fingerprints"],
        {
            "manifest",
            "seed_ledger",
            "run_summary",
            "calibration_evidence",
            "formal_precision",
            "block_artifacts",
            "paired_manifests",
        },
        "source_fingerprints",
    )
    for field in (
        "manifest",
        "seed_ledger",
        "run_summary",
        "calibration_evidence",
        "formal_precision",
    ):
        _validate_digest(source[field], field)
    block_fingerprints = _expect_list(source["block_artifacts"], "block_artifacts")
    paired_fingerprints = _expect_list(source["paired_manifests"], "paired_manifests")
    _validate_digest_registry(block_fingerprints, 240, "block_artifacts")
    _validate_digest_registry(
        paired_fingerprints, 4 * 20 * 3 * 7, "paired_manifests", sorted_values=True
    )

    registry = _expect_list(top["block_registry"], "block_registry")
    expected_keys = _expected_block_keys()
    observed_keys = []
    for index, item in enumerate(registry):
        record = _expect_mapping(
            item,
            {"block_key", "path", "artifact_fingerprint", "result_fingerprint"},
            "block_registry record",
        )
        block_key = record["block_key"]
        if block_key != expected_keys[index] or record["path"] != f"blocks/{block_key}.json":
            raise StudyManifestError("block registry order or path differs")
        _validate_digest(record["artifact_fingerprint"], "artifact_fingerprint")
        _validate_digest(record["result_fingerprint"], "result_fingerprint")
        if record["artifact_fingerprint"] != block_fingerprints[index]:
            raise StudyManifestError("block registry/source fingerprint order differs")
        observed_keys.append(block_key)
    if tuple(observed_keys) != expected_keys:
        raise StudyManifestError("block registry is not canonical")

    traces = _expect_list(top["trace_contrasts"], "trace_contrasts")
    if len(traces) != 4 * 20 * 3 * 7 * 5 * 2:
        raise StudyManifestError("trace contrast count differs")
    for row in traces:
        _validate_trace_row(row)
    if traces != sorted(traces, key=_trace_sort_key):
        raise StudyManifestError("trace contrasts are not canonical")
    if sorted({row["paired_manifest_fingerprint"] for row in traces}) != paired_fingerprints:
        raise StudyManifestError("trace paired fingerprints differ from source registry")

    parents = _expect_list(top["parent_contrasts"], "parent_contrasts")
    if len(parents) != 4 * 20 * 3 * 5 * 2:
        raise StudyManifestError("parent contrast count differs")
    for row in parents:
        _validate_parent_row(row)
    parent_order = lambda row: (
        row["node_count"],
        row["parent_model"],
        row["parent_replicate"],
        row["source_family"],
        row["metric"],
    )
    if parents != sorted(parents, key=parent_order):
        raise StudyManifestError("parent contrasts are not canonical")

    _validate_hierarchies(top["hierarchies"])
    _validate_event_coverage(top["event_coverage"])
    _validate_activity_sensitivity(top["activity_sensitivity"], top["phase"])


def _validate_trace_row(value: object) -> None:
    row = _expect_mapping(value, _TRACE_FIELDS, "trace contrast")
    _validate_cell_identity(row)
    if row["scope"] not in {"same_distribution", "distribution_shift"}:
        raise StudyManifestError("trace scope is invalid")
    if type(row["regime_id"]) is not str or not row["regime_id"]:
        raise StudyManifestError("trace regime_id is invalid")
    _validate_digest(row["paired_manifest_fingerprint"], "paired_manifest_fingerprint")
    if row["source_family"] not in {*_SOURCES, "global"}:
        raise StudyManifestError("trace source family is invalid")
    if row["metric"] not in _METRICS or row["horizon"] != row["node_count"] * 12:
        raise StudyManifestError("trace metric or horizon differs")
    _fraction(row["value"])
    arms = _expect_list(row["binary_arm_events"], "binary_arm_events")
    if row["source_family"] == "global":
        if row["binary_arm_count"] is not None or arms or row["source_event"] is not None:
            raise StudyManifestError("global trace must not claim one binary bracket")
    else:
        if type(row["binary_arm_count"]) is not int or row["binary_arm_count"] not in {1, 2}:
            raise StudyManifestError("source trace binary arm count is invalid")
        if len(arms) != row["binary_arm_count"] or type(row["source_event"]) is not bool:
            raise StudyManifestError("source trace binary event payload differs")
        ids = []
        for arm in arms:
            if type(arm) is not list or len(arm) != 2 or type(arm[0]) is not str or type(arm[1]) is not bool:
                raise StudyManifestError("binary arm event is malformed")
            ids.append(arm[0])
        if ids != sorted(set(ids)):
            raise StudyManifestError("binary arms are not canonical and unique")


def _validate_parent_row(value: object) -> None:
    row = _expect_mapping(value, _PARENT_FIELDS, "parent contrast")
    _validate_cell_identity(row)
    if row["source_family"] not in {*_SOURCES, "global"} or row["metric"] not in _METRICS:
        raise StudyManifestError("parent source or metric is invalid")
    if row["horizon"] != row["node_count"] * 12:
        raise StudyManifestError("parent horizon differs")
    if row["same_distribution_trace_count"] != 4 or row["distribution_shift_trace_count"] != 3:
        raise StudyManifestError("parent scope counts differ from 4:3")
    if row["scope_weights"] != [["same_distribution", 4], ["distribution_shift", 3]]:
        raise StudyManifestError("parent scope weights differ")
    same = _fraction(row["same_distribution_mean"])
    shift = _fraction(row["distribution_shift_mean"])
    combined = _fraction(row["combined_parent_value"])
    if combined != Fraction(4, 7) * same + Fraction(3, 7) * shift:
        raise StudyManifestError("parent 4:3 reconstruction differs")


def _validate_hierarchies(value: object) -> None:
    families = _expect_list(value, "hierarchies")
    specs = _hierarchy_specs()
    if len(families) != len(specs):
        raise StudyManifestError("hierarchy count differs")
    for family, spec in zip(families, specs, strict=True):
        top = _expect_mapping(
            family,
            {
                "family_id",
                "metric",
                "node_count",
                "resamples",
                "root_seed",
                "confidence_level",
                "adjusted_tail_probability",
                "phase_family_scope",
                "intervals",
            },
            "hierarchy",
        )
        if (
            top["family_id"] != spec["family_id"]
            or top["metric"] != spec["metric"]
            or top["node_count"] != spec["node_count"]
            or top["resamples"] != 20_000
            or top["root_seed"] != 2026081003
            or _fraction(top["confidence_level"]) != Fraction(159, 160)
            or _fraction(top["adjusted_tail_probability"]) != Fraction(1, 1600)
            or top["phase_family_scope"]
            != "one-of-eight-local-five-contrast-hierarchies"
        ):
            raise StudyManifestError("hierarchy frozen contract differs")
        intervals = _expect_list(top["intervals"], "hierarchy intervals")
        expected_registrations = spec["registrations"]
        if len(intervals) != 5:
            raise StudyManifestError("hierarchy must contain five intervals")
        global_supported = None
        validated = []
        for interval, registration in zip(
            intervals, expected_registrations, strict=True
        ):
            item = _expect_mapping(interval, _INTERVAL_FIELDS, "interval")
            if (
                item["contrast_id"] != registration["contrast_id"]
                or item["metric"] != spec["metric"]
                or item["node_count"] != spec["node_count"]
                or item["tier"] != registration["tier"]
                or item["beneficial_direction"]
                != registration["beneficial_direction"]
            ):
                raise StudyManifestError("interval registration differs")
            estimate = _fraction(item["estimate"])
            lower = _fraction(item["lower"])
            upper = _fraction(item["upper"])
            if lower > upper or not isinstance(estimate, Fraction):
                raise StudyManifestError("interval endpoints are reversed")
            if _fraction(item["confidence_level"]) != Fraction(159, 160) or _fraction(
                item["tail_probability"]
            ) != Fraction(1, 1600):
                raise StudyManifestError("interval confidence or tail differs")
            if item["parent_count"] != 60 or item["stratum_parent_counts"] != [
                [model, 20] for model in _MODELS
            ]:
                raise StudyManifestError("interval parent counts differ")
            bootstrap = _expect_list(item["bootstrap_values"], "bootstrap_values")
            if len(bootstrap) != 20_000:
                raise StudyManifestError("bootstrap vector must contain 20,000 values")
            bootstrap_values = tuple(_fraction(value) for value in bootstrap)
            if lower != empirical_quantile(bootstrap_values, Fraction(1, 1600)) or upper != empirical_quantile(
                bootstrap_values, Fraction(1599, 1600)
            ):
                raise StudyManifestError("interval endpoints do not replay from bootstrap")
            supported = _interval_direction(item) == "beneficial"
            if type(item["beneficial_effect_supported"]) is not bool or item[
                "beneficial_effect_supported"
            ] is not supported:
                raise StudyManifestError("interval beneficial support differs")
            if item["tier"] == "global":
                if item["gate_state"] != "not_applicable" or item[
                    "inference_status"
                ] != "confirmatory":
                    raise StudyManifestError("global gate/status differs")
                global_supported = supported
            validated.append(item)
        if global_supported is None:
            raise StudyManifestError("hierarchy has no global interval")
        for item in validated:
            if item["tier"] == "secondary":
                expected_gate = "open" if global_supported else "closed"
                expected_status = "confirmatory" if global_supported else "descriptive"
                if item["gate_state"] != expected_gate or item[
                    "inference_status"
                ] != expected_status:
                    raise StudyManifestError("secondary gate/status differs from global")


def _validate_event_coverage(value: object) -> None:
    rows = _expect_list(value, "event_coverage")
    if len(rows) != 4 * 3 * 4 * 2:
        raise StudyManifestError("event coverage cell count differs")
    expected_keys = [
        (size, model, source, scope)
        for size in (30, 60, 120, 240)
        for model in _MODELS
        for source in _SOURCES
        for scope in ("distribution_shift", "same_distribution")
    ]
    observed_keys = []
    for row in rows:
        item = _expect_mapping(
            row,
            {
                "node_count",
                "parent_model",
                "source_family",
                "scope",
                "parent_count",
                "parents",
                "all_parents_q0.10_identified",
                "quantile_estimate",
            },
            "event coverage cell",
        )
        key = (
            item["node_count"],
            item["parent_model"],
            item["source_family"],
            item["scope"],
        )
        observed_keys.append(key)
        if item["parent_count"] != 20 or item["quantile_estimate"] is not None:
            raise StudyManifestError("event coverage parent count/quantile differs")
        parents = _expect_list(item["parents"], "event coverage parents")
        if len(parents) != 20:
            raise StudyManifestError("event coverage requires twenty parents")
        parent_flags = []
        parent_ids = []
        for parent in parents:
            p = _expect_mapping(
                parent,
                {
                    "parent_graph_id",
                    "source_event_count",
                    "trace_count",
                    "source_event_fraction",
                    "source_q0.10_identified",
                    "binary_arms",
                    "source_and_all_binary_q0.10_identified",
                },
                "event coverage parent",
            )
            trace_count = 4 if item["scope"] == "same_distribution" else 3
            if p["trace_count"] != trace_count or type(p["source_event_count"]) is not int or not 0 <= p[
                "source_event_count"
            ] <= trace_count:
                raise StudyManifestError("event coverage source counts differ")
            source_fraction = Fraction(p["source_event_count"], trace_count)
            if _fraction(p["source_event_fraction"]) != source_fraction or p[
                "source_q0.10_identified"
            ] is not (source_fraction >= Fraction(1, 10)):
                raise StudyManifestError("source q0.10 gate differs")
            arms = _expect_list(p["binary_arms"], "coverage binary arms")
            if len(arms) not in {1, 2}:
                raise StudyManifestError("coverage binary bracket width differs")
            arm_flags = []
            arm_ids = []
            for arm in arms:
                a = _expect_mapping(
                    arm,
                    {
                        "variant_id",
                        "event_count",
                        "trace_count",
                        "event_fraction",
                        "q0.10_identified",
                    },
                    "coverage binary arm",
                )
                if type(a["variant_id"]) is not str or type(a["event_count"]) is not int or a[
                    "trace_count"
                ] != trace_count or not 0 <= a["event_count"] <= trace_count:
                    raise StudyManifestError("coverage binary arm counts differ")
                fraction = Fraction(a["event_count"], trace_count)
                flag = fraction >= Fraction(1, 10)
                if _fraction(a["event_fraction"]) != fraction or a[
                    "q0.10_identified"
                ] is not flag:
                    raise StudyManifestError("binary q0.10 gate differs")
                arm_ids.append(a["variant_id"])
                arm_flags.append(flag)
            if arm_ids != sorted(set(arm_ids)):
                raise StudyManifestError("coverage binary arms are not canonical")
            combined = p["source_q0.10_identified"] and all(arm_flags)
            if p["source_and_all_binary_q0.10_identified"] is not combined:
                raise StudyManifestError("parent q0.10 combined gate differs")
            parent_flags.append(combined)
            parent_ids.append(p["parent_graph_id"])
        if parent_ids != sorted(set(parent_ids)):
            raise StudyManifestError("coverage parents are not canonical")
        if item["all_parents_q0.10_identified"] is not all(parent_flags):
            raise StudyManifestError("cell q0.10 gate differs")
    if observed_keys != expected_keys:
        raise StudyManifestError("event coverage cells are not canonical")


def _validate_activity_sensitivity(value: object, phase: str) -> None:
    rows = _expect_list(value, "activity_sensitivity")
    expected_keys = [
        (size, metric, status)
        for size in (30, 60, 120, 240)
        for metric in _METRICS
        for status in ("changed", "unchanged")
    ]
    if len(rows) != len(expected_keys):
        raise StudyManifestError("activity sensitivity cell count differs")
    observed_keys = []
    for row in rows:
        item = _expect_mapping(
            row,
            {
                "phase",
                "node_count",
                "metric",
                "topology_activity",
                "strata",
                "model_aggregation_status",
                "equal_model_descriptive_mean",
                "confirmatory",
            },
            "activity sensitivity cell",
        )
        if item["phase"] != phase or item["confirmatory"] is not False:
            raise StudyManifestError("activity sensitivity phase/status differs")
        key = (item["node_count"], item["metric"], item["topology_activity"])
        observed_keys.append(key)
        strata = _expect_list(item["strata"], "activity strata")
        if len(strata) != 3:
            raise StudyManifestError("activity sensitivity requires three strata")
        means = []
        for model, stratum in zip(_MODELS, strata, strict=True):
            s = _expect_mapping(
                stratum,
                {
                    "parent_model",
                    "parent_count",
                    "parent_values",
                    "mean",
                    "minimum",
                    "maximum",
                    "variance",
                    "interval",
                },
                "activity stratum",
            )
            if s["parent_model"] != model or type(s["parent_count"]) is not int or not 0 <= s[
                "parent_count"
            ] <= 20 or s["variance"] is not None or s["interval"] is not None:
                raise StudyManifestError("activity stratum frozen fields differ")
            parent_values = _expect_list(s["parent_values"], "activity parent_values")
            if len(parent_values) != s["parent_count"]:
                raise StudyManifestError("activity parent count differs")
            ids = []
            values = []
            for pair in parent_values:
                if type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str:
                    raise StudyManifestError("activity parent value is malformed")
                ids.append(pair[0])
                values.append(_fraction(pair[1]))
            if ids != sorted(set(ids)):
                raise StudyManifestError("activity parents are not canonical")
            if not values:
                if any(s[field] is not None for field in ("mean", "minimum", "maximum")):
                    raise StudyManifestError("empty activity stratum summaries must be null")
                means.append(None)
            else:
                mean = sum(values, Fraction(0)) / len(values)
                if _fraction(s["mean"]) != mean or _fraction(s["minimum"]) != min(values) or _fraction(
                    s["maximum"]
                ) != max(values):
                    raise StudyManifestError("activity stratum summary differs")
                means.append(mean)
        if all(mean is not None for mean in means):
            expected_status = "equal-model-descriptive-mean"
            expected_mean = sum(means, Fraction(0)) / 3
            if _fraction(item["equal_model_descriptive_mean"]) != expected_mean:
                raise StudyManifestError("activity equal-model mean differs")
        else:
            expected_status = "not_aggregated_missing_stratum"
            if item["equal_model_descriptive_mean"] is not None:
                raise StudyManifestError("missing activity stratum must prevent aggregation")
        if item["model_aggregation_status"] != expected_status:
            raise StudyManifestError("activity aggregation status differs")
    if observed_keys != expected_keys:
        raise StudyManifestError("activity sensitivity cells are not canonical")


def _validate_replication_nested(top: Mapping[str, object]) -> None:
    _validate_digest(top["analysis_revision"], "analysis_revision", length=40)
    if top["limitations"] != _REPLICATION_LIMITATIONS:
        raise StudyManifestError("replication limitations differ")
    rows = _expect_list(top["contrast_results"], "contrast_results")
    expected_registry = {
        registration["contrast_id"]: (
            spec["metric"],
            spec["node_count"],
            registration["tier"],
            registration["beneficial_direction"],
        )
        for spec in _hierarchy_specs()
        for registration in spec["registrations"]
    }
    ids = []
    records = {}
    for row in rows:
        item = _expect_mapping(
            row,
            {
                "contrast_id",
                "metric",
                "node_count",
                "tier",
                "beneficial_direction",
                "formal_interval_direction",
                "confirmation_interval_direction",
                "formal_gate_state",
                "confirmation_gate_state",
                "formal_phase_success",
                "confirmation_phase_success",
                "formal_point_direction",
                "confirmation_point_direction",
                "point_sign_agreement",
                "replication_state",
            },
            "replication contrast",
        )
        ids.append(item["contrast_id"])
        if item["metric"] not in _METRICS or item["node_count"] not in {30, 60, 120, 240} or item[
            "tier"
        ] not in {"global", "secondary"} or item["beneficial_direction"] not in {
            "positive",
            "negative",
        }:
            raise StudyManifestError("replication registration is invalid")
        registration = (
            item["metric"],
            item["node_count"],
            item["tier"],
            item["beneficial_direction"],
        )
        if expected_registry.get(item["contrast_id"]) != registration:
            raise StudyManifestError("replication contrast registry differs")
        records[item["contrast_id"]] = item
        if item["formal_interval_direction"] not in {"beneficial", "harmful", "inconclusive"} or item[
            "confirmation_interval_direction"
        ] not in {"beneficial", "harmful", "inconclusive"}:
            raise StudyManifestError("replication interval direction is invalid")
        if item["formal_gate_state"] not in {"open", "closed", "not_applicable"} or item[
            "confirmation_gate_state"
        ] not in {"open", "closed", "not_applicable"}:
            raise StudyManifestError("replication gate state is invalid")
        if type(item["formal_phase_success"]) is not bool or type(
            item["confirmation_phase_success"]
        ) is not bool:
            raise StudyManifestError("replication phase success is invalid")
        if item["formal_point_direction"] not in {"beneficial", "harmful", "zero"} or item[
            "confirmation_point_direction"
        ] not in {"beneficial", "harmful", "zero"}:
            raise StudyManifestError("replication point direction is invalid")
        if item["point_sign_agreement"] not in {
            "same_beneficial",
            "same_harmful",
            "one_or_both_zero",
            "opposite",
        } or item["replication_state"] not in {
            "independently_confirmed",
            "formal_only",
            "confirmation_only",
            "neither",
        }:
            raise StudyManifestError("replication state enum is invalid")
        expected_gate_states = (
            {"not_applicable"} if item["tier"] == "global" else {"open", "closed"}
        )
        if item["formal_gate_state"] not in expected_gate_states or item[
            "confirmation_gate_state"
        ] not in expected_gate_states:
            raise StudyManifestError("replication gate state differs from tier")
        expected_formal_success = (
            item["formal_interval_direction"] == "beneficial"
            and item["formal_gate_state"] in {"open", "not_applicable"}
        )
        expected_confirmation_success = (
            item["confirmation_interval_direction"] == "beneficial"
            and item["confirmation_gate_state"] in {"open", "not_applicable"}
        )
        if item["formal_phase_success"] is not expected_formal_success or item[
            "confirmation_phase_success"
        ] is not expected_confirmation_success:
            raise StudyManifestError("replication phase success differs from direction and gate")
        expected_sign = _point_sign_agreement_from_directions(
            item["formal_point_direction"], item["confirmation_point_direction"]
        )
        if item["point_sign_agreement"] != expected_sign:
            raise StudyManifestError("replication point-sign agreement differs")
        expected_state = _replication_state(
            item["formal_phase_success"], item["confirmation_phase_success"]
        )
        if item["replication_state"] != expected_state:
            raise StudyManifestError("replication state differs from phase successes")
    if ids != sorted(expected_registry) or len(records) != len(expected_registry):
        raise StudyManifestError("replication contrasts are not canonical and unique")
    for item in records.values():
        if item["tier"] != "secondary":
            continue
        global_id = f"{item['metric']}.n{item['node_count']:04d}.global"
        global_item = records[global_id]
        for phase in ("formal", "confirmation"):
            expected_gate = (
                "open"
                if global_item[f"{phase}_interval_direction"] == "beneficial"
                else "closed"
            )
            if item[f"{phase}_gate_state"] != expected_gate:
                raise StudyManifestError(
                    "secondary replication gate differs from same-hierarchy global result"
                )


def _validate_cross_phase_sources(formal, confirmation, analysis_revision) -> None:
    if formal["analysis_revision"] != analysis_revision or confirmation[
        "analysis_revision"
    ] != analysis_revision:
        raise StudyManifestError("both phases must bind the same analysis revision")
    if formal["analysis_contract"] != confirmation["analysis_contract"]:
        raise StudyManifestError("phase analysis contracts differ")
    first = formal["source_fingerprints"]
    second = confirmation["source_fingerprints"]
    for shared in ("calibration_evidence", "formal_precision"):
        if first[shared] != second[shared]:
            raise StudyManifestError("phase calibration/precision basis differs")
    first_provenance = {
        first["manifest"],
        first["seed_ledger"],
        first["run_summary"],
        formal["evidence_fingerprint"],
        *first["block_artifacts"],
        *first["paired_manifests"],
    }
    second_provenance = {
        second["manifest"],
        second["seed_ledger"],
        second["run_summary"],
        confirmation["evidence_fingerprint"],
        *second["block_artifacts"],
        *second["paired_manifests"],
    }
    if first_provenance & second_provenance:
        raise StudyManifestError("phase provenance fingerprint sets overlap")


def _validate_cell_identity(row: Mapping[str, object]) -> None:
    if row["node_count"] not in {30, 60, 120, 240} or row[
        "parent_model"
    ] not in _MODELS or type(row["parent_replicate"]) is not int or not 0 <= row[
        "parent_replicate"
    ] < 20:
        raise StudyManifestError("analysis cell identity is invalid")
    if row["parent_graph_id"] != _block_key(row):
        raise StudyManifestError("parent_graph_id differs from analysis cell")


def _expected_block_keys():
    return tuple(
        f"n{size:04d}-r{replicate:04d}-{model}"
        for size in (30, 60, 120, 240)
        for replicate in range(20)
        for model in _MODELS
    )


def _hierarchy_specs():
    output = []
    for metric in _METRICS:
        direction = "negative" if metric == "failure_risk" else "positive"
        for size in (30, 60, 120, 240):
            family_id = f"{metric}.n{size:04d}"
            registrations = [
                {
                    "contrast_id": f"{family_id}.global",
                    "tier": "global",
                    "beneficial_direction": direction,
                }
            ] + [
                {
                    "contrast_id": f"{family_id}.{source}",
                    "tier": "secondary",
                    "beneficial_direction": direction,
                }
                for source in _SOURCES
            ]
            registrations.sort(key=lambda item: item["contrast_id"])
            output.append(
                {
                    "family_id": family_id,
                    "metric": metric,
                    "node_count": size,
                    "registrations": registrations,
                }
            )
    output.sort(key=lambda item: item["family_id"])
    return output


def _validate_digest_registry(values, count, label, *, sorted_values=False):
    if len(values) != count:
        raise StudyManifestError(f"{label} count differs")
    for value in values:
        _validate_digest(value, label)
    if len(set(values)) != len(values) or (sorted_values and values != sorted(values)):
        raise StudyManifestError(f"{label} must be canonical and unique")


def build_replication_evidence(
    formal_evidence_path: Path,
    confirmation_evidence_path: Path,
    *,
    formal_source_paths,
    confirmation_source_paths,
    analysis_revision: str,
) -> dict[str, object]:
    """Strict-load both raw phase chains and apply the frozen state machine."""

    formal_sources = load_phase_sources(*formal_source_paths)
    formal = load_phase_evidence(
        formal_evidence_path,
        sources=formal_sources,
        analysis_revision=analysis_revision,
    )
    formal_execution_revision = formal_sources[2]["code_revision"]
    formal_projection = _replication_phase_projection(formal)
    del formal, formal_sources

    confirmation_sources = load_phase_sources(*confirmation_source_paths)
    confirmation = load_phase_evidence(
        confirmation_evidence_path,
        sources=confirmation_sources,
        analysis_revision=analysis_revision,
    )
    if formal_execution_revision != confirmation_sources[2]["code_revision"]:
        raise StudyManifestError("phase execution revisions differ")
    confirmation_projection = _replication_phase_projection(confirmation)
    del confirmation, confirmation_sources
    _validate_cross_phase_sources(
        formal_projection, confirmation_projection, analysis_revision
    )
    return _build_replication_from_validated_phases(
        formal_projection,
        confirmation_projection,
        analysis_revision=analysis_revision,
    )


def _replication_phase_projection(evidence: Mapping[str, object]) -> dict[str, object]:
    """Drop raw rows and bootstrap arrays after one phase has strict-replayed."""

    return {
        "phase": evidence["phase"],
        "analysis_revision": evidence["analysis_revision"],
        "analysis_contract": dict(evidence["analysis_contract"]),
        "evidence_fingerprint": evidence["evidence_fingerprint"],
        "source_fingerprints": {
            key: list(value) if isinstance(value, list) else value
            for key, value in evidence["source_fingerprints"].items()
        },
        "hierarchies": [
            {
                "intervals": [
                    {
                        field: interval[field]
                        for field in (
                            "contrast_id",
                            "metric",
                            "node_count",
                            "tier",
                            "beneficial_direction",
                            "estimate",
                            "lower",
                            "upper",
                            "gate_state",
                        )
                    }
                    for interval in family["intervals"]
                ]
            }
            for family in evidence["hierarchies"]
        ],
    }


def _build_replication_evidence_from_loaded_sources(
    formal: Mapping[str, object],
    confirmation: Mapping[str, object],
    *,
    formal_sources,
    confirmation_sources,
    analysis_revision: str,
) -> dict[str, object]:
    """Replay already strict-loaded phase sources without pooling outcomes."""

    _validate_digest(analysis_revision, "analysis_revision", length=40)
    validate_phase_evidence(formal, sources=formal_sources)
    validate_phase_evidence(confirmation, sources=confirmation_sources)
    _validate_cross_phase_sources(formal, confirmation, analysis_revision)
    return _build_replication_from_validated_phases(
        formal, confirmation, analysis_revision=analysis_revision
    )


def _build_replication_from_validated_phases(
    formal: Mapping[str, object],
    confirmation: Mapping[str, object],
    *,
    analysis_revision: str,
) -> dict[str, object]:
    if formal["phase"] != "formal" or confirmation["phase"] != "confirmation":
        raise StudyManifestError("replication evidence requires formal then confirmation")
    formal_intervals = _interval_registry(formal)
    confirmation_intervals = _interval_registry(confirmation)
    if set(formal_intervals) != set(confirmation_intervals):
        raise StudyManifestError("phase contrast registries differ")
    results = []
    for contrast_id in sorted(formal_intervals):
        first = formal_intervals[contrast_id]
        second = confirmation_intervals[contrast_id]
        for field in ("tier", "beneficial_direction", "metric", "node_count"):
            if first[field] != second[field]:
                raise StudyManifestError("phase contrast registrations differ")
        formal_direction = _interval_direction(first)
        confirmation_direction = _interval_direction(second)
        formal_gate = first["gate_state"]
        confirmation_gate = second["gate_state"]
        formal_success = formal_direction == "beneficial" and formal_gate in {
            "open",
            "not_applicable",
        }
        confirmation_success = (
            confirmation_direction == "beneficial"
            and confirmation_gate in {"open", "not_applicable"}
        )
        results.append(
            {
                "contrast_id": contrast_id,
                "metric": first["metric"],
                "node_count": first["node_count"],
                "tier": first["tier"],
                "beneficial_direction": first["beneficial_direction"],
                "formal_interval_direction": formal_direction,
                "confirmation_interval_direction": confirmation_direction,
                "formal_gate_state": formal_gate,
                "confirmation_gate_state": confirmation_gate,
                "formal_phase_success": formal_success,
                "confirmation_phase_success": confirmation_success,
                "formal_point_direction": _point_direction(first),
                "confirmation_point_direction": _point_direction(second),
                "point_sign_agreement": _point_sign_agreement(first, second),
                "replication_state": _replication_state(
                    formal_success, confirmation_success
                ),
            }
        )
    result: dict[str, object] = {
        "schema_version": REPLICATION_EVIDENCE_SCHEMA,
        "status": _STATUS,
        "formal_evidence_fingerprint": formal["evidence_fingerprint"],
        "confirmation_evidence_fingerprint": confirmation["evidence_fingerprint"],
        "analysis_revision": analysis_revision,
        "contrast_results": results,
        "limitations": list(_REPLICATION_LIMITATIONS),
    }
    result["replication_fingerprint"] = _mapping_fingerprint(result)
    validate_replication_evidence(result)
    return result


def validate_replication_evidence(
    evidence: object,
    *,
    formal: Mapping[str, object] | None = None,
    confirmation: Mapping[str, object] | None = None,
    formal_sources=None,
    confirmation_sources=None,
    analysis_revision: str | None = None,
) -> None:
    top = _expect_mapping(evidence, _REPLICATION_FIELDS, "replication evidence")
    if top["schema_version"] != REPLICATION_EVIDENCE_SCHEMA or top["status"] != _STATUS:
        raise StudyManifestError("unsupported replication schema or status")
    for field in (
        "formal_evidence_fingerprint",
        "confirmation_evidence_fingerprint",
        "replication_fingerprint",
    ):
        _validate_digest(top[field], field)
    _validate_digest(top["analysis_revision"], "analysis_revision", length=40)
    if top["formal_evidence_fingerprint"] == top["confirmation_evidence_fingerprint"]:
        raise StudyManifestError("phase evidence fingerprints must be disjoint")
    if len(_expect_list(top["contrast_results"], "contrast_results")) != 40:
        raise StudyManifestError("replication evidence requires 40 contrasts")
    _validate_replication_nested(top)
    content = dict(top)
    supplied = content.pop("replication_fingerprint")
    if supplied != _mapping_fingerprint(content):
        raise StudyManifestError("replication fingerprint mismatch")
    supplied_replay = any(
        value is not None
        for value in (
            formal,
            confirmation,
            formal_sources,
            confirmation_sources,
            analysis_revision,
        )
    )
    if supplied_replay:
        if any(
            value is None
            for value in (
                formal,
                confirmation,
                formal_sources,
                confirmation_sources,
                analysis_revision,
            )
        ):
            raise StudyManifestError("strict replication replay requires every source")
        expected = _build_replication_evidence_from_loaded_sources(
            formal,
            confirmation,
            formal_sources=formal_sources,
            confirmation_sources=confirmation_sources,
            analysis_revision=analysis_revision,
        )
        if dict(top) != expected:
            raise StudyManifestError("replication complete replay mismatch")


def load_phase_evidence(path: Path, *, sources, analysis_revision: str):
    """Load phase JSON only with a full raw-source replay."""

    raw = _load_strict_json(path, "phase evidence")
    validate_phase_evidence(raw, sources=(*sources, analysis_revision))
    return raw


def load_replication_evidence(
    path: Path,
    *,
    formal_evidence_path: Path,
    confirmation_evidence_path: Path,
    formal_source_paths,
    confirmation_source_paths,
    analysis_revision: str,
):
    """Load replication JSON only through both strict phase source chains."""

    raw = _load_strict_json(path, "replication evidence")
    expected = build_replication_evidence(
        formal_evidence_path,
        confirmation_evidence_path,
        formal_source_paths=formal_source_paths,
        confirmation_source_paths=confirmation_source_paths,
        analysis_revision=analysis_revision,
    )
    validate_replication_evidence(raw)
    if raw != expected:
        raise StudyManifestError("replication complete replay mismatch")
    return raw


def _extract_trace_contrasts(manifest, artifacts) -> list[dict[str, object]]:
    scopes = {
        regime.regime_id: (
            "same_distribution"
            if regime.shift.value == "same_distribution"
            else "distribution_shift"
        )
        for regime in manifest.regimes
        if regime.role.value == "test"
    }
    if sum(value == "same_distribution" for value in scopes.values()) != 4 or sum(
        value == "distribution_shift" for value in scopes.values()
    ) != 3:
        raise StudyManifestError("held-out scope registry must remain exactly 4:3")
    rows = []
    for artifact in sorted(artifacts, key=_artifact_sort_key):
        block = artifact["block"]
        parent_id = _block_key(block)
        expected_horizon = block["node_count"] * manifest.requests_per_node
        panels = {
            panel["source_variant_id"]: tuple(panel["binary_variant_ids"])
            for panel in artifact["resource_panels"]
        }
        if tuple(sorted(panels)) != _SOURCES or any(
            not binary_ids for binary_ids in panels.values()
        ):
            raise StudyManifestError(
                "resource panels must register one binary bracket per source family"
            )
        held_out = artifact["held_out"]
        if len(held_out) != 7:
            raise StudyManifestError("each formal block requires seven held-out traces")
        for paired in held_out:
            seed = paired["trace_seed"]
            regime_id = seed["regime_id"]
            if regime_id not in scopes:
                raise StudyManifestError("held-out regime is not registered")
            variants = paired["variants"]
            variants_by_id = {item["variant_id"]: item for item in variants}
            if len(variants_by_id) != len(variants):
                raise StudyManifestError("paired trace variant identifiers are not unique")
            for item in variants:
                _validate_event(item["tau_nopath"], expected_horizon)
                if item["horizon"] != expected_horizon:
                    raise StudyManifestError("variant horizon differs from manifest")
            source_values = {}
            for source in _SOURCES:
                candidates = [item for item in variants if item["family"] == source]
                if len(candidates) != 1:
                    raise StudyManifestError("each source family must appear once per trace")
                source_values[source] = candidates[0]
            metric_values: dict[tuple[str, str], Fraction] = {}
            for source, item in source_values.items():
                try:
                    binaries = [variants_by_id[variant_id] for variant_id in panels[source]]
                except KeyError as exc:
                    raise StudyManifestError(
                        "resource panel binary arm is absent from paired trace"
                    ) from exc
                if any(binary["family"] != "binary-matched" for binary in binaries):
                    raise StudyManifestError(
                        "resource panel references a non-binary paired variant"
                    )
                metric_values[(source, "normalized_restricted_tau_nopath")] = Fraction(
                    item["tau_nopath"]["request_index"], expected_horizon
                ) - sum(
                    (
                        Fraction(binary["tau_nopath"]["request_index"], expected_horizon)
                        for binary in binaries
                    ),
                    Fraction(0),
                ) / len(binaries)
                metric_values[(source, "failure_risk")] = Fraction(
                    int(item["tau_nopath"]["observed"]), 1
                ) - sum(
                    (
                        Fraction(int(binary["tau_nopath"]["observed"]), 1)
                        for binary in binaries
                    ),
                    Fraction(0),
                ) / len(binaries)
            for metric in _METRICS:
                metric_values[("global", metric)] = sum(
                    (metric_values[(source, metric)] for source in _SOURCES),
                    Fraction(0),
                ) / len(_SOURCES)
            for source in (*_SOURCES, "global"):
                source_event = (
                    None
                    if source == "global"
                    else bool(source_values[source]["tau_nopath"]["observed"])
                )
                if source == "global":
                    source_binaries = []
                else:
                    source_binaries = [
                        variants_by_id[variant_id] for variant_id in panels[source]
                    ]
                for metric in _METRICS:
                    rows.append(
                        {
                            "node_count": block["node_count"],
                            "parent_model": block["parent_model"],
                            "parent_replicate": block["parent_replicate"],
                            "parent_graph_id": parent_id,
                            "regime_id": regime_id,
                            "scope": scopes[regime_id],
                            "paired_manifest_fingerprint": paired[
                                "paired_manifest_fingerprint"
                            ],
                            "source_family": source,
                            "metric": metric,
                            "horizon": expected_horizon,
                            "binary_arm_count": (
                                None if source == "global" else len(source_binaries)
                            ),
                            "binary_arm_events": [
                                [
                                    binary["variant_id"],
                                    bool(binary["tau_nopath"]["observed"]),
                                ]
                                for binary in source_binaries
                            ],
                            "source_event": source_event,
                            "value": _fraction_payload(metric_values[(source, metric)]),
                        }
                    )
    rows.sort(key=_trace_sort_key)
    return rows


def _aggregate_parent_contrasts(trace_rows) -> list[dict[str, object]]:
    grouped = defaultdict(list)
    for row in trace_rows:
        grouped[
            (
                row["node_count"],
                row["parent_model"],
                row["parent_replicate"],
                row["source_family"],
                row["metric"],
            )
        ].append(row)
    result = []
    for key in sorted(grouped):
        rows = grouped[key]
        same = [_fraction(row["value"]) for row in rows if row["scope"] == "same_distribution"]
        shift = [_fraction(row["value"]) for row in rows if row["scope"] == "distribution_shift"]
        if len(same) != 4 or len(shift) != 3:
            raise StudyManifestError("each parent contrast must retain the frozen 4:3 traces")
        same_mean = sum(same, Fraction(0)) / 4
        shift_mean = sum(shift, Fraction(0)) / 3
        combined = Fraction(4, 7) * same_mean + Fraction(3, 7) * shift_mean
        if combined != sum(same + shift, Fraction(0)) / 7:
            raise StudyManifestError("4:3 reconstruction mismatch")
        result.append(
            {
                "node_count": key[0],
                "parent_model": key[1],
                "parent_replicate": key[2],
                "parent_graph_id": rows[0]["parent_graph_id"],
                "source_family": key[3],
                "metric": key[4],
                "horizon": rows[0]["horizon"],
                "same_distribution_trace_count": 4,
                "same_distribution_mean": _fraction_payload(same_mean),
                "distribution_shift_trace_count": 3,
                "distribution_shift_mean": _fraction_payload(shift_mean),
                "scope_weights": [["same_distribution", 4], ["distribution_shift", 3]],
                "combined_parent_value": _fraction_payload(combined),
            }
        )
    return result


def _build_hierarchies(manifest, precision, trace_rows):
    plan = BootstrapPlan(
        precision["bootstrap"]["root_seed"],
        precision["bootstrap"]["resamples"],
        _fraction(precision["bootstrap"]["local_hierarchy_confidence_level"]),
    )
    output = []
    for family_spec in precision["confirmatory_families"]:
        node_count = family_spec["node_count"]
        metric_name = family_spec["metric"]
        samples = []
        for registration in family_spec["registrations"]:
            source = (
                "global"
                if registration["tier"] == "global"
                else registration["source_family"]
            )
            strata = []
            for model in _MODELS:
                selected = [
                    row
                    for row in trace_rows
                    if row["node_count"] == node_count
                    and row["parent_model"] == model
                    and row["source_family"] == source
                    and row["metric"] == metric_name
                ]
                observations = tuple(
                    BlockContrastObservation(
                        parent_graph_id=row["parent_graph_id"],
                        trace_id=row["regime_id"],
                        analysis_cell_id=(
                            f"{manifest.phase.value}.{metric_name}.n{node_count:04d}.{model}"
                        ),
                        manifest_fingerprint=row["paired_manifest_fingerprint"],
                        treatment_id=source,
                        reference_id="binary-bracket-equal-mean",
                        metric=ContrastMetric(metric_name),
                        horizon=row["horizon"],
                        value=_fraction(row["value"]),
                    )
                    for row in selected
                )
                sample = hierarchical_contrast_sample(
                    registration["contrast_id"], observations
                )
                if len(sample.parents) != 20:
                    raise StudyManifestError("each model stratum requires twenty parents")
                strata.append(StratumContrastSample(model, sample))
            samples.append(
                StratifiedContrastSample(
                    registration["contrast_id"],
                    f"{manifest.phase.value}.{metric_name}.n{node_count:04d}",
                    tuple(strata),
                )
            )
        samples.sort(key=lambda item: item.contrast_id)
        registrations = tuple(
            sorted(
                (
                    ContrastRegistration(
                        item["contrast_id"],
                        InferenceTier.GLOBAL
                        if item["tier"] == "global"
                        else InferenceTier.SECONDARY,
                        BeneficialDirection(item["beneficial_direction"]),
                    )
                    for item in family_spec["registrations"]
                ),
                key=lambda item: (item.tier.value, item.contrast_id),
            )
        )
        hierarchy = ConfirmatoryHierarchy(registrations)
        family = stratified_hierarchical_percentile_intervals(
            tuple(samples), hierarchy, plan
        )
        decisions = apply_stratified_confirmatory_hierarchy(hierarchy, family)
        global_supported = next(
            item.beneficial_effect_supported
            for item in decisions
            if item.registration.tier is InferenceTier.GLOBAL
        )
        intervals = []
        sample_by_id = {item.contrast_id: item for item in samples}
        for decision in sorted(decisions, key=lambda item: item.registration.contrast_id):
            interval = decision.interval
            registration = decision.registration
            intervals.append(
                {
                    "contrast_id": interval.contrast_id,
                    "metric": metric_name,
                    "node_count": node_count,
                    "tier": "global" if registration.tier is InferenceTier.GLOBAL else "secondary",
                    "beneficial_direction": registration.beneficial_direction.value,
                    "estimate": _fraction_payload(interval.estimate),
                    "lower": _fraction_payload(interval.lower),
                    "upper": _fraction_payload(interval.upper),
                    "confidence_level": _fraction_payload(interval.confidence_level),
                    "tail_probability": _fraction_payload(interval.tail_probability),
                    "parent_count": interval.parent_count,
                    "stratum_parent_counts": [
                        list(item)
                        for item in sample_by_id[interval.contrast_id].stratum_parent_counts
                    ],
                    "bootstrap_values": [
                        _fraction_payload(value) for value in interval.bootstrap_values
                    ],
                    "inference_status": decision.status.value,
                    "beneficial_effect_supported": decision.beneficial_effect_supported,
                    "gate_state": (
                        "not_applicable"
                        if registration.tier is InferenceTier.GLOBAL
                        else "open" if global_supported else "closed"
                    ),
                }
            )
        output.append(
            {
                "family_id": family_spec["family_id"],
                "metric": metric_name,
                "node_count": node_count,
                "resamples": plan.resamples,
                "root_seed": plan.root_seed,
                "confidence_level": _fraction_payload(plan.confidence_level),
                "adjusted_tail_probability": _fraction_payload(
                    family.intervals[0].tail_probability
                ),
                "phase_family_scope": "one-of-eight-local-five-contrast-hierarchies",
                "intervals": intervals,
            }
        )
    output.sort(key=lambda item: item["family_id"])
    return output


def _build_event_coverage(trace_rows):
    base_rows = [
        row
        for row in trace_rows
        if row["metric"] == "failure_risk" and row["source_family"] in _SOURCES
    ]
    grouped = defaultdict(list)
    for row in base_rows:
        grouped[
            (
                row["node_count"],
                row["parent_model"],
                row["source_family"],
                row["scope"],
            )
        ].append(row)
    result = []
    for key in sorted(grouped):
        by_parent = defaultdict(list)
        for row in grouped[key]:
            by_parent[row["parent_graph_id"]].append(row)
        parents = []
        for parent_id in sorted(by_parent):
            rows = by_parent[parent_id]
            trace_count = 4 if key[3] == "same_distribution" else 3
            if len(rows) != trace_count:
                raise StudyManifestError("event coverage trace count differs from scope")
            source_events = sum(int(row["source_event"]) for row in rows)
            binary_counts = defaultdict(int)
            binary_events = defaultdict(int)
            for row in rows:
                for variant_id, observed in row["binary_arm_events"]:
                    binary_counts[variant_id] += 1
                    binary_events[variant_id] += int(observed)
            if any(value != trace_count for value in binary_counts.values()):
                raise StudyManifestError("binary arms differ across parent scope traces")
            binary = [
                {
                    "variant_id": variant_id,
                    "event_count": binary_events[variant_id],
                    "trace_count": binary_counts[variant_id],
                    "event_fraction": _fraction_payload(
                        Fraction(binary_events[variant_id], binary_counts[variant_id])
                    ),
                    "q0.10_identified": Fraction(
                        binary_events[variant_id], binary_counts[variant_id]
                    )
                    >= Fraction(1, 10),
                }
                for variant_id in sorted(binary_counts)
            ]
            source_identified = Fraction(source_events, trace_count) >= Fraction(1, 10)
            parents.append(
                {
                    "parent_graph_id": parent_id,
                    "source_event_count": source_events,
                    "trace_count": trace_count,
                    "source_event_fraction": _fraction_payload(
                        Fraction(source_events, trace_count)
                    ),
                    "source_q0.10_identified": source_identified,
                    "binary_arms": binary,
                    "source_and_all_binary_q0.10_identified": source_identified
                    and bool(binary)
                    and all(item["q0.10_identified"] for item in binary),
                }
            )
        result.append(
            {
                "node_count": key[0],
                "parent_model": key[1],
                "source_family": key[2],
                "scope": key[3],
                "parent_count": len(parents),
                "parents": parents,
                "all_parents_q0.10_identified": all(
                    item["source_and_all_binary_q0.10_identified"] for item in parents
                ),
                "quantile_estimate": None,
            }
        )
    return result


def _artifact_activity_flags(artifacts):
    return {
        _block_key(item["block"]): (
            item["training"]["demand_aware"]["topology_fingerprint"]
            != item["training"]["demand_aware"]["seed_topology_fingerprint"]
        )
        for item in artifacts
    }


def _build_activity_sensitivity(manifest, artifacts, parent_rows):
    return _build_activity_sensitivity_from_flags(
        manifest, _artifact_activity_flags(artifacts), parent_rows
    )


def _build_activity_sensitivity_from_flags(manifest, changed, parent_rows):
    source_rows = [row for row in parent_rows if row["source_family"] == "demand-aware"]
    output = []
    for node_count in (30, 60, 120, 240):
        for metric in _METRICS:
            for status, flag in (("changed", True), ("unchanged", False)):
                strata = []
                for model in _MODELS:
                    selected = sorted(
                        (
                            row
                            for row in source_rows
                            if row["node_count"] == node_count
                            and row["parent_model"] == model
                            and row["metric"] == metric
                            and changed[row["parent_graph_id"]] is flag
                        ),
                        key=lambda row: row["parent_graph_id"],
                    )
                    values = [_fraction(row["combined_parent_value"]) for row in selected]
                    strata.append(
                        {
                            "parent_model": model,
                            "parent_count": len(values),
                            "parent_values": [
                                [row["parent_graph_id"], row["combined_parent_value"]]
                                for row in selected
                            ],
                            "mean": None
                            if not values
                            else _fraction_payload(sum(values, Fraction(0)) / len(values)),
                            "minimum": None if not values else _fraction_payload(min(values)),
                            "maximum": None if not values else _fraction_payload(max(values)),
                            "variance": None,
                            "interval": None,
                        }
                    )
                if all(item["parent_count"] > 0 for item in strata):
                    equal_mean = sum(
                        (_fraction(item["mean"]) for item in strata), Fraction(0)
                    ) / 3
                    aggregation_status = "equal-model-descriptive-mean"
                    payload = _fraction_payload(equal_mean)
                else:
                    aggregation_status = "not_aggregated_missing_stratum"
                    payload = None
                output.append(
                    {
                        "phase": manifest.phase.value,
                        "node_count": node_count,
                        "metric": metric,
                        "topology_activity": status,
                        "strata": strata,
                        "model_aggregation_status": aggregation_status,
                        "equal_model_descriptive_mean": payload,
                        "confirmatory": False,
                    }
                )
    return output


def _summary_from_stream_records(
    manifest,
    ledger,
    *,
    code_revision: str,
    environment: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the exact v1 summary from already strict-validated light records."""

    expected_count = len(ledger.parent_seeds) * len(_MODELS)
    ordered = sorted((dict(row) for row in records), key=lambda row: row["block_key"])
    summary: dict[str, object] = {
        "schema_version": STUDY_RUN_SUMMARY_SCHEMA_VERSION,
        "status": "complete" if len(ordered) == expected_count else "in_progress",
        "manifest_fingerprint": manifest.fingerprint,
        "seed_ledger_fingerprint": ledger.fingerprint,
        "code_revision": code_revision,
        "environment": dict(environment),
        "expected_block_count": expected_count,
        "completed_block_count": len(ordered),
        "total_generation_ns": sum(row["generation_ns"] for row in ordered),
        "total_exact_validation_ns": sum(row["validation_ns"] for row in ordered),
        "blocks": ordered,
    }
    summary["summary_fingerprint"] = _mapping_fingerprint(summary)
    validate_study_run_summary(
        summary,
        manifest=manifest,
        ledger=ledger,
        code_revision=code_revision,
        environment=environment,
    )
    return summary


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _exact_phase_block_paths(
    output_root: Path, expected_keys: Sequence[str]
) -> dict[str, Path]:
    """Require one regular artifact per key and no active/foreign block entry."""

    if output_root.is_symlink():
        raise StudyManifestError("phase output root cannot be a symlink")
    block_root = output_root / "blocks"
    if not block_root.is_dir() or block_root.is_symlink():
        raise StudyManifestError("phase block root is missing or redirected")
    lock_root = block_root / ".locks"
    if lock_root.is_symlink() or not lock_root.is_dir() or any(lock_root.iterdir()):
        raise StudyManifestError("phase lock root must exist and be empty")
    expected = set(expected_keys)
    observed = {}
    for entry in block_root.iterdir():
        if entry.name == ".locks":
            continue
        if entry.is_symlink() or not entry.is_file() or entry.suffix != ".json":
            raise StudyManifestError("unknown or transient phase block entry")
        if entry.stem not in expected:
            raise StudyManifestError("foreign phase block artifact")
        observed[entry.stem] = entry
    if set(observed) != expected:
        raise StudyManifestError("phase block registry is not complete")
    return observed


def build_streaming_run_summary(
    manifest,
    ledger,
    *,
    output_root: Path,
    code_revision: str,
    environment: Mapping[str, object],
    artifact_loader=load_synthetic_block_artifact,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Strict-load at most one full artifact and return summary plus byte registry."""

    jobs = sorted(
        (
            f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}",
            seed,
            model,
        )
        for seed in ledger.parent_seeds
        for model in _MODELS
    )
    paths = _exact_phase_block_paths(output_root, [row[0] for row in jobs])
    records = []
    byte_registry = []
    for key, parent_seed, model in jobs:
        path = paths[key]
        before = _sha256_file(path)
        artifact = artifact_loader(
            path,
            manifest=manifest,
            ledger=ledger,
            parent_seed=parent_seed,
            parent_model=model,
            code_revision=code_revision,
            environment=environment,
        )
        if _block_key(artifact["block"]) != key:
            raise StudyManifestError("streamed artifact key differs from registry")
        timing = artifact["timing_ns"]
        records.append(
            {
                "block_key": key,
                "path": f"blocks/{key}.json",
                "artifact_fingerprint": artifact["artifact_fingerprint"],
                "result_fingerprint": artifact["result_fingerprint"],
                "generation_ns": timing["generation"],
                "validation_ns": timing["exact_validation"],
            }
        )
        byte_registry.append({"block_key": key, "file_sha256": before})
        del artifact
    summary = _summary_from_stream_records(
        manifest,
        ledger,
        code_revision=code_revision,
        environment=environment,
        records=records,
    )
    final_paths = _exact_phase_block_paths(output_root, [row[0] for row in jobs])
    if final_paths != paths:
        raise StudyManifestError("phase block registry changed during finalization")
    for row in byte_registry:
        if _sha256_file(final_paths[row["block_key"]]) != row["file_sha256"]:
            raise StudyManifestError("phase block changed during streaming finalization")
    return summary, byte_registry


def generate_streaming_summary(args) -> Path:
    """Publish the exact v1 complete summary without retaining all raw artifacts."""

    root = Path(args.workspace_root).resolve()
    manifest_path, calibration_manifest_path, calibration_path, precision_path = [
        _inside(root, value)
        for value in (
            args.manifest,
            args.calibration_manifest,
            args.calibration_evidence,
            args.precision,
        )
    ]
    manifest = load_study_design_manifest(manifest_path)
    ledger = build_study_seed_ledger(manifest)
    calibration = load_audited_calibration_evidence(calibration_path)
    precision = load_formal_precision_evidence(
        precision_path, calibration_evidence=calibration
    )
    calibration_manifest = load_study_design_manifest(calibration_manifest_path)
    environment = runtime_environment()
    validate_frozen_execution_context(
        manifest,
        code_revision=manifest.code_revision,
        environment=environment,
        precision_evidence=precision,
        calibration_manifest=calibration_manifest,
    )
    _verify_analysis_snapshot(root, args.analysis_revision, manifest.code_revision)
    output_root = (root / manifest.output_root).resolve()
    try:
        output_root.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("phase output root escapes workspace") from exc
    summary, byte_registry = build_streaming_run_summary(
        manifest,
        ledger,
        output_root=output_root,
        code_revision=manifest.code_revision,
        environment=environment,
    )
    if summary["status"] != "complete" or summary["completed_block_count"] != 240:
        raise StudyManifestError("streaming finalization requires exactly 240 blocks")
    target = output_root / "run-summary.json"
    if target.is_symlink():
        raise StudyManifestError("run summary target cannot be a symlink")
    raw_witness_path = Path(args.witness)
    raw_witness_path = (
        raw_witness_path
        if raw_witness_path.is_absolute()
        else root / raw_witness_path
    )
    if raw_witness_path.is_symlink():
        raise StudyManifestError("finalization witness target cannot be a symlink")
    witness_path = _inside(root, raw_witness_path, must_exist=False)
    witness_root = (root / "results/diagnostics/formal-streaming-finalization").resolve()
    try:
        witness_path.relative_to(witness_root)
    except ValueError as exc:
        raise StudyManifestError("finalization witness path is outside its frozen root") from exc
    witness = {
        "schema_version": "formal-streaming-finalization-witness.v1",
        "status": "complete-memory-bounded-strict-replay",
        "phase": manifest.phase.value,
        "analysis_revision": args.analysis_revision,
        "execution_revision": manifest.code_revision,
        "manifest_fingerprint": manifest.fingerprint,
        "summary_fingerprint": summary["summary_fingerprint"],
        "block_count": len(byte_registry),
        "block_byte_registry": byte_registry,
        "limitations": [
            "summary-code-revision-is-scientific-execution-revision",
            "witness-analysis-revision-identifies-streaming-tooling",
            "no-scientific-endpoint-or-contrast-is-emitted-by-finalization",
        ],
    }
    witness["witness_fingerprint"] = _mapping_fingerprint(witness)
    _write_new_or_identical(target, summary, "run summary")
    _write_new_or_identical(witness_path, witness, "finalization witness")
    return target


def load_phase_sources(
    manifest_path: Path,
    summary_path: Path,
    calibration_manifest_path: Path,
    calibration_evidence_path: Path,
    precision_path: Path,
):
    """Load sources in the contract's fixed fail-closed trust-chain order."""

    manifest = load_study_design_manifest(manifest_path)
    ledger = build_study_seed_ledger(manifest)
    calibration = load_audited_calibration_evidence(calibration_evidence_path)
    precision = load_formal_precision_evidence(
        precision_path, calibration_evidence=calibration
    )
    calibration_manifest = load_study_design_manifest(calibration_manifest_path)
    expected_keys = tuple(
        sorted(
            f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}"
            for seed in ledger.parent_seeds
            for model in _MODELS
        )
    )
    summary = load_study_run_summary(summary_path, manifest=manifest, ledger=ledger)
    if summary["status"] != "complete" or summary["expected_block_count"] != 240:
        raise StudyManifestError("analysis requires a complete 240-block summary")
    validate_frozen_execution_context(
        manifest,
        code_revision=summary["code_revision"],
        environment=summary["environment"],
        precision_evidence=precision,
        calibration_manifest=calibration_manifest,
    )
    observed_keys = tuple(item["block_key"] for item in summary["blocks"])
    if observed_keys != expected_keys:
        raise StudyManifestError("summary differs from the canonical 240-block registry")
    seeds = {(item.node_count, item.parent_replicate): item for item in ledger.parent_seeds}
    output_root = summary_path.parent.resolve()
    paths_by_key = _exact_phase_block_paths(output_root, expected_keys)
    trace_rows = []
    activity_flags = {}
    artifact_fingerprints = []
    rebuilt_records = []
    byte_registry = []
    for record in summary["blocks"]:
        path = paths_by_key[record["block_key"]]
        try:
            path.relative_to(output_root)
        except ValueError as exc:
            raise StudyManifestError("summary block path escapes output root") from exc
        parts = record["block_key"].split("-", 2)
        node_count = int(parts[0][1:])
        replicate = int(parts[1][1:])
        before = _sha256_file(path)
        artifact = load_synthetic_block_artifact(
            path,
            manifest=manifest,
            ledger=ledger,
            parent_seed=seeds[(node_count, replicate)],
            parent_model=parts[2],
            code_revision=summary["code_revision"],
            environment=summary["environment"],
        )
        timing = artifact["timing_ns"]
        rebuilt_record = {
            "block_key": record["block_key"],
            "path": f"blocks/{record['block_key']}.json",
            "artifact_fingerprint": artifact["artifact_fingerprint"],
            "result_fingerprint": artifact["result_fingerprint"],
            "generation_ns": timing["generation"],
            "validation_ns": timing["exact_validation"],
        }
        if rebuilt_record != record:
            raise StudyManifestError("summary block record differs from streamed artifact")
        trace_rows.extend(_extract_trace_contrasts(manifest, [artifact]))
        activity_flags.update(_artifact_activity_flags([artifact]))
        artifact_fingerprints.append(artifact["artifact_fingerprint"])
        rebuilt_records.append(rebuilt_record)
        byte_registry.append((record["block_key"], before))
        del artifact
    trace_rows.sort(key=_trace_sort_key)
    rebuilt = _summary_from_stream_records(
        manifest,
        ledger,
        code_revision=summary["code_revision"],
        environment=summary["environment"],
        records=rebuilt_records,
    )
    if rebuilt != summary:
        raise StudyManifestError("complete run summary does not replay exactly")
    final_paths = _exact_phase_block_paths(output_root, expected_keys)
    if final_paths != paths_by_key:
        raise StudyManifestError("phase block registry changed during source projection")
    for key, digest in byte_registry:
        if _sha256_file(final_paths[key]) != digest:
            raise StudyManifestError("phase block changed during source projection")
    projection = {
        "stream_projection_version": 1,
        "trace_contrasts": trace_rows,
        "activity_flags": activity_flags,
        "artifact_fingerprints": artifact_fingerprints,
    }
    return manifest, ledger, summary, projection, calibration, precision


def generate_phase_evidence(args) -> Path:
    root = Path(args.workspace_root).resolve()
    paths = [
        _inside(root, value)
        for value in (
            args.manifest,
            args.summary,
            args.calibration_manifest,
            args.calibration_evidence,
            args.precision,
        )
    ]
    sources = load_phase_sources(*paths)
    _verify_analysis_snapshot(
        root, args.analysis_revision, sources[2]["code_revision"]
    )
    evidence = build_phase_evidence_from_projection(
        *sources, analysis_revision=args.analysis_revision
    )
    validate_phase_evidence(
        evidence,
        sources=(*sources, args.analysis_revision),
    )
    target = _evidence_target(root, args.output, paths)
    _write_new_or_identical(target, evidence, "phase evidence")
    return target


def generate_replication_evidence(args) -> Path:
    root = Path(args.workspace_root).resolve()
    common = [
        _inside(root, value)
        for value in (
            args.calibration_manifest,
            args.calibration_evidence,
            args.precision,
        )
    ]
    formal_paths = [
        _inside(root, args.formal_manifest),
        _inside(root, args.formal_summary),
        *common,
    ]
    confirmation_paths = [
        _inside(root, args.confirmation_manifest),
        _inside(root, args.confirmation_summary),
        *common,
    ]
    formal_evidence_path = _inside(root, args.formal_evidence)
    confirmation_evidence_path = _inside(root, args.confirmation_evidence)
    evidence = build_replication_evidence(
        formal_evidence_path,
        confirmation_evidence_path,
        formal_source_paths=formal_paths,
        confirmation_source_paths=confirmation_paths,
        analysis_revision=args.analysis_revision,
    )
    inputs = [
        *formal_paths,
        *confirmation_paths,
        formal_evidence_path,
        confirmation_evidence_path,
    ]
    target = _evidence_target(root, args.output, inputs)
    _write_new_or_identical(target, evidence, "replication evidence")
    return target


def _analysis_contract():
    return {
        "independent_unit": "parent_graph_within-size-and-parent-model",
        "nested_measurement": "held-out-traffic-trace",
        "binary_bracket_rule": "equal-mean-of-panel-registered-binary-arms-within-trace",
        "scope_rule": "four-sevenths-same-plus-three-sevenths-shift-within-parent",
        "model_rule": "independent-resample-within-three-strata-then-equal-model-mean",
        "primary_endpoints": list(_METRICS),
        "local_hierarchies": 8,
        "contrasts_per_hierarchy": 5,
        "phasewise_contrast_count": 40,
        "lower_quantile": {
            "q": [1, 10],
            "output": "identifiability-and-event-coverage-only",
        },
        "activity_sensitivity": "descriptive-with-no-subgroup-inference",
    }


def _interval_registry(evidence):
    return {
        item["contrast_id"]: item
        for family in evidence["hierarchies"]
        for item in family["intervals"]
    }


def _interval_direction(item):
    lower = _fraction(item["lower"])
    upper = _fraction(item["upper"])
    if item["beneficial_direction"] == "positive":
        if lower > 0:
            return "beneficial"
        if upper < 0:
            return "harmful"
    else:
        if upper < 0:
            return "beneficial"
        if lower > 0:
            return "harmful"
    return "inconclusive"


def _point_direction(item):
    estimate = _fraction(item["estimate"])
    if estimate == 0:
        return "zero"
    beneficial = estimate > 0 if item["beneficial_direction"] == "positive" else estimate < 0
    return "beneficial" if beneficial else "harmful"


def _point_sign_agreement(first, second):
    return _point_sign_agreement_from_directions(
        _point_direction(first), _point_direction(second)
    )


def _point_sign_agreement_from_directions(a, b):
    if "zero" in {a, b}:
        return "one_or_both_zero"
    if a == b == "beneficial":
        return "same_beneficial"
    if a == b == "harmful":
        return "same_harmful"
    return "opposite"


def _replication_state(formal_success, confirmation_success):
    if formal_success and confirmation_success:
        return "independently_confirmed"
    if formal_success:
        return "formal_only"
    if confirmation_success:
        return "confirmation_only"
    return "neither"


def _validate_event(event, horizon):
    if set(event) != {"observed", "request_index"}:
        raise StudyManifestError("tau_nopath event fields differ")
    if type(event["observed"]) is not bool or type(event["request_index"]) is not int:
        raise StudyManifestError("tau_nopath event types differ")
    if not 0 <= event["request_index"] <= horizon:
        raise StudyManifestError("tau_nopath request index is outside the horizon")
    if not event["observed"] and event["request_index"] != horizon:
        raise StudyManifestError("censored tau_nopath must equal the horizon")


def _artifact_sort_key(item):
    return (
        item["block"]["node_count"],
        item["block"]["parent_replicate"],
        item["block"]["parent_model"],
    )


def _trace_sort_key(item):
    return (
        item["node_count"],
        item["parent_model"],
        item["parent_replicate"],
        item["regime_id"],
        item["source_family"],
        item["metric"],
    )


def _block_key(block):
    return (
        f"n{block['node_count']:04d}-r{block['parent_replicate']:04d}-"
        f"{block['parent_model']}"
    )


def _fraction(value):
    if (
        type(value) is not list
        or len(value) != 2
        or type(value[0]) is not int
        or type(value[1]) is not int
        or value[1] <= 0
    ):
        raise StudyManifestError("fraction payload must be [integer, positive integer]")
    result = Fraction(value[0], value[1])
    if [result.numerator, result.denominator] != value:
        raise StudyManifestError("fraction payload must be reduced and canonical")
    return result


def _fraction_payload(value):
    if not isinstance(value, Fraction):
        raise StudyManifestError("internal value is not an exact Fraction")
    return [value.numerator, value.denominator]


def _mapping_fingerprint(mapping):
    return hashlib.sha256(
        json.dumps(
            mapping,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _expect_mapping(value, fields, label):
    if not isinstance(value, Mapping) or set(value) != fields:
        raise StudyManifestError(f"{label} fields differ")
    return value


def _expect_list(value, label):
    if type(value) is not list:
        raise StudyManifestError(f"{label} must be a list")
    return value


def _validate_digest(value, label, *, length=64):
    if (
        type(value) is not str
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError(f"{label} must be lowercase hexadecimal")


def _inside(root: Path, value, *, must_exist=True):
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("analysis path escapes workspace root") from exc
    if must_exist and not resolved.is_file():
        raise StudyManifestError(f"analysis input does not exist: {resolved}")
    return resolved


def _verify_analysis_snapshot(root, revision, execution_revision):
    _validate_digest(revision, "analysis_revision", length=40)
    _validate_digest(execution_revision, "execution_revision", length=40)
    command = ["git", "diff", "--quiet", revision, "--", "tools/formal_inference.py"]
    completed = subprocess.run(command, cwd=root, check=False)
    if completed.returncode != 0:
        raise StudyManifestError("analysis tool differs from declared revision")
    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}:tools/formal_inference.py"],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if exists.returncode != 0:
        raise StudyManifestError("analysis tool is absent from declared revision")

    package = subprocess.run(
        ["git", "diff", "--quiet", execution_revision, "--", "secondaryexploration"],
        cwd=root,
        check=False,
    )
    if package.returncode != 0:
        raise StudyManifestError(
            "analysis dependency package differs from phase execution revision"
        )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "secondaryexploration"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if untracked.returncode != 0 or untracked.stdout.strip():
        raise StudyManifestError(
            "untracked analysis dependency files prevent snapshot verification"
        )


def _load_strict_json(path: Path, label: str):
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            value = json.load(
                handle,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
    except StudyManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StudyManifestError(f"cannot load {label}: {path}") from exc
    if not isinstance(value, Mapping):
        raise StudyManifestError(f"{label} must be a JSON object")
    return dict(value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StudyManifestError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    raise StudyManifestError(f"non-finite JSON constant {value!r} is not allowed")


def _evidence_target(root: Path, value, inputs) -> Path:
    target = _inside(root, value, must_exist=False)
    evidence_root = (root / "results" / "inference").resolve()
    try:
        target.relative_to(evidence_root)
    except ValueError as exc:
        raise StudyManifestError(
            "analysis output must be inside results/inference"
        ) from exc
    resolved_inputs = {Path(item).resolve() for item in inputs}
    if target in resolved_inputs:
        raise StudyManifestError("analysis output cannot overwrite an input")
    return target


def _write_new_or_identical(path: Path, value, label: str) -> None:
    if path.exists():
        existing = _load_strict_json(path, label)
        if existing != value:
            raise StudyManifestError(f"existing {label} differs; refusing overwrite")
        return
    atomic_write_json(path, value)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    finalizer = commands.add_parser(
        "finalize", help="stream one complete phase into the exact v1 run summary"
    )
    finalizer.add_argument("manifest")
    finalizer.add_argument("calibration_manifest")
    finalizer.add_argument("calibration_evidence")
    finalizer.add_argument("precision")
    finalizer.add_argument("--analysis-revision", required=True)
    finalizer.add_argument("--workspace-root", default=".")
    finalizer.add_argument("--witness", required=True)

    phase = commands.add_parser("phase", help="build one strict phase evidence artifact")
    phase.add_argument("manifest")
    phase.add_argument("summary")
    phase.add_argument("calibration_manifest")
    phase.add_argument("calibration_evidence")
    phase.add_argument("precision")
    phase.add_argument("--analysis-revision", required=True)
    phase.add_argument("--workspace-root", default=".")
    phase.add_argument("--output", required=True)

    replication = commands.add_parser(
        "replication", help="build strict cross-phase replication evidence"
    )
    replication.add_argument("--formal-manifest", required=True)
    replication.add_argument("--formal-summary", required=True)
    replication.add_argument("--formal-evidence", required=True)
    replication.add_argument("--confirmation-manifest", required=True)
    replication.add_argument("--confirmation-summary", required=True)
    replication.add_argument("--confirmation-evidence", required=True)
    replication.add_argument("--calibration-manifest", required=True)
    replication.add_argument("--calibration-evidence", required=True)
    replication.add_argument("--precision", required=True)
    replication.add_argument("--analysis-revision", required=True)
    replication.add_argument("--workspace-root", default=".")
    replication.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "finalize":
        target = generate_streaming_summary(args)
    elif args.command == "phase":
        target = generate_phase_evidence(args)
    else:
        target = generate_replication_evidence(args)
    print(target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
