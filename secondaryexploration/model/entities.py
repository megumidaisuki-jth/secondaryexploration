"""Immutable entities for exact hypergraph payment-network state."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


class ModelError(ValueError):
    """Raised when a hypergraph model object violates its structural contract."""


@dataclass(frozen=True, order=True, slots=True)
class BalanceCoordinate:
    """A directional member balance identified within one hyperedge."""

    hyperedge_id: str
    node_id: str

    def __post_init__(self) -> None:
        _validate_identifier(self.hyperedge_id, "hyperedge_id")
        _validate_identifier(self.node_id, "node_id")


@dataclass(frozen=True, slots=True)
class HyperedgeState:
    """Canonical balances for one conserved multi-party channel."""

    hyperedge_id: str
    balances: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.hyperedge_id, "hyperedge_id")
        if type(self.balances) is not tuple:
            raise ModelError("balances must be a canonical tuple")
        if len(self.balances) < 2:
            raise ModelError("a hyperedge must contain at least two member balances")

        member_ids: list[str] = []
        for item in self.balances:
            if type(item) is not tuple or len(item) != 2:
                raise ModelError("each balance must be a (node_id, amount) tuple")
            node_id, amount = item
            _validate_identifier(node_id, "node_id")
            _validate_nonnegative_integer(amount, f"balance[{node_id}]")
            member_ids.append(node_id)

        if len(set(member_ids)) != len(member_ids):
            raise ModelError("hyperedge balances must use unique member identifiers")
        if tuple(sorted(self.balances, key=lambda item: item[0])) != self.balances:
            raise ModelError("hyperedge balances must be in canonical node order")
        if self.total_balance <= 0:
            raise ModelError("a hyperedge must have positive total balance")

    @classmethod
    def from_balances(
        cls,
        hyperedge_id: str,
        balances: Mapping[str, int],
    ) -> "HyperedgeState":
        """Validate a balance mapping and store it in canonical node order."""

        _validate_identifier(hyperedge_id, "hyperedge_id")
        if not isinstance(balances, Mapping):
            raise ModelError("balances must be a mapping")

        pairs: list[tuple[str, int]] = []
        for node_id, amount in balances.items():
            _validate_identifier(node_id, "node_id")
            _validate_nonnegative_integer(amount, f"balance[{node_id}]")
            pairs.append((node_id, amount))
        return cls(hyperedge_id, tuple(sorted(pairs, key=lambda item: item[0])))

    @property
    def members(self) -> tuple[str, ...]:
        """Return member identifiers in canonical order."""

        return tuple(node_id for node_id, _ in self.balances)

    @property
    def total_balance(self) -> int:
        """Return conserved capital held by this hyperedge."""

        return sum(amount for _, amount in self.balances)

    def balance_of(self, node_id: str) -> int:
        """Return one member's hyperedge-local directional balance."""

        for member_id, amount in self.balances:
            if member_id == node_id:
                return amount
        raise ModelError(
            f"member {node_id!r} is not present in hyperedge {self.hyperedge_id!r}"
        )


