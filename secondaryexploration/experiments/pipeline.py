"""Train-once synthetic parent blocks and evaluate only registered held-out traces."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from secondaryexploration.optimization import (
    CapacityOptimizationManifest,
    CapacityOptimizationPlan,
    CapacityOptimizationResult,
    CapacityTrainingScenario,
    DemandAwareObjectiveWeights,
    DemandAwareSearchPlan,
    DemandAwareTopologyResult,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    optimize_common_capacity,
    train_demand_aware_topology,
)
from secondaryexploration.topology import (
    HypergraphTopology,
    ParentGraphDraw,
    ParentGraphModel,
    clique_expansion,
    closed_neighborhood_nch,
    fixed_hyperedge_size,
    match_binary_to_topology,
)

from .paired import (
    PairedRunManifest,
    PairedRunResult,
    TopologyVariant,
    run_paired_experiment,
)
from .study import (
    StudyDesignManifest,
    StudyManifestError,
    StudyParentSeed,
    StudySeedLedger,
    StudyTraceSeed,
    TrafficRegimeRole,
    build_study_seed_ledger,
    generate_declared_parent_ensemble,
    generate_declared_request_trace,
)


SYNTHETIC_PIPELINE_VERSION = "synthetic-parent-block.v1"


@dataclass(frozen=True, slots=True)
class TrainedStudyVariant:
    """One structural variant and its commonly optimized initial state."""

    variant_id: str
    family: str
    topology: HypergraphTopology
    capacity_result: CapacityOptimizationResult

    def __post_init__(self) -> None:
        _validate_identifier(self.variant_id, "variant_id")
        _validate_identifier(self.family, "family")
        if not isinstance(self.topology, HypergraphTopology):
            raise StudyManifestError("variant topology is malformed")
        if not isinstance(self.capacity_result, CapacityOptimizationResult):
            raise StudyManifestError("variant capacity_result is malformed")
        topology_structure = tuple(
            (edge.hyperedge_id, edge.members) for edge in self.topology.hyperedges
        )
        state_structure = tuple(
            (edge.hyperedge_id, edge.members)
            for edge in self.capacity_result.state.hyperedges
        )
        if topology_structure != state_structure:
            raise StudyManifestError("optimized state does not match variant topology")

    @property
    def initial_state(self):
        return self.capacity_result.state


@dataclass(frozen=True, slots=True)
class ResourceComparisonPanel:
    """One hypergraph source and its exact or adjacent binary incidence match."""

    panel_id: str
    source_variant_id: str
    binary_variant_ids: tuple[str, ...]
    source_incidence_count: int
    binary_incidence_deltas: tuple[int, ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.panel_id, "panel_id")
        _validate_identifier(self.source_variant_id, "source_variant_id")
        if type(self.binary_variant_ids) is not tuple or not self.binary_variant_ids:
            raise StudyManifestError("binary_variant_ids must be a nonempty tuple")
        for value in self.binary_variant_ids:
            _validate_identifier(value, "binary_variant_id")
        if len(set(self.binary_variant_ids)) != len(self.binary_variant_ids):
            raise StudyManifestError("binary_variant_ids must be unique")
        if type(self.source_incidence_count) is not int or self.source_incidence_count < 1:
            raise StudyManifestError("source_incidence_count must be positive")
        if (
            type(self.binary_incidence_deltas) is not tuple
            or len(self.binary_incidence_deltas) != len(self.binary_variant_ids)
            or any(delta not in {-1, 0, 1} for delta in self.binary_incidence_deltas)
        ):
            raise StudyManifestError("binary incidence deltas must be aligned -1/0/+1")
        if self.source_incidence_count % 2 == 0:
            if self.binary_incidence_deltas != (0,):
                raise StudyManifestError("even source incidence requires one exact binary match")
        elif self.binary_incidence_deltas != (-1, 1):
            raise StudyManifestError("odd source incidence requires ordered -1/+1 brackets")


@dataclass(frozen=True, slots=True)
class CliqueCostReference:
    """Binary clique-expansion infrastructure witness, not a service competitor."""

    reference_id: str
    source_variant_id: str
    topology: HypergraphTopology

    def __post_init__(self) -> None:
        _validate_identifier(self.reference_id, "reference_id")
        _validate_identifier(self.source_variant_id, "source_variant_id")
        if not isinstance(self.topology, HypergraphTopology):
            raise StudyManifestError("clique cost topology is malformed")
        if any(edge.arity != 2 for edge in self.topology.hyperedges):
            raise StudyManifestError("clique cost reference must be entirely binary")


@dataclass(frozen=True, slots=True)
class HeldOutPairedRun:
    """One registered test trace and its complete paired topology result."""

    trace_seed: StudyTraceSeed
    result: PairedRunResult

    def __post_init__(self) -> None:
        if not isinstance(self.trace_seed, StudyTraceSeed) or self.trace_seed.split != "test":
            raise StudyManifestError("held-out run requires a registered test trace seed")
        if not isinstance(self.result, PairedRunResult):
            raise StudyManifestError("held-out paired result is malformed")
        if self.result.manifest.trace.root_seed != self.trace_seed.trace_root_seed:
            raise StudyManifestError("held-out result uses the wrong traffic seed")
        if self.result.manifest.routing_root_seed != self.trace_seed.routing_root_seed:
            raise StudyManifestError("held-out result uses the wrong routing seed")


@dataclass(frozen=True, slots=True)
class SyntheticParentBlockResult:
    """Complete train-once and held-out evaluation record for one parent graph."""

    pipeline_version: str
    manifest_fingerprint: str
    seed_ledger_fingerprint: str
    parent_seed: StudyParentSeed
    parent_model: ParentGraphModel
    parent_draw: ParentGraphDraw
    training_trace_seeds: tuple[StudyTraceSeed, ...]
    training_demand: DirectedDemandMatrix
    demand_aware_result: DemandAwareTopologyResult
    variants: tuple[TrainedStudyVariant, ...]
    panels: tuple[ResourceComparisonPanel, ...]
    clique_cost_references: tuple[CliqueCostReference, ...]
    held_out_runs: tuple[HeldOutPairedRun, ...]

    def __post_init__(self) -> None:
        if self.pipeline_version != SYNTHETIC_PIPELINE_VERSION:
            raise StudyManifestError("unsupported synthetic pipeline version")
        _validate_digest(self.manifest_fingerprint, "manifest_fingerprint")
        _validate_digest(self.seed_ledger_fingerprint, "seed_ledger_fingerprint")
        if not isinstance(self.parent_seed, StudyParentSeed):
            raise StudyManifestError("parent_seed is malformed")
        if type(self.parent_model) is not ParentGraphModel:
            raise StudyManifestError("parent_model is malformed")
        if not isinstance(self.parent_draw, ParentGraphDraw):
            raise StudyManifestError("parent_draw is malformed")
        if self.parent_draw.model is not self.parent_model:
            raise StudyManifestError("parent draw model does not match parent_model")
        if type(self.training_trace_seeds) is not tuple or not self.training_trace_seeds:
            raise StudyManifestError("training_trace_seeds must be nonempty")
        if any(
            not isinstance(item, StudyTraceSeed) or item.split != "training"
            for item in self.training_trace_seeds
        ):
            raise StudyManifestError("training_trace_seeds contain a non-training record")
        training_keys = tuple(_trace_key(item) for item in self.training_trace_seeds)
        if (
            tuple(sorted(training_keys)) != training_keys
            or len(set(training_keys)) != len(training_keys)
            or any(
                item.node_count != self.parent_seed.node_count
                or item.parent_replicate != self.parent_seed.parent_replicate
                for item in self.training_trace_seeds
            )
        ):
            raise StudyManifestError(
                "training trace seeds must be canonical, unique, and parent-bound"
            )
        if not isinstance(self.training_demand, DirectedDemandMatrix):
            raise StudyManifestError("training_demand is malformed")
        if self.training_demand.nodes != self.parent_draw.graph.nodes:
            raise StudyManifestError("training demand does not match parent nodes")
        if not isinstance(self.demand_aware_result, DemandAwareTopologyResult):
            raise StudyManifestError("demand_aware_result is malformed")
        if type(self.variants) is not tuple or not self.variants:
            raise StudyManifestError("variants must be a nonempty tuple")
        if any(not isinstance(item, TrainedStudyVariant) for item in self.variants):
            raise StudyManifestError("variants contain a malformed entry")
        variant_ids = tuple(item.variant_id for item in self.variants)
        if tuple(sorted(variant_ids)) != variant_ids or len(set(variant_ids)) != len(variant_ids):
            raise StudyManifestError("variants must be canonical with unique identifiers")
        if type(self.panels) is not tuple or any(
            not isinstance(item, ResourceComparisonPanel) for item in self.panels
        ):
            raise StudyManifestError("panels are malformed")
        panel_ids = tuple(item.panel_id for item in self.panels)
        if tuple(sorted(panel_ids)) != panel_ids or len(set(panel_ids)) != len(panel_ids):
            raise StudyManifestError("panels must be canonical with unique identifiers")
        known = set(variant_ids)
        variants_by_id = {item.variant_id: item for item in self.variants}
        if any(
            item.topology.nodes != self.parent_draw.graph.nodes
            for item in self.variants
        ):
            raise StudyManifestError("variant topology does not match parent nodes")
        capacity_manifest_ids = {
            item.capacity_result.manifest_fingerprint for item in self.variants
        }
        capacity_plans = {item.capacity_result.plan for item in self.variants}
        if len(capacity_manifest_ids) != 1 or len(capacity_plans) != 1:
            raise StudyManifestError(
                "all variants require one common capacity manifest and plan"
            )
        for panel in self.panels:
            if panel.source_variant_id not in known or not set(panel.binary_variant_ids) <= known:
                raise StudyManifestError("a resource panel references an unknown variant")
            source_variant = variants_by_id[panel.source_variant_id]
            if source_variant.family != panel.source_variant_id:
                raise StudyManifestError("source variant family does not match its identifier")
            if source_variant.topology.resources.incidence_count != panel.source_incidence_count:
                raise StudyManifestError("resource panel source incidence is inconsistent")
            for binary_id, delta in zip(
                panel.binary_variant_ids,
                panel.binary_incidence_deltas,
            ):
                binary_variant = variants_by_id[binary_id]
                if (
                    binary_variant.family != "binary-matched"
                    or any(edge.arity != 2 for edge in binary_variant.topology.hyperedges)
                    or binary_variant.topology.resources.incidence_count
                    != panel.source_incidence_count + delta
                ):
                    raise StudyManifestError("resource panel binary match is inconsistent")
        panel_variant_ids = {
            variant_id
            for panel in self.panels
            for variant_id in (panel.source_variant_id, *panel.binary_variant_ids)
        }
        if known != panel_variant_ids:
            raise StudyManifestError("variants and resource panels do not cover each other")
        if (
            "demand-aware" not in variants_by_id
            or variants_by_id["demand-aware"].topology
            != self.demand_aware_result.topology
        ):
            raise StudyManifestError("demand-aware result does not match its study variant")
        if type(self.clique_cost_references) is not tuple or any(
            not isinstance(item, CliqueCostReference)
            for item in self.clique_cost_references
        ):
            raise StudyManifestError("clique_cost_references are malformed")
        reference_ids = tuple(item.reference_id for item in self.clique_cost_references)
        if (
            tuple(sorted(reference_ids)) != reference_ids
            or len(set(reference_ids)) != len(reference_ids)
        ):
            raise StudyManifestError(
                "clique cost references must be canonical with unique identifiers"
            )
        panel_source_ids = tuple(panel.source_variant_id for panel in self.panels)
        reference_source_ids = tuple(
            item.source_variant_id for item in self.clique_cost_references
        )
        if (
            len(reference_source_ids) != len(panel_source_ids)
            or set(reference_source_ids) != set(panel_source_ids)
            or len(set(reference_source_ids)) != len(reference_source_ids)
        ):
            raise StudyManifestError(
                "every hypergraph source requires exactly one clique cost reference"
            )
        for reference in self.clique_cost_references:
            expected_source = variants_by_id[reference.source_variant_id].topology
            if reference.reference_id != f"clique-cost-{reference.source_variant_id}":
                raise StudyManifestError("clique cost reference identifier is not canonical")
            if reference.topology != clique_expansion(expected_source):
                raise StudyManifestError(
                    "clique cost reference is not the exact source clique expansion"
                )
        if type(self.held_out_runs) is not tuple or not self.held_out_runs:
            raise StudyManifestError("held_out_runs must be a nonempty tuple")
        if any(not isinstance(item, HeldOutPairedRun) for item in self.held_out_runs):
            raise StudyManifestError("held_out_runs contain a malformed entry")
        held_out_keys = tuple(_trace_key(item.trace_seed) for item in self.held_out_runs)
        if tuple(sorted(held_out_keys)) != held_out_keys or len(set(held_out_keys)) != len(held_out_keys):
            raise StudyManifestError("held-out runs must be canonical and unique")
        expected_paired_variants = tuple(
            TopologyVariant(
                item.variant_id,
                item.family,
                item.topology,
                item.initial_state,
            )
            for item in self.variants
        )
        for item in self.held_out_runs:
            if (
                item.trace_seed.node_count != self.parent_seed.node_count
                or item.trace_seed.parent_replicate
                != self.parent_seed.parent_replicate
            ):
                raise StudyManifestError("held-out trace seed does not match its parent")
            if item.result.manifest.variants != expected_paired_variants:
                raise StudyManifestError(
                    "held-out paired variants do not match the trained variants"
                )

    @property
    def fingerprint(self) -> str:
        payload = {
            "pipeline_version": self.pipeline_version,
            "manifest_fingerprint": self.manifest_fingerprint,
            "seed_ledger_fingerprint": self.seed_ledger_fingerprint,
            "parent": (
                self.parent_seed.node_count,
                self.parent_seed.parent_replicate,
                self.parent_seed.ensemble_base_seed,
                self.parent_seed.capacity_search_seed,
                self.parent_seed.binary_matching_seed,
                self.parent_model.value,
                self.parent_draw.root_seed,
                self.parent_draw.accepted_attempt,
                self.parent_draw.draw_seed,
                self.parent_draw.blocks,
                self.parent_draw.attachment_count,
                self.parent_draw.within_edge_count,
                tuple(edge.endpoints for edge in self.parent_draw.graph.edges),
            ),
            "training_trace_seeds": tuple(
                _trace_seed_payload(item) for item in self.training_trace_seeds
            ),
            "training_demand": self.training_demand.fingerprint,
            "demand_topology": _demand_result_payload(self.demand_aware_result),
            "variants": tuple(
                (
                    item.variant_id,
                    item.family,
                    _topology_payload(item.topology),
                    _capacity_result_payload(item.capacity_result),
                )
                for item in self.variants
            ),
            "panels": tuple(
                (
                    item.panel_id,
                    item.source_variant_id,
                    item.binary_variant_ids,
                    item.source_incidence_count,
                    item.binary_incidence_deltas,
                )
                for item in self.panels
            ),
            "clique_cost_references": tuple(
                (
                    item.reference_id,
                    item.source_variant_id,
                    item.topology.nodes,
                    tuple(
                        (edge.hyperedge_id, edge.members)
                        for edge in item.topology.hyperedges
                    ),
                )
                for item in self.clique_cost_references
            ),
            "held_out": tuple(
                (
                    item.trace_seed.regime_id,
                    item.trace_seed.trace_replicate,
                    _trace_seed_payload(item.trace_seed),
                    item.result.manifest_fingerprint,
                    tuple(
                        (
                            result.variant_id,
                            _simulation_payload(result.simulation),
                        )
                        for result in item.result.variant_results
                    ),
                )
                for item in self.held_out_runs
            ),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def run_synthetic_parent_block(
    manifest: StudyDesignManifest,
    parent_seed: StudyParentSeed,
    parent_model: ParentGraphModel,
) -> SyntheticParentBlockResult:
    """Train on registered traces once and run every registered held-out trace."""

    if not isinstance(manifest, StudyDesignManifest):
        raise StudyManifestError("manifest must be a StudyDesignManifest")
    if not isinstance(parent_seed, StudyParentSeed):
        raise StudyManifestError("parent_seed must be a StudyParentSeed")
    if type(parent_model) is not ParentGraphModel:
        raise StudyManifestError("parent_model must be a ParentGraphModel")
    ledger = build_study_seed_ledger(manifest)
    if parent_seed not in ledger.parent_seeds:
        raise StudyManifestError("parent_seed is not registered by the manifest")
    ensemble = generate_declared_parent_ensemble(manifest, parent_seed)
    draw = {
        ParentGraphModel.ER_GNM: ensemble.er,
        ParentGraphModel.BARABASI_ALBERT: ensemble.ba,
        ParentGraphModel.SBM_FIXED_COUNT: ensemble.sbm,
    }[parent_model]
    parent = draw.graph
    matching_trace_records = tuple(
        item
        for item in ledger.trace_seeds
        if item.node_count == parent_seed.node_count
        and item.parent_replicate == parent_seed.parent_replicate
    )
    training_records = tuple(item for item in matching_trace_records if item.split == "training")
    test_records = tuple(item for item in matching_trace_records if item.split == "test")
    training_scenarios = tuple(
        CapacityTrainingScenario(
            scenario_id=f"{item.regime_id}.r{item.trace_replicate:04d}",
            regime_id=item.regime_id,
            trace=generate_declared_request_trace(manifest, item),
            routing_root_seed=item.routing_root_seed,
        )
        for item in training_records
    )
    training_demand = DirectedDemandMatrix.from_requests(
        parent.nodes,
        tuple(
            request
            for scenario in training_scenarios
            for request in scenario.trace.requests
        ),
    )

    nch = closed_neighborhood_nch(parent)
    fhs3 = fixed_hyperedge_size(parent, 3)
    fhs5 = fixed_hyperedge_size(parent, 5)
    declared_sources = {
        "fhs3": fhs3,
        "fhs5": fhs5,
        "nch": nch,
    }
    if manifest.demand_aware_seed_family not in declared_sources:
        raise StudyManifestError("demand-aware seed family is unavailable")
    demand_seed = declared_sources[manifest.demand_aware_seed_family]
    weights = manifest.objective_weights
    topology_manifest = DemandAwareTrainingManifest.create(
        parent,
        training_demand,
        demand_seed.resources.incidence_count,
        max(edge.arity for edge in demand_seed.hyperedges),
        DemandAwareObjectiveWeights(
            weights.bidirectional_capture,
            weights.directional_imbalance,
            weights.participation,
            weights.coordination_overlap,
        ),
    )
    topology_result = train_demand_aware_topology(
        parent,
        training_demand,
        demand_seed,
        topology_manifest,
        DemandAwareSearchPlan(
            manifest.topology_search.proposal_budget,
            manifest.topology_search.maximum_rounds,
            manifest.topology_search.maximum_move_edges,
        ),
    )
    sources = {
        "demand-aware": topology_result.topology,
        **declared_sources,
    }
    if tuple(sorted(sources)) != manifest.topology_families:
        raise StudyManifestError("constructed topology families do not match the manifest")
    topology_registry: dict[str, tuple[str, HypergraphTopology]] = {
        source_id: (source_id, topology) for source_id, topology in sources.items()
    }
    clique_references = tuple(
        CliqueCostReference(
            reference_id=f"clique-cost-{source_id}",
            source_variant_id=source_id,
            topology=clique_expansion(source),
        )
        for source_id, source in sorted(sources.items())
    )
    panels = []
    for source_id, source in sorted(sources.items()):
        match = match_binary_to_topology(
            parent,
            source,
            root_seed=parent_seed.binary_matching_seed,
        )
        if match.is_exact:
            binary_ids = (f"binary-i{match.lower.resources.incidence_count:08d}",)
            deltas = (0,)
            _register_binary_topology(topology_registry, binary_ids[0], match.lower)
        else:
            binary_ids = (
                f"binary-i{match.lower.resources.incidence_count:08d}",
                f"binary-i{match.upper.resources.incidence_count:08d}",
            )
            deltas = (-1, 1)
            _register_binary_topology(topology_registry, binary_ids[0], match.lower)
            _register_binary_topology(topology_registry, binary_ids[1], match.upper)
        panels.append(
            ResourceComparisonPanel(
                panel_id=f"panel-{source_id}",
                source_variant_id=source_id,
                binary_variant_ids=binary_ids,
                source_incidence_count=source.resources.incidence_count,
                binary_incidence_deltas=deltas,
            )
        )

    initializer = manifest.capacity_initializer
    capacity_manifest = CapacityOptimizationManifest.create(
        training_demand,
        manifest.per_node_capital,
        initializer.load_weight,
        initializer.risk_weight,
        manifest.lower_quantile,
        training_scenarios,
    )
    capacity_plan = CapacityOptimizationPlan(
        manifest.capacity_search.evaluation_budget,
        parent_seed.capacity_search_seed,
        manifest.capacity_search.proposals_per_step_level,
    )
    variants = tuple(
        TrainedStudyVariant(
            variant_id=variant_id,
            family=family,
            topology=topology,
            capacity_result=optimize_common_capacity(
                topology,
                training_demand,
                capacity_manifest,
                capacity_plan,
            ),
        )
        for variant_id, (family, topology) in sorted(topology_registry.items())
    )
    topology_variants = tuple(
        TopologyVariant(
            item.variant_id,
            item.family,
            item.topology,
            item.initial_state,
        )
        for item in variants
    )
    held_out = []
    for record in test_records:
        trace = generate_declared_request_trace(manifest, record)
        paired_manifest = PairedRunManifest(
            block_id=(
                f"{manifest.study_id}.n{parent_seed.node_count}."
                f"r{parent_seed.parent_replicate}.{parent_model.value}."
                f"{record.regime_id}.t{record.trace_replicate}"
            ),
            trace=trace,
            routing_root_seed=record.routing_root_seed,
            variants=topology_variants,
        )
        held_out.append(
            HeldOutPairedRun(
                trace_seed=record,
                result=run_paired_experiment(paired_manifest),
            )
        )
    return SyntheticParentBlockResult(
        pipeline_version=SYNTHETIC_PIPELINE_VERSION,
        manifest_fingerprint=manifest.fingerprint,
        seed_ledger_fingerprint=ledger.fingerprint,
        parent_seed=parent_seed,
        parent_model=parent_model,
        parent_draw=draw,
        training_trace_seeds=training_records,
        training_demand=training_demand,
        demand_aware_result=topology_result,
        variants=variants,
        panels=tuple(sorted(panels, key=lambda item: item.panel_id)),
        clique_cost_references=clique_references,
        held_out_runs=tuple(sorted(held_out, key=lambda item: _trace_key(item.trace_seed))),
    )


def validate_synthetic_parent_block_result(
    result: SyntheticParentBlockResult,
    manifest: StudyDesignManifest,
    parent_seed: StudyParentSeed,
    parent_model: ParentGraphModel,
) -> None:
    """Regenerate training and all held-out runs, rejecting any altered record."""

    if not isinstance(result, SyntheticParentBlockResult):
        raise StudyManifestError("result must be a SyntheticParentBlockResult")
    exact = run_synthetic_parent_block(manifest, parent_seed, parent_model)
    if result != exact:
        raise StudyManifestError("parent block result does not match complete replay")


def _trace_key(item: StudyTraceSeed) -> tuple[int, int, str, str, int]:
    return (
        item.node_count,
        item.parent_replicate,
        item.split,
        item.regime_id,
        item.trace_replicate,
    )


def _trace_seed_payload(item: StudyTraceSeed) -> object:
    return (
        item.node_count,
        item.parent_replicate,
        item.split,
        item.regime_id,
        item.trace_replicate,
        item.trace_root_seed,
        item.routing_root_seed,
    )


def _topology_payload(topology: HypergraphTopology) -> object:
    return (
        topology.nodes,
        tuple(
            (edge.hyperedge_id, edge.members)
            for edge in topology.hyperedges
        ),
    )


def _register_binary_topology(
    registry: dict[str, tuple[str, HypergraphTopology]],
    variant_id: str,
    topology: HypergraphTopology,
) -> None:
    existing = registry.get(variant_id)
    value = ("binary-matched", topology)
    if existing is not None and existing != value:
        raise StudyManifestError(
            "one binary incidence identifier resolved to inconsistent topologies"
        )
    registry[variant_id] = value


def _demand_result_payload(result: DemandAwareTopologyResult) -> object:
    score = result.score
    return (
        result.manifest_fingerprint,
        result.seed_topology_fingerprint,
        result.candidate_pool_fingerprint,
        result.search_plan.fingerprint,
        result.proposal_fingerprints,
        result.feasible_evaluations,
        tuple(
            (
                step.round_index,
                step.proposal_start,
                step.proposal_stop,
                step.feasible_evaluations,
                _fraction_pair(step.before_objective),
                _fraction_pair(step.after_objective),
                step.accepted_topology_fingerprint,
            )
            for step in result.steps
        ),
        (
            score.manifest_fingerprint,
            score.topology_fingerprint,
            score.captured_bidirectional,
            score.captured_imbalance,
            score.participation_burden,
            score.coordination_overlap_burden,
            _fraction_pair(score.normalized_capture),
            _fraction_pair(score.normalized_imbalance),
            _fraction_pair(score.normalized_participation),
            _fraction_pair(score.normalized_coordination_overlap),
            _fraction_pair(score.objective_value),
        ),
    )


def _capacity_result_payload(result: CapacityOptimizationResult) -> object:
    return (
        result.manifest_fingerprint,
        result.topology_fingerprint,
        result.plan.fingerprint,
        result.uniform_score.fingerprint,
        result.load_risk_score.fingerprint,
        result.starting_source,
        tuple(
            (
                proposal.evaluation_index,
                proposal.node_id,
                proposal.donor_edge_id,
                proposal.recipient_edge_id,
                proposal.requested_transfer,
                proposal.actual_transfer,
                proposal.state_fingerprint,
                proposal.score.fingerprint,
            )
            for proposal in result.proposals
        ),
        tuple(
            (
                step.evaluation_index,
                step.before_state_fingerprint,
                step.after_state_fingerprint,
                step.before_score_fingerprint,
                step.after_score_fingerprint,
            )
            for step in result.steps
        ),
        result.score.fingerprint,
    )


def _simulation_payload(simulation) -> object:
    return (
        tuple(
            (edge.hyperedge_id, edge.balances)
            for edge in simulation.initial_state.hyperedges
        ),
        tuple(
            (
                outcome.request_index,
                (
                    outcome.request.source,
                    outcome.request.destination,
                    outcome.request.amount,
                ),
                None
                if outcome.search_result.route is None
                else tuple(
                    (step.hyperedge_id, step.payer, step.payee)
                    for step in outcome.search_result.route.steps
                ),
                outcome.search_result.shortest_hops,
                None
                if outcome.search_result.bottleneck is None
                else _fraction_pair(outcome.search_result.bottleneck),
                outcome.search_result.tied_route_count,
                tuple(
                    (coordinate.hyperedge_id, coordinate.node_id)
                    for coordinate in outcome.depleted_coordinates
                ),
            )
            for outcome in simulation.outcomes
        ),
        tuple(
            (edge.hyperedge_id, edge.balances)
            for edge in simulation.final_state.hyperedges
        ),
        (simulation.tau_dep.observed, simulation.tau_dep.request_index),
        (simulation.tau_nopath.observed, simulation.tau_nopath.request_index),
        (simulation.tau_rej.observed, simulation.tau_rej.request_index),
    )


def _fraction_pair(value) -> tuple[int, int]:
    return (value.numerator, value.denominator)


def _validate_identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise StudyManifestError(f"{label} must be a nonempty unpadded string")


def _validate_digest(value: object, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError(f"{label} must be a lowercase SHA-256 digest")


__all__ = [
    "CliqueCostReference",
    "HeldOutPairedRun",
    "ResourceComparisonPanel",
    "SyntheticParentBlockResult",
    "TrainedStudyVariant",
    "run_synthetic_parent_block",
    "validate_synthetic_parent_block_result",
]
