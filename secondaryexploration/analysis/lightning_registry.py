"""Replayable diagnostic registry for accepted Lightning cross-sections."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from secondaryexploration.experiments.artifacts import atomic_write_json
from secondaryexploration.experiments.lightning_sources import (
    load_historical_gml_source_manifest,
    load_manifested_historical_gml_panel,
    load_manifested_rapid_gossip_snapshot,
    load_rapid_gossip_source_manifest,
)
from secondaryexploration.experiments.prior_paper import (
    PriorPaperInputManifest,
    load_prior_paper_dataset,
)
from secondaryexploration.topology import (
    LIGHTNING_STRATA,
    ParentGraph,
    StratifiedSamplingError,
    parent_graph_fingerprint,
    sample_lightning_subgraphs,
    stratify_lightning_parent,
)


LIGHTNING_REGISTRY_SCHEMA_VERSION = "lightning-sampling-registry.v1"
_LIMITATIONS = (
    "diagnostic replicate count is not the formal experimental sample size",
    "years are separate structural cross-sections, not a longitudinal causal panel",
    "samples from one source graph are structured subsamples, not independent networks",
    "stratum labels describe the anchor in the source LCC, not the whole induced sample",
    "public topology does not identify real Lightning payment-failure rates",
    "rank-score ties are resolved deterministically by public node identifier",
)
_CAPITAL_SEMANTICS = {
    "equal-node-only",
    "equal-node-and-public-capacity-derived",
}


class LightningRegistryError(ValueError):
    """Raised when a diagnostic registry is malformed or cannot replay."""


@dataclass(frozen=True, slots=True)
class LightningPanelInput:
    """One accepted source cross-section supplied to the registry builder."""

    panel_year: int
    source_id: str
    source_fingerprint: str
    capital_semantics: str
    parent: ParentGraph

    def __post_init__(self) -> None:
        if type(self.panel_year) is not int or self.panel_year < 2018:
            raise LightningRegistryError("panel_year is invalid")
        if type(self.source_id) is not str or not self.source_id:
            raise LightningRegistryError("source_id must be nonempty")
        _validate_digest(self.source_fingerprint, "source_fingerprint")
        if self.capital_semantics not in _CAPITAL_SEMANTICS:
            raise LightningRegistryError("capital_semantics is unsupported")
        if not isinstance(self.parent, ParentGraph):
            raise LightningRegistryError("parent must be a ParentGraph")


def build_lightning_sampling_registry(
    panels: tuple[LightningPanelInput, ...],
    *,
    base_seed: int,
    replicate_count: int,
    requested_sizes: tuple[int, ...],
) -> dict[str, object]:
    """Build and self-validate a compact diagnostic sampling registry."""

    _validate_panel_inputs(panels)
    if type(base_seed) is not int or not 0 <= base_seed < 2**64:
        raise LightningRegistryError("base_seed must be an unsigned 64-bit integer")
    if type(replicate_count) is not int or replicate_count <= 0:
        raise LightningRegistryError("replicate_count must be positive")
    if type(requested_sizes) is not tuple or not requested_sizes:
        raise LightningRegistryError("requested_sizes must be canonical and at least two")
    if any(type(value) is not int or value < 2 for value in requested_sizes):
        raise LightningRegistryError("requested_sizes must be canonical and at least two")
    if requested_sizes != tuple(sorted(set(requested_sizes))):
        raise LightningRegistryError("requested_sizes must be canonical and at least two")

    panel_records = [
        _build_panel_record(
            panel,
            base_seed=base_seed,
            replicate_count=replicate_count,
            requested_sizes=requested_sizes,
        )
        for panel in panels
    ]
    registry: dict[str, object] = {
        "schema_version": LIGHTNING_REGISTRY_SCHEMA_VERSION,
        "status": "diagnostic-only-not-formal-sample-size",
        "base_seed": base_seed,
        "replicate_count": replicate_count,
        "requested_sizes": list(requested_sizes),
        "panel_years": [panel.panel_year for panel in panels],
        "panels": panel_records,
        "limitations": list(_LIMITATIONS),
    }
    registry["registry_fingerprint"] = _mapping_fingerprint(registry)
    validate_lightning_sampling_registry(registry, panels)
    return registry


def validate_lightning_sampling_registry(
    registry: object,
    panels: tuple[LightningPanelInput, ...],
) -> None:
    """Fully rebuild a registry from its source parents and compare exactly."""

    if not isinstance(registry, Mapping):
        raise LightningRegistryError("registry must be a mapping")
    expected_fields = {
        "schema_version",
        "status",
        "base_seed",
        "replicate_count",
        "requested_sizes",
        "panel_years",
        "panels",
        "limitations",
        "registry_fingerprint",
    }
    if set(registry) != expected_fields:
        raise LightningRegistryError("registry top-level fields differ from the schema")
    if registry["schema_version"] != LIGHTNING_REGISTRY_SCHEMA_VERSION:
        raise LightningRegistryError("unsupported registry schema")
    if registry["status"] != "diagnostic-only-not-formal-sample-size":
        raise LightningRegistryError("registry cannot be relabelled as formal evidence")
    _validate_digest(registry["registry_fingerprint"], "registry_fingerprint")
    supplied_fingerprint = registry["registry_fingerprint"]
    content = dict(registry)
    del content["registry_fingerprint"]
    if supplied_fingerprint != _mapping_fingerprint(content):
        raise LightningRegistryError("registry fingerprint does not match its content")
    if registry["limitations"] != list(_LIMITATIONS):
        raise LightningRegistryError("registry limitations differ from the frozen contract")
    try:
        requested_sizes = tuple(registry["requested_sizes"])
    except TypeError as exc:
        raise LightningRegistryError("requested_sizes must be a list") from exc
    expected = _build_registry_without_validation(
        panels,
        base_seed=registry["base_seed"],
        replicate_count=registry["replicate_count"],
        requested_sizes=requested_sizes,
    )
    if dict(registry) != expected:
        raise LightningRegistryError("Lightning sampling registry replay mismatch")


def load_lightning_sampling_registry(
    path: str | Path,
    panels: tuple[LightningPanelInput, ...],
) -> dict[str, object]:
    """Load strict JSON and fully replay it from the accepted source parents."""

    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LightningRegistryError(f"cannot load Lightning registry: {path}") from exc
    if not isinstance(raw, dict):
        raise LightningRegistryError("Lightning registry must be a JSON object")
    validate_lightning_sampling_registry(raw, panels)
    return raw


def _build_registry_without_validation(
    panels: tuple[LightningPanelInput, ...],
    *,
    base_seed: int,
    replicate_count: int,
    requested_sizes: tuple[int, ...],
) -> dict[str, object]:
    _validate_panel_inputs(panels)
    panel_records = [
        _build_panel_record(
            panel,
            base_seed=base_seed,
            replicate_count=replicate_count,
            requested_sizes=requested_sizes,
        )
        for panel in panels
    ]
    result: dict[str, object] = {
        "schema_version": LIGHTNING_REGISTRY_SCHEMA_VERSION,
        "status": "diagnostic-only-not-formal-sample-size",
        "base_seed": base_seed,
        "replicate_count": replicate_count,
        "requested_sizes": list(requested_sizes),
        "panel_years": [panel.panel_year for panel in panels],
        "panels": panel_records,
        "limitations": list(_LIMITATIONS),
    }
    result["registry_fingerprint"] = _mapping_fingerprint(result)
    return result


def _build_panel_record(
    panel: LightningPanelInput,
    *,
    base_seed: int,
    replicate_count: int,
    requested_sizes: tuple[int, ...],
) -> dict[str, object]:
    strata = stratify_lightning_parent(panel.parent)
    try:
        samples = sample_lightning_subgraphs(
            panel.parent,
            panel.source_fingerprint,
            panel.panel_year,
            replicate_count,
            requested_sizes,
            base_seed,
            strata=strata,
        )
    except StratifiedSamplingError as exc:
        raise LightningRegistryError(
            f"panel {panel.panel_year} cannot satisfy the diagnostic grid"
        ) from exc
    core_numbers = dict(strata.core_numbers)
    degrees = dict(strata.degrees)
    bridge_metrics = {item.node_id: item for item in strata.bridge_metrics}
    sample_records = []
    for sample in samples:
        bridge = bridge_metrics.get(sample.anchor)
        sample_records.append(
            {
                "stratum": sample.stratum,
                "replicate_index": sample.replicate_index,
                "requested_size": sample.requested_size,
                "semantic_seed": sample.semantic_seed,
                "anchor": sample.anchor,
                "anchor_degree": degrees[sample.anchor],
                "anchor_core_number": core_numbers[sample.anchor],
                "anchor_components_after_removal": (
                    None if bridge is None else bridge.component_count_after_removal
                ),
                "anchor_fragmentation_gain": (
                    None if bridge is None else bridge.fragmentation_gain
                ),
                "node_count": len(sample.subgraph.nodes),
                "edge_count": sample.subgraph.edge_count,
                "discovery_order_fingerprint": _sequence_fingerprint(
                    sample.discovery_order
                ),
                "subgraph_fingerprint": parent_graph_fingerprint(sample.subgraph),
                "sample_fingerprint": sample.fingerprint(),
            }
        )
    return {
        "panel_year": panel.panel_year,
        "source_id": panel.source_id,
        "source_fingerprint": panel.source_fingerprint,
        "capital_semantics": panel.capital_semantics,
        "parent_fingerprint": parent_graph_fingerprint(panel.parent),
        "parent_node_count": len(panel.parent.nodes),
        "parent_edge_count": panel.parent.edge_count,
        "lcc_fingerprint": strata.lcc_fingerprint,
        "lcc_node_count": len(strata.lcc.nodes),
        "lcc_edge_count": strata.lcc.edge_count,
        "strata_fingerprint": strata.fingerprint(),
        "pool_width": strata.pool_width,
        "candidate_counts": {
            stratum: len(strata.candidates(stratum)) for stratum in LIGHTNING_STRATA
        },
        "boundary_ties": _boundary_ties(strata),
        "samples": sample_records,
        "overlap_diagnostics": _overlap_diagnostics(samples),
    }


def _boundary_ties(strata: object) -> dict[str, object]:
    core_numbers = dict(strata.core_numbers)
    degrees = dict(strata.degrees)
    scores = {
        node_id: (core_numbers[node_id], degrees[node_id])
        for node_id in strata.lcc.nodes
    }
    core_boundary = min(scores[node_id] for node_id in strata.core_candidates)
    peripheral_boundary = max(
        scores[node_id] for node_id in strata.peripheral_candidates
    )
    return {
        "core": _tie_record(scores, set(strata.core_candidates), core_boundary),
        "peripheral": _tie_record(
            scores,
            set(strata.peripheral_candidates),
            peripheral_boundary,
        ),
    }


def _tie_record(
    scores: Mapping[str, tuple[int, int]],
    selected: set[str],
    boundary: tuple[int, int],
) -> dict[str, object]:
    tied = {node_id for node_id, score in scores.items() if score == boundary}
    return {
        "boundary_core_number": boundary[0],
        "boundary_degree": boundary[1],
        "total_nodes_at_boundary_score": len(tied),
        "selected_nodes_at_boundary_score": len(tied & selected),
    }


def _overlap_diagnostics(samples: Sequence[object]) -> list[dict[str, object]]:
    indexed = {
        (sample.stratum, sample.replicate_index, sample.requested_size): set(
            sample.discovery_order
        )
        for sample in samples
    }
    strata = sorted({key[0] for key in indexed}, key=LIGHTNING_STRATA.index)
    sizes = sorted({key[2] for key in indexed})
    replicates = sorted({key[1] for key in indexed})
    records = []
    for stratum in strata:
        for size in sizes:
            for left_index, left in enumerate(replicates):
                for right in replicates[left_index + 1 :]:
                    left_nodes = indexed[(stratum, left, size)]
                    right_nodes = indexed[(stratum, right, size)]
                    intersection = len(left_nodes & right_nodes)
                    union = len(left_nodes | right_nodes)
                    records.append(
                        {
                            "stratum": stratum,
                            "requested_size": size,
                            "left_replicate": left,
                            "right_replicate": right,
                            "intersection_count": intersection,
                            "union_count": union,
                            "identical_node_set": intersection == union,
                        }
                    )
    return records


def load_accepted_panel_inputs(
    *,
    historical_manifest_path: str | Path,
    historical_archive_path: str | Path,
    prior_topology_path: str | Path,
    prior_trace_path: str | Path,
    rgs_manifest_path: str | Path,
    rgs_snapshot_path: str | Path,
) -> tuple[LightningPanelInput, ...]:
    """Load all four hash-attested public source panels."""

    historical = load_historical_gml_source_manifest(historical_manifest_path)
    panel_2020 = load_manifested_historical_gml_panel(
        historical, historical_archive_path, 2020
    )
    panel_2023 = load_manifested_historical_gml_panel(
        historical, historical_archive_path, 2023
    )
    prior_manifest = PriorPaperInputManifest.published()
    prior = load_prior_paper_dataset(
        prior_topology_path,
        prior_trace_path,
        prior_manifest,
    )
    rgs_manifest = load_rapid_gossip_source_manifest(rgs_manifest_path)
    rgs = load_manifested_rapid_gossip_snapshot(rgs_manifest, rgs_snapshot_path)
    return (
        LightningPanelInput(
            2020,
            f"{historical.source_id}:{panel_2020.member_name}",
            panel_2020.member_sha256,
            "equal-node-only",
            panel_2020.parent,
        ),
        LightningPanelInput(
            2022,
            f"prior-paper:{prior_manifest.upstream_commit}",
            prior_manifest.topology_sha256,
            "equal-node-and-public-capacity-derived",
            prior.parent,
        ),
        LightningPanelInput(
            2023,
            f"{historical.source_id}:{panel_2023.member_name}",
            panel_2023.member_sha256,
            "equal-node-only",
            panel_2023.parent,
        ),
        LightningPanelInput(
            2026,
            rgs_manifest.source_id,
            rgs.source_sha256,
            "equal-node-and-public-capacity-derived",
            rgs.parent,
        ),
    )


def _validate_panel_inputs(panels: tuple[LightningPanelInput, ...]) -> None:
    if type(panels) is not tuple or not panels:
        raise LightningRegistryError("panels must be a nonempty canonical tuple")
    if any(not isinstance(panel, LightningPanelInput) for panel in panels):
        raise LightningRegistryError("panels contain an invalid input")
    years = tuple(panel.panel_year for panel in panels)
    if years != tuple(sorted(set(years))):
        raise LightningRegistryError("panel years must be canonical and unique")


def _sequence_fingerprint(values: Sequence[str]) -> str:
    payload = json.dumps(
        list(values), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
        raise LightningRegistryError(f"{label} must be a lowercase SHA-256 digest")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LightningRegistryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the diagnostic-only Lightning sampling registry"
    )
    parser.add_argument("--historical-manifest", required=True)
    parser.add_argument("--historical-archive", required=True)
    parser.add_argument("--prior-topology", required=True)
    parser.add_argument("--prior-trace", required=True)
    parser.add_argument("--rgs-manifest", required=True)
    parser.add_argument("--rgs-snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-seed", type=int, default=2026080702)
    parser.add_argument("--replicate-count", type=int, default=3)
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[30, 60, 120, 240],
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    panels = load_accepted_panel_inputs(
        historical_manifest_path=args.historical_manifest,
        historical_archive_path=args.historical_archive,
        prior_topology_path=args.prior_topology,
        prior_trace_path=args.prior_trace,
        rgs_manifest_path=args.rgs_manifest,
        rgs_snapshot_path=args.rgs_snapshot,
    )
    registry = build_lightning_sampling_registry(
        panels,
        base_seed=args.base_seed,
        replicate_count=args.replicate_count,
        requested_sizes=tuple(args.sizes),
    )
    atomic_write_json(Path(args.output), registry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LIGHTNING_REGISTRY_SCHEMA_VERSION",
    "LightningPanelInput",
    "LightningRegistryError",
    "build_lightning_sampling_registry",
    "load_accepted_panel_inputs",
    "load_lightning_sampling_registry",
    "validate_lightning_sampling_registry",
]
