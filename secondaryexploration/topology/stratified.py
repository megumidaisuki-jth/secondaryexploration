"""Deterministic structural strata and connected induced-subgraph samples."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import json

from secondaryexploration.randomness import SeedError, derive_seed

from .parent import GraphEdge, ParentGraph


LIGHTNING_STRATA_VERSION = 1
LIGHTNING_SUBGRAPH_SAMPLE_VERSION = 1
LIGHTNING_STRATA = ("core", "bridge", "peripheral")
_DIGEST_HEX = frozenset("0123456789abcdef")
_PRIORITY_DOMAIN = b"secondaryexploration.lightning-subgraph-priority.v1\x00"


class StratifiedSamplingError(ValueError):
    """Raised when structural stratification or sampling cannot be replayed."""


@dataclass(frozen=True, order=True, slots=True)
class BridgeMetric:
    """Exact articulation impact in one connected parent graph."""

    node_id: str
    component_count_after_removal: int
    fragmentation_gain: int

    def __post_init__(self) -> None:
        if type(self.node_id) is not str or not self.node_id:
            raise StratifiedSamplingError("bridge metric node_id must be nonempty")
        if (
            type(self.component_count_after_removal) is not int
            or self.component_count_after_removal < 2
        ):
            raise StratifiedSamplingError("an articulation must create at least two components")
        if type(self.fragmentation_gain) is not int or self.fragmentation_gain < 1:
            raise StratifiedSamplingError("bridge fragmentation gain must be positive")


@dataclass(frozen=True, slots=True)
class LightningStrataRecord:
    """Complete integer-valued structural classification of one source LCC."""

    version: int
    source_parent_fingerprint: str
    lcc: ParentGraph
    pool_width: int
    core_numbers: tuple[tuple[str, int], ...]
    degrees: tuple[tuple[str, int], ...]
    bridge_metrics: tuple[BridgeMetric, ...]
    core_candidates: tuple[str, ...]
    bridge_candidates: tuple[str, ...]
    peripheral_candidates: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version != LIGHTNING_STRATA_VERSION:
            raise StratifiedSamplingError("unsupported Lightning strata version")
        _validate_digest(self.source_parent_fingerprint, "source_parent_fingerprint")
        if not isinstance(self.lcc, ParentGraph) or not self.lcc.is_connected:
            raise StratifiedSamplingError("Lightning strata require a connected LCC")
        if type(self.pool_width) is not int or self.pool_width <= 0:
            raise StratifiedSamplingError("strata pool width must be positive")
        expected_nodes = self.lcc.nodes
        _validate_metric_table(self.core_numbers, expected_nodes, "core number")
        _validate_metric_table(self.degrees, expected_nodes, "degree")
        if tuple(metric.node_id for metric in self.bridge_metrics) != tuple(
            sorted(metric.node_id for metric in self.bridge_metrics)
        ):
            raise StratifiedSamplingError("bridge metrics must be canonical by node_id")
        bridge_metric_nodes = {metric.node_id for metric in self.bridge_metrics}
        if not bridge_metric_nodes.issubset(set(expected_nodes)):
            raise StratifiedSamplingError("bridge metric references an unknown node")
        for label, candidates in (
            ("core", self.core_candidates),
            ("bridge", self.bridge_candidates),
            ("peripheral", self.peripheral_candidates),
        ):
            if type(candidates) is not tuple or not candidates:
                raise StratifiedSamplingError(f"{label} candidate pool must be nonempty")
            if candidates != tuple(sorted(candidates)) or len(set(candidates)) != len(candidates):
                raise StratifiedSamplingError(f"{label} candidates must be canonical and unique")
            if not set(candidates).issubset(set(expected_nodes)):
                raise StratifiedSamplingError(f"{label} candidate references an unknown node")
        if len(self.core_candidates) != self.pool_width or len(
            self.peripheral_candidates
        ) != self.pool_width:
            raise StratifiedSamplingError("rank-tail candidate pools must match pool_width")
        pools = (
            set(self.core_candidates),
            set(self.bridge_candidates),
            set(self.peripheral_candidates),
        )
        if pools[0] & pools[1] or pools[0] & pools[2] or pools[1] & pools[2]:
            raise StratifiedSamplingError("Lightning candidate pools must be disjoint")
        if not set(self.bridge_candidates).issubset(bridge_metric_nodes):
            raise StratifiedSamplingError("bridge candidates must be articulation vertices")

    @property
    def lcc_fingerprint(self) -> str:
        return parent_graph_fingerprint(self.lcc)

    def candidates(self, stratum: str) -> tuple[str, ...]:
        _validate_stratum(stratum)
        if stratum == "core":
            return self.core_candidates
        if stratum == "bridge":
            return self.bridge_candidates
        return self.peripheral_candidates

    def fingerprint(self) -> str:
        mapping = {
            "version": self.version,
            "source_parent_fingerprint": self.source_parent_fingerprint,
            "lcc_fingerprint": self.lcc_fingerprint,
            "pool_width": self.pool_width,
            "core_numbers": [list(item) for item in self.core_numbers],
            "degrees": [list(item) for item in self.degrees],
            "bridge_metrics": [
                {
                    "node_id": metric.node_id,
                    "component_count_after_removal": metric.component_count_after_removal,
                    "fragmentation_gain": metric.fragmentation_gain,
                }
                for metric in self.bridge_metrics
            ],
            "core_candidates": list(self.core_candidates),
            "bridge_candidates": list(self.bridge_candidates),
            "peripheral_candidates": list(self.peripheral_candidates),
        }
        return _mapping_fingerprint(mapping)


@dataclass(frozen=True, slots=True)
class LightningSubgraphSample:
    """Replayable connected induced sample from one structural stratum."""

    version: int
    source_fingerprint: str
    source_parent_fingerprint: str
    lcc_fingerprint: str
    strata_fingerprint: str
    panel_year: int
    stratum: str
    replicate_index: int
    requested_size: int
    semantic_seed: int
    anchor: str
    discovery_order: tuple[str, ...]
    subgraph: ParentGraph

    def __post_init__(self) -> None:
        if self.version != LIGHTNING_SUBGRAPH_SAMPLE_VERSION:
            raise StratifiedSamplingError("unsupported Lightning sample version")
        for value, label in (
            (self.source_fingerprint, "source_fingerprint"),
            (self.source_parent_fingerprint, "source_parent_fingerprint"),
            (self.lcc_fingerprint, "lcc_fingerprint"),
            (self.strata_fingerprint, "strata_fingerprint"),
        ):
            _validate_digest(value, label)
        if type(self.panel_year) is not int or self.panel_year < 2018:
            raise StratifiedSamplingError("panel_year is invalid")
        _validate_stratum(self.stratum)
        if type(self.replicate_index) is not int or self.replicate_index < 0:
            raise StratifiedSamplingError("replicate_index must be nonnegative")
        if type(self.requested_size) is not int or self.requested_size < 2:
            raise StratifiedSamplingError("requested_size must be at least two")
        if type(self.semantic_seed) is not int or not 0 <= self.semantic_seed < 2**64:
            raise StratifiedSamplingError("semantic_seed must be an unsigned 64-bit integer")
        if type(self.discovery_order) is not tuple or len(
            self.discovery_order
        ) != self.requested_size:
            raise StratifiedSamplingError("discovery order must match requested_size")
        if len(set(self.discovery_order)) != len(self.discovery_order):
            raise StratifiedSamplingError("discovery order must contain unique nodes")
        if not self.discovery_order or self.discovery_order[0] != self.anchor:
            raise StratifiedSamplingError("sample anchor must start the discovery order")
        if not isinstance(self.subgraph, ParentGraph) or not self.subgraph.is_connected:
            raise StratifiedSamplingError("sample subgraph must be connected")
        if self.subgraph.nodes != tuple(sorted(self.discovery_order)):
            raise StratifiedSamplingError("sample nodes must equal the discovery order set")

    def fingerprint(self) -> str:
        mapping = {
            "version": self.version,
            "source_fingerprint": self.source_fingerprint,
            "source_parent_fingerprint": self.source_parent_fingerprint,
            "lcc_fingerprint": self.lcc_fingerprint,
            "strata_fingerprint": self.strata_fingerprint,
            "panel_year": self.panel_year,
            "stratum": self.stratum,
            "replicate_index": self.replicate_index,
            "requested_size": self.requested_size,
            "semantic_seed": self.semantic_seed,
            "anchor": self.anchor,
            "discovery_order": list(self.discovery_order),
            "subgraph_fingerprint": parent_graph_fingerprint(self.subgraph),
        }
        return _mapping_fingerprint(mapping)


def parent_graph_fingerprint(parent: ParentGraph) -> str:
    """Return a versioned canonical fingerprint for a parent graph."""

    if not isinstance(parent, ParentGraph):
        raise StratifiedSamplingError("parent must be a ParentGraph")
    digest = hashlib.sha256(b"secondaryexploration.parent-graph.v1\x00")
    for node_id in parent.nodes:
        _hash_text(digest, node_id)
    digest.update(b"\xff")
    for edge in parent.edges:
        _hash_text(digest, edge.left)
        _hash_text(digest, edge.right)
    return digest.hexdigest()


def largest_connected_parent(parent: ParentGraph) -> ParentGraph:
    """Return the canonical largest connected component of a parent graph."""

    if not isinstance(parent, ParentGraph):
        raise StratifiedSamplingError("parent must be a ParentGraph")
    unseen = set(parent.nodes)
    components: list[tuple[str, ...]] = []
    while unseen:
        start = min(unseen)
        visited = {start}
        frontier = [start]
        unseen.remove(start)
        while frontier:
            current = frontier.pop()
            for neighbor in parent.neighbors(current):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    visited.add(neighbor)
                    frontier.append(neighbor)
        components.append(tuple(sorted(visited)))
    selected = min(components, key=lambda component: (-len(component), component))
    return _induced_parent(parent, selected)


def stratify_lightning_parent(parent: ParentGraph) -> LightningStrataRecord:
    """Build mutually exclusive core, bridge, and peripheral candidate pools."""

    source_parent_fingerprint = parent_graph_fingerprint(parent)
    lcc = largest_connected_parent(parent)
    if len(lcc.nodes) < 5:
        raise StratifiedSamplingError("Lightning LCC must contain at least five nodes")
    degrees = {node_id: lcc.degree(node_id) for node_id in lcc.nodes}
    core_numbers = _core_numbers(lcc)
    pool_width = (len(lcc.nodes) + 4) // 5
    ranked = sorted(
        lcc.nodes,
        key=lambda node_id: (core_numbers[node_id], degrees[node_id], node_id),
    )
    peripheral = set(ranked[:pool_width])
    core = set(ranked[-pool_width:])
    if core & peripheral:
        raise StratifiedSamplingError("core and peripheral rank tails overlap")
    articulation = _articulation_metrics(lcc)
    bridge = set(articulation) - core - peripheral
    if not bridge:
        raise StratifiedSamplingError("no bridge candidates remain after rank-tail exclusion")
    return LightningStrataRecord(
        version=LIGHTNING_STRATA_VERSION,
        source_parent_fingerprint=source_parent_fingerprint,
        lcc=lcc,
        pool_width=pool_width,
        core_numbers=tuple((node_id, core_numbers[node_id]) for node_id in lcc.nodes),
        degrees=tuple((node_id, degrees[node_id]) for node_id in lcc.nodes),
        bridge_metrics=tuple(articulation[node_id] for node_id in sorted(articulation)),
        core_candidates=tuple(sorted(core)),
        bridge_candidates=tuple(sorted(bridge)),
        peripheral_candidates=tuple(sorted(peripheral)),
    )


def validate_lightning_strata_record(
    parent: ParentGraph,
    strata: LightningStrataRecord,
) -> None:
    """Reject a cached strata record unless it is the canonical parent result."""

    if not isinstance(strata, LightningStrataRecord):
        raise StratifiedSamplingError("strata must be a LightningStrataRecord")
    expected = stratify_lightning_parent(parent)
    if strata != expected or strata.fingerprint() != expected.fingerprint():
        raise StratifiedSamplingError("Lightning strata replay mismatch")


def sample_lightning_subgraph(
    parent: ParentGraph,
    source_fingerprint: str,
    panel_year: int,
    stratum: str,
    replicate_index: int,
    requested_size: int,
    base_seed: int,
    *,
    strata: LightningStrataRecord | None = None,
) -> LightningSubgraphSample:
    """Select one exact-size connected induced sample using hash-ordered BFS."""

    _validate_digest(source_fingerprint, "source_fingerprint")
    if type(panel_year) is not int or panel_year < 2018:
        raise StratifiedSamplingError("panel_year is invalid")
    _validate_stratum(stratum)
    if type(replicate_index) is not int or replicate_index < 0:
        raise StratifiedSamplingError("replicate_index must be nonnegative")
    if type(requested_size) is not int or requested_size < 2:
        raise StratifiedSamplingError("requested_size must be at least two")
    if strata is None:
        strata = stratify_lightning_parent(parent)
    else:
        validate_lightning_strata_record(parent, strata)
    if requested_size > len(strata.lcc.nodes):
        raise StratifiedSamplingError("requested_size exceeds the source LCC")
    candidates = strata.candidates(stratum)
    if replicate_index >= len(candidates):
        raise StratifiedSamplingError("replicate_index exceeds the stratum candidate pool")
    namespace = f"lightning.subgraph.v1.{panel_year}.{stratum}.{source_fingerprint}"
    try:
        anchor_seed = derive_seed(base_seed, f"{namespace}.anchors", 0)
        semantic_seed = derive_seed(
            base_seed,
            f"{namespace}.growth",
            replicate_index,
        )
    except SeedError as exc:
        raise StratifiedSamplingError("invalid Lightning subgraph seed tuple") from exc
    ranked_candidates = sorted(
        candidates,
        key=lambda node_id: (_node_priority(anchor_seed, "anchor", node_id), node_id),
    )
    anchor = ranked_candidates[replicate_index]
    discovery_order = _breadth_first_prefix(
        strata.lcc,
        anchor,
        requested_size,
        semantic_seed,
    )
    subgraph = _induced_parent(strata.lcc, discovery_order)
    return LightningSubgraphSample(
        version=LIGHTNING_SUBGRAPH_SAMPLE_VERSION,
        source_fingerprint=source_fingerprint,
        source_parent_fingerprint=strata.source_parent_fingerprint,
        lcc_fingerprint=strata.lcc_fingerprint,
        strata_fingerprint=strata.fingerprint(),
        panel_year=panel_year,
        stratum=stratum,
        replicate_index=replicate_index,
        requested_size=requested_size,
        semantic_seed=semantic_seed,
        anchor=anchor,
        discovery_order=discovery_order,
        subgraph=subgraph,
    )


def validate_lightning_subgraph_sample(
    parent: ParentGraph,
    expected_source_fingerprint: str,
    base_seed: int,
    sample: LightningSubgraphSample,
) -> None:
    """Fully replay a public sample record from the original source parent."""

    if not isinstance(sample, LightningSubgraphSample):
        raise StratifiedSamplingError("sample must be a LightningSubgraphSample")
    if sample.source_fingerprint != expected_source_fingerprint:
        raise StratifiedSamplingError("sample source fingerprint mismatch")
    expected = sample_lightning_subgraph(
        parent,
        expected_source_fingerprint,
        sample.panel_year,
        sample.stratum,
        sample.replicate_index,
        sample.requested_size,
        base_seed,
    )
    if sample != expected or sample.fingerprint() != expected.fingerprint():
        raise StratifiedSamplingError("Lightning subgraph sample replay mismatch")


def _core_numbers(parent: ParentGraph) -> dict[str, int]:
    import heapq

    residual_degree = {node_id: parent.degree(node_id) for node_id in parent.nodes}
    heap = [(degree, node_id) for node_id, degree in residual_degree.items()]
    heapq.heapify(heap)
    removed: set[str] = set()
    core: dict[str, int] = {}
    current_core = 0
    while heap:
        degree, node_id = heapq.heappop(heap)
        if node_id in removed or degree != residual_degree[node_id]:
            continue
        removed.add(node_id)
        current_core = max(current_core, degree)
        core[node_id] = current_core
        for neighbor in parent.neighbors(node_id):
            if neighbor not in removed:
                residual_degree[neighbor] -= 1
                heapq.heappush(heap, (residual_degree[neighbor], neighbor))
    return core


def _articulation_metrics(parent: ParentGraph) -> dict[str, BridgeMetric]:
    root = parent.nodes[0]
    discovery: dict[str, int] = {root: 0}
    low: dict[str, int] = {root: 0}
    subtree_size: dict[str, int] = {root: 1}
    parent_of: dict[str, str | None] = {root: None}
    child_count: dict[str, int] = {node_id: 0 for node_id in parent.nodes}
    separated_sizes: dict[str, list[int]] = {node_id: [] for node_id in parent.nodes}
    counter = 1
    stack: list[tuple[str, object]] = [(root, iter(parent.neighbors(root)))]
    while stack:
        node_id, iterator = stack[-1]
        try:
            neighbor = next(iterator)
        except StopIteration:
            stack.pop()
            parent_id = parent_of[node_id]
            if parent_id is not None:
                subtree_size[parent_id] += subtree_size[node_id]
                low[parent_id] = min(low[parent_id], low[node_id])
                if low[node_id] >= discovery[parent_id]:
                    separated_sizes[parent_id].append(subtree_size[node_id])
            continue
        if neighbor == parent_of[node_id]:
            continue
        if neighbor not in discovery:
            parent_of[neighbor] = node_id
            discovery[neighbor] = counter
            low[neighbor] = counter
            subtree_size[neighbor] = 1
            counter += 1
            child_count[node_id] += 1
            stack.append((neighbor, iter(parent.neighbors(neighbor))))
        else:
            low[node_id] = min(low[node_id], discovery[neighbor])
    if len(discovery) != len(parent.nodes):
        raise StratifiedSamplingError("articulation analysis requires a connected graph")
    total = len(parent.nodes)
    metrics: dict[str, BridgeMetric] = {}
    for node_id in parent.nodes:
        separated = separated_sizes[node_id]
        if parent_of[node_id] is None:
            if child_count[node_id] <= 1:
                continue
            parts = list(separated)
        else:
            if not separated:
                continue
            remainder = total - 1 - sum(separated)
            parts = list(separated)
            if remainder > 0:
                parts.append(remainder)
        if len(parts) < 2:
            continue
        metrics[node_id] = BridgeMetric(
            node_id,
            len(parts),
            total - 1 - max(parts),
        )
    return metrics


def _breadth_first_prefix(
    parent: ParentGraph,
    anchor: str,
    requested_size: int,
    seed: int,
) -> tuple[str, ...]:
    selected = {anchor}
    order = [anchor]
    frontier = deque([anchor])
    while frontier and len(order) < requested_size:
        current = frontier.popleft()
        neighbors = sorted(
            parent.neighbors(current),
            key=lambda node_id: (
                _node_priority(seed, f"neighbor:{current}", node_id),
                node_id,
            ),
        )
        for neighbor in neighbors:
            if neighbor in selected:
                continue
            selected.add(neighbor)
            order.append(neighbor)
            frontier.append(neighbor)
            if len(order) == requested_size:
                break
    if len(order) != requested_size:
        raise StratifiedSamplingError("connected growth exhausted before requested_size")
    return tuple(order)


def _induced_parent(parent: ParentGraph, nodes: tuple[str, ...]) -> ParentGraph:
    node_set = set(nodes)
    return ParentGraph.from_edges(
        node_set,
        (edge.endpoints for edge in parent.edges if edge.left in node_set and edge.right in node_set),
    )


def _node_priority(seed: int, purpose: str, node_id: str) -> bytes:
    digest = hashlib.sha256(_PRIORITY_DOMAIN)
    digest.update(seed.to_bytes(8, "big"))
    _hash_text(digest, purpose)
    _hash_text(digest, node_id)
    return digest.digest()


def _hash_text(digest: object, value: str) -> None:
    encoded = value.encode("utf-8")
    digest.update(len(encoded).to_bytes(4, "big"))
    digest.update(encoded)


def _mapping_fingerprint(mapping: dict[str, object]) -> str:
    payload = json.dumps(
        mapping,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_metric_table(
    values: tuple[tuple[str, int], ...],
    expected_nodes: tuple[str, ...],
    label: str,
) -> None:
    if type(values) is not tuple or tuple(node_id for node_id, _ in values) != expected_nodes:
        raise StratifiedSamplingError(f"{label} table must cover canonical LCC nodes")
    if any(type(value) is not int or value < 0 for _, value in values):
        raise StratifiedSamplingError(f"{label} values must be nonnegative integers")


def _validate_digest(value: str, label: str) -> None:
    if type(value) is not str or len(value) != 64 or not set(value).issubset(_DIGEST_HEX):
        raise StratifiedSamplingError(f"{label} must be a lowercase SHA-256 digest")


def _validate_stratum(value: str) -> None:
    if value not in LIGHTNING_STRATA:
        raise StratifiedSamplingError(f"stratum must be one of {LIGHTNING_STRATA}")


__all__ = [
    "LIGHTNING_STRATA",
    "LIGHTNING_STRATA_VERSION",
    "LIGHTNING_SUBGRAPH_SAMPLE_VERSION",
    "BridgeMetric",
    "LightningStrataRecord",
    "LightningSubgraphSample",
    "StratifiedSamplingError",
    "largest_connected_parent",
    "parent_graph_fingerprint",
    "sample_lightning_subgraph",
    "stratify_lightning_parent",
    "validate_lightning_strata_record",
    "validate_lightning_subgraph_sample",
]
