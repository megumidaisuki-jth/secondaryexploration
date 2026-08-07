"""Canonical resumable artifacts for synthetic study parent blocks."""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from secondaryexploration.metrics import RunCostMetrics
from secondaryexploration.optimization import DirectedDemandMatrix
from secondaryexploration.topology import ParentGraphModel

from .paired import TopologyVariant
from .pipeline import SYNTHETIC_PIPELINE_VERSION, SyntheticParentBlockResult
from .study import (
    StudyDesignManifest,
    StudyManifestError,
    StudyParentSeed,
    StudySeedLedger,
    generate_declared_parent_ensemble,
    generate_declared_request_trace,
    validate_study_seed_ledger,
)


BLOCK_ARTIFACT_SCHEMA_VERSION = "synthetic-block-artifact.v1"
STUDY_RUN_SUMMARY_SCHEMA_VERSION = "synthetic-study-run-summary.v1"
_RUN_SUMMARY_TOP_LEVEL_FIELDS = {
    "schema_version",
    "status",
    "manifest_fingerprint",
    "seed_ledger_fingerprint",
    "code_revision",
    "environment",
    "expected_block_count",
    "completed_block_count",
    "total_generation_ns",
    "total_exact_validation_ns",
    "blocks",
    "summary_fingerprint",
}
_RUN_SUMMARY_BLOCK_FIELDS = {
    "block_key",
    "path",
    "artifact_fingerprint",
    "result_fingerprint",
    "generation_ns",
    "validation_ns",
}
_BLOCK_KEY_PATTERN = re.compile(
    r"n[0-9]{4,}-r[0-9]{4,}-(?:er_gnm|barabasi_albert|sbm_fixed_count)\Z"
)
_BLOCK_TOP_LEVEL_FIELDS = {
    "schema_version",
    "pipeline_version",
    "manifest_fingerprint",
    "seed_ledger_fingerprint",
    "code_revision",
    "environment",
    "block",
    "result_fingerprint",
    "result_witness",
    "timing_ns",
    "training",
    "variants",
    "resource_panels",
    "clique_cost_references",
    "held_out",
    "artifact_fingerprint",
}
_PARENT_MODEL_VALUES = (
    "er_gnm",
    "barabasi_albert",
    "sbm_fixed_count",
)


def build_synthetic_block_artifact(
    result: SyntheticParentBlockResult,
    *,
    code_revision: str,
    environment: Mapping[str, object],
    generation_ns: int,
    validation_ns: int,
) -> dict[str, object]:
    """Summarize one fully generated and exactly replay-validated block."""

    if not isinstance(result, SyntheticParentBlockResult):
        raise StudyManifestError("result must be a SyntheticParentBlockResult")
    validate_code_revision(code_revision)
    environment_mapping = _canonical_environment(environment)
    _validate_duration(generation_ns, "generation_ns")
    _validate_duration(validation_ns, "validation_ns")

    trained = {item.variant_id: item for item in result.variants}
    artifact: dict[str, object] = {
        "schema_version": BLOCK_ARTIFACT_SCHEMA_VERSION,
        "pipeline_version": result.pipeline_version,
        "manifest_fingerprint": result.manifest_fingerprint,
        "seed_ledger_fingerprint": result.seed_ledger_fingerprint,
        "code_revision": code_revision,
        "environment": environment_mapping,
        "block": _block_payload(result),
        "result_fingerprint": result.fingerprint,
        "result_witness": result.to_fingerprint_mapping(),
        "timing_ns": {
            "generation": generation_ns,
            "exact_validation": validation_ns,
        },
        "training": {
            "demand_fingerprint": result.training_demand.fingerprint,
            "trace_seeds": [
                _trace_seed_payload(item) for item in result.training_trace_seeds
            ],
            "demand_aware": {
                "manifest_fingerprint": result.demand_aware_result.manifest_fingerprint,
                "seed_topology_fingerprint": (
                    result.demand_aware_result.seed_topology_fingerprint
                ),
                "candidate_pool_fingerprint": (
                    result.demand_aware_result.candidate_pool_fingerprint
                ),
                "search_plan_fingerprint": (
                    result.demand_aware_result.search_plan.fingerprint
                ),
                "proposals_considered": (
                    result.demand_aware_result.proposals_considered
                ),
                "feasible_evaluations": (
                    result.demand_aware_result.feasible_evaluations
                ),
                "accepted_steps": len(result.demand_aware_result.steps),
                "topology_fingerprint": (
                    result.demand_aware_result.score.topology_fingerprint
                ),
                "objective": _fraction_payload(
                    result.demand_aware_result.score.objective_value
                ),
            },
        },
        "variants": [
            {
                "variant_id": item.variant_id,
                "family": item.family,
                "topology_fingerprint": _topology_fingerprint(item.topology),
                "resources": _resource_payload(item.topology.resources),
                "capacity_manifest_fingerprint": (
                    item.capacity_result.manifest_fingerprint
                ),
                "capacity_plan_fingerprint": item.capacity_result.plan.fingerprint,
                "capacity_evaluations": item.capacity_result.evaluation_count,
                "capacity_starting_source": item.capacity_result.starting_source,
                "capacity_score_fingerprint": item.capacity_result.score.fingerprint,
                "initial_state_fingerprint": _state_fingerprint(item.initial_state),
            }
            for item in result.variants
        ],
        "resource_panels": [
            {
                "panel_id": item.panel_id,
                "source_variant_id": item.source_variant_id,
                "binary_variant_ids": list(item.binary_variant_ids),
                "source_incidence_count": item.source_incidence_count,
                "binary_incidence_deltas": list(item.binary_incidence_deltas),
            }
            for item in result.panels
        ],
        "clique_cost_references": [
            {
                "reference_id": item.reference_id,
                "source_variant_id": item.source_variant_id,
                "topology_fingerprint": _topology_fingerprint(item.topology),
                "resources": _resource_payload(item.topology.resources),
            }
            for item in result.clique_cost_references
        ],
        "held_out": [
            {
                "trace_seed": _trace_seed_payload(item.trace_seed),
                "paired_manifest_fingerprint": item.result.manifest_fingerprint,
                "variants": [
                    _held_out_variant_payload(
                        trained[variant_result.variant_id],
                        variant_result.simulation,
                    )
                    for variant_result in item.result.variant_results
                ],
            }
            for item in result.held_out_runs
        ],
    }
    artifact["artifact_fingerprint"] = _mapping_fingerprint(artifact)
    validate_synthetic_block_artifact(artifact)
    return artifact


