"""Strict study-design manifests and phase-separated deterministic seed ledgers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
import hashlib
import json
from math import comb
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any

from secondaryexploration.randomness import derive_seed
from secondaryexploration.topology import (
    MatchedParentEnsemble,
    matched_synthetic_parent_graphs,
)
from secondaryexploration.traffic import (
    AmountDistribution,
    DemandKernel,
    RequestTrace,
    community_local_kernel,
    directional_drift_kernel,
    generate_request_trace,
    hotspot_kernel,
    uniform_kernel,
)


STUDY_MANIFEST_SCHEMA_VERSION = 1
STUDY_SEED_LEDGER_VERSION = "study-seed-ledger.v1"
PRIMARY_SYNTHETIC_SIZES = (30, 60, 120, 240)
_MAX_UNSIGNED_64 = 2**64 - 1
_MAX_REPLICATES = 1_000_000
_MAX_PARENT_ATTEMPTS = 10_000
_PORTABLE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_NON_PORTABLE_PATH_CHARACTER = re.compile(r'[<>:"|?*\x00-\x1f]')


class StudyManifestError(ValueError):
    """Raised when a study design or seed record is incomplete or ambiguous."""


class StudyPhase(str, Enum):
    PILOT = "pilot"
    FORMAL = "formal"
    CONFIRMATION = "confirmation"


class TrafficKernelKind(str, Enum):
    UNIFORM = "uniform"
    COMMUNITY = "community"
    HOTSPOT = "hotspot"
    DIRECTIONAL = "directional"


class TrafficRegimeRole(str, Enum):
    TRAINING = "training"
    TEST = "test"


class TrafficShift(str, Enum):
    NONE = "none"
    SAME_DISTRIBUTION = "same_distribution"
    HOTSPOT_RELOCATION = "hotspot_relocation"
    DIRECTION_REVERSAL = "direction_reversal"
    CROSS_COMMUNITY_INCREASE = "cross_community_increase"


@dataclass(frozen=True, slots=True)
class SyntheticSizeCell:
    """Exact matched-parent resources for one network size."""

    node_count: int
    attachment_count: int
    block_count: int
    sbm_within_edge_count: int

    def __post_init__(self) -> None:
        if type(self.node_count) is not int or self.node_count not in PRIMARY_SYNTHETIC_SIZES:
            raise StudyManifestError("node_count must be a registered primary size")
        if (
            type(self.attachment_count) is not int
            or not 1 <= self.attachment_count < self.node_count
        ):
            raise StudyManifestError("attachment_count is invalid for node_count")
        if (
            type(self.block_count) is not int
            or not 2 <= self.block_count <= self.node_count
        ):
            raise StudyManifestError("block_count is invalid for node_count")
        if type(self.sbm_within_edge_count) is not int:
            raise StudyManifestError("sbm_within_edge_count must be an integer")
        block_sizes = _balanced_block_sizes(self.node_count, self.block_count)
        within_capacity = sum(comb(size, 2) for size in block_sizes)
        between_capacity = comb(self.node_count, 2) - within_capacity
        between_count = self.target_edge_count - self.sbm_within_edge_count
        if not 0 <= self.sbm_within_edge_count <= within_capacity:
            raise StudyManifestError("SBM within-edge count exceeds within-block capacity")
        if not self.block_count - 1 <= between_count <= between_capacity:
            raise StudyManifestError(
                "SBM between-edge count cannot support the declared connected block matrix"
            )
        if not self.node_count - 1 <= self.target_edge_count <= comb(self.node_count, 2):
            raise StudyManifestError("BA target edge count cannot form a simple connected graph")

    @property
    def target_edge_count(self) -> int:
        return self.attachment_count * (self.node_count - self.attachment_count)

    @property
    def blocks(self) -> tuple[tuple[str, ...], ...]:
        nodes = _canonical_nodes(self.node_count)
        sizes = _balanced_block_sizes(self.node_count, self.block_count)
        output = []
        offset = 0
        for size in sizes:
            output.append(nodes[offset : offset + size])
            offset += size
        return tuple(output)


@dataclass(frozen=True, slots=True)
class StudyObjectiveWeights:
    """Exact four-term topology-training coefficients."""

    bidirectional_capture: Fraction
    directional_imbalance: Fraction
    participation: Fraction
    coordination_overlap: Fraction

    def __post_init__(self) -> None:
        for name, value in (
            ("bidirectional_capture", self.bidirectional_capture),
            ("directional_imbalance", self.directional_imbalance),
            ("participation", self.participation),
            ("coordination_overlap", self.coordination_overlap),
        ):
            if not isinstance(value, Fraction) or value < 0:
                raise StudyManifestError(f"{name} must be a nonnegative Fraction")
        if self.bidirectional_capture <= 0:
            raise StudyManifestError("bidirectional_capture must be positive")


@dataclass(frozen=True, slots=True)
class CapacityInitializerWeights:
    load_weight: Fraction
    risk_weight: Fraction

    def __post_init__(self) -> None:
        for name, value in (
            ("load_weight", self.load_weight),
            ("risk_weight", self.risk_weight),
        ):
            if not isinstance(value, Fraction) or value < 0:
                raise StudyManifestError(f"{name} must be a nonnegative Fraction")


@dataclass(frozen=True, slots=True)
class TopologySearchBudget:
    proposal_budget: int
    maximum_rounds: int
    maximum_move_edges: int

    def __post_init__(self) -> None:
        _validate_positive_u64(self.proposal_budget, "topology proposal_budget")
        _validate_positive_u64(self.maximum_rounds, "topology maximum_rounds")
        if type(self.maximum_move_edges) is not int or not 1 <= self.maximum_move_edges <= 3:
            raise StudyManifestError("topology maximum_move_edges must be in [1, 3]")


@dataclass(frozen=True, slots=True)
class CapacitySearchBudget:
    evaluation_budget: int
    proposals_per_step_level: int

    def __post_init__(self) -> None:
        if (
            type(self.evaluation_budget) is not int
            or not 2 <= self.evaluation_budget <= _MAX_UNSIGNED_64
        ):
            raise StudyManifestError("capacity evaluation_budget must be at least two")
        _validate_positive_u64(
            self.proposals_per_step_level,
            "capacity proposals_per_step_level",
        )


@dataclass(frozen=True, slots=True)
class TrafficRegimeSpec:
    """One training or held-out traffic distribution and declared relationship."""

    regime_id: str
    role: TrafficRegimeRole
    kernel: TrafficKernelKind
    shift: TrafficShift
    training_reference: str | None
    parameters: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.regime_id, "regime_id")
        if type(self.role) is not TrafficRegimeRole:
            raise StudyManifestError("role must be a TrafficRegimeRole")
        if type(self.kernel) is not TrafficKernelKind:
            raise StudyManifestError("kernel must be a TrafficKernelKind")
        if type(self.shift) is not TrafficShift:
            raise StudyManifestError("shift must be a TrafficShift")
        if type(self.parameters) is not tuple:
            raise StudyManifestError("parameters must be a canonical tuple")
        names = []
        for item in self.parameters:
            if type(item) is not tuple or len(item) != 2:
                raise StudyManifestError("each traffic parameter must be a name/value pair")
            name, value = item
            _validate_identifier(name, "traffic parameter")
            if type(value) is not int:
                raise StudyManifestError("traffic parameter values must be integers")
            names.append(name)
        if tuple(sorted(self.parameters)) != self.parameters or len(set(names)) != len(names):
            raise StudyManifestError("traffic parameters must be canonical and unique")
        expected = {
            TrafficKernelKind.UNIFORM: set(),
            TrafficKernelKind.COMMUNITY: {"cross_weight", "within_weight"},
            TrafficKernelKind.HOTSPOT: {
                "base_weight",
                "hotspot_count",
                "hotspot_multiplier",
                "hotspot_offset",
            },
            TrafficKernelKind.DIRECTIONAL: {
                "forward_weight",
                "reverse_weight",
                "split_denominator",
                "split_numerator",
                "within_weight",
            },
        }[self.kernel]
        if set(names) != expected:
            raise StudyManifestError(
                f"{self.kernel.value} parameters must be exactly {tuple(sorted(expected))}"
            )
        for name, value in self.parameters:
            if name == "hotspot_offset":
                if value < 0:
                    raise StudyManifestError("hotspot_offset must be nonnegative")
            elif value <= 0:
                raise StudyManifestError(f"{name} must be positive")
        if self.role is TrafficRegimeRole.TRAINING:
            if self.shift is not TrafficShift.NONE or self.training_reference is not None:
                raise StudyManifestError("training regimes cannot declare shifts or references")
        else:
            if self.shift is TrafficShift.NONE:
                raise StudyManifestError("test regimes must declare their distribution relation")
            if self.training_reference is None:
                raise StudyManifestError("test regimes must reference a training regime")
            _validate_identifier(self.training_reference, "training_reference")

    def parameter(self, name: str) -> int:
        for parameter_name, value in self.parameters:
            if parameter_name == name:
                return value
        raise StudyManifestError(f"traffic parameter {name!r} is not declared")


@dataclass(frozen=True, slots=True)
class StudyDesignManifest:
    """Complete result-independent identity of one pilot or frozen study phase."""

    schema_version: int
    study_id: str
    phase: StudyPhase
    base_seed: int
    output_root: str
    basis_fingerprint: str | None
    code_revision: str | None
    environment_fingerprint: str | None
    size_cells: tuple[SyntheticSizeCell, ...]
    parent_replicates: int
    maximum_parent_attempts: int
    training_traces_per_regime: int
    test_traces_per_regime: int
    requests_per_node: int
    per_node_capital: int
    amount_weights: tuple[tuple[int, int], ...]
    topology_max_arities: tuple[int, ...]
    topology_families: tuple[str, ...]
    demand_aware_seed_family: str
    objective_weights: StudyObjectiveWeights
    topology_search: TopologySearchBudget
    capacity_initializer: CapacityInitializerWeights
    capacity_search: CapacitySearchBudget
    lower_quantile: Fraction
    regimes: tuple[TrafficRegimeSpec, ...]
    _fingerprint: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != STUDY_MANIFEST_SCHEMA_VERSION:
            raise StudyManifestError("unsupported study manifest schema_version")
        _validate_identifier(self.study_id, "study_id")
        if type(self.phase) is not StudyPhase:
            raise StudyManifestError("phase must be a StudyPhase")
        _validate_unsigned_64(self.base_seed, "base_seed")
        _validate_output_root(self.output_root)
        _validate_phase_provenance(self)
        if type(self.size_cells) is not tuple or not self.size_cells:
            raise StudyManifestError("size_cells must be a nonempty tuple")
        if any(not isinstance(cell, SyntheticSizeCell) for cell in self.size_cells):
            raise StudyManifestError("size_cells contain a malformed entry")
        node_counts = tuple(cell.node_count for cell in self.size_cells)
        if tuple(sorted(node_counts)) != node_counts or len(set(node_counts)) != len(node_counts):
            raise StudyManifestError("size_cells must be canonical and unique")
        if self.phase is not StudyPhase.PILOT and node_counts != PRIMARY_SYNTHETIC_SIZES:
            raise StudyManifestError("formal and confirmation phases require all primary sizes")
        for name, value in (
            ("parent_replicates", self.parent_replicates),
            ("training_traces_per_regime", self.training_traces_per_regime),
            ("test_traces_per_regime", self.test_traces_per_regime),
            ("requests_per_node", self.requests_per_node),
            ("per_node_capital", self.per_node_capital),
        ):
            if type(value) is not int or not 1 <= value <= _MAX_REPLICATES:
                raise StudyManifestError(f"{name} must be in [1, 1000000]")
        if (
            type(self.maximum_parent_attempts) is not int
            or not 1 <= self.maximum_parent_attempts <= _MAX_PARENT_ATTEMPTS
        ):
            raise StudyManifestError("maximum_parent_attempts must be in [1, 10000]")
        if self.phase is not StudyPhase.PILOT and self.parent_replicates < 2:
            raise StudyManifestError(
                "formal and confirmation phases require multiple parent graphs"
            )
        if type(self.amount_weights) is not tuple or not self.amount_weights:
            raise StudyManifestError("amount_weights must be a nonempty tuple")
        amounts = []
        for item in self.amount_weights:
            if (
                type(item) is not tuple
                or len(item) != 2
                or type(item[0]) is not int
                or type(item[1]) is not int
                or item[0] <= 0
                or item[1] <= 0
            ):
                raise StudyManifestError("amount_weights must contain positive integer pairs")
            amounts.append(item[0])
        if tuple(sorted(self.amount_weights)) != self.amount_weights or len(set(amounts)) != len(amounts):
            raise StudyManifestError("amount_weights must be canonical with unique amounts")
        if max(amounts) > self.per_node_capital:
            raise StudyManifestError("payment amounts cannot exceed per-node capital")
        if self.topology_max_arities != (3, 5):
            raise StudyManifestError("primary topology_max_arities must be exactly (3, 5)")
        if self.topology_families != ("demand-aware", "fhs3", "fhs5", "nch"):
            raise StudyManifestError(
                "topology_families must be exactly demand-aware, fhs3, fhs5, nch"
            )
        if self.demand_aware_seed_family != "fhs5":
            raise StudyManifestError("demand_aware_seed_family must be fhs5")
        if not isinstance(self.objective_weights, StudyObjectiveWeights):
            raise StudyManifestError("objective_weights are malformed")
        if not isinstance(self.topology_search, TopologySearchBudget):
            raise StudyManifestError("topology_search is malformed")
        if not isinstance(self.capacity_initializer, CapacityInitializerWeights):
            raise StudyManifestError("capacity_initializer is malformed")
        if not isinstance(self.capacity_search, CapacitySearchBudget):
            raise StudyManifestError("capacity_search is malformed")
        if not isinstance(self.lower_quantile, Fraction) or not 0 < self.lower_quantile <= 1:
            raise StudyManifestError("lower_quantile must be a Fraction in (0, 1]")
        if type(self.regimes) is not tuple or not self.regimes:
            raise StudyManifestError("regimes must be a nonempty tuple")
        if any(not isinstance(item, TrafficRegimeSpec) for item in self.regimes):
            raise StudyManifestError("regimes contain a malformed entry")
        regime_ids = tuple(item.regime_id for item in self.regimes)
        if tuple(sorted(regime_ids)) != regime_ids or len(set(regime_ids)) != len(regime_ids):
            raise StudyManifestError("regimes must be canonical with unique identifiers")
        _validate_regime_registry(self)
        canonical = json.dumps(
            self.to_canonical_mapping(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        object.__setattr__(self, "_fingerprint", hashlib.sha256(canonical).hexdigest())

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    @property
    def canonical_json(self) -> str:
        return json.dumps(
            self.to_canonical_mapping(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def to_canonical_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "phase": self.phase.value,
            "base_seed": self.base_seed,
            "output_root": self.output_root,
            "basis_fingerprint": self.basis_fingerprint,
            "code_revision": self.code_revision,
            "environment_fingerprint": self.environment_fingerprint,
            "size_cells": tuple(
                {
                    "node_count": cell.node_count,
                    "attachment_count": cell.attachment_count,
                    "block_count": cell.block_count,
                    "sbm_within_edge_count": cell.sbm_within_edge_count,
                }
                for cell in self.size_cells
            ),
            "parent_replicates": self.parent_replicates,
            "maximum_parent_attempts": self.maximum_parent_attempts,
            "training_traces_per_regime": self.training_traces_per_regime,
            "test_traces_per_regime": self.test_traces_per_regime,
            "requests_per_node": self.requests_per_node,
            "per_node_capital": self.per_node_capital,
            "amount_weights": self.amount_weights,
            "topology_max_arities": self.topology_max_arities,
            "topology_families": self.topology_families,
            "demand_aware_seed_family": self.demand_aware_seed_family,
            "objective_weights": {
                "bidirectional_capture": _fraction_pair(
                    self.objective_weights.bidirectional_capture
                ),
                "directional_imbalance": _fraction_pair(
                    self.objective_weights.directional_imbalance
                ),
                "participation": _fraction_pair(self.objective_weights.participation),
                "coordination_overlap": _fraction_pair(
                    self.objective_weights.coordination_overlap
                ),
            },
            "topology_search": {
                "proposal_budget": self.topology_search.proposal_budget,
                "maximum_rounds": self.topology_search.maximum_rounds,
                "maximum_move_edges": self.topology_search.maximum_move_edges,
            },
            "capacity_initializer": {
                "load_weight": _fraction_pair(self.capacity_initializer.load_weight),
                "risk_weight": _fraction_pair(self.capacity_initializer.risk_weight),
            },
            "capacity_search": {
                "evaluation_budget": self.capacity_search.evaluation_budget,
                "proposals_per_step_level": self.capacity_search.proposals_per_step_level,
            },
            "lower_quantile": _fraction_pair(self.lower_quantile),
            "regimes": tuple(
                {
                    "regime_id": regime.regime_id,
                    "role": regime.role.value,
                    "kernel": regime.kernel.value,
                    "shift": regime.shift.value,
                    "training_reference": regime.training_reference,
                    "parameters": dict(regime.parameters),
                }
                for regime in self.regimes
            ),
        }

    def size_cell(self, node_count: int) -> SyntheticSizeCell:
        for cell in self.size_cells:
            if cell.node_count == node_count:
                return cell
        raise StudyManifestError(f"node_count {node_count} is not registered")

    def regime(self, regime_id: str) -> TrafficRegimeSpec:
        for regime in self.regimes:
            if regime.regime_id == regime_id:
                return regime
        raise StudyManifestError(f"regime {regime_id!r} is not registered")


@dataclass(frozen=True, slots=True)
class StudyParentSeed:
    node_count: int
    parent_replicate: int
    ensemble_base_seed: int
    capacity_search_seed: int
    binary_matching_seed: int

    def __post_init__(self) -> None:
        if type(self.node_count) is not int or self.node_count not in PRIMARY_SYNTHETIC_SIZES:
            raise StudyManifestError("parent seed node_count is invalid")
        if type(self.parent_replicate) is not int or self.parent_replicate < 0:
            raise StudyManifestError("parent_replicate must be nonnegative")
        _validate_unsigned_64(self.ensemble_base_seed, "ensemble_base_seed")
        _validate_unsigned_64(self.capacity_search_seed, "capacity_search_seed")
        _validate_unsigned_64(self.binary_matching_seed, "binary_matching_seed")
        if len(
            {
                self.ensemble_base_seed,
                self.capacity_search_seed,
                self.binary_matching_seed,
            }
        ) != 3:
            raise StudyManifestError("parent-block component seeds must be distinct")


@dataclass(frozen=True, slots=True)
class StudyTraceSeed:
    node_count: int
    parent_replicate: int
    split: str
    regime_id: str
    trace_replicate: int
    trace_root_seed: int
    routing_root_seed: int

    def __post_init__(self) -> None:
        if type(self.node_count) is not int or self.node_count not in PRIMARY_SYNTHETIC_SIZES:
            raise StudyManifestError("trace seed node_count is invalid")
        if type(self.parent_replicate) is not int or self.parent_replicate < 0:
            raise StudyManifestError("parent_replicate must be nonnegative")
        if self.split not in {"training", "test"}:
            raise StudyManifestError("trace split must be training or test")
        _validate_identifier(self.regime_id, "trace regime_id")
        if type(self.trace_replicate) is not int or self.trace_replicate < 0:
            raise StudyManifestError("trace_replicate must be nonnegative")
        _validate_unsigned_64(self.trace_root_seed, "trace_root_seed")
        _validate_unsigned_64(self.routing_root_seed, "routing_root_seed")
        if self.trace_root_seed == self.routing_root_seed:
            raise StudyManifestError("traffic and routing seeds must be distinct")


@dataclass(frozen=True, slots=True)
class StudySeedLedger:
    """Complete finite seed allocation derived from one study manifest."""

    manifest_fingerprint: str
    parent_seeds: tuple[StudyParentSeed, ...]
    trace_seeds: tuple[StudyTraceSeed, ...]
    ledger_version: str = STUDY_SEED_LEDGER_VERSION

    def __post_init__(self) -> None:
        _validate_sha256(self.manifest_fingerprint, "manifest_fingerprint")
        if self.ledger_version != STUDY_SEED_LEDGER_VERSION:
            raise StudyManifestError("unsupported study seed ledger version")
        if type(self.parent_seeds) is not tuple or any(
            not isinstance(item, StudyParentSeed) for item in self.parent_seeds
        ):
            raise StudyManifestError("parent_seeds are malformed")
        if type(self.trace_seeds) is not tuple or any(
            not isinstance(item, StudyTraceSeed) for item in self.trace_seeds
        ):
            raise StudyManifestError("trace_seeds are malformed")
        if tuple(sorted(self.parent_seeds, key=_parent_seed_key)) != self.parent_seeds:
            raise StudyManifestError("parent_seeds are not canonical")
        if tuple(sorted(self.trace_seeds, key=_trace_seed_key)) != self.trace_seeds:
            raise StudyManifestError("trace_seeds are not canonical")
        semantic_parent_keys = tuple((x.node_count, x.parent_replicate) for x in self.parent_seeds)
        semantic_trace_keys = tuple(
            (x.node_count, x.parent_replicate, x.split, x.regime_id, x.trace_replicate)
            for x in self.trace_seeds
        )
        if len(set(semantic_parent_keys)) != len(semantic_parent_keys):
            raise StudyManifestError("parent seed semantics are duplicated")
        if len(set(semantic_trace_keys)) != len(semantic_trace_keys):
            raise StudyManifestError("trace seed semantics are duplicated")
        all_seeds = tuple(
            seed
            for item in self.parent_seeds
            for seed in (
                item.ensemble_base_seed,
                item.capacity_search_seed,
                item.binary_matching_seed,
            )
        ) + tuple(
            seed
            for item in self.trace_seeds
            for seed in (item.trace_root_seed, item.routing_root_seed)
        )
        if len(set(all_seeds)) != len(all_seeds):
            raise StudyManifestError("finite study seed ledger contains a collision")

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.study-seed-ledger.v1\x00")
        _hash_field(digest, self.manifest_fingerprint)
        _hash_field(digest, self.ledger_version)
        _hash_count(digest, len(self.parent_seeds))
        for item in self.parent_seeds:
            _hash_count(digest, item.node_count)
            _hash_count(digest, item.parent_replicate)
            _hash_count(digest, item.ensemble_base_seed)
            _hash_count(digest, item.capacity_search_seed)
            _hash_count(digest, item.binary_matching_seed)
        _hash_count(digest, len(self.trace_seeds))
        for item in self.trace_seeds:
            _hash_count(digest, item.node_count)
            _hash_count(digest, item.parent_replicate)
            _hash_field(digest, item.split)
            _hash_field(digest, item.regime_id)
            _hash_count(digest, item.trace_replicate)
            _hash_count(digest, item.trace_root_seed)
            _hash_count(digest, item.routing_root_seed)
        return digest.hexdigest()


def load_study_design_manifest(path: str | Path) -> StudyDesignManifest:
    """Load strict UTF-8 JSON and reject every unknown or duplicate field."""

    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as stream:
            raw = json.load(
                stream,
                object_pairs_hook=_mapping_without_duplicate_keys,
                parse_constant=_reject_non_json_constant,
            )
    except StudyManifestError as exc:
        raise StudyManifestError(f"invalid study manifest {source}: {exc}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StudyManifestError(f"could not load study manifest {source}: {exc}") from exc
    try:
        return _manifest_from_mapping(raw)
    except (StudyManifestError, KeyError, TypeError, ValueError) as exc:
        raise StudyManifestError(f"invalid study manifest {source}: {exc}") from exc


def build_study_seed_ledger(manifest: StudyDesignManifest) -> StudySeedLedger:
    """Derive every parent, traffic, and routing seed from semantic namespaces."""

    if not isinstance(manifest, StudyDesignManifest):
        raise StudyManifestError("manifest must be a StudyDesignManifest")
    parents = []
    traces = []
    for cell in manifest.size_cells:
        for parent_replicate in range(manifest.parent_replicates):
            block_root = derive_seed(
                manifest.base_seed,
                f"study.{manifest.phase.value}.parent-block.n{cell.node_count}",
                parent_replicate,
            )
            parents.append(
                StudyParentSeed(
                    node_count=cell.node_count,
                    parent_replicate=parent_replicate,
                    ensemble_base_seed=derive_seed(
                        block_root,
                        "study.parent.ensemble",
                        0,
                    ),
                    capacity_search_seed=derive_seed(
                        block_root,
                        "study.capacity.search",
                        0,
                    ),
                    binary_matching_seed=derive_seed(
                        block_root,
                        "study.binary.matching",
                        0,
                    ),
                )
            )
            for regime in manifest.regimes:
                split = "training" if regime.role is TrafficRegimeRole.TRAINING else "test"
                count = (
                    manifest.training_traces_per_regime
                    if split == "training"
                    else manifest.test_traces_per_regime
                )
                for trace_replicate in range(count):
                    semantic_root = derive_seed(
                        block_root,
                        f"study.{split}.{regime.regime_id}",
                        trace_replicate,
                    )
                    traces.append(
                        StudyTraceSeed(
                            node_count=cell.node_count,
                            parent_replicate=parent_replicate,
                            split=split,
                            regime_id=regime.regime_id,
                            trace_replicate=trace_replicate,
                            trace_root_seed=derive_seed(
                                semantic_root,
                                "study.traffic.trace",
                                0,
                            ),
                            routing_root_seed=derive_seed(
                                semantic_root,
                                "study.routing.trace",
                                0,
                            ),
                        )
                    )
    return StudySeedLedger(
        manifest_fingerprint=manifest.fingerprint,
        parent_seeds=tuple(sorted(parents, key=_parent_seed_key)),
        trace_seeds=tuple(sorted(traces, key=_trace_seed_key)),
    )


def validate_study_seed_ledger(
    ledger: StudySeedLedger,
    manifest: StudyDesignManifest,
) -> None:
    if not isinstance(ledger, StudySeedLedger):
        raise StudyManifestError("ledger must be a StudySeedLedger")
    exact = build_study_seed_ledger(manifest)
    if ledger != exact:
        raise StudyManifestError("study seed ledger does not match complete regeneration")


def generate_declared_parent_ensemble(
    manifest: StudyDesignManifest,
    record: StudyParentSeed,
) -> MatchedParentEnsemble:
    """Generate one matched ER/BA/SBM ensemble from a registered parent record."""

    _require_parent_record(manifest, record)
    cell = manifest.size_cell(record.node_count)
    return matched_synthetic_parent_graphs(
        node_count=cell.node_count,
        attachment_count=cell.attachment_count,
        block_count=cell.block_count,
        sbm_within_edge_count=cell.sbm_within_edge_count,
        base_seed=record.ensemble_base_seed,
        replicate_index=0,
        max_attempts=manifest.maximum_parent_attempts,
    )


def generate_declared_request_trace(
    manifest: StudyDesignManifest,
    record: StudyTraceSeed,
) -> RequestTrace:
    """Generate one exact registered trace without consulting a topology."""

    _require_trace_record(manifest, record)
    cell = manifest.size_cell(record.node_count)
    regime = manifest.regime(record.regime_id)
    kernel = traffic_kernel_for(cell, regime)
    amounts = AmountDistribution.from_weights(manifest.amount_weights)
    return generate_request_trace(
        kernel,
        amounts,
        record.node_count * manifest.requests_per_node,
        root_seed=record.trace_root_seed,
    )


def traffic_kernel_for(
    cell: SyntheticSizeCell,
    regime: TrafficRegimeSpec,
) -> DemandKernel:
    """Construct a topology-blind kernel from canonical study labels."""

    if not isinstance(cell, SyntheticSizeCell) or not isinstance(regime, TrafficRegimeSpec):
        raise StudyManifestError("cell and regime must be registered study objects")
    nodes = _canonical_nodes(cell.node_count)
    if regime.kernel is TrafficKernelKind.UNIFORM:
        return uniform_kernel(nodes)
    if regime.kernel is TrafficKernelKind.COMMUNITY:
        return community_local_kernel(
            nodes,
            cell.blocks,
            regime.parameter("within_weight"),
            regime.parameter("cross_weight"),
        )
    if regime.kernel is TrafficKernelKind.HOTSPOT:
        start = regime.parameter("hotspot_offset")
        stop = start + regime.parameter("hotspot_count")
        return hotspot_kernel(
            nodes,
            nodes[start:stop],
            regime.parameter("base_weight"),
            regime.parameter("hotspot_multiplier"),
        )
    split = (
        cell.node_count
        * regime.parameter("split_numerator")
        // regime.parameter("split_denominator")
    )
    return directional_drift_kernel(
        nodes,
        nodes[:split],
        nodes[split:],
        regime.parameter("forward_weight"),
        regime.parameter("reverse_weight"),
        regime.parameter("within_weight"),
    )


def _manifest_from_mapping(raw: object) -> StudyDesignManifest:
    top = _expect_mapping(
        raw,
        {
            "schema_version",
            "study_id",
            "phase",
            "base_seed",
            "output_root",
            "basis_fingerprint",
            "code_revision",
            "environment_fingerprint",
            "size_cells",
            "parent_replicates",
            "maximum_parent_attempts",
            "training_traces_per_regime",
            "test_traces_per_regime",
            "requests_per_node",
            "per_node_capital",
            "amount_weights",
            "topology_max_arities",
            "topology_families",
            "demand_aware_seed_family",
            "objective_weights",
            "topology_search",
            "capacity_initializer",
            "capacity_search",
            "lower_quantile",
            "regimes",
        },
        "manifest",
    )
    size_cells = tuple(
        SyntheticSizeCell(**_expect_mapping(item, {
            "node_count", "attachment_count", "block_count", "sbm_within_edge_count"
        }, "size cell"))
        for item in _expect_list(top["size_cells"], "size_cells")
    )
    weights_raw = _expect_mapping(
        top["objective_weights"],
        {"bidirectional_capture", "directional_imbalance", "participation", "coordination_overlap"},
        "objective_weights",
    )
    topology_raw = _expect_mapping(
        top["topology_search"],
        {"proposal_budget", "maximum_rounds", "maximum_move_edges"},
        "topology_search",
    )
    capacity_raw = _expect_mapping(
        top["capacity_search"],
        {"evaluation_budget", "proposals_per_step_level"},
        "capacity_search",
    )
    initializer_raw = _expect_mapping(
        top["capacity_initializer"],
        {"load_weight", "risk_weight"},
        "capacity_initializer",
    )
    regimes = []
    for item in _expect_list(top["regimes"], "regimes"):
        value = _expect_mapping(
            item,
            {"regime_id", "role", "kernel", "shift", "training_reference", "parameters"},
            "regime",
        )
        parameters = _expect_mapping(value["parameters"], set(value["parameters"]), "parameters")
        regimes.append(
            TrafficRegimeSpec(
                regime_id=value["regime_id"],
                role=TrafficRegimeRole(value["role"]),
                kernel=TrafficKernelKind(value["kernel"]),
                shift=TrafficShift(value["shift"]),
                training_reference=value["training_reference"],
                parameters=tuple(sorted(parameters.items())),
            )
        )
    return StudyDesignManifest(
        schema_version=top["schema_version"],
        study_id=top["study_id"],
        phase=StudyPhase(top["phase"]),
        base_seed=top["base_seed"],
        output_root=top["output_root"],
        basis_fingerprint=top["basis_fingerprint"],
        code_revision=top["code_revision"],
        environment_fingerprint=top["environment_fingerprint"],
        size_cells=size_cells,
        parent_replicates=top["parent_replicates"],
        maximum_parent_attempts=top["maximum_parent_attempts"],
        training_traces_per_regime=top["training_traces_per_regime"],
        test_traces_per_regime=top["test_traces_per_regime"],
        requests_per_node=top["requests_per_node"],
        per_node_capital=top["per_node_capital"],
        amount_weights=tuple(tuple(item) for item in _expect_list(top["amount_weights"], "amount_weights")),
        topology_max_arities=tuple(_expect_list(top["topology_max_arities"], "topology_max_arities")),
        topology_families=tuple(_expect_list(top["topology_families"], "topology_families")),
        demand_aware_seed_family=top["demand_aware_seed_family"],
        objective_weights=StudyObjectiveWeights(
            bidirectional_capture=_fraction_from_json(weights_raw["bidirectional_capture"], "bidirectional_capture"),
            directional_imbalance=_fraction_from_json(weights_raw["directional_imbalance"], "directional_imbalance"),
            participation=_fraction_from_json(weights_raw["participation"], "participation"),
            coordination_overlap=_fraction_from_json(weights_raw["coordination_overlap"], "coordination_overlap"),
        ),
        topology_search=TopologySearchBudget(**topology_raw),
        capacity_initializer=CapacityInitializerWeights(
            load_weight=_fraction_from_json(initializer_raw["load_weight"], "load_weight"),
            risk_weight=_fraction_from_json(initializer_raw["risk_weight"], "risk_weight"),
        ),
        capacity_search=CapacitySearchBudget(**capacity_raw),
        lower_quantile=_fraction_from_json(top["lower_quantile"], "lower_quantile"),
        regimes=tuple(regimes),
    )


def _validate_regime_registry(manifest: StudyDesignManifest) -> None:
    training = tuple(x for x in manifest.regimes if x.role is TrafficRegimeRole.TRAINING)
    tests = tuple(x for x in manifest.regimes if x.role is TrafficRegimeRole.TEST)
    if tuple(sorted(x.kernel.value for x in training)) != tuple(
        sorted(kind.value for kind in TrafficKernelKind)
    ):
        raise StudyManifestError("training registry must contain each primary kernel exactly once")
    training_by_id = {x.regime_id: x for x in training}
    if len(tests) != 7:
        raise StudyManifestError(
            "test registry must contain exactly four ID tests and three shifts"
        )
    community_training = next(
        item for item in training if item.kernel is TrafficKernelKind.COMMUNITY
    )
    hotspot_training = next(
        item for item in training if item.kernel is TrafficKernelKind.HOTSPOT
    )
    directional_training = next(
        item for item in training if item.kernel is TrafficKernelKind.DIRECTIONAL
    )
    if community_training.parameter("within_weight") <= community_training.parameter("cross_weight"):
        raise StudyManifestError("community-local training requires within_weight > cross_weight")
    if hotspot_training.parameter("hotspot_multiplier") <= 1:
        raise StudyManifestError("hotspot training requires hotspot_multiplier > 1")
    if directional_training.parameter("forward_weight") == directional_training.parameter("reverse_weight"):
        raise StudyManifestError("directional training requires unequal forward/reverse weights")
    same_distribution_refs = []
    observed_shifts = []
    for test in tests:
        if test.training_reference not in training_by_id:
            raise StudyManifestError("test regime references an unknown training regime")
        reference = training_by_id[test.training_reference]
        if test.shift is TrafficShift.SAME_DISTRIBUTION:
            if test.kernel is not reference.kernel or test.parameters != reference.parameters:
                raise StudyManifestError("same-distribution test must copy its training kernel")
            same_distribution_refs.append(reference.regime_id)
        elif test.shift is TrafficShift.HOTSPOT_RELOCATION:
            _validate_hotspot_relocation(manifest, reference, test)
            observed_shifts.append(test.shift)
        elif test.shift is TrafficShift.DIRECTION_REVERSAL:
            _validate_direction_reversal(reference, test)
            observed_shifts.append(test.shift)
        elif test.shift is TrafficShift.CROSS_COMMUNITY_INCREASE:
            _validate_cross_community(reference, test)
            observed_shifts.append(test.shift)
    if sorted(same_distribution_refs) != sorted(training_by_id):
        raise StudyManifestError(
            "every training regime requires exactly one same-distribution test"
        )
    required_shifts = {
        TrafficShift.HOTSPOT_RELOCATION,
        TrafficShift.DIRECTION_REVERSAL,
        TrafficShift.CROSS_COMMUNITY_INCREASE,
    }
    if len(observed_shifts) != 3 or set(observed_shifts) != required_shifts:
        raise StudyManifestError(
            "test registry must contain each registered shift exactly once"
        )
    for regime in manifest.regimes:
        for cell in manifest.size_cells:
            if regime.kernel is TrafficKernelKind.HOTSPOT:
                start = regime.parameter("hotspot_offset")
                count = regime.parameter("hotspot_count")
                if start + count > cell.node_count or count >= cell.node_count:
                    raise StudyManifestError("hotspot range is invalid for a size cell")
            if regime.kernel is TrafficKernelKind.DIRECTIONAL:
                numerator = regime.parameter("split_numerator")
                denominator = regime.parameter("split_denominator")
                if (
                    numerator >= denominator
                    or cell.node_count * numerator % denominator != 0
                    or not 1 <= cell.node_count * numerator // denominator < cell.node_count
                ):
                    raise StudyManifestError(
                        "directional split ratio must divide every registered size"
                    )


def _validate_hotspot_relocation(manifest, reference, test) -> None:
    if reference.kernel is not TrafficKernelKind.HOTSPOT or test.kernel is not reference.kernel:
        raise StudyManifestError("hotspot relocation must reference a hotspot training regime")
    for name in ("base_weight", "hotspot_multiplier", "hotspot_count"):
        if test.parameter(name) != reference.parameter(name):
            raise StudyManifestError("hotspot relocation changed a non-location parameter")
    for cell in manifest.size_cells:
        ref_nodes = set(range(
            reference.parameter("hotspot_offset"),
            reference.parameter("hotspot_offset") + reference.parameter("hotspot_count"),
        ))
        test_nodes = set(range(
            test.parameter("hotspot_offset"),
            test.parameter("hotspot_offset") + test.parameter("hotspot_count"),
        ))
        if ref_nodes.intersection(test_nodes) or max(ref_nodes.union(test_nodes)) >= cell.node_count:
            raise StudyManifestError("hotspot relocation must be disjoint in every size cell")


def _validate_direction_reversal(reference, test) -> None:
    if reference.kernel is not TrafficKernelKind.DIRECTIONAL or test.kernel is not reference.kernel:
        raise StudyManifestError("direction reversal must reference directional training")
    if (
        test.parameter("forward_weight") != reference.parameter("reverse_weight")
        or test.parameter("reverse_weight") != reference.parameter("forward_weight")
        or test.parameter("within_weight") != reference.parameter("within_weight")
        or test.parameter("split_numerator") != reference.parameter("split_numerator")
        or test.parameter("split_denominator") != reference.parameter("split_denominator")
    ):
        raise StudyManifestError("direction reversal parameters are not an exact swap")


def _validate_cross_community(reference, test) -> None:
    if reference.kernel is not TrafficKernelKind.COMMUNITY or test.kernel is not reference.kernel:
        raise StudyManifestError("cross-community shift must reference community training")
    if (
        test.parameter("within_weight") != reference.parameter("within_weight")
        or test.parameter("cross_weight") <= reference.parameter("cross_weight")
    ):
        raise StudyManifestError("cross-community test must strictly increase only cross weight")


def _require_parent_record(manifest, record) -> None:
    if not isinstance(manifest, StudyDesignManifest) or not isinstance(record, StudyParentSeed):
        raise StudyManifestError("manifest and parent record have invalid types")
    ledger = build_study_seed_ledger(manifest)
    if record not in ledger.parent_seeds:
        raise StudyManifestError("parent record is not registered by the manifest")


def _require_trace_record(manifest, record) -> None:
    if not isinstance(manifest, StudyDesignManifest) or not isinstance(record, StudyTraceSeed):
        raise StudyManifestError("manifest and trace record have invalid types")
    ledger = build_study_seed_ledger(manifest)
    if record not in ledger.trace_seeds:
        raise StudyManifestError("trace record is not registered by the manifest")


def _validate_phase_provenance(manifest) -> None:
    values = (
        manifest.basis_fingerprint,
        manifest.code_revision,
        manifest.environment_fingerprint,
    )
    if manifest.phase is StudyPhase.PILOT:
        if any(value is not None for value in values):
            raise StudyManifestError("pilot provenance fields must remain null until freeze")
        return
    _validate_sha256(manifest.basis_fingerprint, "basis_fingerprint")
    _validate_sha256(manifest.environment_fingerprint, "environment_fingerprint")
    if (
        not isinstance(manifest.code_revision, str)
        or len(manifest.code_revision) not in {40, 64}
        or any(character not in "0123456789abcdef" for character in manifest.code_revision)
    ):
        raise StudyManifestError("code_revision must be a full lowercase Git object id")


def _expect_mapping(raw: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise StudyManifestError(f"{label} must be an object")
    missing = expected.difference(raw)
    unknown = set(raw).difference(expected)
    if missing or unknown:
        parts = []
        if missing:
            parts.append("missing keys: " + ", ".join(sorted(missing)))
        if unknown:
            parts.append("unknown keys: " + ", ".join(sorted(map(str, unknown))))
        raise StudyManifestError(f"{label} " + "; ".join(parts))
    return dict(raw)


def _expect_list(raw: object, label: str) -> list[Any]:
    if type(raw) is not list:
        raise StudyManifestError(f"{label} must be a JSON array")
    return raw


def _fraction_from_json(raw: object, label: str) -> Fraction:
    values = _expect_list(raw, label)
    if len(values) != 2 or any(type(value) is not int for value in values):
        raise StudyManifestError(f"{label} must be [integer numerator, positive denominator]")
    if values[1] <= 0:
        raise StudyManifestError(f"{label} denominator must be positive")
    return Fraction(values[0], values[1])


def _fraction_pair(value: Fraction) -> tuple[int, int]:
    return (value.numerator, value.denominator)


def _mapping_without_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    output = {}
    for key, value in pairs:
        if key in output:
            raise StudyManifestError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _reject_non_json_constant(value: str) -> object:
    raise StudyManifestError(f"non-JSON numeric constant: {value}")


def _balanced_block_sizes(node_count: int, block_count: int) -> tuple[int, ...]:
    quotient, remainder = divmod(node_count, block_count)
    return tuple(quotient + int(index < remainder) for index in range(block_count))


def _canonical_nodes(node_count: int) -> tuple[str, ...]:
    return tuple(f"v{index:08d}" for index in range(node_count))


def _parent_seed_key(item: StudyParentSeed) -> tuple[int, int]:
    return (item.node_count, item.parent_replicate)


def _trace_seed_key(item: StudyTraceSeed) -> tuple[int, int, str, str, int]:
    return (
        item.node_count,
        item.parent_replicate,
        item.split,
        item.regime_id,
        item.trace_replicate,
    )


def _validate_identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or _PORTABLE_ID.fullmatch(value) is None:
        raise StudyManifestError(f"{label} must be a portable nonempty identifier")


def _validate_output_root(value: object) -> None:
    if not isinstance(value, str) or not value or value != value.strip() or "\\" in value:
        raise StudyManifestError("output_root must be an unpadded portable relative path")
    if _NON_PORTABLE_PATH_CHARACTER.search(value) is not None:
        raise StudyManifestError("output_root contains a non-portable character")
    windows = PureWindowsPath(value)
    if PurePosixPath(value).is_absolute() or windows.is_absolute() or windows.drive:
        raise StudyManifestError("output_root must be relative")
    if any(segment in {"", ".", ".."} for segment in value.split("/")):
        raise StudyManifestError("output_root contains an unsafe segment")


def _validate_positive_u64(value: object, label: str) -> None:
    if type(value) is not int or not 1 <= value <= _MAX_UNSIGNED_64:
        raise StudyManifestError(f"{label} must be a positive unsigned-64 integer")


def _validate_unsigned_64(value: object, label: str) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise StudyManifestError(f"{label} must be unsigned 64-bit")


def _validate_sha256(value: object, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise StudyManifestError(f"{label} must be a lowercase SHA-256 digest")


def _hash_field(digest: "hashlib._Hash", value: str) -> None:
    encoded = value.encode("utf-8")
    _hash_count(digest, len(encoded))
    digest.update(encoded)


def _hash_count(digest: "hashlib._Hash", value: int) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise StudyManifestError("hash count is outside unsigned-64 range")
    digest.update(value.to_bytes(8, "big", signed=False))


__all__ = [
    "STUDY_MANIFEST_SCHEMA_VERSION",
    "STUDY_SEED_LEDGER_VERSION",
    "PRIMARY_SYNTHETIC_SIZES",
    "CapacitySearchBudget",
    "CapacityInitializerWeights",
    "StudyDesignManifest",
    "StudyManifestError",
    "StudyObjectiveWeights",
    "StudyParentSeed",
    "StudyPhase",
    "StudySeedLedger",
    "StudyTraceSeed",
    "SyntheticSizeCell",
    "TopologySearchBudget",
    "TrafficKernelKind",
    "TrafficRegimeRole",
    "TrafficRegimeSpec",
    "TrafficShift",
    "build_study_seed_ledger",
    "generate_declared_parent_ensemble",
    "generate_declared_request_trace",
    "load_study_design_manifest",
    "traffic_kernel_for",
    "validate_study_seed_ledger",
]
