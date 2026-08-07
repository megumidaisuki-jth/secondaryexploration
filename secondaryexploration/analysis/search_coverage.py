"""Training-only demand-aware search-coverage diagnostics."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from secondaryexploration.experiments.artifacts import atomic_write_json
from secondaryexploration.experiments.study import (
    StudyDesignManifest,
    StudyManifestError,
    StudyPhase,
    StudySeedLedger,
    build_study_seed_ledger,
    generate_declared_parent_ensemble,
    generate_declared_request_trace,
    load_study_design_manifest,
)
from secondaryexploration.optimization import (
    DemandAwareObjectiveWeights,
    DemandAwareSearchPlan,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    train_demand_aware_topology,
)
from secondaryexploration.topology import ParentGraphModel, fixed_hyperedge_size


SEARCH_COVERAGE_SCHEMA_VERSION = "demand-search-coverage.v1"
_PARENT_MODELS = (
    ParentGraphModel.ER_GNM,
    ParentGraphModel.BARABASI_ALBERT,
    ParentGraphModel.SBM_FIXED_COUNT,
)
_TOP_FIELDS = {
    "schema_version",
    "scope",
    "held_out_accessed",
    "manifest_fingerprint",
    "seed_ledger_fingerprint",
    "proposal_budgets",
    "maximum_rounds",
    "maximum_move_edges",
    "blocks",
    "summaries",
    "diagnostic_fingerprint",
}
_BLOCK_FIELDS = {
    "parent_graph_id",
    "node_count",
    "parent_replicate",
    "parent_model",
    "training_trace_count",
    "training_demand_fingerprint",
    "seed_topology_fingerprint",
    "budget_results",
}
_BUDGET_RESULT_FIELDS = {
    "proposal_budget",
    "proposals_considered",
    "feasible_evaluations",
    "accepted_steps",
    "topology_changed",
    "topology_fingerprint",
    "objective",
}


def build_search_coverage_diagnostic(
    manifest: StudyDesignManifest,
    *,
    proposal_budgets: tuple[int, ...],
) -> dict[str, object]:
    """Replay topology training only; never construct a held-out request trace."""

    if not isinstance(manifest, StudyDesignManifest):
        raise StudyManifestError("manifest must be a StudyDesignManifest")
    if manifest.phase is not StudyPhase.PILOT:
        raise StudyManifestError("search coverage requires a pilot manifest")
    _validate_budgets(proposal_budgets)
    ledger = build_study_seed_ledger(manifest)
    blocks = []
    for parent_seed in ledger.parent_seeds:
        training_records = tuple(
            item
            for item in ledger.trace_seeds
            if item.node_count == parent_seed.node_count
            and item.parent_replicate == parent_seed.parent_replicate
            and item.split == "training"
        )
        if not training_records:
            raise StudyManifestError("search diagnostic requires training traces")
        requests = tuple(
            request
            for record in training_records
            for request in generate_declared_request_trace(manifest, record).requests
        )
        ensemble = generate_declared_parent_ensemble(manifest, parent_seed)
        draws = {
            ParentGraphModel.ER_GNM: ensemble.er,
            ParentGraphModel.BARABASI_ALBERT: ensemble.ba,
            ParentGraphModel.SBM_FIXED_COUNT: ensemble.sbm,
        }
        for model in _PARENT_MODELS:
            parent = draws[model].graph
            demand = DirectedDemandMatrix.from_requests(parent.nodes, requests)
            seed_topology = _demand_seed_topology(manifest, parent)
            training_manifest = _training_manifest(manifest, parent, demand, seed_topology)
            budget_results = []
            seed_topology_fingerprint = None
            for budget in proposal_budgets:
                result = train_demand_aware_topology(
                    parent,
                    demand,
                    seed_topology,
                    training_manifest,
                    DemandAwareSearchPlan(
                        budget,
                        manifest.topology_search.maximum_rounds,
                        manifest.topology_search.maximum_move_edges,
                    ),
                )
                budget_results.append(
                    {
                        "proposal_budget": budget,
                        "proposals_considered": result.proposals_considered,
                        "feasible_evaluations": result.feasible_evaluations,
                        "accepted_steps": len(result.steps),
                        "topology_changed": result.topology != seed_topology,
                        "topology_fingerprint": result.score.topology_fingerprint,
                        "objective": _fraction_payload(result.score.objective_value),
                    }
                )
                if seed_topology_fingerprint is None:
                    seed_topology_fingerprint = result.seed_topology_fingerprint
            blocks.append(
                {
                    "parent_graph_id": (
                        f"n{parent_seed.node_count:04d}-"
                        f"r{parent_seed.parent_replicate:04d}-{model.value}"
                    ),
                    "node_count": parent_seed.node_count,
                    "parent_replicate": parent_seed.parent_replicate,
                    "parent_model": model.value,
                    "training_trace_count": len(training_records),
                    "training_demand_fingerprint": demand.fingerprint,
                    "seed_topology_fingerprint": seed_topology_fingerprint,
                    "budget_results": budget_results,
                }
            )
    blocks.sort(key=lambda item: item["parent_graph_id"])
    summaries = []
    for budget in proposal_budgets:
        results = [
            next(
                result
                for result in block["budget_results"]
                if result["proposal_budget"] == budget
            )
            for block in blocks
        ]
        summaries.append(
            {
                "proposal_budget": budget,
                "block_count": len(results),
                "changed_block_count": sum(item["topology_changed"] for item in results),
                "feasible_block_count": sum(
                    item["feasible_evaluations"] > 0 for item in results
                ),
                "total_proposals_considered": sum(
                    item["proposals_considered"] for item in results
                ),
                "total_feasible_evaluations": sum(
                    item["feasible_evaluations"] for item in results
                ),
                "total_accepted_steps": sum(item["accepted_steps"] for item in results),
            }
        )
    diagnostic: dict[str, object] = {
        "schema_version": SEARCH_COVERAGE_SCHEMA_VERSION,
        "scope": "training_topology_only",
        "held_out_accessed": False,
        "manifest_fingerprint": manifest.fingerprint,
        "seed_ledger_fingerprint": ledger.fingerprint,
        "proposal_budgets": list(proposal_budgets),
        "maximum_rounds": manifest.topology_search.maximum_rounds,
        "maximum_move_edges": manifest.topology_search.maximum_move_edges,
        "blocks": blocks,
        "summaries": summaries,
    }
    diagnostic["diagnostic_fingerprint"] = _fingerprint(diagnostic)
    validate_search_coverage_diagnostic(
        diagnostic,
        manifest=manifest,
        ledger=ledger,
    )
    return diagnostic


def validate_search_coverage_diagnostic(
    diagnostic: object,
    *,
    manifest: StudyDesignManifest | None = None,
    ledger: StudySeedLedger | None = None,
    source_replay: bool = False,
) -> None:
    """Validate internal arithmetic and optionally replay all training searches."""

    if not isinstance(diagnostic, Mapping) or set(diagnostic) != _TOP_FIELDS:
        raise StudyManifestError("search diagnostic has invalid top-level fields")
    if diagnostic["schema_version"] != SEARCH_COVERAGE_SCHEMA_VERSION:
        raise StudyManifestError("unsupported search diagnostic schema_version")
    if diagnostic["scope"] != "training_topology_only":
        raise StudyManifestError("search diagnostic scope is unsupported")
    if diagnostic["held_out_accessed"] is not False:
        raise StudyManifestError("search diagnostic must not access held-out traces")
    for field in (
        "manifest_fingerprint",
        "seed_ledger_fingerprint",
        "diagnostic_fingerprint",
    ):
        _validate_digest(diagnostic[field], field)
    budgets = diagnostic["proposal_budgets"]
    if not isinstance(budgets, list):
        raise StudyManifestError("proposal_budgets must be a list")
    _validate_budgets(tuple(budgets))
    for field in ("maximum_rounds", "maximum_move_edges"):
        if type(diagnostic[field]) is not int or diagnostic[field] < 1:
            raise StudyManifestError(f"{field} must be positive integer")
    blocks = diagnostic["blocks"]
    summaries = diagnostic["summaries"]
    if not isinstance(blocks, list) or not blocks:
        raise StudyManifestError("search diagnostic blocks must be nonempty list")
    if not isinstance(summaries, list) or len(summaries) != len(budgets):
        raise StudyManifestError("search diagnostic summaries do not match budgets")
    block_ids = [item.get("parent_graph_id") for item in blocks if isinstance(item, Mapping)]
    if len(block_ids) != len(blocks) or block_ids != sorted(block_ids) or len(set(block_ids)) != len(block_ids):
        raise StudyManifestError("search diagnostic blocks must be canonical and unique")
    for block in blocks:
        if set(block) != _BLOCK_FIELDS:
            raise StudyManifestError("search diagnostic block fields are invalid")
        if (
            type(block["node_count"]) is not int
            or block["node_count"] < 1
            or type(block["parent_replicate"]) is not int
            or block["parent_replicate"] < 0
            or type(block["training_trace_count"]) is not int
            or block["training_trace_count"] < 1
        ):
            raise StudyManifestError("search diagnostic block counts are invalid")
        if block["parent_model"] not in {model.value for model in _PARENT_MODELS}:
            raise StudyManifestError("search diagnostic parent model is unsupported")
        expected_id = (
            f"n{block['node_count']:04d}-r{block['parent_replicate']:04d}-"
            f"{block['parent_model']}"
        )
        if block["parent_graph_id"] != expected_id:
            raise StudyManifestError("search diagnostic parent id is not canonical")
        for field in ("training_demand_fingerprint", "seed_topology_fingerprint"):
            _validate_digest(block[field], field)
        results = block["budget_results"]
        if not isinstance(results, list) or len(results) != len(budgets):
            raise StudyManifestError("block budget results do not match budgets")
        for result, budget in zip(results, budgets, strict=True):
            if not isinstance(result, Mapping) or set(result) != _BUDGET_RESULT_FIELDS:
                raise StudyManifestError("search budget result fields are invalid")
            if result["proposal_budget"] != budget:
                raise StudyManifestError("search budget result order is inconsistent")
            for field in (
                "proposals_considered",
                "feasible_evaluations",
                "accepted_steps",
            ):
                if type(result[field]) is not int or result[field] < 0:
                    raise StudyManifestError(f"search result {field} is invalid")
            if (
                result["proposals_considered"] > budget
                or result["feasible_evaluations"] > result["proposals_considered"]
                or result["accepted_steps"] > diagnostic["maximum_rounds"]
            ):
                raise StudyManifestError("search result counts exceed their bounds")
            if type(result["topology_changed"]) is not bool:
                raise StudyManifestError("search topology_changed must be boolean")
            _validate_digest(result["topology_fingerprint"], "topology_fingerprint")
            if result["topology_changed"] != (
                result["topology_fingerprint"] != block["seed_topology_fingerprint"]
            ):
                raise StudyManifestError("search topology change flag is inconsistent")
            if result["topology_changed"] != (result["accepted_steps"] > 0):
                raise StudyManifestError("search accepted steps are inconsistent")
            _validate_fraction_payload(result["objective"], "search objective")
    for summary, budget in zip(summaries, budgets, strict=True):
        if not isinstance(summary, Mapping) or summary.get("proposal_budget") != budget:
            raise StudyManifestError("search diagnostic summary budget is inconsistent")
        results = [
            next(
                item
                for item in block["budget_results"]
                if item["proposal_budget"] == budget
            )
            for block in blocks
        ]
        expected = {
            "proposal_budget": budget,
            "block_count": len(results),
            "changed_block_count": sum(item["topology_changed"] for item in results),
            "feasible_block_count": sum(item["feasible_evaluations"] > 0 for item in results),
            "total_proposals_considered": sum(item["proposals_considered"] for item in results),
            "total_feasible_evaluations": sum(item["feasible_evaluations"] for item in results),
            "total_accepted_steps": sum(item["accepted_steps"] for item in results),
        }
        if dict(summary) != expected:
            raise StudyManifestError("search diagnostic summary arithmetic is inconsistent")
    if diagnostic["diagnostic_fingerprint"] != _fingerprint(diagnostic):
        raise StudyManifestError("search diagnostic fingerprint does not match content")
    if manifest is not None:
        if diagnostic["manifest_fingerprint"] != manifest.fingerprint:
            raise StudyManifestError("search diagnostic does not match manifest")
        if diagnostic["maximum_rounds"] != manifest.topology_search.maximum_rounds or diagnostic["maximum_move_edges"] != manifest.topology_search.maximum_move_edges:
            raise StudyManifestError("search diagnostic does not match topology search plan")
    if ledger is not None and diagnostic["seed_ledger_fingerprint"] != ledger.fingerprint:
        raise StudyManifestError("search diagnostic does not match seed ledger")
    if source_replay:
        if manifest is None:
            raise StudyManifestError("source replay requires a manifest")
        rebuilt = build_search_coverage_diagnostic(
            manifest,
            proposal_budgets=tuple(budgets),
        )
        if dict(diagnostic) != rebuilt:
            raise StudyManifestError("search diagnostic does not match training-only replay")


def load_search_coverage_diagnostic(
    path: str | Path,
    **expected: object,
) -> dict[str, object]:
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
        raise StudyManifestError(f"could not load search diagnostic {source}: {exc}") from exc
    validate_search_coverage_diagnostic(raw, **expected)
    return dict(raw)


def generate_search_coverage_diagnostic(
    manifest_path: str | Path,
    *,
    proposal_budgets: tuple[int, ...],
    output_path: str | Path,
) -> Path:
    manifest = load_study_design_manifest(manifest_path)
    diagnostic = build_search_coverage_diagnostic(
        manifest,
        proposal_budgets=proposal_budgets,
    )
    target = Path(output_path).resolve()
    atomic_write_json(target, diagnostic)
    return target


def _training_manifest(manifest, parent, demand, seed_topology):
    weights = manifest.objective_weights
    return DemandAwareTrainingManifest.create(
        parent,
        demand,
        seed_topology.resources.incidence_count,
        max(edge.arity for edge in seed_topology.hyperedges),
        DemandAwareObjectiveWeights(
            weights.bidirectional_capture,
            weights.directional_imbalance,
            weights.participation,
            weights.coordination_overlap,
        ),
    )


def _demand_seed_topology(manifest, parent):
    family = manifest.demand_aware_seed_family
    if not family.startswith("fhs") or not family[3:].isdigit():
        raise StudyManifestError("search diagnostic seed family is unsupported")
    maximum_arity = int(family[3:])
    if maximum_arity not in manifest.topology_max_arities:
        raise StudyManifestError("search diagnostic seed arity is not registered")
    return fixed_hyperedge_size(parent, maximum_arity)


def _validate_budgets(value: tuple[int, ...]) -> None:
    if (
        type(value) is not tuple
        or not value
        or tuple(sorted(value)) != value
        or len(set(value)) != len(value)
        or any(type(item) is not int or item < 1 for item in value)
    ):
        raise StudyManifestError("proposal budgets must be canonical unique positives")


def _fraction_payload(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _validate_fraction_payload(value: object, field: str) -> Fraction:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(item) is not int for item in value)
        or value[1] <= 0
    ):
        raise StudyManifestError(f"{field} must be a rational pair")
    fraction = Fraction(value[0], value[1])
    if value != [fraction.numerator, fraction.denominator]:
        raise StudyManifestError(f"{field} must be canonical")
    return fraction


def _validate_digest(value: object, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError(f"{field} must be lowercase SHA-256 hexadecimal")


def _fingerprint(value: Mapping[str, object]) -> str:
    payload = dict(value)
    payload.pop("diagnostic_fingerprint", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
        description="Replay training-only demand-aware proposal coverage.",
    )
    parser.add_argument("manifest")
    parser.add_argument("--proposal-budget", action="append", type=int, required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    path = generate_search_coverage_diagnostic(
        arguments.manifest,
        proposal_budgets=tuple(sorted(arguments.proposal_budget)),
        output_path=arguments.output,
    )
    print(path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SEARCH_COVERAGE_SCHEMA_VERSION",
    "build_search_coverage_diagnostic",
    "generate_search_coverage_diagnostic",
    "load_search_coverage_diagnostic",
    "main",
    "validate_search_coverage_diagnostic",
]