def validate_synthetic_block_artifact(
    artifact: object,
    *,
    manifest: StudyDesignManifest | None = None,
    ledger: StudySeedLedger | None = None,
    parent_seed: StudyParentSeed | None = None,
    parent_model: str | None = None,
    code_revision: str | None = None,
    environment: Mapping[str, object] | None = None,
) -> None:
    """Reject malformed, corrupted, or context-mismatched block artifacts."""

    top = _expect_mapping(artifact, _BLOCK_TOP_LEVEL_FIELDS, "block artifact")
    if top["schema_version"] != BLOCK_ARTIFACT_SCHEMA_VERSION:
        raise StudyManifestError("unsupported block artifact schema_version")
    if top["pipeline_version"] != SYNTHETIC_PIPELINE_VERSION:
        raise StudyManifestError("unsupported block artifact pipeline_version")
    _validate_digest(top["manifest_fingerprint"], "manifest_fingerprint")
    _validate_digest(top["seed_ledger_fingerprint"], "seed_ledger_fingerprint")
    _validate_digest(top["result_fingerprint"], "result_fingerprint")
    _validate_digest(top["artifact_fingerprint"], "artifact_fingerprint")
    validate_code_revision(top["code_revision"])
    canonical_environment = _canonical_environment(top["environment"])
    if _json_fingerprint(top["result_witness"]) != top["result_fingerprint"]:
        raise StudyManifestError(
            "result_fingerprint does not match the complete result witness"
        )

    supplied_fingerprint = top["artifact_fingerprint"]
    without_fingerprint = dict(top)
    del without_fingerprint["artifact_fingerprint"]
    if supplied_fingerprint != _mapping_fingerprint(without_fingerprint):
        raise StudyManifestError("block artifact fingerprint does not match its content")

    block = _expect_mapping(
        top["block"],
        {
            "node_count",
            "parent_replicate",
            "parent_model",
            "ensemble_base_seed",
            "capacity_search_seed",
            "binary_matching_seed",
            "draw_root_seed",
            "accepted_attempt",
            "draw_seed",
            "edge_count",
        },
        "block",
    )
    for name in (
        "node_count",
        "parent_replicate",
        "ensemble_base_seed",
        "capacity_search_seed",
        "binary_matching_seed",
        "draw_root_seed",
        "accepted_attempt",
        "draw_seed",
        "edge_count",
    ):
        _validate_nonnegative_int(block[name], f"block {name}")
    if block["parent_model"] not in _PARENT_MODEL_VALUES:
        raise StudyManifestError("block parent_model is unsupported")
    timing = _expect_mapping(
        top["timing_ns"],
        {"generation", "exact_validation"},
        "timing_ns",
    )
    _validate_duration(timing["generation"], "generation timing")
    _validate_duration(timing["exact_validation"], "validation timing")
    training = _expect_mapping(
        top["training"],
        {"demand_fingerprint", "trace_seeds", "demand_aware"},
        "training",
    )
    _validate_digest(training["demand_fingerprint"], "demand_fingerprint")
    if not isinstance(training["trace_seeds"], list) or not training["trace_seeds"]:
        raise StudyManifestError("training trace_seeds must be a nonempty list")
    for item in training["trace_seeds"]:
        _validate_trace_seed_mapping(item, "training trace_seed")
    demand_aware = _expect_mapping(
        training["demand_aware"],
        {
            "manifest_fingerprint",
            "seed_topology_fingerprint",
            "candidate_pool_fingerprint",
            "search_plan_fingerprint",
            "proposals_considered",
            "feasible_evaluations",
            "accepted_steps",
            "topology_fingerprint",
            "objective",
        },
        "demand_aware",
    )
    for name in (
        "manifest_fingerprint",
        "seed_topology_fingerprint",
        "candidate_pool_fingerprint",
        "search_plan_fingerprint",
        "topology_fingerprint",
    ):
        _validate_digest(demand_aware[name], name)
    _validate_fraction_payload(demand_aware["objective"], "objective")
    for name in ("proposals_considered", "feasible_evaluations", "accepted_steps"):
        _validate_nonnegative_int(demand_aware[name], name)
    if demand_aware["feasible_evaluations"] > demand_aware["proposals_considered"]:
        raise StudyManifestError("demand-aware feasible evaluations exceed proposals")

    variants = _expect_list(top["variants"], "variants", nonempty=True)
    variant_ids = []
    variant_values: dict[object, Mapping[str, object]] = {}
    for item in variants:
        value = _expect_mapping(
            item,
            {
                "variant_id",
                "family",
                "topology_fingerprint",
                "resources",
                "capacity_manifest_fingerprint",
                "capacity_plan_fingerprint",
                "capacity_evaluations",
                "capacity_starting_source",
                "capacity_score_fingerprint",
                "initial_state_fingerprint",
            },
            "variant",
        )
        variant_ids.append(value["variant_id"])
        if not isinstance(value["variant_id"], str) or not value["variant_id"]:
            raise StudyManifestError("variant_id must be a nonempty string")
        if not isinstance(value["family"], str) or not value["family"]:
            raise StudyManifestError("variant family must be a nonempty string")
        variant_values[value["variant_id"]] = value
        for name in (
            "topology_fingerprint",
            "capacity_manifest_fingerprint",
            "capacity_plan_fingerprint",
            "capacity_score_fingerprint",
            "initial_state_fingerprint",
        ):
            _validate_digest(value[name], name)
        _validate_resource_mapping(value["resources"], "variant resources")
        _validate_nonnegative_int(
            value["capacity_evaluations"],
            "capacity_evaluations",
        )
        if value["capacity_starting_source"] not in {"uniform", "load-risk"}:
            raise StudyManifestError("capacity_starting_source is unsupported")
    if variant_ids != sorted(variant_ids) or len(set(variant_ids)) != len(variant_ids):
        raise StudyManifestError("artifact variants must be canonical and unique")

    panels = _expect_list(top["resource_panels"], "resource_panels", nonempty=True)
    panel_values = []
    for item in panels:
        panel = _expect_mapping(
            item,
            {
                "panel_id",
                "source_variant_id",
                "binary_variant_ids",
                "source_incidence_count",
                "binary_incidence_deltas",
            },
            "resource panel",
        )
        panel_values.append(panel)
        if not isinstance(panel["binary_variant_ids"], list) or not isinstance(
            panel["binary_incidence_deltas"], list
        ):
            raise StudyManifestError("resource panel binary fields must be lists")
        if len(panel["binary_variant_ids"]) != len(panel["binary_incidence_deltas"]):
            raise StudyManifestError("resource panel binary fields are not aligned")
        _validate_nonnegative_int(
            panel["source_incidence_count"],
            "source_incidence_count",
        )
        if any(delta not in {-1, 0, 1} for delta in panel["binary_incidence_deltas"]):
            raise StudyManifestError("binary incidence deltas must be -1, 0, or 1")
    references = _expect_list(
        top["clique_cost_references"],
        "clique_cost_references",
        nonempty=True,
    )
    for item in references:
        value = _expect_mapping(
            item,
            {
                "reference_id",
                "source_variant_id",
                "topology_fingerprint",
                "resources",
            },
            "clique cost reference",
        )
        _validate_digest(value["topology_fingerprint"], "clique topology fingerprint")
        _validate_resource_mapping(value["resources"], "clique resources")

    held_out = _expect_list(top["held_out"], "held_out", nonempty=True)
    held_out_keys = []
    for item in held_out:
        value = _expect_mapping(
            item,
            {"trace_seed", "paired_manifest_fingerprint", "variants"},
            "held_out record",
        )
        trace_seed = _validate_trace_seed_mapping(value["trace_seed"], "held-out trace_seed")
        held_out_keys.append(
            (
                trace_seed["regime_id"],
                trace_seed["trace_replicate"],
            )
        )
        _validate_digest(
            value["paired_manifest_fingerprint"],
            "paired_manifest_fingerprint",
        )
        run_variants = _expect_list(
            value["variants"],
            "held-out variants",
            nonempty=True,
        )
        observed_variant_ids = []
        for run_variant in run_variants:
            observed_variant_ids.append(
                _validate_held_out_variant_mapping(
                    run_variant,
                    resources_by_variant={
                        key: value["resources"]
                        for key, value in variant_values.items()
                    },
                    family_by_variant={
                        key: value["family"]
                        for key, value in variant_values.items()
                    },
                    amount_bounds=(
                        None
                        if manifest is None
                        else (
                            min(amount for amount, _ in manifest.amount_weights),
                            max(amount for amount, _ in manifest.amount_weights),
                        )
                    ),
                )
            )
        if observed_variant_ids != variant_ids:
            raise StudyManifestError(
                "held-out variants do not match the artifact variant registry"
            )
    if held_out_keys != sorted(held_out_keys) or len(set(held_out_keys)) != len(held_out_keys):
        raise StudyManifestError("held-out artifact records must be canonical and unique")
    _validate_summary_against_result_witness(top)

    if manifest is not None and top["manifest_fingerprint"] != manifest.fingerprint:
        raise StudyManifestError("artifact does not match the expected study manifest")
    if ledger is not None and top["seed_ledger_fingerprint"] != ledger.fingerprint:
        raise StudyManifestError("artifact does not match the expected seed ledger")
    if parent_seed is not None:
        expected = (
            parent_seed.node_count,
            parent_seed.parent_replicate,
            parent_seed.ensemble_base_seed,
            parent_seed.capacity_search_seed,
            parent_seed.binary_matching_seed,
        )
        observed = (
            block["node_count"],
            block["parent_replicate"],
            block["ensemble_base_seed"],
            block["capacity_search_seed"],
            block["binary_matching_seed"],
        )
        if observed != expected:
            raise StudyManifestError("artifact does not match the expected parent seed")
    if parent_model is not None and block["parent_model"] != parent_model:
        raise StudyManifestError("artifact does not match the expected parent model")
    if code_revision is not None and top["code_revision"] != code_revision:
        raise StudyManifestError("artifact does not match the expected code revision")
    if environment is not None and canonical_environment != _canonical_environment(environment):
        raise StudyManifestError("artifact does not match the expected environment")
    if manifest is not None and ledger is not None and parent_seed is not None:
        _validate_artifact_scientific_context(
            top,
            block,
            training,
            variants,
            panel_values,
            held_out,
            manifest,
            ledger,
            parent_seed,
            parent_model,
        )


