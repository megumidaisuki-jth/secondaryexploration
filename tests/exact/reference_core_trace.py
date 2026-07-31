"""Independent two-node integer oracle for short core request traces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReferenceRequest:
    source: str
    destination: str
    amount: int


@dataclass(frozen=True, slots=True)
class ReferenceTrace:
    final_source_balance: int
    final_destination_balance: int
    accepted: tuple[bool, ...]
    tau_dep: tuple[bool, int]
    tau_nopath: tuple[bool, int]
    tau_rej: tuple[bool, int]
    cumulative_successes: tuple[int, ...]
    failure_episodes: tuple[tuple[int, int, bool], ...]
    recovery: tuple[int, bool, int] | None


def run_two_node_reference(
    source_balance: int,
    destination_balance: int,
    requests: tuple[ReferenceRequest, ...],
) -> ReferenceTrace:
    """Execute direct integer debits/credits without production components."""

    balances = {"s": source_balance, "t": destination_balance}
    first_depletion = 0 if 0 in balances.values() else None
    first_no_path: int | None = None
    first_rejection: int | None = None
    accepted: list[bool] = []
    for request_index, request in enumerate(requests, start=1):
        if balances[request.source] < request.amount:
            accepted.append(False)
            if first_no_path is None:
                first_no_path = request_index
            if first_rejection is None:
                first_rejection = request_index
            continue

        balances[request.source] -= request.amount
        balances[request.destination] += request.amount
        accepted.append(True)
        if first_depletion is None and balances[request.source] == 0:
            first_depletion = request_index

    horizon = len(requests)
    accepted_tuple = tuple(accepted)
    return ReferenceTrace(
        final_source_balance=balances["s"],
        final_destination_balance=balances["t"],
        accepted=accepted_tuple,
        tau_dep=_event_or_censor(first_depletion, horizon),
        tau_nopath=_event_or_censor(first_no_path, horizon),
        tau_rej=_event_or_censor(first_rejection, horizon),
        cumulative_successes=_cumulative_successes(accepted_tuple),
        failure_episodes=_failure_episodes(accepted_tuple),
        recovery=_recovery(accepted_tuple),
    )


def _event_or_censor(event_index: int | None, horizon: int) -> tuple[bool, int]:
    if event_index is None:
        return (False, horizon)
    return (True, event_index)


def _cumulative_successes(accepted: tuple[bool, ...]) -> tuple[int, ...]:
    total = 0
    cumulative = []
    for value in accepted:
        total += int(value)
        cumulative.append(total)
    return tuple(cumulative)


def _failure_episodes(
    accepted: tuple[bool, ...],
) -> tuple[tuple[int, int, bool], ...]:
    episodes: list[tuple[int, int, bool]] = []
    start: int | None = None
    length = 0
    for request_index, succeeded in enumerate(accepted, start=1):
        if not succeeded:
            if start is None:
                start = request_index
            length += 1
        elif start is not None:
            episodes.append((start, length, True))
            start = None
            length = 0
    if start is not None:
        episodes.append((start, length, False))
    return tuple(episodes)


def _recovery(
    accepted: tuple[bool, ...],
) -> tuple[int, bool, int] | None:
    origin = next(
        (index for index, succeeded in enumerate(accepted, start=1) if not succeeded),
        None,
    )
    if origin is None:
        return None
    for request_index, succeeded in enumerate(accepted[origin:], start=origin + 1):
        if succeeded:
            return (origin, True, request_index)
    return (origin, False, len(accepted))


__all__ = ["ReferenceRequest", "ReferenceTrace", "run_two_node_reference"]
