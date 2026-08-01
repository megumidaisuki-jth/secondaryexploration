"""Paired topology execution with request-indexed common random tickets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random
from collections.abc import Iterator

from secondaryexploration.model import HypergraphState
from secondaryexploration.randomness import SeedError, derive_seed
from secondaryexploration.simulation import (
    CoreSimulationResult,
    run_core_trace_with_request_rngs,
)
from secondaryexploration.topology import (
    HypergraphTopology,
    node_capital_totals,
)
from secondaryexploration.traffic import RequestTrace


_MAX_UNSIGNED_64 = 2**64 - 1
_MANIFEST_SCHEMA = "paired-run-manifest.v1"


class ExperimentError(ValueError):
    """Raised when a paired experiment input or result is inconsistent."""


class RouteChoiceRandom(random.Random):
    """A Random-compatible computational mapper for one shared quantile."""

    def __init__(self, ticket: int) -> None:
        _validate_unsigned_64(ticket, "route ticket")
        super().__init__(0)
        self._route_ticket = ticket
        self._used = False
        self._refinement_blocks_used = 0

    @property
    def route_ticket(self) -> int:
        return self._route_ticket

    @property
    def refinement_blocks_used(self) -> int:
        return self._refinement_blocks_used

    def randrange(self, start, stop=None, step=1):
        if stop is not None or step != 1:
            raise ExperimentError(
                "route-choice RNG supports only the one-argument randrange(stop) form"
            )
        if type(start) is not int or start <= 0:
            raise ExperimentError("route-choice stop must be a positive integer")
        if self._used:
            raise ExperimentError("route-choice RNG may be consumed at most once")
        self._used = True

        prefix = self._route_ticket
        bit_count = 64
        extension_index = 0
        while True:
            denominator = 1 << bit_count
            lower_bin = prefix * start // denominator
            upper_bin = ((prefix + 1) * start - 1) // denominator
            if lower_bin == upper_bin:
                return lower_bin
            prefix = (prefix << 64) | derive_seed(
                self._route_ticket,
                "routing.quantile.extension",
                extension_index,
            )
            bit_count += 64
            extension_index += 1
            self._refinement_blocks_used = extension_index


def route_choice_ticket(root_seed: int, request_index: int) -> int:
    """Derive the common unsigned ticket for one one-based request index."""

    _validate_unsigned_64(root_seed, "routing_root_seed")
    if type(request_index) is not int or not 1 <= request_index <= _MAX_UNSIGNED_64:
        raise ExperimentError("request_index must be an integer in [1, 2**64 - 1]")
    try:
        return derive_seed(root_seed, "routing.ticket", request_index)
    except SeedError as exc:
        raise ExperimentError("invalid route-choice seed request") from exc


def route_choice_rng(root_seed: int, request_index: int) -> RouteChoiceRandom:
    """Return a Random-compatible mapper for one common route-choice ticket."""

    return RouteChoiceRandom(route_choice_ticket(root_seed, request_index))


@dataclass(frozen=True, slots=True)
class TopologyVariant:
    """One labeled structural topology and its exact initial balances."""

    variant_id: str
    family: str
    topology: HypergraphTopology
    initial_state: HypergraphState

    def __post_init__(self) -> None:
        _validate_identifier(self.variant_id, "variant_id")
        _validate_identifier(self.family, "family")
        if not isinstance(self.topology, HypergraphTopology):
            raise ExperimentError("topology must be a HypergraphTopology")
        if not self.topology.is_connected:
            raise ExperimentError("paired topology variants must be connected")
        if not isinstance(self.initial_state, HypergraphState):
            raise ExperimentError("initial_state must be a HypergraphState")
        if self.initial_state.nodes != self.topology.nodes:
            raise ExperimentError("initial-state nodes do not match topology nodes")
        topology_structure = tuple(
            (edge.hyperedge_id, edge.members) for edge in self.topology.hyperedges
        )
        state_structure = tuple(
            (edge.hyperedge_id, edge.members) for edge in self.initial_state.hyperedges
        )
        if state_structure != topology_structure:
            raise ExperimentError(
                "initial-state hyperedges and members do not match the topology"
            )


@dataclass(frozen=True, slots=True)
class PairedRunManifest:
    """Complete immutable scientific inputs for one paired experimental block."""

    block_id: str
    trace: RequestTrace
    routing_root_seed: int
    variants: tuple[TopologyVariant, ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.block_id, "block_id")
        if not isinstance(self.trace, RequestTrace):
            raise ExperimentError("trace must be a RequestTrace")
        _validate_unsigned_64(self.routing_root_seed, "routing_root_seed")
        if type(self.variants) is not tuple or len(self.variants) < 2:
            raise ExperimentError("variants must be a tuple containing at least two variants")
        if any(not isinstance(variant, TopologyVariant) for variant in self.variants):
            raise ExperimentError("variants must contain only TopologyVariant objects")
        variant_ids = tuple(variant.variant_id for variant in self.variants)
        if len(set(variant_ids)) != len(variant_ids):
            raise ExperimentError("variant identifiers must be unique")
        if tuple(sorted(variant_ids)) != variant_ids:
            raise ExperimentError("variants must be in canonical variant_id order")

        nodes = self.variants[0].topology.nodes
        if self.trace.kernel.nodes != nodes:
            raise ExperimentError("trace-kernel nodes do not match paired topology nodes")
        if any(variant.topology.nodes != nodes for variant in self.variants[1:]):
            raise ExperimentError("all paired variants must use the same node mapping")
        capital_witness = node_capital_totals(self.variants[0].initial_state)
        if any(
            node_capital_totals(variant.initial_state) != capital_witness
            for variant in self.variants[1:]
        ):
            raise ExperimentError("all paired variants must have equal per-node capital")

    @property
    def canonical_json(self) -> str:
        return json.dumps(
            _manifest_payload(self),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VariantRunResult:
    """One labeled simulation result within a paired block."""

    variant_id: str
    simulation: CoreSimulationResult

    def __post_init__(self) -> None:
        _validate_identifier(self.variant_id, "variant_id")
        if not isinstance(self.simulation, CoreSimulationResult):
            raise ExperimentError("simulation must be a CoreSimulationResult")


@dataclass(frozen=True, slots=True)
class PairedRunResult:
    """Validated exact results for every variant in one paired manifest."""

    manifest: PairedRunManifest
    variant_results: tuple[VariantRunResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, PairedRunManifest):
            raise ExperimentError("manifest must be a PairedRunManifest")
        if type(self.variant_results) is not tuple or any(
            not isinstance(item, VariantRunResult) for item in self.variant_results
        ):
            raise ExperimentError("variant_results must be a VariantRunResult tuple")
        expected_ids = tuple(variant.variant_id for variant in self.manifest.variants)
        observed_ids = tuple(item.variant_id for item in self.variant_results)
        if observed_ids != expected_ids:
            raise ExperimentError(
                "variant_results must contain every manifest variant in canonical order"
            )

        for variant, item in zip(self.manifest.variants, self.variant_results):
            simulation = item.simulation
            if simulation.initial_state != variant.initial_state:
                raise ExperimentError("result initial state does not match its variant")
            if simulation.horizon != self.manifest.trace.length:
                raise ExperimentError("result horizon does not match the manifest trace")
            if any(
                outcome.request is not request
                for outcome, request in zip(
                    simulation.outcomes,
                    self.manifest.trace.requests,
                )
            ):
                raise ExperimentError("result did not reuse the manifest request objects")
            exact_replay = run_core_trace_with_request_rngs(
                variant.initial_state,
                self.manifest.trace.requests,
                _request_rngs(self.manifest),
            )
            if simulation != exact_replay:
                raise ExperimentError(
                    "result does not match the manifest common route-choice tickets"
                )

    @property
    def manifest_fingerprint(self) -> str:
        return self.manifest.fingerprint

    @property
    def horizon(self) -> int:
        return self.manifest.trace.length


def run_paired_experiment(manifest: PairedRunManifest) -> PairedRunResult:
    """Execute every variant against one exact trace and common ticket family."""

    if not isinstance(manifest, PairedRunManifest):
        raise ExperimentError("manifest must be a PairedRunManifest")
    results = tuple(
        VariantRunResult(
            variant_id=variant.variant_id,
            simulation=run_core_trace_with_request_rngs(
                variant.initial_state,
                manifest.trace.requests,
                _request_rngs(manifest),
            ),
        )
        for variant in manifest.variants
    )
    return PairedRunResult(manifest=manifest, variant_results=results)


def _request_rngs(manifest: PairedRunManifest) -> Iterator[RouteChoiceRandom]:
    return (
        route_choice_rng(manifest.routing_root_seed, request_index)
        for request_index in range(1, manifest.trace.length + 1)
    )


def _manifest_payload(manifest: PairedRunManifest) -> dict[str, object]:
    return {
        "schema_version": _MANIFEST_SCHEMA,
        "block_id": manifest.block_id,
        "routing_root_seed": manifest.routing_root_seed,
        "trace": {
            "kernel": {
                "nodes": manifest.trace.kernel.nodes,
                "pair_weights": manifest.trace.kernel.pair_weights,
            },
            "amount_distribution": manifest.trace.amount_distribution.amount_weights,
            "length": manifest.trace.length,
            "root_seed": manifest.trace.root_seed,
            "requests": tuple(
                (request.source, request.destination, request.amount)
                for request in manifest.trace.requests
            ),
        },
        "variants": tuple(
            {
                "variant_id": variant.variant_id,
                "family": variant.family,
                "topology": {
                    "nodes": variant.topology.nodes,
                    "hyperedges": tuple(
                        (edge.hyperedge_id, edge.members)
                        for edge in variant.topology.hyperedges
                    ),
                },
                "initial_state": tuple(
                    (edge.hyperedge_id, edge.balances)
                    for edge in variant.initial_state.hyperedges
                ),
            }
            for variant in manifest.variants
        ),
    }


def _validate_unsigned_64(value: object, field: str) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise ExperimentError(f"{field} must be an integer in [0, 2**64 - 1]")


def _validate_identifier(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise ExperimentError(f"{field} must be a string")
    if not value or value != value.strip():
        raise ExperimentError(f"{field} must be non-empty and have no outer whitespace")
    if "\x00" in value:
        raise ExperimentError(f"{field} must not contain NUL")


__all__ = [
    "ExperimentError",
    "PairedRunManifest",
    "PairedRunResult",
    "RouteChoiceRandom",
    "TopologyVariant",
    "VariantRunResult",
    "route_choice_rng",
    "route_choice_ticket",
    "run_paired_experiment",
]