def load_synthetic_block_artifact(
    path: str | Path,
    **expected: object,
) -> dict[str, object]:
    """Load strict UTF-8 JSON and validate a resumable block artifact."""

    artifact = _load_strict_json(path)
    validate_synthetic_block_artifact(artifact, **expected)
    return dict(artifact)


def build_study_run_summary(
    manifest: StudyDesignManifest,
    ledger: StudySeedLedger,
    *,
    code_revision: str,
    environment: Mapping[str, object],
    block_artifacts: list[Mapping[str, object]],
) -> dict[str, object]:
    """Build the canonical progress/complete index for all block artifacts."""

    validate_code_revision(code_revision)
    validate_study_seed_ledger(ledger, manifest)
    expected_block_keys = tuple(
        f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}"
        for seed in ledger.parent_seeds
        for model in _PARENT_MODEL_VALUES
    )
    expected_block_count = len(expected_block_keys)
    seeds_by_key = {
        (seed.node_count, seed.parent_replicate): seed
        for seed in ledger.parent_seeds
    }
    records = []
    for artifact in block_artifacts:
        top = _expect_mapping(artifact, _BLOCK_TOP_LEVEL_FIELDS, "block artifact")
        block = _expect_mapping(
            top["block"],
            {
                "node_count",
                "parent_replicate",
                "parent_model",
                "ensemble_base_seed",
                "capacity_search_seed",
                "binary_matching_seed",
                "draw_root_seed",
                "accepted_attempt",
                "draw_seed",
                "edge_count",
            },
            "block",
        )
        seed_key = (block["node_count"], block["parent_replicate"])
        try:
            parent_seed = seeds_by_key[seed_key]
        except KeyError as exc:
            raise StudyManifestError(
                "summary artifact parent is not registered by the ledger"
            ) from exc
        validate_synthetic_block_artifact(
            top,
            manifest=manifest,
            ledger=ledger,
            parent_seed=parent_seed,
            parent_model=block["parent_model"],
            code_revision=code_revision,
            environment=environment,
        )
        block_key = (
            f"n{parent_seed.node_count:04d}-r{parent_seed.parent_replicate:04d}-"
            f"{block['parent_model']}"
        )
        if block_key not in expected_block_keys:
            raise StudyManifestError("summary block_key is not registered by the ledger")
        timing = _expect_mapping(
            top["timing_ns"],
            {"generation", "exact_validation"},
            "timing_ns",
        )
        records.append(
            {
                "block_key": block_key,
                "path": f"blocks/{block_key}.json",
                "artifact_fingerprint": top["artifact_fingerprint"],
                "result_fingerprint": top["result_fingerprint"],
                "generation_ns": timing["generation"],
                "validation_ns": timing["exact_validation"],
            }
        )
    if len(records) > expected_block_count:
        raise StudyManifestError("completed blocks exceed expected_block_count")
    records.sort(key=lambda item: item["block_key"])
    block_keys = [item.get("block_key") for item in records]
    if len(set(block_keys)) != len(block_keys):
        raise StudyManifestError("summary block records must be unique")
    summary: dict[str, object] = {
        "schema_version": STUDY_RUN_SUMMARY_SCHEMA_VERSION,
        "status": "complete" if len(records) == expected_block_count else "in_progress",
        "manifest_fingerprint": manifest.fingerprint,
        "seed_ledger_fingerprint": ledger.fingerprint,
        "code_revision": code_revision,
        "environment": _canonical_environment(environment),
        "expected_block_count": expected_block_count,
        "completed_block_count": len(records),
        "total_generation_ns": sum(
            _record_duration(item, "generation_ns") for item in records
        ),
        "total_exact_validation_ns": sum(
            _record_duration(item, "validation_ns") for item in records
        ),
        "blocks": records,
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


def validate_study_run_summary(
    summary: object,
    *,
    manifest: StudyDesignManifest | None = None,
    ledger: StudySeedLedger | None = None,
    code_revision: str | None = None,
    environment: Mapping[str, object] | None = None,
    block_artifacts: list[Mapping[str, object]] | None = None,
) -> None:
    """Reject malformed, corrupted, or context-mismatched run indexes."""

    top = _expect_mapping(summary, _RUN_SUMMARY_TOP_LEVEL_FIELDS, "run summary")
    if top["schema_version"] != STUDY_RUN_SUMMARY_SCHEMA_VERSION:
        raise StudyManifestError("unsupported run summary schema_version")
    if top["status"] not in {"in_progress", "complete"}:
        raise StudyManifestError("run summary status is unsupported")
    for name in (
        "manifest_fingerprint",
        "seed_ledger_fingerprint",
        "summary_fingerprint",
    ):
        _validate_digest(top[name], name)
    validate_code_revision(top["code_revision"])
    canonical_environment = _canonical_environment(top["environment"])
    for name in (
        "expected_block_count",
        "completed_block_count",
        "total_generation_ns",
        "total_exact_validation_ns",
    ):
        _validate_nonnegative_int(top[name], name)
    if top["expected_block_count"] < 1:
        raise StudyManifestError("expected_block_count must be positive")
    if top["completed_block_count"] > top["expected_block_count"]:
        raise StudyManifestError("completed blocks exceed expected_block_count")
    expected_status = (
        "complete"
        if top["completed_block_count"] == top["expected_block_count"]
        else "in_progress"
    )
    if top["status"] != expected_status:
        raise StudyManifestError("run summary status does not match block counts")

    records = _expect_list(top["blocks"], "run summary blocks", nonempty=False)
    if len(records) != top["completed_block_count"]:
        raise StudyManifestError("run summary block count does not match records")
    keys: list[str] = []
    generation_total = 0
    validation_total = 0
    for item in records:
        record = _expect_mapping(item, _RUN_SUMMARY_BLOCK_FIELDS, "summary block")
        block_key = record["block_key"]
        if (
            not isinstance(block_key, str)
            or _BLOCK_KEY_PATTERN.fullmatch(block_key) is None
        ):
            raise StudyManifestError("summary block_key is malformed")
        if record["path"] != f"blocks/{block_key}.json":
            raise StudyManifestError("summary block path is not canonical")
        keys.append(block_key)
        for name in ("artifact_fingerprint", "result_fingerprint"):
            _validate_digest(record[name], name)
        _validate_duration(record["generation_ns"], "generation_ns")
        _validate_duration(record["validation_ns"], "validation_ns")
        generation_total += record["generation_ns"]
        validation_total += record["validation_ns"]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise StudyManifestError("run summary block records must be canonical and unique")
    if generation_total != top["total_generation_ns"]:
        raise StudyManifestError("run summary generation total does not match records")
    if validation_total != top["total_exact_validation_ns"]:
        raise StudyManifestError("run summary validation total does not match records")
    without_fingerprint = dict(top)
    del without_fingerprint["summary_fingerprint"]
    if top["summary_fingerprint"] != _mapping_fingerprint(without_fingerprint):
        raise StudyManifestError("run summary fingerprint does not match its content")

    if manifest is not None and top["manifest_fingerprint"] != manifest.fingerprint:
        raise StudyManifestError("run summary does not match the expected study manifest")
    if ledger is not None and top["seed_ledger_fingerprint"] != ledger.fingerprint:
        raise StudyManifestError("run summary does not match the expected seed ledger")
    if code_revision is not None and top["code_revision"] != code_revision:
        raise StudyManifestError("run summary does not match the expected code revision")
    if environment is not None and canonical_environment != _canonical_environment(environment):
        raise StudyManifestError("run summary does not match the expected environment")
    if manifest is not None and ledger is not None:
        validate_study_seed_ledger(ledger, manifest)
        expected_keys = tuple(
            sorted(
                f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}"
                for seed in ledger.parent_seeds
                for model in _PARENT_MODEL_VALUES
            )
        )
        if top["expected_block_count"] != len(expected_keys):
            raise StudyManifestError("run summary expected count does not match ledger")
        if not set(keys).issubset(expected_keys):
            raise StudyManifestError("run summary contains an unregistered block")
        if top["status"] == "complete" and tuple(keys) != expected_keys:
            raise StudyManifestError("complete run summary omits registered blocks")
    if block_artifacts is not None:
        if manifest is None or ledger is None:
            raise StudyManifestError(
                "manifest and ledger are required to bind summary block artifacts"
            )
        rebuilt = build_study_run_summary(
            manifest,
            ledger,
            code_revision=top["code_revision"],
            environment=canonical_environment,
            block_artifacts=block_artifacts,
        )
        if dict(top) != rebuilt:
            raise StudyManifestError("run summary does not match its block artifacts")