@dataclass(frozen=True, slots=True)
class HypergraphState:
    """Canonical, hashable state of all nodes and conserved hyperedges."""

    nodes: tuple[str, ...]
    hyperedges: tuple[HyperedgeState, ...]

    def __post_init__(self) -> None:
        if type(self.nodes) is not tuple:
            raise ModelError("nodes must be a canonical tuple")
        if not self.nodes:
            raise ModelError("nodes must contain at least one node")
        for node_id in self.nodes:
            _validate_identifier(node_id, "node_id")
        if len(set(self.nodes)) != len(self.nodes):
            raise ModelError("nodes must be unique")
        if tuple(sorted(self.nodes)) != self.nodes:
            raise ModelError("nodes must be in canonical order")

        if type(self.hyperedges) is not tuple:
            raise ModelError("hyperedges must be a canonical tuple")
        if any(not isinstance(edge, HyperedgeState) for edge in self.hyperedges):
            raise ModelError("hyperedges must contain only HyperedgeState objects")
        edge_ids = tuple(edge.hyperedge_id for edge in self.hyperedges)
        if len(set(edge_ids)) != len(edge_ids):
            raise ModelError("hyperedges must use unique identifiers")
        if tuple(sorted(edge_ids)) != edge_ids:
            raise ModelError("hyperedges must be in canonical identifier order")

        node_set = set(self.nodes)
        for edge in self.hyperedges:
            unknown_members = [member for member in edge.members if member not in node_set]
            if unknown_members:
                rendered = ", ".join(repr(member) for member in unknown_members)
                raise ModelError(
                    f"hyperedge {edge.hyperedge_id!r} member {rendered} is not in "
                    "the network node set"
                )

    @classmethod
    def from_balances(
        cls,
        nodes: Iterable[str],
        hyperedges: Mapping[str, Mapping[str, int]],
    ) -> "HypergraphState":
        """Construct a canonical state from user-facing collections."""

        if isinstance(nodes, (str, bytes)):
            raise ModelError("nodes must be an iterable of node identifiers")
        try:
            node_tuple = tuple(nodes)
        except TypeError as exc:
            raise ModelError("nodes must be an iterable of node identifiers") from exc
        for node_id in node_tuple:
            _validate_identifier(node_id, "node_id")
        if len(set(node_tuple)) != len(node_tuple):
            raise ModelError("nodes must be unique")

        if not isinstance(hyperedges, Mapping):
            raise ModelError("hyperedges must be a mapping")
        edge_states = [
            HyperedgeState.from_balances(edge_id, balances)
            for edge_id, balances in hyperedges.items()
        ]
        return cls(
            nodes=tuple(sorted(node_tuple)),
            hyperedges=tuple(
                sorted(edge_states, key=lambda edge: edge.hyperedge_id)
            ),
        )

    @property
    def total_balance(self) -> int:
        """Return total capital across separately conserved hyperedges."""

        return sum(edge.total_balance for edge in self.hyperedges)

    def edge(self, hyperedge_id: str) -> HyperedgeState:
        """Return a hyperedge by identifier."""

        for edge in self.hyperedges:
            if edge.hyperedge_id == hyperedge_id:
                return edge
        raise ModelError(f"hyperedge {hyperedge_id!r} not found")


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    """An attempted directed payment in exact integer units."""

    source: str
    destination: str
    amount: int

    def __post_init__(self) -> None:
        _validate_identifier(self.source, "source")
        _validate_identifier(self.destination, "destination")
        if self.source == self.destination:
            raise ModelError("payment source and destination must differ")
        _validate_positive_integer(self.amount, "amount")


@dataclass(frozen=True, slots=True)
class TransferStep:
    """One payer-to-payee transfer inside a single hyperedge."""

    hyperedge_id: str
    payer: str
    payee: str

    def __post_init__(self) -> None:
        _validate_identifier(self.hyperedge_id, "hyperedge_id")
        _validate_identifier(self.payer, "payer")
        _validate_identifier(self.payee, "payee")
        if self.payer == self.payee:
            raise ModelError("transfer payer and payee must differ")


@dataclass(frozen=True, slots=True)
class Route:
    """A simple continuous alternating node-hyperedge payment path."""

    steps: tuple[TransferStep, ...]

    def __post_init__(self) -> None:
        if type(self.steps) is not tuple:
            raise ModelError("route steps must be a tuple")
        if not self.steps:
            raise ModelError("route must contain a non-empty step tuple")
        if any(not isinstance(step, TransferStep) for step in self.steps):
            raise ModelError("route steps must contain only TransferStep objects")

        for previous, current in zip(self.steps, self.steps[1:]):
            if previous.payee != current.payer:
                raise ModelError("route steps must form a continuous node path")

        edge_ids = tuple(step.hyperedge_id for step in self.steps)
        if len(set(edge_ids)) != len(edge_ids):
            raise ModelError("a simple route must not repeat a hyperedge")
        if len(set(self.nodes)) != len(self.nodes):
            raise ModelError("a simple route must not repeat a node")

    @property
    def source(self) -> str:
        """Return the route's first payer."""

        return self.steps[0].payer

    @property
    def destination(self) -> str:
        """Return the route's final payee."""

        return self.steps[-1].payee

    @property
    def hop_count(self) -> int:
        """Return the number of traversed hyperedges."""

        return len(self.steps)

    @property
    def nodes(self) -> tuple[str, ...]:
        """Return the continuous node sequence along the route."""

        return (self.steps[0].payer,) + tuple(step.payee for step in self.steps)


def _validate_identifier(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise ModelError(f"{field} must be a string")
    if not value or value != value.strip():
        raise ModelError(f"{field} must be non-empty and have no outer whitespace")
    if "\x00" in value:
        raise ModelError(f"{field} must not contain NUL")


def _validate_nonnegative_integer(value: object, field: str) -> None:
    if type(value) is not int or value < 0:
        raise ModelError(f"{field} must be a non-negative integer")


def _validate_positive_integer(value: object, field: str) -> None:
    if type(value) is not int or value <= 0:
        raise ModelError(f"{field} must be a positive integer")


__all__ = [
    "BalanceCoordinate",
    "HyperedgeState",
    "HypergraphState",
    "ModelError",
    "PaymentRequest",
    "Route",
    "TransferStep",
]
