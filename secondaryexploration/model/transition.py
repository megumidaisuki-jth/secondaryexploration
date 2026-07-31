"""Preflight-checked atomic transitions for declared payment routes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .entities import (
    BalanceCoordinate,
    HyperedgeState,
    HypergraphState,
    ModelError,
    PaymentRequest,
    Route,
    TransferStep,
)


class RejectionReason(str, Enum):
    """Modeled reasons why a structurally valid declared route is rejected."""

    INSUFFICIENT_BALANCE = "insufficient_balance"


@dataclass(frozen=True, slots=True)
class PaymentTransition:
    """The immutable outcome of attempting one declared atomic route."""

    state: HypergraphState
    accepted: bool
    rejection_reason: RejectionReason | None
    depleted_coordinates: tuple[BalanceCoordinate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.state, HypergraphState):
            raise ModelError("transition state must be a HypergraphState")
        if type(self.accepted) is not bool:
            raise ModelError("transition accepted flag must be boolean")
        if self.rejection_reason is not None and not isinstance(
            self.rejection_reason,
            RejectionReason,
        ):
            raise ModelError("transition rejection_reason is invalid")
        if type(self.depleted_coordinates) is not tuple or any(
            not isinstance(coordinate, BalanceCoordinate)
            for coordinate in self.depleted_coordinates
        ):
            raise ModelError("depleted_coordinates must be a coordinate tuple")
        if len(set(self.depleted_coordinates)) != len(self.depleted_coordinates):
            raise ModelError("depleted_coordinates must be unique")
        if tuple(sorted(self.depleted_coordinates)) != self.depleted_coordinates:
            raise ModelError("depleted_coordinates must be in canonical order")

        if self.accepted and self.rejection_reason is not None:
            raise ModelError("an accepted transition must not have a rejection reason")
        if not self.accepted and self.rejection_reason is None:
            raise ModelError("a rejected transition must have a rejection reason")
        if not self.accepted and self.depleted_coordinates:
            raise ModelError("a rejected transition must not report depleted coordinates")

        if self.accepted:
            for coordinate in self.depleted_coordinates:
                try:
                    edge = self.state.edge(coordinate.hyperedge_id)
                    post_balance = edge.balance_of(coordinate.node_id)
                except ModelError as exc:
                    raise ModelError(
                        "a depleted coordinate must exist in the transition state"
                    ) from exc
                if post_balance != 0:
                    raise ModelError(
                        "a depleted coordinate must reference a zero post-state balance"
                    )


def is_route_feasible(
    state: HypergraphState,
    request: PaymentRequest,
    route: Route,
) -> bool:
    """Return whether every paying coordinate can fund the declared route."""

    routed_edges = _validate_route_against_state(state, request, route)
    return all(
        edge.balance_of(step.payer) >= request.amount
        for step, edge in routed_edges
    )


def apply_atomic_payment(
    state: HypergraphState,
    request: PaymentRequest,
    route: Route,
) -> PaymentTransition:
    """Apply all route deltas, or return the exact original state on rejection."""

    routed_edges = _validate_route_against_state(state, request, route)
    if any(
        edge.balance_of(step.payer) < request.amount
        for step, edge in routed_edges
    ):
        return PaymentTransition(
            state=state,
            accepted=False,
            rejection_reason=RejectionReason.INSUFFICIENT_BALANCE,
            depleted_coordinates=(),
        )

    replacements: dict[str, HyperedgeState] = {}
    depleted: list[BalanceCoordinate] = []
    for step, edge in routed_edges:
        updated_balances = dict(edge.balances)
        updated_balances[step.payer] -= request.amount
        updated_balances[step.payee] += request.amount
        updated_edge = HyperedgeState.from_balances(
            edge.hyperedge_id,
            updated_balances,
        )
        replacements[edge.hyperedge_id] = updated_edge
        if updated_balances[step.payer] == 0:
            depleted.append(BalanceCoordinate(edge.hyperedge_id, step.payer))

    new_state = HypergraphState(
        nodes=state.nodes,
        hyperedges=tuple(
            replacements.get(edge.hyperedge_id, edge) for edge in state.hyperedges
        ),
    )
    return PaymentTransition(
        state=new_state,
        accepted=True,
        rejection_reason=None,
        depleted_coordinates=tuple(sorted(depleted)),
    )


def _validate_route_against_state(
    state: HypergraphState,
    request: PaymentRequest,
    route: Route,
) -> tuple[tuple[TransferStep, HyperedgeState], ...]:
    if not isinstance(state, HypergraphState):
        raise ModelError("state must be a HypergraphState")
    if not isinstance(request, PaymentRequest):
        raise ModelError("request must be a PaymentRequest")
    if not isinstance(route, Route):
        raise ModelError("route must be a Route")

    node_set = set(state.nodes)
    if request.source not in node_set:
        raise ModelError(
            f"request source {request.source!r} is not in the network node set"
        )
    if request.destination not in node_set:
        raise ModelError(
            f"request destination {request.destination!r} is not in the network node set"
        )
    if route.source != request.source or route.destination != request.destination:
        raise ModelError("route endpoints do not match payment request endpoints")

    routed_edges: list[tuple[TransferStep, HyperedgeState]] = []
    for step in route.steps:
        edge = state.edge(step.hyperedge_id)
        if step.payer not in edge.members:
            raise ModelError(
                f"route payer {step.payer!r} is not a member of hyperedge "
                f"{edge.hyperedge_id!r}"
            )
        if step.payee not in edge.members:
            raise ModelError(
                f"route payee {step.payee!r} is not a member of hyperedge "
                f"{edge.hyperedge_id!r}"
            )
        routed_edges.append((step, edge))
    return tuple(routed_edges)


__all__ = [
    "PaymentTransition",
    "RejectionReason",
    "apply_atomic_payment",
    "is_route_feasible",
]
