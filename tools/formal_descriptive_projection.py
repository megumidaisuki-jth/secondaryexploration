"""Build the frozen result-blind descriptive topology/balance/cost projection."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction
import json
from itertools import combinations
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
    route_choice_rng,
)
from secondaryexploration.experiments.artifacts import (
    load_study_run_summary,
    load_synthetic_block_artifact,
)
from secondaryexploration.experiments.runner import validate_frozen_execution_context
from secondaryexploration.experiments.pipeline import (
    ResourceComparisonPanel,
    _simulation_payload,
)
from secondaryexploration.model import HypergraphState, PaymentRequest
from secondaryexploration.simulation import run_core_trace_with_request_rngs
from tools import formal_inference as primary


SCHEMA_VERSION = "formal-descriptive-mechanism-evidence.v1"
STATUS = "complete-exploratory-no-inference"
EXECUTION_REVISION = "425710a418b1b28e6c5cd813dff18aeeaa6303c3"
BASE_ANALYSIS_REVISION = "9ecaadec84f8bebe799fb507969de8e0a0947b66"
_TOOL_PATHS = (
    "tools/formal_descriptive_projection.py",
    "docs/plans/2026-08-11-formal-descriptive-mechanism-projection.md",
)
_STATIC_METRICS = (
    "topology_pair_coverage_fraction",
    "topology_mean_pair_multiplicity_covered",
    "initial_coordinate_imbalance",
)
_DYNAMIC_METRICS = (
    "final_coordinate_imbalance",
    "final_zero_coordinate_fraction",
    "optimal_route_multiplicity_mass_per_attempt",
    "multiple_optimal_route_fraction_per_attempt",
    "route_bottleneck_mass_per_attempt",
    "route_hop_mass_per_attempt",
    "traversed_hyperedge_count_per_attempt",
    "signaled_participant_slots_per_attempt",
    "quadratic_coordination_exposure_per_attempt",
    "unique_signaled_participants_per_attempt",
)
_METRICS = _STATIC_METRICS + _DYNAMIC_METRICS
_METRIC_KIND = {
    metric: "static-parent" if metric in _STATIC_METRICS else "held-out-4:3"
    for metric in _METRICS
}
_LIMITATIONS = [
    "exploratory-descriptive-only-with-no-confidence-interval-or-p-value",
    "cannot-rescue-a-failed-formal-or-confirmation-contrast",
    "topology-balance-and-cost-associations-do-not-identify-mechanisms",
    "formal-and-confirmation-projections-remain-separate",
    "lightning-structural-panels-are-outside-this-synthetic-projection",
]
_TOP_FIELDS = {
    "schema_version",
    "status",
    "phase",
    "study_id",
    "projection_revision",
    "execution_revision",
    "base_analysis_revision",
    "source_fingerprints",
    "metric_registry",
    "block_registry",
    "parent_contrasts",
    "summaries",
    "limitations",
    "projection_fingerprint",
}
_PARENT_FIELDS = {
    "phase",
    "node_count",
    "parent_model",
    "parent_replicate",
    "parent_graph_id",
    "source_family",
    "metric",
    "metric_kind",
    "same_distribution_mean",
    "distribution_shift_mean",
    "combined_parent_value",
}


def _metric_registry() -> list[dict[str, object]]:
    descriptions = {
        "topology_pair_coverage_fraction": "covered unordered pairs / choose(n,2)",
        "topology_mean_pair_multiplicity_covered": "hyperedge pair multiplicity / covered pairs",
        "initial_coordinate_imbalance": "incidence-mean absolute initial balance-share deviation",
        "final_coordinate_imbalance": "incidence-mean absolute final balance-share deviation",
        "final_zero_coordinate_fraction": "zero final balance coordinates / incidence count",
        "optimal_route_multiplicity_mass_per_attempt": "sum optimal tied-route counts / horizon",
        "multiple_optimal_route_fraction_per_attempt": "requests with multiple optimal routes / horizon",
        "route_bottleneck_mass_per_attempt": "sum selected-route bottlenecks / horizon",
        "route_hop_mass_per_attempt": "sum selected-route shortest hops / horizon",
        "traversed_hyperedge_count_per_attempt": "traversed hyperedges / horizon",
        "signaled_participant_slots_per_attempt": "signaled participant slots / horizon",
        "quadratic_coordination_exposure_per_attempt": "quadratic coordination exposure / horizon",
        "unique_signaled_participants_per_attempt": "unique signaled participants / horizon",
    }
    return [
        {
            "metric": metric,
            "metric_kind": _METRIC_KIND[metric],
            "contrast": "source-minus-registered-binary-mean",
            "description": descriptions[metric],
            "inference": "none-exploratory-descriptive-only",
        }
        for metric in _METRICS
    ]


def _sequence(value: object, length: int, label: str) -> list[object]:
    if type(value) is not list or len(value) != length:
        raise StudyManifestError(f"{label} must contain exactly {length} fields")
    return value


def _sequence_any(value: object, label: str) -> list[object]:
    if type(value) is not list:
        raise StudyManifestError(f"{label} must be a list")
    return value


def _mapping(value: object, fields: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise StudyManifestError(f"{label} fields differ")
    return value


def _fraction(value: object, label: str) -> Fraction:
    pair = _sequence(value, 2, label)
    if type(pair[0]) is not int or type(pair[1]) is not int or pair[1] <= 0:
        raise StudyManifestError(f"{label} is not an exact fraction")
    result = Fraction(pair[0], pair[1])
    if [result.numerator, result.denominator] != pair:
        raise StudyManifestError(f"{label} fraction is not canonical")
    return result


def _payload(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _mean(values: Sequence[Fraction]) -> Fraction:
    if not values:
        raise StudyManifestError("cannot average an empty metric collection")
    return sum(values, Fraction(0)) / len(values)


def _topology_metrics(payload: object) -> dict[str, Fraction]:
    topology = _sequence(payload, 2, "topology witness")
    nodes = _sequence_any(topology[0], "topology nodes")
    if not nodes or any(type(node) is not str for node in nodes) or len(set(nodes)) != len(nodes):
        raise StudyManifestError("topology nodes are malformed")
    node_set = set(nodes)
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    seen_edges = set()
    for raw_edge in _sequence_any(topology[1], "topology hyperedges"):
        edge = _sequence(raw_edge, 2, "topology hyperedge")
        edge_id = edge[0]
        members = _sequence_any(edge[1], "hyperedge members")
        if (
            type(edge_id) is not str
            or edge_id in seen_edges
            or len(members) < 2
            or any(type(member) is not str or member not in node_set for member in members)
            or len(set(members)) != len(members)
        ):
            raise StudyManifestError("topology hyperedge is malformed")
        seen_edges.add(edge_id)
        for first, second in combinations(sorted(members), 2):
            pair_counts[(first, second)] += 1
    denominator = len(nodes) * (len(nodes) - 1) // 2
    if denominator <= 0 or not pair_counts:
        raise StudyManifestError("topology has no covered node pair")
    return {
        "topology_pair_coverage_fraction": Fraction(len(pair_counts), denominator),
        "topology_mean_pair_multiplicity_covered": Fraction(
            sum(pair_counts.values()), len(pair_counts)
        ),
    }


def _topology_resource_profile(payload: object) -> tuple[int, bool]:
    topology = _sequence(payload, 2, "topology witness")
    edges = _sequence_any(topology[1], "topology hyperedges")
    arities = [
        len(_sequence_any(_sequence(edge, 2, "topology hyperedge")[1], "members"))
        for edge in edges
    ]
    return sum(arities), bool(arities) and all(arity == 2 for arity in arities)


def _validated_resource_panels(artifact, variant_witnesses):
    families = {variant_id: value[1] for variant_id, value in variant_witnesses.items()}
    profiles = {
        variant_id: _topology_resource_profile(value[2])
        for variant_id, value in variant_witnesses.items()
    }
    mappings = []
    contracts = []
    for raw_panel in artifact["resource_panels"]:
        panel = _mapping(
            raw_panel,
            {
                "panel_id",
                "source_variant_id",
                "binary_variant_ids",
                "source_incidence_count",
                "binary_incidence_deltas",
            },
            "resource panel",
        )
        contract = ResourceComparisonPanel(
            panel["panel_id"],
            panel["source_variant_id"],
            tuple(_sequence_any(panel["binary_variant_ids"], "binary variant ids")),
            panel["source_incidence_count"],
            tuple(
                _sequence_any(
                    panel["binary_incidence_deltas"], "binary incidence deltas"
                )
            ),
        )
        source = contract.source_variant_id
        if source not in families or families[source] != source:
            raise StudyManifestError("resource panel source family differs")
        source_incidence = profiles[source][0]
        if source_incidence != contract.source_incidence_count:
            raise StudyManifestError("resource panel source incidence differs")
        for binary_id, delta in zip(
            contract.binary_variant_ids, contract.binary_incidence_deltas
        ):
            if (
                binary_id not in families
                or families[binary_id] != "binary-matched"
                or not profiles[binary_id][1]
                or profiles[binary_id][0] != source_incidence + delta
            ):
                raise StudyManifestError("resource panel binary match differs")
        mappings.append(panel)
        contracts.append(contract)
    panel_ids = tuple(item.panel_id for item in contracts)
    if panel_ids != tuple(sorted(panel_ids)) or len(set(panel_ids)) != len(panel_ids):
        raise StudyManifestError("resource panel registry is not canonical")
    source_ids = tuple(item.source_variant_id for item in contracts)
    if tuple(sorted(source_ids)) != primary._SOURCES:
        raise StudyManifestError("resource panel source registry differs")
    covered = {
        variant_id
        for item in contracts
        for variant_id in (item.source_variant_id, *item.binary_variant_ids)
    }
    if covered != set(variant_witnesses):
        raise StudyManifestError("resource panels do not cover the variant registry")
    return mappings


def _state_metrics(
    state_payload: object, topology_payload: object
) -> tuple[Fraction, Fraction]:
    topology = _sequence(topology_payload, 2, "topology witness")
    topology_edges = {
        edge[0]: tuple(edge[1])
        for edge in (
            _sequence(item, 2, "topology hyperedge")
            for item in _sequence_any(topology[1], "topology hyperedges")
        )
    }
    state_edges = _sequence_any(state_payload, "state hyperedges")
    if len(state_edges) != len(topology_edges):
        raise StudyManifestError("state and topology hyperedge counts differ")
    deviations = []
    zero_count = 0
    seen = set()
    for raw_edge in state_edges:
        edge = _sequence(raw_edge, 2, "state hyperedge")
        edge_id = edge[0]
        balances = _sequence_any(edge[1], "state balances")
        if type(edge_id) is not str or edge_id in seen or edge_id not in topology_edges:
            raise StudyManifestError("state hyperedge identifier differs")
        seen.add(edge_id)
        members = []
        values = []
        for raw_balance in balances:
            pair = _sequence(raw_balance, 2, "state balance")
            if type(pair[0]) is not str or type(pair[1]) is not int or pair[1] < 0:
                raise StudyManifestError("state balance is malformed")
            members.append(pair[0])
            values.append(pair[1])
        if tuple(members) != topology_edges[edge_id]:
            raise StudyManifestError("state members differ from topology")
        total = sum(values)
        if total <= 0:
            raise StudyManifestError("state hyperedge has nonpositive total balance")
        equal_share = Fraction(1, len(values))
        for value in values:
            deviations.append(abs(Fraction(value, total) - equal_share))
            zero_count += value == 0
    if seen != set(topology_edges) or not deviations:
        raise StudyManifestError("state hyperedge registry differs")
    return _mean(deviations), Fraction(zero_count, len(deviations))


def _state_from_witness(state_payload: object, topology_payload: object):
    topology = _sequence(topology_payload, 2, "topology witness")
    nodes = _sequence_any(topology[0], "topology nodes")
    balances = {}
    for raw_edge in _sequence_any(state_payload, "state hyperedges"):
        edge = _sequence(raw_edge, 2, "state hyperedge")
        edge_id = edge[0]
        if type(edge_id) is not str or edge_id in balances:
            raise StudyManifestError("state hyperedge identifier differs")
        balance_pairs = _sequence_any(edge[1], "state balances")
        balances[edge_id] = {
            _sequence(pair, 2, "state balance")[0]: _sequence(
                pair, 2, "state balance"
            )[1]
            for pair in balance_pairs
        }
        if len(balances[edge_id]) != len(balance_pairs):
            raise StudyManifestError("state balance member is duplicated")
    return HypergraphState.from_balances(nodes, balances)


def _validate_exact_simulation_replay(
    simulation_payload: object,
    topology_payload: object,
    routing_root_seed: int,
) -> None:
    """Rebuild the core record so its constructor replays every route exactly."""

    simulation = _sequence(simulation_payload, 6, "simulation witness")
    try:
        initial_state = _state_from_witness(simulation[0], topology_payload)
        requests = []
        for raw_outcome in _sequence_any(simulation[1], "simulation outcomes"):
            outcome = _sequence(raw_outcome, 7, "request outcome")
            request_payload = _sequence(outcome[1], 3, "payment request")
            requests.append(PaymentRequest(*request_payload))
        exact = run_core_trace_with_request_rngs(
            initial_state,
            tuple(requests),
            (
                route_choice_rng(routing_root_seed, request_index)
                for request_index in range(1, len(requests) + 1)
            ),
        )
        expected_wire = json.dumps(
            _simulation_payload(exact),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        observed_wire = json.dumps(
            simulation,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if observed_wire != expected_wire:
            raise StudyManifestError(
                "simulation witness differs from exact paired route-choice replay"
            )
    except StudyManifestError:
        raise
    except (TypeError, ValueError) as exc:
        raise StudyManifestError(
            "simulation witness fails exact route/state replay"
        ) from exc


def _simulation_metrics(
    simulation_payload: object,
    topology_payload: object,
    dynamic_costs: Mapping[str, object],
    expected_horizon: int,
    routing_root_seed: int,
) -> tuple[object, dict[str, Fraction]]:
    simulation = _sequence(simulation_payload, 6, "simulation witness")
    _validate_exact_simulation_replay(
        simulation, topology_payload, routing_root_seed
    )
    initial_state, outcomes, final_state = simulation[:3]
    outcome_rows = _sequence_any(outcomes, "simulation outcomes")
    if len(outcome_rows) != expected_horizon:
        raise StudyManifestError("simulation outcome count differs from horizon")
    route_count_mass = 0
    multiple_count = 0
    bottleneck_mass = Fraction(0)
    hop_mass = 0
    for raw_outcome in outcome_rows:
        outcome = _sequence(raw_outcome, 7, "request outcome")
        route, hops, bottleneck, tied_count = outcome[2:6]
        if route is None:
            if hops is not None or bottleneck is not None or tied_count != 0:
                raise StudyManifestError("no-path route metadata differs")
            continue
        route_steps = _sequence_any(route, "selected route")
        if (
            type(hops) is not int
            or hops < 1
            or len(route_steps) != hops
            or type(tied_count) is not int
            or tied_count < 1
        ):
            raise StudyManifestError("selected route metadata is malformed")
        bottleneck_value = _fraction(bottleneck, "route bottleneck")
        if not 0 <= bottleneck_value <= 1:
            raise StudyManifestError("route bottleneck is outside [0, 1]")
        route_count_mass += tied_count
        multiple_count += tied_count > 1
        bottleneck_mass += bottleneck_value
        hop_mass += hops
    final_imbalance, final_zero = _state_metrics(final_state, topology_payload)
    cost_fields = {
        "traversed_hyperedge_count",
        "signaled_participant_slots",
        "quadratic_coordination_exposure",
        "unique_signaled_participants",
        "route_arity_histogram",
    }
    costs = _mapping(dynamic_costs, cost_fields, "dynamic costs")
    metrics = {
        "final_coordinate_imbalance": final_imbalance,
        "final_zero_coordinate_fraction": final_zero,
        "optimal_route_multiplicity_mass_per_attempt": Fraction(
            route_count_mass, expected_horizon
        ),
        "multiple_optimal_route_fraction_per_attempt": Fraction(
            multiple_count, expected_horizon
        ),
        "route_bottleneck_mass_per_attempt": bottleneck_mass / expected_horizon,
        "route_hop_mass_per_attempt": Fraction(hop_mass, expected_horizon),
    }
    for source_name, metric_name in (
        ("traversed_hyperedge_count", "traversed_hyperedge_count_per_attempt"),
        ("signaled_participant_slots", "signaled_participant_slots_per_attempt"),
        (
            "quadratic_coordination_exposure",
            "quadratic_coordination_exposure_per_attempt",
        ),
        (
            "unique_signaled_participants",
            "unique_signaled_participants_per_attempt",
        ),
    ):
        value = costs[source_name]
        if type(value) is not int or value < 0:
            raise StudyManifestError("dynamic cost is malformed")
        metrics[metric_name] = Fraction(value, expected_horizon)
    return initial_state, metrics


def _project_block(manifest, artifact: Mapping[str, object]) -> list[dict[str, object]]:
    block = artifact["block"]
    node_count = block["node_count"]
    replicate = block["parent_replicate"]
    model = block["parent_model"]
    parent_id = primary._block_key(block)
    expected_horizon = node_count * manifest.requests_per_node
    witness = artifact["result_witness"]
    variant_witnesses = {}
    for raw_variant in _sequence_any(witness["variants"], "variant witnesses"):
        variant = _sequence(raw_variant, 4, "variant witness")
        if type(variant[0]) is not str or variant[0] in variant_witnesses:
            raise StudyManifestError("variant witness identifiers differ")
        variant_witnesses[variant[0]] = variant
    panels = _validated_resource_panels(artifact, variant_witnesses)
    summary_held_out = {}
    for record in artifact["held_out"]:
        seed = record["trace_seed"]
        key = (seed["regime_id"], seed["trace_replicate"])
        if key in summary_held_out:
            raise StudyManifestError("held-out summary trace is duplicated")
        summary_held_out[key] = {
            item["variant_id"]: item for item in record["variants"]
        }
    scopes = {
        regime.regime_id: (
            "same_distribution"
            if regime.shift.value == "same_distribution"
            else "distribution_shift"
        )
        for regime in manifest.regimes
        if regime.role.value == "test"
    }
    trace_metrics: dict[tuple[str, int], dict[str, dict[str, Fraction]]] = {}
    initial_states: dict[str, object] = {}
    for raw_trace in _sequence_any(witness["held_out"], "held-out witnesses"):
        trace = _sequence(raw_trace, 5, "held-out witness")
        key = (trace[0], trace[1])
        if key not in summary_held_out or key in trace_metrics or trace[0] not in scopes:
            raise StudyManifestError("held-out witness registry differs")
        by_variant = {}
        trace_seed = _sequence(trace[2], 7, "held-out seed witness")
        routing_root_seed = trace_seed[6]
        for raw_result in _sequence_any(trace[4], "held-out variant witnesses"):
            result = _sequence(raw_result, 2, "held-out variant witness")
            variant_id = result[0]
            if variant_id not in variant_witnesses or variant_id in by_variant:
                raise StudyManifestError("held-out variant witness registry differs")
            summary = summary_held_out[key].get(variant_id)
            if summary is None:
                raise StudyManifestError("held-out summary variant is missing")
            initial_state, metrics = _simulation_metrics(
                result[1],
                variant_witnesses[variant_id][2],
                summary["dynamic_costs"],
                expected_horizon,
                routing_root_seed,
            )
            existing = initial_states.get(variant_id)
            if existing is None:
                initial_states[variant_id] = initial_state
            elif existing != initial_state:
                raise StudyManifestError("variant initial state differs across traces")
            by_variant[variant_id] = metrics
        if set(by_variant) != set(variant_witnesses):
            raise StudyManifestError("held-out variant witnesses are incomplete")
        trace_metrics[key] = by_variant
    if set(trace_metrics) != set(summary_held_out) or len(trace_metrics) != 7:
        raise StudyManifestError("held-out trace witness registry is incomplete")

    static_metrics = {}
    for variant_id, variant in variant_witnesses.items():
        values = _topology_metrics(variant[2])
        initial_imbalance, _ = _state_metrics(initial_states[variant_id], variant[2])
        values["initial_coordinate_imbalance"] = initial_imbalance
        static_metrics[variant_id] = values

    rows = []
    for panel in sorted(panels, key=lambda item: item["source_variant_id"]):
        source = panel["source_variant_id"]
        binary_ids = tuple(panel["binary_variant_ids"])
        if not binary_ids or source not in variant_witnesses or any(
            item not in variant_witnesses for item in binary_ids
        ):
            raise StudyManifestError("resource panel variant registry differs")
        for metric in _STATIC_METRICS:
            contrast = static_metrics[source][metric] - _mean(
                [static_metrics[item][metric] for item in binary_ids]
            )
            rows.append(
                _parent_row(
                    manifest.phase.value,
                    node_count,
                    model,
                    replicate,
                    parent_id,
                    source,
                    metric,
                    None,
                    None,
                    contrast,
                )
            )
        dynamic_contrasts: dict[str, dict[str, list[Fraction]]] = {
            metric: {"same_distribution": [], "distribution_shift": []}
            for metric in _DYNAMIC_METRICS
        }
        for key, by_variant in trace_metrics.items():
            scope = scopes[key[0]]
            for metric in _DYNAMIC_METRICS:
                contrast = by_variant[source][metric] - _mean(
                    [by_variant[item][metric] for item in binary_ids]
                )
                dynamic_contrasts[metric][scope].append(contrast)
        for metric in _DYNAMIC_METRICS:
            same = dynamic_contrasts[metric]["same_distribution"]
            shifted = dynamic_contrasts[metric]["distribution_shift"]
            if len(same) != 4 or len(shifted) != 3:
                raise StudyManifestError("held-out descriptive scope counts differ")
            same_mean = _mean(same)
            shift_mean = _mean(shifted)
            combined = Fraction(4, 7) * same_mean + Fraction(3, 7) * shift_mean
            rows.append(
                _parent_row(
                    manifest.phase.value,
                    node_count,
                    model,
                    replicate,
                    parent_id,
                    source,
                    metric,
                    same_mean,
                    shift_mean,
                    combined,
                )
            )
    return sorted(rows, key=_parent_sort_key)


def _parent_row(
    phase,
    node_count,
    model,
    replicate,
    parent_id,
    source,
    metric,
    same,
    shifted,
    combined,
):
    return {
        "phase": phase,
        "node_count": node_count,
        "parent_model": model,
        "parent_replicate": replicate,
        "parent_graph_id": parent_id,
        "source_family": source,
        "metric": metric,
        "metric_kind": _METRIC_KIND[metric],
        "same_distribution_mean": None if same is None else _payload(same),
        "distribution_shift_mean": None if shifted is None else _payload(shifted),
        "combined_parent_value": _payload(combined),
    }


def _parent_sort_key(row):
    return (
        row["node_count"],
        primary._MODELS.index(row["parent_model"]),
        row["parent_replicate"],
        primary._SOURCES.index(row["source_family"]),
        _METRICS.index(row["metric"]),
    )


def _build_summaries(phase: str, rows: Sequence[Mapping[str, object]]):
    registry = defaultdict(list)
    for row in rows:
        registry[
            (
                row["node_count"],
                row["parent_model"],
                row["parent_replicate"],
                row["source_family"],
                row["metric"],
            )
        ].append(row)
    output = []
    for size in (30, 60, 120, 240):
        for source in primary._SOURCES:
            for metric in _METRICS:
                strata = []
                means = []
                for model in primary._MODELS:
                    values = []
                    for replicate in range(20):
                        candidates = registry[
                            (size, model, replicate, source, metric)
                        ]
                        if len(candidates) != 1:
                            raise StudyManifestError("descriptive parent registry differs")
                        values.append(
                            (
                                candidates[0]["parent_graph_id"],
                                _fraction(
                                    candidates[0]["combined_parent_value"],
                                    "combined parent value",
                                ),
                            )
                        )
                    mean = _mean([value for _, value in values])
                    means.append(mean)
                    strata.append(
                        {
                            "parent_model": model,
                            "parent_count": 20,
                            "parent_values": [
                                [parent_id, _payload(value)]
                                for parent_id, value in values
                            ],
                            "mean": _payload(mean),
                            "minimum": _payload(min(value for _, value in values)),
                            "maximum": _payload(max(value for _, value in values)),
                        }
                    )
                output.append(
                    {
                        "phase": phase,
                        "node_count": size,
                        "source_family": source,
                        "metric": metric,
                        "metric_kind": _METRIC_KIND[metric],
                        "strata": strata,
                        "equal_model_mean": _payload(_mean(means)),
                        "inference": "none-exploratory-descriptive-only",
                    }
                )
    return output


def build_phase_projection(
    manifest,
    ledger,
    summary,
    calibration,
    precision,
    *,
    output_root: Path,
    projection_revision: str,
    artifact_loader=load_synthetic_block_artifact,
    block_projector=_project_block,
):
    if manifest.phase not in {StudyPhase.FORMAL, StudyPhase.CONFIRMATION}:
        raise StudyManifestError("descriptive projection requires a registered phase")
    if summary["status"] != "complete" or summary["completed_block_count"] != 240:
        raise StudyManifestError("descriptive projection requires complete 240 blocks")
    if summary["code_revision"] != EXECUTION_REVISION:
        raise StudyManifestError("descriptive projection execution revision differs")
    primary._validate_digest(projection_revision, "projection_revision", length=40)
    expected_keys = tuple(item["block_key"] for item in summary["blocks"])
    if expected_keys != primary._expected_block_keys():
        raise StudyManifestError("summary block registry is not canonical")
    paths = primary._exact_phase_block_paths(output_root, expected_keys)
    seeds = {(item.node_count, item.parent_replicate): item for item in ledger.parent_seeds}
    rows = []
    rebuilt_records = []
    byte_registry = []
    artifact_fingerprints = []
    for record in summary["blocks"]:
        key = record["block_key"]
        parts = key.split("-", 2)
        node_count = int(parts[0][1:])
        replicate = int(parts[1][1:])
        path = paths[key]
        before = primary._sha256_file(path)
        artifact = artifact_loader(
            path,
            manifest=manifest,
            ledger=ledger,
            parent_seed=seeds[(node_count, replicate)],
            parent_model=parts[2],
            code_revision=summary["code_revision"],
            environment=summary["environment"],
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
        if rebuilt != record:
            raise StudyManifestError("summary differs from descriptive source artifact")
        rows.extend(block_projector(manifest, artifact))
        rebuilt_records.append(rebuilt)
        artifact_fingerprints.append(artifact["artifact_fingerprint"])
        byte_registry.append(
            {
                "block_key": key,
                "path": f"blocks/{key}.json",
                "artifact_fingerprint": artifact["artifact_fingerprint"],
                "result_fingerprint": artifact["result_fingerprint"],
                "file_sha256": before,
            }
        )
        del artifact
    rebuilt_summary = primary._summary_from_stream_records(
        manifest,
        ledger,
        code_revision=summary["code_revision"],
        environment=summary["environment"],
        records=rebuilt_records,
    )
    if rebuilt_summary != summary:
        raise StudyManifestError("complete summary does not replay for projection")
    final_paths = primary._exact_phase_block_paths(output_root, expected_keys)
    if final_paths != paths:
        raise StudyManifestError("phase registry changed during descriptive projection")
    for record in byte_registry:
        if primary._sha256_file(final_paths[record["block_key"]]) != record["file_sha256"]:
            raise StudyManifestError("phase block changed during descriptive projection")
    rows.sort(key=_parent_sort_key)
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "phase": manifest.phase.value,
        "study_id": manifest.study_id,
        "projection_revision": projection_revision,
        "execution_revision": summary["code_revision"],
        "base_analysis_revision": BASE_ANALYSIS_REVISION,
        "source_fingerprints": {
            "manifest": manifest.fingerprint,
            "seed_ledger": ledger.fingerprint,
            "run_summary": summary["summary_fingerprint"],
            "calibration_evidence": calibration["evidence_fingerprint"],
            "formal_precision": precision["precision_fingerprint"],
            "block_artifacts": artifact_fingerprints,
        },
        "metric_registry": _metric_registry(),
        "block_registry": byte_registry,
        "parent_contrasts": rows,
        "summaries": _build_summaries(manifest.phase.value, rows),
        "limitations": list(_LIMITATIONS),
    }
    evidence["projection_fingerprint"] = primary._mapping_fingerprint(evidence)
    validate_phase_projection(evidence)
    return evidence


def validate_phase_projection(value: object) -> None:
    top = _mapping(value, _TOP_FIELDS, "descriptive projection")
    if top["schema_version"] != SCHEMA_VERSION or top["status"] != STATUS:
        raise StudyManifestError("unsupported descriptive projection schema or status")
    if top["phase"] not in {"formal", "confirmation"}:
        raise StudyManifestError("descriptive projection phase differs")
    if top["study_id"] != f"synthetic-{top['phase']}-v1":
        raise StudyManifestError("descriptive projection study_id differs")
    primary._validate_digest(top["projection_revision"], "projection_revision", length=40)
    if top["execution_revision"] != EXECUTION_REVISION or top[
        "base_analysis_revision"
    ] != BASE_ANALYSIS_REVISION:
        raise StudyManifestError("descriptive projection revision bindings differ")
    if top["metric_registry"] != _metric_registry() or top["limitations"] != _LIMITATIONS:
        raise StudyManifestError("descriptive metric registry or limitations differ")
    source = _mapping(
        top["source_fingerprints"],
        {
            "manifest",
            "seed_ledger",
            "run_summary",
            "calibration_evidence",
            "formal_precision",
            "block_artifacts",
        },
        "descriptive source fingerprints",
    )
    for field in (
        "manifest",
        "seed_ledger",
        "run_summary",
        "calibration_evidence",
        "formal_precision",
    ):
        primary._validate_digest(source[field], field)
    if type(source["block_artifacts"]) is not list or len(source["block_artifacts"]) != 240:
        raise StudyManifestError("descriptive source block fingerprints differ")
    for digest in source["block_artifacts"]:
        primary._validate_digest(digest, "block artifact")
    blocks = _sequence_any(top["block_registry"], "descriptive block registry")
    if len(blocks) != 240:
        raise StudyManifestError("descriptive block registry count differs")
    expected_keys = primary._expected_block_keys()
    for index, record in enumerate(blocks):
        item = _mapping(
            record,
            {
                "block_key",
                "path",
                "artifact_fingerprint",
                "result_fingerprint",
                "file_sha256",
            },
            "descriptive block record",
        )
        key = expected_keys[index]
        if item["block_key"] != key or item["path"] != f"blocks/{key}.json":
            raise StudyManifestError("descriptive block registry is not canonical")
        for field in ("artifact_fingerprint", "result_fingerprint", "file_sha256"):
            primary._validate_digest(item[field], field)
        if item["artifact_fingerprint"] != source["block_artifacts"][index]:
            raise StudyManifestError("descriptive block fingerprint order differs")
    rows = _sequence_any(top["parent_contrasts"], "descriptive parent contrasts")
    if len(rows) != 4 * 20 * 3 * 4 * len(_METRICS):
        raise StudyManifestError("descriptive parent contrast count differs")
    expected_order = []
    for size in (30, 60, 120, 240):
        for model in primary._MODELS:
            for replicate in range(20):
                for source_family in primary._SOURCES:
                    for metric in _METRICS:
                        expected_order.append((size, model, replicate, source_family, metric))
    observed_order = []
    for row in rows:
        item = _mapping(row, _PARENT_FIELDS, "descriptive parent contrast")
        key = (
            item["node_count"],
            item["parent_model"],
            item["parent_replicate"],
            item["source_family"],
            item["metric"],
        )
        observed_order.append(key)
        expected_parent = (
            f"n{item['node_count']:04d}-r{item['parent_replicate']:04d}-"
            f"{item['parent_model']}"
        )
        if (
            item["phase"] != top["phase"]
            or item["metric_kind"] != _METRIC_KIND.get(item["metric"])
            or item["parent_graph_id"] != expected_parent
        ):
            raise StudyManifestError("descriptive parent identity differs")
        combined = _fraction(item["combined_parent_value"], "combined parent value")
        if item["metric_kind"] == "static-parent":
            if item["same_distribution_mean"] is not None or item[
                "distribution_shift_mean"
            ] is not None:
                raise StudyManifestError("static metric cannot have scope means")
        else:
            same = _fraction(item["same_distribution_mean"], "same mean")
            shifted = _fraction(item["distribution_shift_mean"], "shift mean")
            if combined != Fraction(4, 7) * same + Fraction(3, 7) * shifted:
                raise StudyManifestError("descriptive 4:3 aggregation differs")
    if observed_order != expected_order:
        raise StudyManifestError("descriptive parent contrasts are not canonical")
    expected_summaries = _build_summaries(top["phase"], rows)
    if top["summaries"] != expected_summaries:
        raise StudyManifestError("descriptive summaries do not replay")
    content = dict(top)
    supplied = content.pop("projection_fingerprint")
    if supplied != primary._mapping_fingerprint(content):
        raise StudyManifestError("descriptive projection fingerprint mismatch")


def load_phase_projection(
    path: Path,
    *,
    manifest,
    ledger,
    summary,
    calibration,
    precision,
    output_root: Path,
    projection_revision: str,
    artifact_loader=load_synthetic_block_artifact,
    block_projector=_project_block,
):
    """Load evidence only after a bounded complete replay of every raw block."""

    raw = primary._load_strict_json(path, "descriptive projection")
    validate_phase_projection(raw)
    expected = build_phase_projection(
        manifest,
        ledger,
        summary,
        calibration,
        precision,
        output_root=output_root,
        projection_revision=projection_revision,
        artifact_loader=artifact_loader,
        block_projector=block_projector,
    )
    if raw != expected:
        raise StudyManifestError("descriptive projection complete replay mismatch")
    return raw


def _verify_projection_snapshot(root: Path, revision: str) -> None:
    primary._validate_digest(revision, "projection_revision", length=40)
    primary._verify_analysis_snapshot(root, BASE_ANALYSIS_REVISION, EXECUTION_REVISION)
    for path in _TOOL_PATHS:
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}:{path}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if exists.returncode != 0:
            raise StudyManifestError("projection source is absent from declared revision")
    clean = subprocess.run(
        ["git", "diff", "--quiet", revision, "--", *_TOOL_PATHS],
        cwd=root,
        check=False,
    )
    if clean.returncode != 0:
        raise StudyManifestError("projection source differs from declared revision")


def generate_phase_projection(args) -> Path:
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
    _verify_projection_snapshot(root, args.projection_revision)
    manifest = load_study_design_manifest(paths[0])
    ledger = build_study_seed_ledger(manifest)
    summary = load_study_run_summary(paths[1], manifest=manifest, ledger=ledger)
    calibration_manifest = load_study_design_manifest(paths[2])
    calibration = load_audited_calibration_evidence(paths[3])
    precision = load_formal_precision_evidence(
        paths[4], calibration_evidence=calibration
    )
    validate_frozen_execution_context(
        manifest,
        code_revision=summary["code_revision"],
        environment=summary["environment"],
        precision_evidence=precision,
        calibration_manifest=calibration_manifest,
    )
    evidence = build_phase_projection(
        manifest,
        ledger,
        summary,
        calibration,
        precision,
        output_root=paths[1].parent.resolve(),
        projection_revision=args.projection_revision,
    )
    target = primary._evidence_target(root, args.output, paths)
    primary._write_new_or_identical(target, evidence, "descriptive projection")
    return target


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("summary")
    parser.add_argument("calibration_manifest")
    parser.add_argument("calibration_evidence")
    parser.add_argument("precision")
    parser.add_argument("--projection-revision", required=True)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    target = generate_phase_projection(_parser().parse_args(argv))
    print(target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