def load_study_run_summary(
    path: str | Path,
    **expected: object,
) -> dict[str, object]:
    """Load strict UTF-8 JSON and validate a synthetic-study run index."""

    summary = _load_strict_json(path)
    validate_study_run_summary(summary, **expected)
    return dict(summary)


def atomic_write_json(path: str | Path, value: Mapping[str, object]) -> None:
    """Durably replace one JSON file using a same-directory temporary file."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise StudyManifestError("artifact content is not strict canonical JSON") from exc
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_name = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    finally:
        if temporary_name is not None:
            temporary = Path(temporary_name)
            if temporary.exists():
                temporary.unlink()


def _block_payload(result: SyntheticParentBlockResult) -> dict[str, object]:
    seed = result.parent_seed
    draw = result.parent_draw
    return {
        "node_count": seed.node_count,
        "parent_replicate": seed.parent_replicate,
        "parent_model": result.parent_model.value,
        "ensemble_base_seed": seed.ensemble_base_seed,
        "capacity_search_seed": seed.capacity_search_seed,
        "binary_matching_seed": seed.binary_matching_seed,
        "draw_root_seed": draw.root_seed,
        "accepted_attempt": draw.accepted_attempt,
        "draw_seed": draw.draw_seed,
        "edge_count": draw.graph.edge_count,
    }


def _trace_seed_payload(item) -> dict[str, object]:
    return {
        "node_count": item.node_count,
        "parent_replicate": item.parent_replicate,
        "split": item.split,
        "regime_id": item.regime_id,
        "trace_replicate": item.trace_replicate,
        "trace_root_seed": item.trace_root_seed,
        "routing_root_seed": item.routing_root_seed,
    }


def _held_out_variant_payload(trained, simulation) -> dict[str, object]:
    variant = TopologyVariant(
        trained.variant_id,
        trained.family,
        trained.topology,
        trained.initial_state,
    )
    costs = RunCostMetrics(variant, simulation)
    return {
        "variant_id": trained.variant_id,
        "family": trained.family,
        "horizon": simulation.horizon,
        "tau_dep": _event_payload(simulation.tau_dep),
        "tau_nopath": _event_payload(simulation.tau_nopath),
        "tau_rej": _event_payload(simulation.tau_rej),
        "accepted_request_count": costs.accepted_request_count,
        "accepted_value": costs.accepted_value,
        "success_rate": (
            None
            if simulation.success_rate is None
            else _fraction_payload(simulation.success_rate)
        ),
        "initial_state_fingerprint": _state_fingerprint(simulation.initial_state),
        "final_state_fingerprint": _state_fingerprint(simulation.final_state),
        "dynamic_costs": {
            "traversed_hyperedge_count": costs.traversed_hyperedge_count,
            "signaled_participant_slots": costs.signaled_participant_slots,
            "quadratic_coordination_exposure": (
                costs.quadratic_coordination_exposure
            ),
            "unique_signaled_participants": costs.unique_signaled_participants,
            "route_arity_histogram": [
                [arity, count] for arity, count in costs.route_arity_histogram
            ],
        },
    }


def _event_payload(observation) -> dict[str, object]:
    return {
        "observed": observation.observed,
        "request_index": observation.request_index,
    }


def _resource_payload(resources) -> dict[str, int]:
    return {
        "node_count": resources.node_count,
        "hyperedge_count": resources.hyperedge_count,
        "incidence_count": resources.incidence_count,
        "maximum_arity": resources.maximum_arity,
        "pairwise_member_exposure": resources.pairwise_member_exposure,
    }


def _topology_fingerprint(topology) -> str:
    return _json_fingerprint(
        {
            "nodes": topology.nodes,
            "hyperedges": [
                [edge.hyperedge_id, edge.members]
                for edge in topology.hyperedges
            ],
        }
    )


def _state_fingerprint(state) -> str:
    return _json_fingerprint(
        {
            "nodes": state.nodes,
            "hyperedges": [
                [edge.hyperedge_id, edge.balances]
                for edge in state.hyperedges
            ],
        }
    )


def _fraction_payload(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _validate_held_out_variant_mapping(
    value: object,
    *,
    resources_by_variant: Mapping[object, object],
    family_by_variant: Mapping[object, object],
    amount_bounds: tuple[int, int] | None,
) -> object:
    item = _expect_mapping(
        value,
        {
            "variant_id",
            "family",
            "horizon",
            "tau_dep",
            "tau_nopath",
            "tau_rej",
            "accepted_request_count",
            "accepted_value",
            "success_rate",
            "initial_state_fingerprint",
            "final_state_fingerprint",
            "dynamic_costs",
        },
        "held-out variant",
    )
    variant_id = item["variant_id"]
    if variant_id not in resources_by_variant:
        raise StudyManifestError("held-out variant is not in the trained registry")
    if item["family"] != family_by_variant[variant_id]:
        raise StudyManifestError("held-out family does not match the trained registry")
    resources = _expect_mapping(
        resources_by_variant[variant_id],
        {
            "node_count",
            "hyperedge_count",
            "incidence_count",
            "maximum_arity",
            "pairwise_member_exposure",
        },
        "held-out variant resources",
    )
    horizon = item["horizon"]
    _validate_nonnegative_int(horizon, "held-out horizon")
    for name in ("tau_dep", "tau_nopath", "tau_rej"):
        event = _expect_mapping(item[name], {"observed", "request_index"}, name)
        if (
            type(event["observed"]) is not bool
            or type(event["request_index"]) is not int
            or not 0 <= event["request_index"] <= horizon
            or (not event["observed"] and event["request_index"] != horizon)
            or (name != "tau_dep" and event["observed"] and event["request_index"] < 1)
        ):
            raise StudyManifestError(f"{name} is malformed")
    accepted_count = item["accepted_request_count"]
    accepted_value = item["accepted_value"]
    if type(accepted_count) is not int or not 0 <= accepted_count <= horizon:
        raise StudyManifestError("accepted_request_count is outside the horizon")
    _validate_nonnegative_int(accepted_value, "accepted_value")
    if horizon == 0:
        if item["success_rate"] is not None:
            raise StudyManifestError("zero-horizon success_rate must be null")
    else:
        _validate_fraction_payload(item["success_rate"], "success_rate")
        if Fraction(*item["success_rate"]) != Fraction(accepted_count, horizon):
            raise StudyManifestError("success_rate does not match accepted_request_count")
    if amount_bounds is not None:
        minimum, maximum = amount_bounds
        if not minimum * accepted_count <= accepted_value <= maximum * accepted_count:
            raise StudyManifestError("accepted_value is inconsistent with accepted count")
    _validate_digest(item["initial_state_fingerprint"], "initial_state_fingerprint")
    _validate_digest(item["final_state_fingerprint"], "final_state_fingerprint")
    dynamic = _expect_mapping(
        item["dynamic_costs"],
        {
            "traversed_hyperedge_count",
            "signaled_participant_slots",
            "quadratic_coordination_exposure",
            "unique_signaled_participants",
            "route_arity_histogram",
        },
        "dynamic_costs",
    )
    if not isinstance(dynamic["route_arity_histogram"], list):
        raise StudyManifestError("route_arity_histogram must be a list")
    for name in (
        "traversed_hyperedge_count",
        "signaled_participant_slots",
        "quadratic_coordination_exposure",
        "unique_signaled_participants",
    ):
        _validate_nonnegative_int(dynamic[name], name)
    histogram = dynamic["route_arity_histogram"]
    if any(
        not isinstance(pair, list)
        or len(pair) != 2
        or type(pair[0]) is not int
        or type(pair[1]) is not int
        or pair[0] < 2
        or pair[1] < 0
        for pair in histogram
    ):
        raise StudyManifestError("route_arity_histogram is malformed")
    arities = [pair[0] for pair in histogram]
    if arities != sorted(arities) or len(set(arities)) != len(arities):
        raise StudyManifestError("route_arity_histogram must be canonical")
    if dynamic["traversed_hyperedge_count"] != sum(pair[1] for pair in histogram):
        raise StudyManifestError("traversed count does not match arity histogram")
    if dynamic["signaled_participant_slots"] != sum(
        pair[0] * pair[1] for pair in histogram
    ):
        raise StudyManifestError("participant slots do not match arity histogram")
    if dynamic["quadratic_coordination_exposure"] != sum(
        pair[0] * pair[0] * pair[1] for pair in histogram
    ):
        raise StudyManifestError("coordination exposure does not match arity histogram")
    if dynamic["unique_signaled_participants"] > resources["node_count"] * horizon:
        raise StudyManifestError("unique signaled participants exceed the horizon bound")
    return variant_id


def _validate_trace_seed_mapping(value: object, context: str) -> Mapping[str, object]:
    return _expect_mapping(
        value,
        {
            "node_count",
            "parent_replicate",
            "split",
            "regime_id",
            "trace_replicate",
            "trace_root_seed",
            "routing_root_seed",
        },
        context,
    )


def _validate_artifact_scientific_context(
    top: Mapping[str, object],
    block: Mapping[str, object],
    training: Mapping[str, object],
    variants: list[object],
    panels: list[Mapping[str, object]],
    held_out: list[object],
    manifest: StudyDesignManifest,
    ledger: StudySeedLedger,
    parent_seed: StudyParentSeed,
    parent_model: str | None,
) -> None:
    validate_study_seed_ledger(ledger, manifest)
    model_value = block["parent_model"] if parent_model is None else parent_model
    try:
        model = ParentGraphModel(model_value)
    except (TypeError, ValueError) as exc:
        raise StudyManifestError("artifact parent model is unsupported") from exc
    ensemble = generate_declared_parent_ensemble(manifest, parent_seed)
    draw = {
        ParentGraphModel.ER_GNM: ensemble.er,
        ParentGraphModel.BARABASI_ALBERT: ensemble.ba,
        ParentGraphModel.SBM_FIXED_COUNT: ensemble.sbm,
    }[model]
    expected_block = {
        "node_count": parent_seed.node_count,
        "parent_replicate": parent_seed.parent_replicate,
        "parent_model": model.value,
        "ensemble_base_seed": parent_seed.ensemble_base_seed,
        "capacity_search_seed": parent_seed.capacity_search_seed,
        "binary_matching_seed": parent_seed.binary_matching_seed,
        "draw_root_seed": draw.root_seed,
        "accepted_attempt": draw.accepted_attempt,
        "draw_seed": draw.draw_seed,
        "edge_count": draw.graph.edge_count,
    }
    if dict(block) != expected_block:
        raise StudyManifestError("artifact parent draw does not match exact regeneration")

    block_traces = tuple(
        item
        for item in ledger.trace_seeds
        if item.node_count == parent_seed.node_count
        and item.parent_replicate == parent_seed.parent_replicate
    )
    expected_training = [
        _trace_seed_payload(item) for item in block_traces if item.split == "training"
    ]
    if training["trace_seeds"] != expected_training:
        raise StudyManifestError("artifact training seeds do not match the exact ledger")
    regenerated_demand = DirectedDemandMatrix.from_requests(
        draw.graph.nodes,
        tuple(
            request
            for trace_seed in block_traces
            if trace_seed.split == "training"
            for request in generate_declared_request_trace(
                manifest,
                trace_seed,
            ).requests
        ),
    )
    if training["demand_fingerprint"] != regenerated_demand.fingerprint:
        raise StudyManifestError("training demand does not match exact trace regeneration")
    expected_held_out = [
        _trace_seed_payload(item) for item in block_traces if item.split == "test"
    ]
    observed_held_out = [
        dict(_expect_mapping(item, {"trace_seed", "paired_manifest_fingerprint", "variants"}, "held_out"))[
            "trace_seed"
        ]
        for item in held_out
    ]
    if observed_held_out != expected_held_out:
        raise StudyManifestError("artifact held-out seeds do not match the exact ledger")

    variant_mappings = [
        _expect_mapping(
            item,
            {
                "variant_id",
                "family",
                "topology_fingerprint",
                "resources",
                "capacity_manifest_fingerprint",
                "capacity_plan_fingerprint",
                "capacity_evaluations",
                "capacity_starting_source",
                "capacity_score_fingerprint",
                "initial_state_fingerprint",
            },
            "variant",
        )
        for item in variants
    ]
    by_id = {item["variant_id"]: item for item in variant_mappings}
    source_ids = set(manifest.topology_families)
    if not source_ids <= set(by_id):
        raise StudyManifestError("artifact is missing a declared topology family")
    for variant_id, item in by_id.items():
        resources = _expect_mapping(
            item["resources"],
            {
                "node_count",
                "hyperedge_count",
                "incidence_count",
                "maximum_arity",
                "pairwise_member_exposure",
            },
            "variant resources",
        )
        if resources["node_count"] != parent_seed.node_count:
            raise StudyManifestError("variant resource node count does not match parent")
        if item["capacity_evaluations"] != manifest.capacity_search.evaluation_budget:
            raise StudyManifestError("variant capacity budget does not match manifest")
        expected_family = variant_id if variant_id in source_ids else "binary-matched"
        if item["family"] != expected_family:
            raise StudyManifestError("variant family does not match its registry role")
        if variant_id not in source_ids and resources["maximum_arity"] != 2:
            raise StudyManifestError("binary-matched artifact variant is not binary")
    if len({item["capacity_manifest_fingerprint"] for item in variant_mappings}) != 1:
        raise StudyManifestError("artifact variants do not share one capacity manifest")
    if len({item["capacity_plan_fingerprint"] for item in variant_mappings}) != 1:
        raise StudyManifestError("artifact variants do not share one capacity plan")

    panel_source_ids = []
    covered_variant_ids = set()
    for panel in panels:
        source_id = panel["source_variant_id"]
        binary_ids = panel["binary_variant_ids"]
        deltas = panel["binary_incidence_deltas"]
        if source_id not in by_id or any(binary_id not in by_id for binary_id in binary_ids):
            raise StudyManifestError("resource panel references an unknown variant")
        source_resources = by_id[source_id]["resources"]
        if panel["source_incidence_count"] != source_resources["incidence_count"]:
            raise StudyManifestError("panel source incidence does not match resources")
        for binary_id, delta in zip(binary_ids, deltas):
            if (
                by_id[binary_id]["resources"]["incidence_count"]
                != panel["source_incidence_count"] + delta
            ):
                raise StudyManifestError("panel binary incidence delta is inconsistent")
        panel_source_ids.append(source_id)
        covered_variant_ids.update((source_id, *binary_ids))
    if set(panel_source_ids) != source_ids or len(panel_source_ids) != len(source_ids):
        raise StudyManifestError("resource panels do not cover each source exactly once")
    if covered_variant_ids != set(by_id):
        raise StudyManifestError("resource panels and artifact variants do not cover each other")

    expected_horizon = manifest.requests_per_node * parent_seed.node_count
    for held_out_record in held_out:
        record = _expect_mapping(
            held_out_record,
            {"trace_seed", "paired_manifest_fingerprint", "variants"},
            "held_out",
        )
        for variant in record["variants"]:
            if variant["horizon"] != expected_horizon:
                raise StudyManifestError("held-out horizon does not match the manifest")


def _validate_summary_against_result_witness(top: Mapping[str, object]) -> None:
    witness = _expect_mapping(
        top["result_witness"],
        {
            "pipeline_version",
            "manifest_fingerprint",
            "seed_ledger_fingerprint",
            "parent",
            "training_trace_seeds",
            "training_demand",
            "demand_topology",
            "variants",
            "panels",
            "clique_cost_references",
            "held_out",
        },
        "result_witness",
    )
    if (
        witness["pipeline_version"] != top["pipeline_version"]
        or witness["manifest_fingerprint"] != top["manifest_fingerprint"]
        or witness["seed_ledger_fingerprint"] != top["seed_ledger_fingerprint"]
    ):
        raise StudyManifestError("result witness identity does not match the artifact")
    parent_witness = _expect_sequence(witness["parent"], 13, "parent witness")
    block = top["block"]
    if (
        block["node_count"],
        block["parent_replicate"],
        block["ensemble_base_seed"],
        block["capacity_search_seed"],
        block["binary_matching_seed"],
        block["parent_model"],
        block["draw_root_seed"],
        block["accepted_attempt"],
        block["draw_seed"],
        block["edge_count"],
    ) != (
        parent_witness[0],
        parent_witness[1],
        parent_witness[2],
        parent_witness[3],
        parent_witness[4],
        parent_witness[5],
        parent_witness[6],
        parent_witness[7],
        parent_witness[8],
        len(_expect_sequence_any(parent_witness[12], "parent edge witness")),
    ):
        raise StudyManifestError("block summary does not match parent witness")
    training = top["training"]
    if training["demand_fingerprint"] != witness["training_demand"]:
        raise StudyManifestError("training demand summary does not match result witness")
    witness_training_seeds = []
    for seed_value in _expect_sequence_any(
        witness["training_trace_seeds"],
        "training seed witness",
    ):
        seed = _expect_sequence(seed_value, 7, "training seed witness")
        witness_training_seeds.append(
            {
                "node_count": seed[0],
                "parent_replicate": seed[1],
                "split": seed[2],
                "regime_id": seed[3],
                "trace_replicate": seed[4],
                "trace_root_seed": seed[5],
                "routing_root_seed": seed[6],
            }
        )
    if training["trace_seeds"] != witness_training_seeds:
        raise StudyManifestError("training seeds do not match result witness")
    demand_witness = _expect_sequence(
        witness["demand_topology"],
        8,
        "demand topology witness",
    )
    demand_score = _expect_sequence(demand_witness[7], 11, "demand score witness")
    demand_summary = training["demand_aware"]
    expected_demand_summary = {
        "manifest_fingerprint": demand_witness[0],
        "seed_topology_fingerprint": demand_witness[1],
        "candidate_pool_fingerprint": demand_witness[2],
        "search_plan_fingerprint": demand_witness[3],
        "proposals_considered": len(_expect_sequence_any(demand_witness[4], "proposals")),
        "feasible_evaluations": demand_witness[5],
        "accepted_steps": len(_expect_sequence_any(demand_witness[6], "steps")),
        "topology_fingerprint": demand_score[1],
        "objective": list(_expect_sequence(demand_score[10], 2, "objective witness")),
    }
    if dict(demand_summary) != expected_demand_summary:
        raise StudyManifestError("demand-aware summary does not match result witness")

    witness_variants = _expect_sequence_any(witness["variants"], "variant witness")
    artifact_variants = top["variants"]
    if len(witness_variants) != len(artifact_variants):
        raise StudyManifestError("variant summary count does not match result witness")
    topology_by_id: dict[object, tuple[list[object], list[object]]] = {}
    family_by_id: dict[object, object] = {}
    expected_variant_summaries = []
    for value in witness_variants:
        variant = _expect_sequence(value, 4, "variant witness")
        topology = _expect_sequence(variant[2], 2, "topology witness")
        nodes = list(_expect_sequence_any(topology[0], "topology nodes"))
        edges = list(_expect_sequence_any(topology[1], "topology edges"))
        topology_by_id[variant[0]] = (nodes, edges)
        family_by_id[variant[0]] = variant[1]
        resources = _resources_from_topology_witness(nodes, edges)
        capacity = _expect_sequence(variant[3], 9, "capacity witness")
        expected_variant_summaries.append(
            {
                "variant_id": variant[0],
                "family": variant[1],
                "topology_fingerprint": _json_fingerprint(
                    {"nodes": nodes, "hyperedges": edges}
                ),
                "resources": resources,
                "capacity_manifest_fingerprint": capacity[0],
                "capacity_plan_fingerprint": capacity[2],
                "capacity_evaluations": 2
                + len(_expect_sequence_any(capacity[6], "capacity proposals")),
                "capacity_starting_source": capacity[5],
                "capacity_score_fingerprint": capacity[8],
            }
        )
    for expected, observed in zip(expected_variant_summaries, artifact_variants):
        comparable = dict(observed)
        comparable.pop("initial_state_fingerprint")
        if comparable != expected:
            raise StudyManifestError("variant summary does not match result witness")

    expected_panels = []
    for value in _expect_sequence_any(witness["panels"], "panel witness"):
        panel = _expect_sequence(value, 5, "panel witness")
        expected_panels.append(
            {
                "panel_id": panel[0],
                "source_variant_id": panel[1],
                "binary_variant_ids": list(
                    _expect_sequence_any(panel[2], "binary ids witness")
                ),
                "source_incidence_count": panel[3],
                "binary_incidence_deltas": list(
                    _expect_sequence_any(panel[4], "binary deltas witness")
                ),
            }
        )
    if top["resource_panels"] != expected_panels:
        raise StudyManifestError("resource panels do not match result witness")

    expected_references = []
    for value in _expect_sequence_any(
        witness["clique_cost_references"],
        "clique reference witness",
    ):
        reference = _expect_sequence(value, 4, "clique reference witness")
        nodes = list(_expect_sequence_any(reference[2], "clique nodes witness"))
        edges = list(_expect_sequence_any(reference[3], "clique edges witness"))
        expected_references.append(
            {
                "reference_id": reference[0],
                "source_variant_id": reference[1],
                "topology_fingerprint": _json_fingerprint(
                    {"nodes": nodes, "hyperedges": edges}
                ),
                "resources": _resources_from_topology_witness(nodes, edges),
            }
        )
    if top["clique_cost_references"] != expected_references:
        raise StudyManifestError("clique references do not match result witness")

    witness_runs = _expect_sequence_any(witness["held_out"], "held-out witness")
    artifact_runs = top["held_out"]
    if len(witness_runs) != len(artifact_runs):
        raise StudyManifestError("held-out count does not match result witness")
    initial_fingerprints: dict[object, str] = {}
    for witness_run, artifact_run in zip(witness_runs, artifact_runs):
        run = _expect_sequence(witness_run, 5, "held-out run witness")
        trace_seed = _expect_sequence(run[2], 7, "held-out seed witness")
        observed_seed = artifact_run["trace_seed"]
        expected_seed = {
            "node_count": trace_seed[0],
            "parent_replicate": trace_seed[1],
            "split": trace_seed[2],
            "regime_id": trace_seed[3],
            "trace_replicate": trace_seed[4],
            "trace_root_seed": trace_seed[5],
            "routing_root_seed": trace_seed[6],
        }
        if (
            run[0] != observed_seed["regime_id"]
            or run[1] != observed_seed["trace_replicate"]
            or observed_seed != expected_seed
            or run[3] != artifact_run["paired_manifest_fingerprint"]
        ):
            raise StudyManifestError("held-out identity does not match result witness")
        witnessed_variants = _expect_sequence_any(run[4], "held-out variant witness")
        if len(witnessed_variants) != len(artifact_run["variants"]):
            raise StudyManifestError("held-out variant count does not match witness")
        for witnessed, observed in zip(witnessed_variants, artifact_run["variants"]):
            pair = _expect_sequence(witnessed, 2, "held-out variant witness")
            if pair[0] != observed["variant_id"]:
                raise StudyManifestError("held-out variant id does not match witness")
            nodes, edges = topology_by_id[pair[0]]
            expected = _summary_from_simulation_witness(
                pair[0],
                family_by_id[pair[0]],
                nodes,
                edges,
                pair[1],
            )
            if dict(observed) != expected:
                raise StudyManifestError("held-out service summary does not match witness")
            initial_fingerprints.setdefault(
                pair[0],
                expected["initial_state_fingerprint"],
            )
    for variant in artifact_variants:
        if variant["initial_state_fingerprint"] != initial_fingerprints[variant["variant_id"]]:
            raise StudyManifestError("trained initial state does not match run witness")


def _summary_from_simulation_witness(
    variant_id: object,
    family: object,
    nodes: list[object],
    edges: list[object],
    value: object,
) -> dict[str, object]:
    simulation = _expect_sequence(value, 6, "simulation witness")
    initial_state = list(_expect_sequence_any(simulation[0], "initial state witness"))
    outcomes = list(_expect_sequence_any(simulation[1], "outcome witness"))
    final_state = list(_expect_sequence_any(simulation[2], "final state witness"))
    arity_by_edge = {}
    members_by_edge = {}
    for edge in edges:
        edge_value = _expect_sequence(edge, 2, "topology edge witness")
        members = list(_expect_sequence_any(edge_value[1], "edge members"))
        arity_by_edge[edge_value[0]] = len(members)
        members_by_edge[edge_value[0]] = set(members)
    accepted_count = 0
    accepted_value = 0
    arity_counts: dict[int, int] = {}
    unique_signaled = 0
    for outcome_value in outcomes:
        outcome = _expect_sequence(outcome_value, 7, "outcome witness")
        request = _expect_sequence(outcome[1], 3, "request witness")
        route = outcome[2]
        if route is None:
            continue
        accepted_count += 1
        accepted_value += request[2]
        signaled = set()
        for step_value in _expect_sequence_any(route, "route witness"):
            step = _expect_sequence(step_value, 3, "route step witness")
            try:
                arity = arity_by_edge[step[0]]
                signaled.update(members_by_edge[step[0]])
            except KeyError as exc:
                raise StudyManifestError("route witness references an unknown edge") from exc
            arity_counts[arity] = arity_counts.get(arity, 0) + 1
        unique_signaled += len(signaled)
    histogram = [[arity, arity_counts[arity]] for arity in sorted(arity_counts)]
    horizon = len(outcomes)
    return {
        "variant_id": variant_id,
        "family": family,
        "horizon": horizon,
        "tau_dep": _event_from_witness(simulation[3], "tau_dep"),
        "tau_nopath": _event_from_witness(simulation[4], "tau_nopath"),
        "tau_rej": _event_from_witness(simulation[5], "tau_rej"),
        "accepted_request_count": accepted_count,
        "accepted_value": accepted_value,
        "success_rate": None if horizon == 0 else _fraction_payload(Fraction(accepted_count, horizon)),
        "initial_state_fingerprint": _json_fingerprint(
            {"nodes": nodes, "hyperedges": initial_state}
        ),
        "final_state_fingerprint": _json_fingerprint(
            {"nodes": nodes, "hyperedges": final_state}
        ),
        "dynamic_costs": {
            "traversed_hyperedge_count": sum(count for _, count in histogram),
            "signaled_participant_slots": sum(
                arity * count for arity, count in histogram
            ),
            "quadratic_coordination_exposure": sum(
                arity * arity * count for arity, count in histogram
            ),
            "unique_signaled_participants": unique_signaled,
            "route_arity_histogram": histogram,
        },
    }


def _event_from_witness(value: object, context: str) -> dict[str, object]:
    event = _expect_sequence(value, 2, f"{context} witness")
    return {"observed": event[0], "request_index": event[1]}


def _resources_from_topology_witness(
    nodes: list[object],
    edges: list[object],
) -> dict[str, int]:
    arities = []
    for edge in edges:
        edge_value = _expect_sequence(edge, 2, "topology edge witness")
        arities.append(len(_expect_sequence_any(edge_value[1], "edge members")))
    return {
        "node_count": len(nodes),
        "hyperedge_count": len(edges),
        "incidence_count": sum(arities),
        "maximum_arity": max(arities, default=0),
        "pairwise_member_exposure": sum(
            arity * (arity - 1) // 2 for arity in arities
        ),
    }


def _expect_sequence(value: object, length: int, context: str) -> list[object]:
    items = _expect_sequence_any(value, context)
    if len(items) != length:
        raise StudyManifestError(f"{context} must contain exactly {length} items")
    return items


def _expect_sequence_any(value: object, context: str) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise StudyManifestError(f"{context} must be a sequence")
    return list(value)


def _validate_nonnegative_int(value: object, field: str) -> None:
    if type(value) is not int or value < 0:
        raise StudyManifestError(f"{field} must be a nonnegative integer")


def _validate_resource_mapping(value: object, context: str) -> None:
    resources = _expect_mapping(
        value,
        {
            "node_count",
            "hyperedge_count",
            "incidence_count",
            "maximum_arity",
            "pairwise_member_exposure",
        },
        context,
    )
    if any(type(item) is not int or item < 0 for item in resources.values()):
        raise StudyManifestError(f"{context} values must be nonnegative integers")


def _validate_fraction_payload(value: object, context: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or type(value[0]) is not int
        or type(value[1]) is not int
        or value[1] <= 0
    ):
        raise StudyManifestError(f"{context} must be an integer fraction pair")


def _canonical_environment(value: object) -> dict[str, object]:
    environment = _expect_mapping(
        value,
        {"python_implementation", "python_version", "platform_system", "machine"},
        "environment",
    )
    if not all(isinstance(item, str) and item for item in environment.values()):
        raise StudyManifestError("environment values must be nonempty strings")
    return dict(environment)


def _load_strict_json(path: str | Path) -> Mapping[str, object]:
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as stream:
            value = json.load(
                stream,
                object_pairs_hook=_mapping_without_duplicate_keys,
                parse_constant=_reject_non_json_constant,
            )
    except StudyManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StudyManifestError(f"could not load artifact {source}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise StudyManifestError("artifact must be a JSON object")
    return value


def _mapping_without_duplicate_keys(pairs) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise StudyManifestError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _reject_non_json_constant(value: str) -> None:
    raise StudyManifestError(f"non-finite JSON number {value!r} is not allowed")


def _expect_mapping(value: object, fields: set[str], context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StudyManifestError(f"{context} must be an object")
    actual = set(value)
    if actual != fields:
        missing = tuple(sorted(fields - actual))
        unknown = tuple(sorted(actual - fields))
        raise StudyManifestError(
            f"{context} fields are invalid; missing={missing}, unknown={unknown}"
        )
    return value


def _expect_list(value: object, context: str, *, nonempty: bool) -> list[object]:
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "nonempty " if nonempty else ""
        raise StudyManifestError(f"{context} must be a {qualifier}list")
    return value


def _validate_digest(value: object, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError(f"{field} must be lowercase SHA-256 hex")


def validate_code_revision(value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError("code_revision must be a full lowercase Git SHA-1")


def _validate_duration(value: object, field: str) -> None:
    if type(value) is not int or value < 0:
        raise StudyManifestError(f"{field} must be nonnegative integer nanoseconds")


def _record_duration(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    _validate_duration(value, field)
    return value


def _mapping_fingerprint(value: Mapping[str, object]) -> str:
    payload = dict(value)
    payload.pop("artifact_fingerprint", None)
    payload.pop("summary_fingerprint", None)
    return _json_fingerprint(payload)


def _json_fingerprint(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StudyManifestError("artifact content is not strict canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "BLOCK_ARTIFACT_SCHEMA_VERSION",
    "STUDY_RUN_SUMMARY_SCHEMA_VERSION",
    "atomic_write_json",
    "build_study_run_summary",
    "build_synthetic_block_artifact",
    "load_study_run_summary",
    "load_synthetic_block_artifact",
    "validate_code_revision",
    "validate_study_run_summary",
    "validate_synthetic_block_artifact",
]
