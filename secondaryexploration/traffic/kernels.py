"""Exact integer-weight iid demand kernels and payment amounts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import json


class TrafficError(ValueError):
    """Raised when a traffic kernel, amount table, or trace is inconsistent."""


@dataclass(frozen=True, slots=True)
class DemandKernel:
    """Canonical full-support integer weights over ordered node pairs."""

    nodes: tuple[str, ...]
    pair_weights: tuple[tuple[str, str, int], ...]

    def __post_init__(self) -> None:
        if type(self.nodes) is not tuple or len(self.nodes) < 2:
            raise TrafficError("kernel nodes must be a canonical tuple of at least two")
        for node in self.nodes:
            _validate_identifier(node, "kernel node")
        if len(set(self.nodes)) != len(self.nodes):
            raise TrafficError("kernel nodes must be unique")
        if tuple(sorted(self.nodes)) != self.nodes:
            raise TrafficError("kernel nodes must be in canonical order")

        if type(self.pair_weights) is not tuple:
            raise TrafficError("pair_weights must be a canonical tuple")
        observed_pairs: list[tuple[str, str]] = []
        for entry in self.pair_weights:
            if type(entry) is not tuple or len(entry) != 3:
                raise TrafficError(
                    "each pair weight must be a (source, destination, weight) tuple"
                )
            source, destination, weight = entry
            _validate_identifier(source, "pair source")
            _validate_identifier(destination, "pair destination")
            if source == destination:
                raise TrafficError("demand-kernel pairs must have distinct endpoints")
            _validate_positive_integer(weight, "pair weight")
            observed_pairs.append((source, destination))
        if tuple(sorted(self.pair_weights, key=lambda item: item[:2])) != self.pair_weights:
            raise TrafficError("pair_weights must be in canonical ordered-pair order")
        if len(set(observed_pairs)) != len(observed_pairs):
            raise TrafficError("pair_weights must not repeat an ordered pair")
        expected_pairs = {
            (source, destination)
            for source in self.nodes
            for destination in self.nodes
            if source != destination
        }
        if set(observed_pairs) != expected_pairs:
            raise TrafficError(
                "pair_weights must contain every ordered pair exactly once"
            )

    @classmethod
    def from_weights(
        cls,
        nodes: Iterable[str],
        pair_weights: Iterable[tuple[str, str, int]],
    ) -> "DemandKernel":
        canonical_nodes = _canonical_nodes(nodes)
        if isinstance(pair_weights, (str, bytes)):
            raise TrafficError("pair_weights must be an iterable of triples")
        try:
            entries = tuple(pair_weights)
        except TypeError as exc:
            raise TrafficError("pair_weights must be an iterable of triples") from exc
        try:
            canonical = tuple(sorted(entries, key=lambda item: item[:2]))
        except (TypeError, AttributeError) as exc:
            raise TrafficError("pair_weights must contain sortable triples") from exc
        return cls(
            nodes=canonical_nodes,
            pair_weights=canonical,
        )

    @property
    def total_weight(self) -> int:
        return sum(weight for _, _, weight in self.pair_weights)

    @property
    def fingerprint(self) -> str:
        payload = {
            "nodes": self.nodes,
            "pair_weights": self.pair_weights,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def weight_of(self, source: str, destination: str) -> int:
        for pair_source, pair_destination, weight in self.pair_weights:
            if pair_source == source and pair_destination == destination:
                return weight
        raise TrafficError(
            f"ordered pair ({source!r}, {destination!r}) is not in the kernel"
        )

    def pair_for_ticket(self, ticket: int) -> tuple[str, str]:
        _validate_ticket(ticket, self.total_weight)
        cumulative = 0
        for source, destination, weight in self.pair_weights:
            cumulative += weight
            if ticket < cumulative:
                return (source, destination)
        raise AssertionError("kernel ticket was not resolved")


@dataclass(frozen=True, slots=True)
class AmountDistribution:
    """Canonical integer weights over distinct positive payment amounts."""

    amount_weights: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if type(self.amount_weights) is not tuple or not self.amount_weights:
            raise TrafficError("amount_weights must be a non-empty canonical tuple")
        amounts: list[int] = []
        for entry in self.amount_weights:
            if type(entry) is not tuple or len(entry) != 2:
                raise TrafficError("each amount weight must be an (amount, weight) tuple")
            amount, weight = entry
            _validate_positive_integer(amount, "payment amount")
            _validate_positive_integer(weight, "amount weight")
            amounts.append(amount)
        if tuple(sorted(self.amount_weights)) != self.amount_weights:
            raise TrafficError("amount_weights must be in canonical amount order")
        if len(set(amounts)) != len(amounts):
            raise TrafficError("amount_weights must use distinct amounts")

    @classmethod
    def from_weights(
        cls,
        amount_weights: Iterable[tuple[int, int]],
    ) -> "AmountDistribution":
        if isinstance(amount_weights, (str, bytes)):
            raise TrafficError("amount_weights must be an iterable of pairs")
        try:
            entries = tuple(amount_weights)
        except TypeError as exc:
            raise TrafficError("amount_weights must be an iterable of pairs") from exc
        try:
            canonical = tuple(sorted(entries))
        except TypeError as exc:
            raise TrafficError("amount_weights must contain sortable pairs") from exc
        return cls(canonical)

    @property
    def total_weight(self) -> int:
        return sum(weight for _, weight in self.amount_weights)

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.amount_weights,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def amount_for_ticket(self, ticket: int) -> int:
        _validate_ticket(ticket, self.total_weight)
        cumulative = 0
        for amount, weight in self.amount_weights:
            cumulative += weight
            if ticket < cumulative:
                return amount
        raise AssertionError("amount ticket was not resolved")


def uniform_kernel(nodes: Iterable[str]) -> DemandKernel:
    """Return equal weight on every ordered pair of distinct nodes."""

    canonical_nodes = _canonical_nodes(nodes)
    return _kernel_from_rule(canonical_nodes, lambda _source, _destination: 1)


def community_local_kernel(
    nodes: Iterable[str],
    blocks: Iterable[Iterable[str]],
    within_weight: int,
    cross_weight: int,
) -> DemandKernel:
    """Return a full-support kernel with distinct within/cross block weights."""

    canonical_nodes = _canonical_nodes(nodes)
    _validate_positive_integer(within_weight, "within_weight")
    _validate_positive_integer(cross_weight, "cross_weight")
    canonical_blocks = _canonical_partition(blocks, canonical_nodes)
    block_index = {
        node: index
        for index, block in enumerate(canonical_blocks)
        for node in block
    }
    return _kernel_from_rule(
        canonical_nodes,
        lambda source, destination: (
            within_weight
            if block_index[source] == block_index[destination]
            else cross_weight
        ),
    )


def hotspot_kernel(
    nodes: Iterable[str],
    hotspots: Iterable[str],
    base_weight: int,
    hotspot_multiplier: int,
) -> DemandKernel:
    """Weight a pair once per exogenously declared hotspot endpoint."""

    canonical_nodes = _canonical_nodes(nodes)
    _validate_positive_integer(base_weight, "base_weight")
    _validate_positive_integer(hotspot_multiplier, "hotspot_multiplier")
    hotspot_tuple = _canonical_subset(hotspots, canonical_nodes, "hotspots")
    if not hotspot_tuple or len(hotspot_tuple) == len(canonical_nodes):
        raise TrafficError("hotspots must be a non-empty proper node subset")
    hotspot_set = set(hotspot_tuple)
    return _kernel_from_rule(
        canonical_nodes,
        lambda source, destination: base_weight
        * hotspot_multiplier ** (
            int(source in hotspot_set) + int(destination in hotspot_set)
        ),
    )


def directional_drift_kernel(
    nodes: Iterable[str],
    left_group: Iterable[str],
    right_group: Iterable[str],
    forward_weight: int,
    reverse_weight: int,
    within_weight: int,
) -> DemandKernel:
    """Return asymmetric weights across an exogenous two-group partition."""

    canonical_nodes = _canonical_nodes(nodes)
    _validate_positive_integer(forward_weight, "forward_weight")
    _validate_positive_integer(reverse_weight, "reverse_weight")
    _validate_positive_integer(within_weight, "within_weight")
    left = _canonical_subset(left_group, canonical_nodes, "left_group")
    right = _canonical_subset(right_group, canonical_nodes, "right_group")
    if not left or not right or set(left).intersection(right):
        raise TrafficError("directional groups must be non-empty and disjoint")
    if set(left).union(right) != set(canonical_nodes):
        raise TrafficError("directional groups must partition the complete node set")
    left_set = set(left)
    right_set = set(right)

    def weight(source: str, destination: str) -> int:
        if source in left_set and destination in right_set:
            return forward_weight
        if source in right_set and destination in left_set:
            return reverse_weight
        return within_weight

    return _kernel_from_rule(canonical_nodes, weight)


def _kernel_from_rule(nodes, weight_rule) -> DemandKernel:
    return DemandKernel(
        nodes=nodes,
        pair_weights=tuple(
            (source, destination, weight_rule(source, destination))
            for source in nodes
            for destination in nodes
            if source != destination
        ),
    )


def _canonical_nodes(nodes: Iterable[str]) -> tuple[str, ...]:
    if isinstance(nodes, (str, bytes)):
        raise TrafficError("nodes must be an iterable of identifiers")
    try:
        node_tuple = tuple(nodes)
    except TypeError as exc:
        raise TrafficError("nodes must be an iterable of identifiers") from exc
    if len(node_tuple) < 2:
        raise TrafficError("traffic kernels require at least two nodes")
    for node in node_tuple:
        _validate_identifier(node, "node")
    if len(set(node_tuple)) != len(node_tuple):
        raise TrafficError("nodes must be unique")
    return tuple(sorted(node_tuple))


def _canonical_partition(
    blocks: Iterable[Iterable[str]],
    nodes: tuple[str, ...],
) -> tuple[tuple[str, ...], ...]:
    if isinstance(blocks, (str, bytes)):
        raise TrafficError("blocks must be an iterable of node groups")
    try:
        raw_blocks = tuple(blocks)
    except TypeError as exc:
        raise TrafficError("blocks must be an iterable of node groups") from exc
    canonical: list[tuple[str, ...]] = []
    for block in raw_blocks:
        canonical.append(_canonical_subset(block, nodes, "block"))
    if len(canonical) < 2 or any(not block for block in canonical):
        raise TrafficError("community kernels require at least two non-empty blocks")
    flattened = tuple(node for block in canonical for node in block)
    if len(set(flattened)) != len(flattened):
        raise TrafficError("community blocks must be disjoint")
    if set(flattened) != set(nodes):
        raise TrafficError("community blocks must partition the complete node set")
    return tuple(sorted(canonical, key=lambda block: block[0]))


def _canonical_subset(
    values: Iterable[str],
    nodes: tuple[str, ...],
    field: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TrafficError(f"{field} must be an iterable of node identifiers")
    try:
        value_tuple = tuple(values)
    except TypeError as exc:
        raise TrafficError(
            f"{field} must be an iterable of node identifiers"
        ) from exc
    for value in value_tuple:
        _validate_identifier(value, field)
    if len(set(value_tuple)) != len(value_tuple):
        raise TrafficError(f"{field} must not repeat a node")
    unknown = tuple(value for value in value_tuple if value not in set(nodes))
    if unknown:
        raise TrafficError(f"{field} contains an unknown node {unknown[0]!r}")
    return tuple(sorted(value_tuple))


def _validate_identifier(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise TrafficError(f"{field} must be a string")
    if not value or value != value.strip():
        raise TrafficError(f"{field} must be non-empty and have no outer whitespace")
    if "\x00" in value:
        raise TrafficError(f"{field} must not contain NUL")


def _validate_positive_integer(value: object, field: str) -> None:
    if type(value) is not int or value <= 0:
        raise TrafficError(f"{field} must be a positive integer")


def _validate_ticket(ticket: object, total_weight: int) -> None:
    if type(ticket) is not int or not 0 <= ticket < total_weight:
        raise TrafficError(f"ticket must be an integer in [0, {total_weight})")


__all__ = [
    "AmountDistribution",
    "DemandKernel",
    "TrafficError",
    "community_local_kernel",
    "directional_drift_kernel",
    "hotspot_kernel",
    "uniform_kernel",
]
