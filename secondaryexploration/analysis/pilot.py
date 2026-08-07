"""Parent-aware descriptive evidence from exact synthetic pilot artifacts."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from secondaryexploration.experiments.artifacts import (
    atomic_write_json,
    load_study_run_summary,
    load_synthetic_block_artifact,
    validate_study_run_summary,
    validate_synthetic_block_artifact,
)
from secondaryexploration.experiments.study import (
    StudyDesignManifest,
    StudyManifestError,
    StudyPhase,
    StudySeedLedger,
    TrafficRegimeRole,
    build_study_seed_ledger,
    load_study_design_manifest,
)


PILOT_EVIDENCE_SCHEMA_VERSION = "synthetic-pilot-evidence.v1"
_EVIDENCE_TOP_LEVEL_FIELDS = {
    "schema_version",
    "study_id",
    "phase",
    "manifest_fingerprint",
    "seed_ledger_fingerprint",
    "run_summary_fingerprint",
    "code_revision",
    "environment",
    "estimand_contract",
    "counts",
    "blocks",
    "demand_aware_search",
    "summaries",
    "limitations",
    "evidence_fingerprint",
}
_EVIDENCE_COUNT_FIELDS = {
    "block_count",
    "node_size_count",
    "parent_graph_count_by_size",
    "held_out_trace_count",
    "panel_trace_contrast_count",
}
_EVIDENCE_BLOCK_FIELDS = {
    "parent_graph_id",
    "node_count",
    "parent_model",
    "parent_replicate",
    "artifact_fingerprint",
    "result_fingerprint",
    "held_out_trace_count",
}
_DEMAND_BLOCK_FIELDS = {
    "parent_graph_id",
    "proposals_considered",
    "feasible_evaluations",
    "accepted_steps",
    "topology_changed",
}
_ESTIMAND_CONTRACT = {
    "binary_bracket_rule": "equal_mean_within_trace",
    "trace_rule": "equal_mean_within_parent_graph",
    "parent_rule": "equal_mean_across_parent_graphs",
    "tau_nopath_rule": "restricted_time_plus_event_indicator",
    "cost_rule": "componentwise_no_weighted_total",
    "inference_status": "descriptive_pilot_only",
}
_DYNAMIC_COST_FIELDS = (
    "traversed_hyperedge_count",
    "signaled_participant_slots",
    "unique_signaled_participants",
    "quadratic_coordination_exposure",
)
_RESOURCE_FIELDS = (
    "hyperedge_count",
    "incidence_count",
    "maximum_arity",
    "pairwise_member_exposure",
)
_SERVICE_METRIC_FIELDS = (
    "normalized_restricted_tau_nopath",
    "failure_risk",
    "success_rate",
    "accepted_value",
)
_SUMMARY_VALUE_FIELDS = {
    "parent_graph_count",
    "trace_contrast_count",
    "binary_arm_observation_count",
    "source_tau_nopath_event_count",
    "binary_tau_nopath_event_equivalent",
    "metrics",
    "dynamic_cost_per_attempt",
    "dynamic_cost_per_accepted",
}
_STATIC_RESOURCE_FIELDS = {
    "parent_graph_count",
    "binary_arm_count",
    "all_incidence_deltas_within_one",
    "metrics",
}
_ENVIRONMENT_FIELDS = {
    "python_implementation",
    "python_version",
    "platform_system",
    "machine",
}


def build_pilot_evidence(
    manifest: StudyDesignManifest,
    ledger: StudySeedLedger,
    run_summary: Mapping[str, object],
    block_artifacts: list[Mapping[str, object]],
) -> dict[str, object]:
    """Build exact descriptive evidence without treating traces as parents."""

    if not isinstance(manifest, StudyDesignManifest):
        raise StudyManifestError("manifest must be a StudyDesignManifest")
    if manifest.phase is not StudyPhase.PILOT:
        raise StudyManifestError("pilot evidence requires a pilot-phase manifest")
    if not isinstance(ledger, StudySeedLedger):
        raise StudyManifestError("ledger must be a StudySeedLedger")
    validate_study_run_summary(
        run_summary,
        manifest=manifest,
        ledger=ledger,
        block_artifacts=block_artifacts,
    )
    if run_summary["status"] != "complete":
        raise StudyManifestError("pilot evidence requires a complete run summary")

    parent_seeds = {
        (item.node_count, item.parent_replicate): item
        for item in ledger.parent_seeds
    }
    regimes = {
        item.regime_id: item
        for item in manifest.regimes
        if item.role is TrafficRegimeRole.TEST
    }
    observations: list[dict[str, object]] = []
    resources: list[dict[str, object]] = []
    blocks: list[dict[str, object]] = []
    demand_blocks: list[dict[str, object]] = []

    for artifact in block_artifacts:
        block = artifact["block"]
        parent_seed = parent_seeds[(block["node_count"], block["parent_replicate"])]
        validate_synthetic_block_artifact(
            artifact,
            manifest=manifest,
            ledger=ledger,
            parent_seed=parent_seed,
            parent_model=block["parent_model"],
            code_revision=run_summary["code_revision"],
            environment=run_summary["environment"],
        )
        parent_id = _parent_id(block)
        variants = {item["variant_id"]: item for item in artifact["variants"]}
        held_out = artifact["held_out"]
        panels = artifact["resource_panels"]
        expected_sources = tuple(sorted(manifest.topology_families))
        observed_sources = tuple(sorted(item["source_variant_id"] for item in panels))
        if observed_sources != expected_sources:
            raise StudyManifestError(
                "pilot resource panels do not match registered topology families"
            )

        blocks.append(
            {
                "parent_graph_id": parent_id,
                "node_count": block["node_count"],
                "parent_model": block["parent_model"],
                "parent_replicate": block["parent_replicate"],
                "artifact_fingerprint": artifact["artifact_fingerprint"],
                "result_fingerprint": artifact["result_fingerprint"],
                "held_out_trace_count": len(held_out),
            }
        )
        demand = artifact["training"]["demand_aware"]
        changed = demand["topology_fingerprint"] != demand["seed_topology_fingerprint"]
        demand_blocks.append(
            {
                "parent_graph_id": parent_id,
                "proposals_considered": demand["proposals_considered"],
                "feasible_evaluations": demand["feasible_evaluations"],
                "accepted_steps": demand["accepted_steps"],
                "topology_changed": changed,
            }
        )

        for panel in panels:
            source_id = panel["source_variant_id"]
            binary_ids = tuple(panel["binary_variant_ids"])
            source_resource = variants[source_id]["resources"]
            binary_resources = [variants[item]["resources"] for item in binary_ids]
            resources.append(
                {
                    "node_count": block["node_count"],
                    "parent_graph_id": parent_id,
                    "source_variant_id": source_id,
                    "metrics": {
                        field: _triplet(
                            Fraction(source_resource[field], 1),
                            _mean(Fraction(item[field], 1) for item in binary_resources),
                        )
                        for field in _RESOURCE_FIELDS
                    },
                    "binary_arm_count": len(binary_ids),
                    "incidence_deltas": tuple(panel["binary_incidence_deltas"]),
                }
            )
            for held_out_run in held_out:
                trace_seed = held_out_run["trace_seed"]
                regime_id = trace_seed["regime_id"]
                try:
                    regime = regimes[regime_id]
                except KeyError as exc:
                    raise StudyManifestError(
                        "artifact contains an unregistered held-out regime"
                    ) from exc
                run_variants = {
                    item["variant_id"]: item for item in held_out_run["variants"]
                }
                source = run_variants[source_id]
                binary = [run_variants[item] for item in binary_ids]
                horizon = source["horizon"]
                if any(item["horizon"] != horizon for item in binary):
                    raise StudyManifestError("panel variants do not share a horizon")
                observations.append(
                    _trace_observation(
                        node_count=block["node_count"],
                        parent_graph_id=parent_id,
                        regime_id=regime_id,
                        scope=(
                            "same_distribution"
                            if regime.shift.value == "same_distribution"
                            else "distribution_shift"
                        ),
                        source_variant_id=source_id,
                        binary_arm_count=len(binary),
                        horizon=horizon,
                        source=source,
                        binary=binary,
                    )
                )

    blocks.sort(key=lambda item: item["parent_graph_id"])
    demand_blocks.sort(key=lambda item: item["parent_graph_id"])
    observations.sort(key=_observation_key)
    resources.sort(
        key=lambda item: (
            item["node_count"],
            item["source_variant_id"],
            item["parent_graph_id"],
        )
    )
    by_size_family = _group_summaries(
        observations,
        resources,
        group_fields=("node_count", "source_variant_id"),
    )
    by_size_family_scope = _group_summaries(
        observations,
        resources=None,
        group_fields=("node_count", "source_variant_id", "scope"),
    )
    global_by_size = _group_summaries(
        observations,
        resources=None,
        group_fields=("node_count",),
    )

    changed_ids = [
        item["parent_graph_id"] for item in demand_blocks if item["topology_changed"]
    ]
    limitations = [
        "no_confirmatory_intervals_or_hypothesis_tests",
        "pilot_results_cannot_be_relabelled_as_formal_evidence",
    ]
    if manifest.parent_replicates == 1:
        limitations.insert(0, "one_parent_replicate_per_model_and_size")
    if not any(item["source_tau_nopath_observed"] for item in observations):
        limitations.append(
            "all_hypergraph_tau_nopath_observations_right_censored_at_horizon"
        )
    if len(changed_ids) * 2 < len(demand_blocks):
        limitations.append("demand_aware_search_inactive_in_most_blocks")

    evidence: dict[str, object] = {
        "schema_version": PILOT_EVIDENCE_SCHEMA_VERSION,
        "study_id": manifest.study_id,
        "phase": manifest.phase.value,
        "manifest_fingerprint": manifest.fingerprint,
        "seed_ledger_fingerprint": ledger.fingerprint,
        "run_summary_fingerprint": run_summary["summary_fingerprint"],
        "code_revision": run_summary["code_revision"],
        "environment": dict(run_summary["environment"]),
        "estimand_contract": dict(_ESTIMAND_CONTRACT),
        "counts": {
            "block_count": len(blocks),
            "node_size_count": len({item["node_count"] for item in blocks}),
            "parent_graph_count_by_size": [
                {
                    "node_count": node_count,
                    "count": sum(item["node_count"] == node_count for item in blocks),
                }
                for node_count in sorted({item["node_count"] for item in blocks})
            ],
            "held_out_trace_count": sum(
                item["held_out_trace_count"] for item in blocks
            ),
            "panel_trace_contrast_count": len(observations),
        },
        "blocks": blocks,
        "demand_aware_search": {
            "blocks": demand_blocks,
            "topology_changed_block_count": len(changed_ids),
            "topology_unchanged_block_count": len(demand_blocks) - len(changed_ids),
            "topology_changed_parent_graph_ids": changed_ids,
            "total_feasible_evaluations": sum(
                item["feasible_evaluations"] for item in demand_blocks
            ),
            "total_accepted_steps": sum(item["accepted_steps"] for item in demand_blocks),
        },
        "summaries": {
            "by_size_family": by_size_family,
            "by_size_family_scope": by_size_family_scope,
            "global_by_size": global_by_size,
        },
        "limitations": limitations,
    }
    evidence["evidence_fingerprint"] = _fingerprint(evidence)
    validate_pilot_evidence(
        evidence,
        manifest=manifest,
        ledger=ledger,
        run_summary=run_summary,
    )
    return evidence


def validate_pilot_evidence(
    evidence: object,
    *,
    manifest: StudyDesignManifest | None = None,
    ledger: StudySeedLedger | None = None,
    run_summary: Mapping[str, object] | None = None,
    block_artifacts: list[Mapping[str, object]] | None = None,
) -> None:
    """Reject corrupted evidence and optionally bind it to complete sources."""

    top = _exact_mapping(evidence, _EVIDENCE_TOP_LEVEL_FIELDS, "pilot evidence")
    if top["schema_version"] != PILOT_EVIDENCE_SCHEMA_VERSION:
        raise StudyManifestError("unsupported pilot evidence schema_version")
    if not isinstance(top["study_id"], str) or not top["study_id"]:
        raise StudyManifestError("pilot evidence study_id must be nonempty")
    if top["phase"] != StudyPhase.PILOT.value:
        raise StudyManifestError("pilot evidence phase must be pilot")
    for name in (
        "manifest_fingerprint",
        "seed_ledger_fingerprint",
        "run_summary_fingerprint",
        "evidence_fingerprint",
    ):
        _validate_digest(top[name], name)
    if (
        not isinstance(top["code_revision"], str)
        or len(top["code_revision"]) != 40
        or any(character not in "0123456789abcdef" for character in top["code_revision"])
    ):
        raise StudyManifestError("pilot evidence code_revision must be full Git SHA-1")
    environment_value = _exact_mapping(
        top["environment"],
        _ENVIRONMENT_FIELDS,
        "pilot evidence environment",
    )
    if any(
        not isinstance(environment_value[name], str) or not environment_value[name]
        for name in _ENVIRONMENT_FIELDS
    ):
        raise StudyManifestError("pilot evidence environment values must be nonempty strings")
    if top["estimand_contract"] != _ESTIMAND_CONTRACT:
        raise StudyManifestError("pilot evidence estimand contract is unsupported")

    counts = _exact_mapping(top["counts"], _EVIDENCE_COUNT_FIELDS, "evidence counts")
    for name in (
        "block_count",
        "node_size_count",
        "held_out_trace_count",
        "panel_trace_contrast_count",
    ):
        if type(counts[name]) is not int or counts[name] < 1:
            raise StudyManifestError(f"evidence {name} must be positive integer")
    blocks = _list(top["blocks"], "evidence blocks")
    if len(blocks) != counts["block_count"]:
        raise StudyManifestError("evidence block_count does not match blocks")
    block_ids = []
    node_counts = set()
    held_out_total = 0
    for item in blocks:
        block = _exact_mapping(item, _EVIDENCE_BLOCK_FIELDS, "evidence block")
        parent_id = block["parent_graph_id"]
        if not isinstance(parent_id, str) or not parent_id:
            raise StudyManifestError("evidence parent_graph_id must be nonempty")
        block_ids.append(parent_id)
        for name in ("node_count", "held_out_trace_count"):
            if type(block[name]) is not int or block[name] < 1:
                raise StudyManifestError(f"evidence block {name} must be positive")
        if type(block["parent_replicate"]) is not int or block["parent_replicate"] < 0:
            raise StudyManifestError("evidence parent_replicate must be nonnegative")
        if block["parent_model"] not in {
            "er_gnm",
            "barabasi_albert",
            "sbm_fixed_count",
        }:
            raise StudyManifestError("evidence parent_model is unsupported")
        if parent_id != (
            f"n{block['node_count']:04d}-r{block['parent_replicate']:04d}-"
            f"{block['parent_model']}"
        ):
            raise StudyManifestError("evidence parent_graph_id is not canonical")
        for name in ("artifact_fingerprint", "result_fingerprint"):
            _validate_digest(block[name], name)
        node_counts.add(block["node_count"])
        held_out_total += block["held_out_trace_count"]
    if block_ids != sorted(block_ids) or len(set(block_ids)) != len(block_ids):
        raise StudyManifestError("evidence blocks must be canonical and unique")
    if len(node_counts) != counts["node_size_count"]:
        raise StudyManifestError("evidence node_size_count does not match blocks")
    if held_out_total != counts["held_out_trace_count"]:
        raise StudyManifestError("evidence held_out_trace_count does not match blocks")

    size_counts = _list(
        counts["parent_graph_count_by_size"],
        "parent_graph_count_by_size",
    )
    for item in size_counts:
        size_item = _exact_mapping(
            item,
            {"node_count", "count"},
            "parent graph size count",
        )
        for name in ("node_count", "count"):
            if type(size_item[name]) is not int or size_item[name] < 1:
                raise StudyManifestError(
                    f"parent graph size {name} must be positive integer"
                )
    expected_size_counts = [
        {
            "node_count": node_count,
            "count": sum(block["node_count"] == node_count for block in blocks),
        }
        for node_count in sorted(node_counts)
    ]
    if size_counts != expected_size_counts:
        raise StudyManifestError("parent_graph_count_by_size does not match blocks")

    demand = _exact_mapping(
        top["demand_aware_search"],
        {
            "blocks",
            "topology_changed_block_count",
            "topology_unchanged_block_count",
            "topology_changed_parent_graph_ids",
            "total_feasible_evaluations",
            "total_accepted_steps",
        },
        "demand-aware evidence",
    )
    demand_blocks = _list(demand["blocks"], "demand-aware blocks")
    demand_ids = []
    changed_ids = []
    feasible_total = 0
    accepted_total = 0
    for item in demand_blocks:
        block = _exact_mapping(item, _DEMAND_BLOCK_FIELDS, "demand-aware block")
        if not isinstance(block["parent_graph_id"], str) or not block["parent_graph_id"]:
            raise StudyManifestError("demand-aware parent_graph_id must be nonempty")
        demand_ids.append(block["parent_graph_id"])
        if type(block["topology_changed"]) is not bool:
            raise StudyManifestError("topology_changed must be boolean")
        for name in (
            "proposals_considered",
            "feasible_evaluations",
            "accepted_steps",
        ):
            if type(block[name]) is not int or block[name] < 0:
                raise StudyManifestError(f"demand-aware {name} must be nonnegative")
        if block["topology_changed"]:
            changed_ids.append(block["parent_graph_id"])
        feasible_total += block["feasible_evaluations"]
        accepted_total += block["accepted_steps"]
    if demand_ids != block_ids:
        raise StudyManifestError("demand-aware blocks do not match evidence blocks")
    if demand["topology_changed_parent_graph_ids"] != changed_ids:
        raise StudyManifestError("changed demand-aware block ids are inconsistent")
    if demand["topology_changed_block_count"] != len(changed_ids):
        raise StudyManifestError("changed demand-aware block count is inconsistent")
    if demand["topology_unchanged_block_count"] != len(blocks) - len(changed_ids):
        raise StudyManifestError("unchanged demand-aware block count is inconsistent")
    if demand["total_feasible_evaluations"] != feasible_total:
        raise StudyManifestError("demand-aware feasible total is inconsistent")
    if demand["total_accepted_steps"] != accepted_total:
        raise StudyManifestError("demand-aware accepted total is inconsistent")

    summaries = _exact_mapping(
        top["summaries"],
        {"by_size_family", "by_size_family_scope", "global_by_size"},
        "pilot summaries",
    )
    _validate_summary_rows(
        summaries["by_size_family"],
        group_fields=("node_count", "source_variant_id"),
        include_resources=True,
        label="by_size_family",
    )
    _validate_summary_rows(
        summaries["by_size_family_scope"],
        group_fields=("node_count", "source_variant_id", "scope"),
        include_resources=False,
        label="by_size_family_scope",
    )
    _validate_summary_rows(
        summaries["global_by_size"],
        group_fields=("node_count",),
        include_resources=False,
        label="global_by_size",
    )
    limitations = _list(top["limitations"], "pilot limitations")
    if (
        any(not isinstance(item, str) or not item for item in limitations)
        or len(set(limitations)) != len(limitations)
    ):
        raise StudyManifestError("pilot limitations must be unique nonempty strings")
    if top["evidence_fingerprint"] != _fingerprint(top):
        raise StudyManifestError("pilot evidence fingerprint does not match content")

    if manifest is not None:
        if top["study_id"] != manifest.study_id or top["manifest_fingerprint"] != manifest.fingerprint:
            raise StudyManifestError("pilot evidence does not match study manifest")
        if counts["panel_trace_contrast_count"] != (
            counts["held_out_trace_count"] * len(manifest.topology_families)
        ):
            raise StudyManifestError("pilot panel-trace count does not match manifest")
    if ledger is not None and top["seed_ledger_fingerprint"] != ledger.fingerprint:
        raise StudyManifestError("pilot evidence does not match seed ledger")
    if run_summary is not None:
        validate_study_run_summary(run_summary)
        for evidence_name, summary_name in (
            ("manifest_fingerprint", "manifest_fingerprint"),
            ("seed_ledger_fingerprint", "seed_ledger_fingerprint"),
            ("run_summary_fingerprint", "summary_fingerprint"),
            ("code_revision", "code_revision"),
            ("environment", "environment"),
        ):
            if top[evidence_name] != run_summary[summary_name]:
                raise StudyManifestError("pilot evidence does not match run summary")
    if block_artifacts is not None:
        if manifest is None or ledger is None or run_summary is None:
            raise StudyManifestError(
                "manifest, ledger, and run_summary are required for source regeneration"
            )
        rebuilt = build_pilot_evidence(
            manifest,
            ledger,
            run_summary,
            block_artifacts,
        )
        if dict(top) != rebuilt:
            raise StudyManifestError("pilot evidence does not match deterministic sources")


def load_pilot_evidence(
    path: str | Path,
    **expected: object,
) -> dict[str, object]:
    """Load strict UTF-8 JSON and validate compact pilot evidence."""

    source = Path(path)
    try:
        raw = json.loads(
            source.read_text(encoding="utf-8"),
            object_pairs_hook=_mapping_without_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except StudyManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StudyManifestError(f"could not load pilot evidence {source}: {exc}") from exc
    validate_pilot_evidence(raw, **expected)
    return dict(raw)


def generate_pilot_evidence(
    manifest_path: str | Path,
    *,
    workspace_root: str | Path,
    summary_path: str | Path | None = None,
    output_path: str | Path,
) -> Path:
    """Load exact run artifacts and atomically write one compact evidence file."""

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
    artifacts = []
    for record in run_summary["blocks"]:
        artifact_path = (resolved_summary.parent / record["path"]).resolve()
        try:
            artifact_path.relative_to(resolved_summary.parent)
        except ValueError as exc:
            raise StudyManifestError("summary block path escapes output root") from exc
        block_key = record["block_key"]
        parts = block_key.split("-", 2)
        node_count = int(parts[0][1:])
        parent_replicate = int(parts[1][1:])
        parent_model = parts[2]
        parent_seed = next(
            (
                item
                for item in ledger.parent_seeds
                if item.node_count == node_count
                and item.parent_replicate == parent_replicate
            ),
            None,
        )
        if parent_seed is None:
            raise StudyManifestError("summary block is absent from the seed ledger")
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
    evidence = build_pilot_evidence(manifest, ledger, run_summary, artifacts)
    target = Path(output_path)
    if not target.is_absolute():
        target = (root / target).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise StudyManifestError("output_path escapes workspace_root") from exc
    atomic_write_json(target, evidence)
    return target


def _trace_observation(
    *,
    node_count: int,
    parent_graph_id: str,
    regime_id: str,
    scope: str,
    source_variant_id: str,
    binary_arm_count: int,
    horizon: int,
    source: Mapping[str, object],
    binary: list[Mapping[str, object]],
) -> dict[str, object]:
    source_tau = Fraction(source["tau_nopath"]["request_index"], horizon)
    binary_tau = _mean(
        Fraction(item["tau_nopath"]["request_index"], horizon) for item in binary
    )
    source_failure = Fraction(int(source["tau_nopath"]["observed"]), 1)
    binary_failure = _mean(
        Fraction(int(item["tau_nopath"]["observed"]), 1) for item in binary
    )
    source_success = Fraction(*source["success_rate"])
    binary_success = _mean(Fraction(*item["success_rate"]) for item in binary)
    source_value = Fraction(source["accepted_value"], 1)
    binary_value = _mean(Fraction(item["accepted_value"], 1) for item in binary)
    dynamic_per_attempt = {}
    dynamic_per_accepted = {}
    for field in _DYNAMIC_COST_FIELDS:
        source_cost = Fraction(source["dynamic_costs"][field], horizon)
        binary_cost = _mean(
            Fraction(item["dynamic_costs"][field], horizon) for item in binary
        )
        dynamic_per_attempt[field] = _triplet(source_cost, binary_cost)
        source_count = source["accepted_request_count"]
        binary_counts = [item["accepted_request_count"] for item in binary]
        source_per_accepted = (
            None
            if source_count == 0
            else Fraction(source["dynamic_costs"][field], source_count)
        )
        binary_defined = [
            Fraction(item["dynamic_costs"][field], count)
            for item, count in zip(binary, binary_counts, strict=True)
            if count > 0
        ]
        binary_per_accepted = (
            None if len(binary_defined) != len(binary) else _mean(binary_defined)
        )
        dynamic_per_accepted[field] = (
            None
            if source_per_accepted is None or binary_per_accepted is None
            else _triplet(source_per_accepted, binary_per_accepted)
        )
    return {
        "node_count": node_count,
        "parent_graph_id": parent_graph_id,
        "regime_id": regime_id,
        "scope": scope,
        "source_variant_id": source_variant_id,
        "binary_arm_count": binary_arm_count,
        "source_tau_nopath_observed": source["tau_nopath"]["observed"],
        "binary_tau_nopath_event_mean": binary_failure,
        "metrics": {
            "normalized_restricted_tau_nopath": _triplet(source_tau, binary_tau),
            "failure_risk": _triplet(source_failure, binary_failure),
            "success_rate": _triplet(source_success, binary_success),
            "accepted_value": _triplet(source_value, binary_value),
        },
        "dynamic_cost_per_attempt": dynamic_per_attempt,
        "dynamic_cost_per_accepted": dynamic_per_accepted,
    }


def _group_summaries(
    observations: list[dict[str, object]],
    resources: list[dict[str, object]] | None,
    *,
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for item in observations:
        grouped[tuple(item[field] for field in group_fields)].append(item)
    resource_groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    if resources is not None:
        for item in resources:
            resource_groups[tuple(item[field] for field in group_fields)].append(item)
    summaries = []
    for key in sorted(grouped):
        items = grouped[key]
        summary = {field: value for field, value in zip(group_fields, key, strict=True)}
        summary.update(_summarize_observations(items))
        if resources is not None:
            summary["static_resources"] = _summarize_resource_observations(
                resource_groups[key]
            )
        summaries.append(summary)
    return summaries


def _summarize_observations(items: list[dict[str, object]]) -> dict[str, object]:
    parents = sorted({item["parent_graph_id"] for item in items})
    metric_summary = {}
    for metric in (
        "normalized_restricted_tau_nopath",
        "failure_risk",
        "success_rate",
        "accepted_value",
    ):
        metric_summary[metric] = _parent_equal_triplet(
            items,
            lambda item, metric=metric: item["metrics"][metric],
        )
    cost_attempt = {
        field: _parent_equal_triplet(
            items,
            lambda item, field=field: item["dynamic_cost_per_attempt"][field],
        )
        for field in _DYNAMIC_COST_FIELDS
    }
    cost_accepted = {}
    for field in _DYNAMIC_COST_FIELDS:
        defined = [
            item for item in items if item["dynamic_cost_per_accepted"][field] is not None
        ]
        cost_accepted[field] = {
            "defined_trace_count": len(defined),
            "defined_parent_graph_count": len(
                {item["parent_graph_id"] for item in defined}
            ),
            "values": (
                None
                if not defined
                else _parent_equal_triplet(
                    defined,
                    lambda item, field=field: item["dynamic_cost_per_accepted"][field],
                )
            ),
        }
    return {
        "parent_graph_count": len(parents),
        "trace_contrast_count": len(items),
        "binary_arm_observation_count": sum(item["binary_arm_count"] for item in items),
        "source_tau_nopath_event_count": sum(
            item["source_tau_nopath_observed"] for item in items
        ),
        "binary_tau_nopath_event_equivalent": _fraction_payload(
            sum(
                (item["binary_tau_nopath_event_mean"] for item in items),
                start=Fraction(0, 1),
            )
        ),
        "metrics": metric_summary,
        "dynamic_cost_per_attempt": cost_attempt,
        "dynamic_cost_per_accepted": cost_accepted,
    }


def _summarize_resource_observations(
    items: list[dict[str, object]],
) -> dict[str, object]:
    if not items:
        raise StudyManifestError("resource summary group is empty")
    return {
        "parent_graph_count": len(items),
        "binary_arm_count": sum(item["binary_arm_count"] for item in items),
        "all_incidence_deltas_within_one": all(
            all(delta in {-1, 0, 1} for delta in item["incidence_deltas"])
            for item in items
        ),
        "metrics": {
            field: _equal_triplet_mean(item["metrics"][field] for item in items)
            for field in _RESOURCE_FIELDS
        },
    }


def _parent_equal_triplet(items, accessor) -> dict[str, list[int]]:
    by_parent: dict[str, list[tuple[Fraction, Fraction, Fraction]]] = defaultdict(list)
    for item in items:
        by_parent[item["parent_graph_id"]].append(accessor(item))
    parent_means = [_equal_triplet_mean(values, encoded=False) for values in by_parent.values()]
    return _equal_triplet_mean(parent_means)


def _equal_triplet_mean(
    values: Iterable[tuple[Fraction, Fraction, Fraction]],
    *,
    encoded: bool = True,
):
    value_tuple = tuple(values)
    if not value_tuple:
        raise StudyManifestError("cannot average an empty pilot evidence group")
    result = tuple(_mean(value[index] for value in value_tuple) for index in range(3))
    if not encoded:
        return result
    return {
        "source": _fraction_payload(result[0]),
        "binary": _fraction_payload(result[1]),
        "difference": _fraction_payload(result[2]),
    }


def _triplet(source: Fraction, binary: Fraction) -> tuple[Fraction, Fraction, Fraction]:
    return (source, binary, source - binary)


def _mean(values: Iterable[Fraction]) -> Fraction:
    value_tuple = tuple(values)
    if not value_tuple:
        raise StudyManifestError("cannot average an empty pilot evidence group")
    return sum(value_tuple, start=Fraction(0, 1)) / len(value_tuple)


def _fraction_payload(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _parent_id(block: Mapping[str, object]) -> str:
    return (
        f"n{block['node_count']:04d}-r{block['parent_replicate']:04d}-"
        f"{block['parent_model']}"
    )


def _observation_key(item: Mapping[str, object]) -> tuple[object, ...]:
    return (
        item["node_count"],
        item["source_variant_id"],
        item["scope"],
        item["parent_graph_id"],
        item["regime_id"],
    )


def _fingerprint(value: Mapping[str, object]) -> str:
    payload = dict(value)
    payload.pop("evidence_fingerprint", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_summary_rows(
    value: object,
    *,
    group_fields: tuple[str, ...],
    include_resources: bool,
    label: str,
) -> None:
    rows = _list(value, label)
    row_fields = set(group_fields) | _SUMMARY_VALUE_FIELDS
    if include_resources:
        row_fields.add("static_resources")
    keys = []
    for item in rows:
        row = _exact_mapping(item, row_fields, f"{label} row")
        for field in group_fields:
            group_value = row[field]
            if field == "node_count":
                if type(group_value) is not int or group_value < 1:
                    raise StudyManifestError(f"{label} node_count must be positive")
            elif field == "source_variant_id":
                if not isinstance(group_value, str) or not group_value:
                    raise StudyManifestError(
                        f"{label} source_variant_id must be nonempty"
                    )
            elif field == "scope":
                if group_value not in {"same_distribution", "distribution_shift"}:
                    raise StudyManifestError(f"{label} scope is unsupported")
            else:
                raise StudyManifestError(f"unsupported pilot summary group field {field}")
        keys.append(tuple(row[field] for field in group_fields))
        _validate_summary_values(row, label)
        if include_resources:
            _validate_static_resources(row["static_resources"], label)
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise StudyManifestError(f"{label} rows must be canonical and unique")


def _validate_summary_values(row: Mapping[str, object], label: str) -> None:
    for field in (
        "parent_graph_count",
        "trace_contrast_count",
        "binary_arm_observation_count",
    ):
        if type(row[field]) is not int or row[field] < 1:
            raise StudyManifestError(f"{label} {field} must be positive integer")
    if (
        type(row["source_tau_nopath_event_count"]) is not int
        or not 0
        <= row["source_tau_nopath_event_count"]
        <= row["trace_contrast_count"]
    ):
        raise StudyManifestError(f"{label} source event count is invalid")
    if row["binary_arm_observation_count"] < row["trace_contrast_count"]:
        raise StudyManifestError(f"{label} binary arm count is too small")
    binary_events = _validate_fraction_payload(
        row["binary_tau_nopath_event_equivalent"],
        f"{label} binary event equivalent",
    )
    if not 0 <= binary_events <= row["trace_contrast_count"]:
        raise StudyManifestError(f"{label} binary event equivalent is out of bounds")

    metrics = _exact_mapping(
        row["metrics"],
        set(_SERVICE_METRIC_FIELDS),
        f"{label} service metrics",
    )
    for field in _SERVICE_METRIC_FIELDS:
        source, binary, _ = _validate_triplet(metrics[field], f"{label} {field}")
        if field in {
            "normalized_restricted_tau_nopath",
            "failure_risk",
            "success_rate",
        }:
            if not 0 <= source <= 1 or not 0 <= binary <= 1:
                raise StudyManifestError(f"{label} {field} arms must be in [0, 1]")
        elif source < 0 or binary < 0:
            raise StudyManifestError(f"{label} accepted_value arms must be nonnegative")

    per_attempt = _exact_mapping(
        row["dynamic_cost_per_attempt"],
        set(_DYNAMIC_COST_FIELDS),
        f"{label} dynamic cost per attempt",
    )
    for field in _DYNAMIC_COST_FIELDS:
        source, binary, _ = _validate_triplet(
            per_attempt[field],
            f"{label} dynamic cost per attempt {field}",
        )
        if source < 0 or binary < 0:
            raise StudyManifestError(f"{label} dynamic cost arms must be nonnegative")

    per_accepted = _exact_mapping(
        row["dynamic_cost_per_accepted"],
        set(_DYNAMIC_COST_FIELDS),
        f"{label} dynamic cost per accepted",
    )
    for field in _DYNAMIC_COST_FIELDS:
        cost = _exact_mapping(
            per_accepted[field],
            {"defined_trace_count", "defined_parent_graph_count", "values"},
            f"{label} per-accepted {field}",
        )
        for count_field, upper in (
            ("defined_trace_count", row["trace_contrast_count"]),
            ("defined_parent_graph_count", row["parent_graph_count"]),
        ):
            if (
                type(cost[count_field]) is not int
                or not 0 <= cost[count_field] <= upper
            ):
                raise StudyManifestError(
                    f"{label} {field} {count_field} is invalid"
                )
        if cost["defined_trace_count"] == 0:
            if cost["defined_parent_graph_count"] != 0 or cost["values"] is not None:
                raise StudyManifestError(
                    f"{label} undefined per-accepted {field} is inconsistent"
                )
        else:
            if cost["defined_parent_graph_count"] < 1 or cost["values"] is None:
                raise StudyManifestError(
                    f"{label} defined per-accepted {field} is inconsistent"
                )
            source, binary, _ = _validate_triplet(
                cost["values"],
                f"{label} dynamic cost per accepted {field}",
            )
            if source < 0 or binary < 0:
                raise StudyManifestError(
                    f"{label} per-accepted cost arms must be nonnegative"
                )


def _validate_static_resources(value: object, label: str) -> None:
    resources = _exact_mapping(
        value,
        _STATIC_RESOURCE_FIELDS,
        f"{label} static resources",
    )
    for field in ("parent_graph_count", "binary_arm_count"):
        if type(resources[field]) is not int or resources[field] < 1:
            raise StudyManifestError(f"{label} resource {field} must be positive")
    if type(resources["all_incidence_deltas_within_one"]) is not bool:
        raise StudyManifestError(f"{label} incidence-match flag must be boolean")
    metrics = _exact_mapping(
        resources["metrics"],
        set(_RESOURCE_FIELDS),
        f"{label} resource metrics",
    )
    for field in _RESOURCE_FIELDS:
        source, binary, _ = _validate_triplet(
            metrics[field],
            f"{label} resource {field}",
        )
        if source < 0 or binary < 0:
            raise StudyManifestError(f"{label} resource arms must be nonnegative")


def _validate_triplet(
    value: object,
    label: str,
) -> tuple[Fraction, Fraction, Fraction]:
    triplet = _exact_mapping(value, {"source", "binary", "difference"}, label)
    source = _validate_fraction_payload(triplet["source"], f"{label} source")
    binary = _validate_fraction_payload(triplet["binary"], f"{label} binary")
    difference = _validate_fraction_payload(
        triplet["difference"],
        f"{label} difference",
    )
    if difference != source - binary:
        raise StudyManifestError(f"{label} difference does not match its arms")
    return source, binary, difference


def _validate_fraction_payload(value: object, label: str) -> Fraction:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(item) is not int for item in value)
        or value[1] <= 0
    ):
        raise StudyManifestError(f"{label} must be [integer, positive integer]")
    fraction = Fraction(value[0], value[1])
    if value != [fraction.numerator, fraction.denominator]:
        raise StudyManifestError(f"{label} must be a canonical fraction")
    return fraction


def _exact_mapping(value: object, fields: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StudyManifestError(f"{label} must be a mapping")
    keys = set(value)
    if keys != fields:
        missing = sorted(fields - keys)
        unknown = sorted(keys - fields, key=repr)
        raise StudyManifestError(
            f"{label} keys mismatch; missing={missing!r}; unknown={unknown!r}"
        )
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list) or not value:
        raise StudyManifestError(f"{label} must be a nonempty list")
    return value


def _validate_digest(value: object, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError(f"{field} must be lowercase SHA-256 hexadecimal")


def _mapping_without_duplicate_keys(pairs):
    mapping = {}
    for key, value in pairs:
        if key in mapping:
            raise StudyManifestError(f"duplicate JSON key {key!r}")
        mapping[key] = value
    return mapping


def _reject_non_json_constant(value: str):
    raise StudyManifestError(f"non-finite JSON constant {value!r} is not allowed")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build exact parent-aware descriptive pilot evidence.",
    )
    parser.add_argument("manifest", help="strict pilot study manifest JSON")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--summary", default=None)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    path = generate_pilot_evidence(
        arguments.manifest,
        workspace_root=arguments.workspace_root,
        summary_path=arguments.summary,
        output_path=arguments.output,
    )
    print(path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PILOT_EVIDENCE_SCHEMA_VERSION",
    "build_pilot_evidence",
    "generate_pilot_evidence",
    "load_pilot_evidence",
    "main",
    "validate_pilot_evidence",
]
