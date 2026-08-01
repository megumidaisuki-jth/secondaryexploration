"""Hash-attested inputs and topology semantics for verification Gate V1."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import csv
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import zipfile

from secondaryexploration.model import HypergraphState, PaymentRequest
from secondaryexploration.topology import (
    GraphEdge,
    HypergraphTopology,
    ParentGraph,
    TopologyError,
    binary_topology,
    closed_neighborhood_nch,
    fixed_hyperedge_size,
    node_budget_capital_state,
)


UPSTREAM_COMMIT = "2c4ffc92d704fa1b043fac395c1e5f662990d497"
PUBLISHED_TOPOLOGY_SHA256 = (
    "20998f859721383a8bbb23abd512043a53f6f98e5c658f12e369620cf3093499"
)
PUBLISHED_TRACE_SHA256 = (
    "705e619032964cb038044c3e54f2cae035759b43e75469f8b82094982d1e6cc9"
)
ACTIVE_CHANNEL_RULE = "at-least-one-directional-policy-present-and-enabled"


class PriorPaperError(ValueError):
    """Raised when a Gate-V1 source or derived object violates its contract."""


@dataclass(frozen=True, slots=True)
class PriorPaperInputManifest:
    """Expected identity and semantics of the accessible published inputs."""

    upstream_commit: str
    topology_sha256: str
    trace_sha256: str
    active_channel_rule: str = ACTIVE_CHANNEL_RULE

    def __post_init__(self) -> None:
        _validate_hex_digest(self.upstream_commit, 40, "upstream_commit")
        _validate_hex_digest(self.topology_sha256, 64, "topology_sha256")
        _validate_hex_digest(self.trace_sha256, 64, "trace_sha256")
        if self.active_channel_rule != ACTIVE_CHANNEL_RULE:
            raise PriorPaperError("unsupported active-channel rule")

    @classmethod
    def published(cls) -> "PriorPaperInputManifest":
        return cls(
            upstream_commit=UPSTREAM_COMMIT,
            topology_sha256=PUBLISHED_TOPOLOGY_SHA256,
            trace_sha256=PUBLISHED_TRACE_SHA256,
        )


@dataclass(frozen=True, slots=True)
class PriorPaperDataset:
    """Canonical simple active graph, capacities, and common request trace."""

    manifest: PriorPaperInputManifest
    parent: ParentGraph
    edge_capacities: tuple[tuple[GraphEdge, int], ...]
    networkx_edge_order: tuple[tuple[str, str], ...]
    requests: tuple[PaymentRequest, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, PriorPaperInputManifest):
            raise PriorPaperError("manifest must be a PriorPaperInputManifest")
        if not isinstance(self.parent, ParentGraph):
            raise PriorPaperError("parent must be a ParentGraph")
        if type(self.edge_capacities) is not tuple:
            raise PriorPaperError("edge_capacities must be a canonical tuple")
        observed_edges = tuple(edge for edge, _ in self.edge_capacities)
        if observed_edges != self.parent.edges:
            raise PriorPaperError("edge capacities must align with every parent edge")
        if any(type(capacity) is not int or capacity <= 0 for _, capacity in self.edge_capacities):
            raise PriorPaperError("every channel capacity must be a positive integer")
        if type(self.networkx_edge_order) is not tuple or any(
            type(edge) is not tuple or len(edge) != 2
            for edge in self.networkx_edge_order
        ):
            raise PriorPaperError("networkx_edge_order must be an endpoint-pair tuple")
        try:
            ordered_canonical = tuple(
                GraphEdge.from_endpoints(left, right)
                for left, right in self.networkx_edge_order
            )
        except TopologyError as exc:
            raise PriorPaperError("networkx edge order contains a malformed edge") from exc
        if len(set(ordered_canonical)) != len(ordered_canonical) or set(
            ordered_canonical
        ) != set(self.parent.edges):
            raise PriorPaperError(
                "networkx edge order must contain every simple parent edge once"
            )
        if type(self.requests) is not tuple or any(
            not isinstance(request, PaymentRequest) for request in self.requests
        ):
            raise PriorPaperError("requests must be a PaymentRequest tuple")

    @property
    def channel_capacity_map(self) -> dict[GraphEdge, int]:
        return dict(self.edge_capacities)

    @property
    def scaled_node_budgets(self) -> dict[str, int]:
        """Return exact doubled-unit budgets under an equal channel split."""

        budgets = {node_id: 0 for node_id in self.parent.nodes}
        for edge, capacity in self.edge_capacities:
            budgets[edge.left] += capacity
            budgets[edge.right] += capacity
        return budgets

    @property
    def scaled_requests(self) -> tuple[PaymentRequest, ...]:
        """Double amounts so odd SAT channel capacities split exactly."""

        return tuple(
            PaymentRequest(
                request.source,
                request.destination,
                2 * request.amount,
            )
            for request in self.requests
        )

    @property
    def out_of_graph_request_count(self) -> int:
        """Count published requests whose source or target is not active."""

        node_set = set(self.parent.nodes)
        return sum(
            request.source not in node_set or request.destination not in node_set
            for request in self.requests
        )


@dataclass(frozen=True, slots=True)
class PriorPaperTopologyDescriptor:
    """Exact structural descriptors used in the Gate-V1 discrepancy ledger."""

    node_count: int
    hyperedge_count: int
    incidence_count: int
    mean_incidence_degree: Fraction
    mean_hyperedge_arity: Fraction
    maximum_arity: int


def load_prior_paper_dataset(
    topology_zip: str | Path,
    trace_csv: str | Path,
    manifest: PriorPaperInputManifest,
) -> PriorPaperDataset:
    """Load and verify the public 2022 inputs using standard-library parsers."""

    if not isinstance(manifest, PriorPaperInputManifest):
        raise PriorPaperError("manifest must be a PriorPaperInputManifest")
    topology_path = Path(topology_zip)
    trace_path = Path(trace_csv)
    _verify_digest(topology_path, manifest.topology_sha256, "topology")
    _verify_digest(trace_path, manifest.trace_sha256, "trace")

    payload = _read_only_json_member(topology_path)
    raw_edges = payload.get("edges")
    if not isinstance(raw_edges, list):
        raise PriorPaperError("topology JSON must contain an edge list")
    capacities: dict[GraphEdge, int] = {}
    node_order: list[str] = []
    known_nodes: set[str] = set()
    neighbor_order: dict[str, list[str]] = {}
    neighbor_sets: dict[str, set[str]] = {}
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict) or not _is_active_channel(raw_edge):
            continue
        try:
            edge = GraphEdge.from_endpoints(
                raw_edge["node1_pub"],
                raw_edge["node2_pub"],
            )
            capacity = int(raw_edge["capacity"])
        except (KeyError, TypeError, ValueError, TopologyError) as exc:
            raise PriorPaperError("active channel record is malformed") from exc
        if capacity <= 0:
            raise PriorPaperError("active channel capacity must be positive")
        capacities[edge] = capacities.get(edge, 0) + capacity
        for node_id in (raw_edge["node1_pub"], raw_edge["node2_pub"]):
            if node_id not in known_nodes:
                known_nodes.add(node_id)
                node_order.append(node_id)
                neighbor_order[node_id] = []
                neighbor_sets[node_id] = set()
        left, right = raw_edge["node1_pub"], raw_edge["node2_pub"]
        if right not in neighbor_sets[left]:
            neighbor_sets[left].add(right)
            neighbor_order[left].append(right)
        if left not in neighbor_sets[right]:
            neighbor_sets[right].add(left)
            neighbor_order[right].append(left)
    if not capacities:
        raise PriorPaperError("active-channel filter produced an empty graph")

    nodes = sorted(
        {endpoint for edge in capacities for endpoint in edge.endpoints}
    )
    parent = ParentGraph.from_edges(nodes, (edge.endpoints for edge in capacities))
    ordered_capacities = tuple((edge, capacities[edge]) for edge in parent.edges)
    seen_edges: set[GraphEdge] = set()
    networkx_edge_order: list[tuple[str, str]] = []
    for left in node_order:
        for right in neighbor_order[left]:
            edge = GraphEdge.from_endpoints(left, right)
            if edge not in seen_edges:
                seen_edges.add(edge)
                networkx_edge_order.append((left, right))
    requests = _load_requests(trace_path)
    return PriorPaperDataset(
        manifest,
        parent,
        ordered_capacities,
        tuple(networkx_edge_order),
        requests,
    )


def prior_paper_binary_state(dataset: PriorPaperDataset) -> HypergraphState:
    """Construct the published LN baseline with an exact equal channel split."""

    if not isinstance(dataset, PriorPaperDataset):
        raise PriorPaperError("dataset must be a PriorPaperDataset")
    topology = binary_topology(dataset.parent)
    capacities = dataset.channel_capacity_map
    balances = {
        spec.hyperedge_id: {
            member: capacities[parent_edge]
            for member in spec.members
        }
        for spec, parent_edge in zip(topology.hyperedges, dataset.parent.edges)
    }
    return HypergraphState.from_balances(topology.nodes, balances)


def prior_paper_transformed_state(
    dataset: PriorPaperDataset,
    topology: HypergraphTopology,
) -> HypergraphState:
    """Allocate every published node budget evenly over transformed incidences."""

    if not isinstance(dataset, PriorPaperDataset):
        raise PriorPaperError("dataset must be a PriorPaperDataset")
    if not isinstance(topology, HypergraphTopology):
        raise PriorPaperError("topology must be a HypergraphTopology")
    if topology.nodes != dataset.parent.nodes:
        raise PriorPaperError("transformed topology must preserve the source nodes")
    return node_budget_capital_state(topology, dataset.scaled_node_budgets)


def componentwise_closed_neighborhood_nch(parent: ParentGraph) -> HypergraphTopology:
    """Apply the corrected NCH construction independently to each component."""

    return _componentwise_transform(parent, closed_neighborhood_nch)


def published_order_closed_neighborhood_nch(
    dataset: PriorPaperDataset,
) -> HypergraphTopology:
    """Reproduce NetworkX's order-sensitive local-ratio NCH cover.

    NetworkX graphs preserve node and adjacency insertion order. The accessible
    source dependency iterates that order, whereas the primary paper-2 NCH uses
    a canonical edge order. This function isolates the source-compatible order
    while retaining the declared closed-neighborhood correction.
    """

    if not isinstance(dataset, PriorPaperDataset):
        raise PriorPaperError("dataset must be a PriorPaperDataset")
    residual_cost = {node_id: 1 for node_id in dataset.parent.nodes}
    cover: set[str] = set()
    for left, right in dataset.networkx_edge_order:
        if left in cover or right in cover:
            continue
        if residual_cost[left] <= residual_cost[right]:
            cover.add(left)
            residual_cost[right] -= residual_cost[left]
        else:
            cover.add(right)
            residual_cost[left] -= residual_cost[right]
    hyperedges = {
        f"published-nch-{index:08d}": (cover_node,)
        + dataset.parent.neighbors(cover_node)
        for index, cover_node in enumerate(sorted(cover))
    }
    topology = HypergraphTopology.from_edges(dataset.parent.nodes, hyperedges)
    if any(degree == 0 for _, degree in topology.node_incidence_degrees):
        raise PriorPaperError("published-order NCH orphaned a source node")
    return topology


def componentwise_fixed_hyperedge_size(
    parent: ParentGraph,
    maximum_arity: int,
) -> HypergraphTopology:
    """Apply FHS independently while preserving a disconnected source graph."""

    if type(maximum_arity) is not int or maximum_arity < 2:
        raise PriorPaperError("maximum_arity must be an integer of at least two")
    return _componentwise_transform(
        parent,
        lambda component: fixed_hyperedge_size(
            component,
            min(maximum_arity, len(component.nodes)),
        ),
    )


def describe_prior_paper_topology(
    topology: HypergraphTopology,
) -> PriorPaperTopologyDescriptor:
    if not isinstance(topology, HypergraphTopology):
        raise PriorPaperError("topology must be a HypergraphTopology")
    resources = topology.resources
    if resources.hyperedge_count == 0:
        raise PriorPaperError("described topology must contain hyperedges")
    return PriorPaperTopologyDescriptor(
        node_count=resources.node_count,
        hyperedge_count=resources.hyperedge_count,
        incidence_count=resources.incidence_count,
        mean_incidence_degree=Fraction(
            resources.incidence_count,
            resources.node_count,
        ),
        mean_hyperedge_arity=Fraction(
            resources.incidence_count,
            resources.hyperedge_count,
        ),
        maximum_arity=resources.maximum_arity,
    )


def _componentwise_transform(
    parent: ParentGraph,
    transform: Callable[[ParentGraph], HypergraphTopology],
) -> HypergraphTopology:
    if not isinstance(parent, ParentGraph):
        raise PriorPaperError("parent must be a ParentGraph")
    components = _connected_components(parent)
    if any(len(component) < 2 for component in components):
        raise PriorPaperError("source parent must not contain isolated nodes")
    component_index = {
        node_id: index
        for index, component in enumerate(components)
        for node_id in component
    }
    component_edges: list[list[tuple[str, str]]] = [
        [] for _ in components
    ]
    for edge in parent.edges:
        index = component_index[edge.left]
        if component_index[edge.right] != index:
            raise RuntimeError("connected-component index split one parent edge")
        component_edges[index].append(edge.endpoints)

    combined: dict[str, tuple[str, ...]] = {}
    for index, (nodes, edges) in enumerate(zip(components, component_edges)):
        component_parent = ParentGraph.from_edges(nodes, edges)
        transformed = transform(component_parent)
        for edge in transformed.hyperedges:
            combined[f"component-{index:04d}-{edge.hyperedge_id}"] = edge.members
    return HypergraphTopology.from_edges(parent.nodes, combined)


def _connected_components(parent: ParentGraph) -> tuple[tuple[str, ...], ...]:
    unseen = set(parent.nodes)
    components: list[tuple[str, ...]] = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        stack = [start]
        component = [start]
        while stack:
            current = stack.pop()
            for neighbor in parent.neighbors(current):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.append(neighbor)
                    stack.append(neighbor)
        components.append(tuple(sorted(component)))
    return tuple(sorted(components, key=lambda component: component[0]))


def _is_active_channel(raw_edge: Mapping[str, object]) -> bool:
    return _is_enabled_policy(raw_edge.get("node1_policy")) or _is_enabled_policy(
        raw_edge.get("node2_policy")
    )


def _is_enabled_policy(policy: object) -> bool:
    return isinstance(policy, Mapping) and not bool(policy.get("disabled", False))


def _read_only_json_member(path: Path) -> dict[str, object]:
    try:
        with zipfile.ZipFile(path) as archive:
            members = tuple(
                name for name in archive.namelist() if not name.endswith("/")
            )
            if len(members) != 1:
                raise PriorPaperError("topology ZIP must contain exactly one file")
            with archive.open(members[0]) as raw:
                payload = json.load(io.TextIOWrapper(raw, encoding="utf-8"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise PriorPaperError("topology ZIP cannot be decoded") from exc
    if not isinstance(payload, dict):
        raise PriorPaperError("topology JSON root must be an object")
    return payload


def _load_requests(path: Path) -> tuple[PaymentRequest, ...]:
    requests: list[PaymentRequest] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"transaction_id", "source", "target", "amount_SAT"}
            if reader.fieldnames is None or set(reader.fieldnames) != required:
                raise PriorPaperError("trace CSV schema is not the published schema")
            transaction_ids: set[str] = set()
            for row in reader:
                transaction_id = row["transaction_id"]
                if transaction_id in transaction_ids:
                    raise PriorPaperError("trace transaction identifiers must be unique")
                transaction_ids.add(transaction_id)
                requests.append(
                    PaymentRequest(
                        row["source"],
                        row["target"],
                        int(row["amount_SAT"]),
                    )
                )
    except (OSError, TypeError, ValueError) as exc:
        if isinstance(exc, PriorPaperError):
            raise
        raise PriorPaperError("trace CSV cannot be decoded") from exc
    if not requests:
        raise PriorPaperError("trace CSV must contain requests")
    return tuple(requests)


def _verify_digest(path: Path, expected: str, label: str) -> None:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PriorPaperError(f"{label} input cannot be read") from exc
    if digest != expected:
        raise PriorPaperError(
            f"{label} SHA-256 mismatch: expected {expected}, observed {digest}"
        )


def _validate_hex_digest(value: object, length: int, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != length
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PriorPaperError(f"{field} must be a lowercase {length}-digit hex value")


__all__ = [
    "ACTIVE_CHANNEL_RULE",
    "PUBLISHED_TOPOLOGY_SHA256",
    "PUBLISHED_TRACE_SHA256",
    "UPSTREAM_COMMIT",
    "PriorPaperDataset",
    "PriorPaperError",
    "PriorPaperInputManifest",
    "PriorPaperTopologyDescriptor",
    "componentwise_closed_neighborhood_nch",
    "componentwise_fixed_hyperedge_size",
    "describe_prior_paper_topology",
    "load_prior_paper_dataset",
    "prior_paper_binary_state",
    "prior_paper_transformed_state",
    "published_order_closed_neighborhood_nch",
]
