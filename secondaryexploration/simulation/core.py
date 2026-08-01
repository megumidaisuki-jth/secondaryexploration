"""Core request-clock simulation with explicit censored first events."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
import random

from secondaryexploration.model import (
    BalanceCoordinate,
    HypergraphState,
    PaymentRequest,
    Route,
    apply_atomic_payment,
)
from secondaryexploration.routing import RouteSearchResult, find_feasible_route


class SimulationError(ValueError):
    """Raised when a core trace or recorded simulation result is inconsistent."""


@dataclass(frozen=True, slots=True)
class EventObservation:
    """An observed first-event index or a right-censoring index."""

    observed: bool
    request_index: int

    def __post_init__(self) -> None:
        if type(self.observed) is not bool:
            raise SimulationError("event observed flag must be boolean")
        if type(self.request_index) is not int or self.request_index < 0:
            raise SimulationError("event request_index must be a non-negative integer")

    @classmethod
    def observed_at(cls, request_index: int) -> "EventObservation":
        return cls(observed=True, request_index=request_index)

    @classmethod
    def censored_at(cls, request_index: int) -> "EventObservation":
        return cls(observed=False, request_index=request_index)


@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    """First accepted service after the first final rejection."""

    origin_request: int
    observed: bool
    request_index: int

    def __post_init__(self) -> None:
        if type(self.origin_request) is not int or self.origin_request < 1:
            raise SimulationError("recovery origin_request must be a positive integer")
        if type(self.observed) is not bool:
            raise SimulationError("recovery observed flag must be boolean")
        if type(self.request_index) is not int or self.request_index < self.origin_request:
            raise SimulationError(
                "recovery request_index must not precede origin_request"
            )
        if self.observed and self.request_index <= self.origin_request:
            raise SimulationError("observed recovery must occur later than rejection")

    @property
    def elapsed_requests(self) -> int:
        return self.request_index - self.origin_request


@dataclass(frozen=True, slots=True)
class FailureEpisode:
    """One maximal run of consecutive finally rejected requests."""

    start_request: int
    length: int
    ended_by_success: bool

    def __post_init__(self) -> None:
        if type(self.start_request) is not int or self.start_request < 1:
            raise SimulationError("failure start_request must be a positive integer")
        if type(self.length) is not int or self.length < 1:
            raise SimulationError("failure episode length must be a positive integer")
        if type(self.ended_by_success) is not bool:
            raise SimulationError("ended_by_success must be boolean")

    @property
    def end_request(self) -> int:
        return self.start_request + self.length - 1


@dataclass(frozen=True, slots=True)
class CoreRequestOutcome:
    """Auditable outcome of one request under the complete core router."""

    request_index: int
    request: PaymentRequest
    search_result: RouteSearchResult
    depleted_coordinates: tuple[BalanceCoordinate, ...]

    def __post_init__(self) -> None:
        if type(self.request_index) is not int or self.request_index < 1:
            raise SimulationError("outcome request_index must be a positive integer")
        if not isinstance(self.request, PaymentRequest):
            raise SimulationError("outcome request must be a PaymentRequest")
        if not isinstance(self.search_result, RouteSearchResult):
            raise SimulationError("outcome search_result must be a RouteSearchResult")
        if type(self.depleted_coordinates) is not tuple or any(
            not isinstance(coordinate, BalanceCoordinate)
            for coordinate in self.depleted_coordinates
        ):
            raise SimulationError("outcome depleted_coordinates must be a tuple")
        if len(set(self.depleted_coordinates)) != len(self.depleted_coordinates):
            raise SimulationError("outcome depleted_coordinates must be unique")
        if tuple(sorted(self.depleted_coordinates)) != self.depleted_coordinates:
            raise SimulationError("outcome depleted_coordinates must be canonical")
        if self.search_result.route is None and self.depleted_coordinates:
            raise SimulationError("a no-path outcome cannot report depletion")

    @property
    def accepted(self) -> bool:
        return self.search_result.route is not None

    @property
    def no_path(self) -> bool:
        return self.search_result.route is None

    @property
    def final_rejected(self) -> bool:
        return self.search_result.route is None


@dataclass(frozen=True, slots=True)
class CoreSimulationResult:
    """Validated complete record for one finite core request trace."""

    initial_state: HypergraphState
    final_state: HypergraphState
    outcomes: tuple[CoreRequestOutcome, ...]
    tau_dep: EventObservation
    tau_nopath: EventObservation
    tau_rej: EventObservation

    def __post_init__(self) -> None:
        if not isinstance(self.initial_state, HypergraphState):
            raise SimulationError("initial_state must be a HypergraphState")
        if not isinstance(self.final_state, HypergraphState):
            raise SimulationError("final_state must be a HypergraphState")
        if type(self.outcomes) is not tuple or any(
            not isinstance(outcome, CoreRequestOutcome) for outcome in self.outcomes
        ):
            raise SimulationError("outcomes must be a CoreRequestOutcome tuple")
        if not all(
            isinstance(observation, EventObservation)
            for observation in (self.tau_dep, self.tau_nopath, self.tau_rej)
        ):
            raise SimulationError("all tau fields must be EventObservation objects")

        replay_state = self.initial_state
        replay_search_rng = random.Random(0)
        first_depletion = 0 if _has_zero_balance(replay_state) else None
        first_no_path: int | None = None
        first_rejection: int | None = None
        for expected_index, outcome in enumerate(self.outcomes, start=1):
            if outcome.request_index != expected_index:
                raise SimulationError("outcome request indices must be consecutive")

            expected_search = find_feasible_route(
                replay_state,
                outcome.request,
                replay_search_rng,
            )
            recorded_search = outcome.search_result
            if recorded_search.route is None:
                if expected_search.route is not None:
                    raise SimulationError(
                        "recorded no-path request is feasible on replay"
                    )
                if first_no_path is None:
                    first_no_path = expected_index
                if first_rejection is None:
                    first_rejection = expected_index
                continue

            if expected_search.route is None:
                raise SimulationError(
                    "recorded selected route has no feasible path on replay"
                )
            if (
                recorded_search.shortest_hops,
                recorded_search.bottleneck,
                recorded_search.tied_route_count,
            ) != (
                expected_search.shortest_hops,
                expected_search.bottleneck,
                expected_search.tied_route_count,
            ):
                raise SimulationError(
                    "recorded search metadata does not match full replay search"
                )

            transition = apply_atomic_payment(
                replay_state,
                outcome.request,
                recorded_search.route,
            )
            if not transition.accepted:
                raise SimulationError("recorded selected route is not feasible on replay")
            if (
                _route_bottleneck(
                    replay_state,
                    outcome.request,
                    recorded_search.route,
                )
                != expected_search.bottleneck
            ):
                raise SimulationError(
                    "recorded route does not attain the full-search bottleneck"
                )
            if transition.depleted_coordinates != outcome.depleted_coordinates:
                raise SimulationError("recorded depleted_coordinates do not match replay")
            if first_depletion is None and transition.depleted_coordinates:
                first_depletion = expected_index
            replay_state = transition.state

        if replay_state != self.final_state:
            raise SimulationError("final_state does not match replayed outcomes")

        expected_tau_dep = _event_or_censor(first_depletion, self.horizon)
        expected_tau_nopath = _event_or_censor(first_no_path, self.horizon)
        expected_tau_rej = _event_or_censor(first_rejection, self.horizon)
        if self.tau_dep != expected_tau_dep:
            raise SimulationError("tau_dep does not match the first replayed depletion")
        if self.tau_nopath != expected_tau_nopath:
            raise SimulationError("tau_nopath does not match the first no-path request")
        if self.tau_rej != expected_tau_rej:
            raise SimulationError("tau_rej does not match the first final rejection")

    @property
    def horizon(self) -> int:
        return len(self.outcomes)

    @property
    def cumulative_successes(self) -> tuple[int, ...]:
        cumulative: list[int] = []
        accepted_count = 0
        for outcome in self.outcomes:
            accepted_count += int(outcome.accepted)
            cumulative.append(accepted_count)
        return tuple(cumulative)

    @property
    def success_rate(self) -> Fraction | None:
        if self.horizon == 0:
            return None
        accepted_count = sum(outcome.accepted for outcome in self.outcomes)
        return Fraction(accepted_count, self.horizon)

    @property
    def failure_episodes(self) -> tuple[FailureEpisode, ...]:
        episodes: list[FailureEpisode] = []
        start_request: int | None = None
        length = 0
        for outcome in self.outcomes:
            if outcome.final_rejected:
                if start_request is None:
                    start_request = outcome.request_index
                length += 1
            elif start_request is not None:
                episodes.append(
                    FailureEpisode(
                        start_request=start_request,
                        length=length,
                        ended_by_success=True,
                    )
                )
                start_request = None
                length = 0
        if start_request is not None:
            episodes.append(
                FailureEpisode(
                    start_request=start_request,
                    length=length,
                    ended_by_success=False,
                )
            )
        return tuple(episodes)

    @property
    def recovery_after_first_rejection(self) -> RecoveryObservation | None:
        first_rejection = next(
            (
                outcome.request_index
                for outcome in self.outcomes
                if outcome.final_rejected
            ),
            None,
        )
        if first_rejection is None:
            return None
        for outcome in self.outcomes[first_rejection:]:
            if outcome.accepted:
                return RecoveryObservation(
                    origin_request=first_rejection,
                    observed=True,
                    request_index=outcome.request_index,
                )
        return RecoveryObservation(
            origin_request=first_rejection,
            observed=False,
            request_index=self.horizon,
        )


def run_core_trace(
    initial_state: HypergraphState,
    requests: Iterable[PaymentRequest],
    rng: random.Random,
) -> CoreSimulationResult:
    """Run every request through complete routing and atomic settlement."""

    _validate_initial_state(initial_state)
    if not isinstance(rng, random.Random):
        raise SimulationError("rng must be an explicit random.Random instance")
    request_trace = _validated_request_trace(requests)
    return _run_validated_trace(
        initial_state,
        request_trace,
        (rng for _ in request_trace),
    )


def run_core_trace_with_request_rngs(
    initial_state: HypergraphState,
    requests: Iterable[PaymentRequest],
    request_rngs: Iterable[random.Random],
) -> CoreSimulationResult:
    """Run a trace with one explicit route-choice RNG per request.

    This entry point lets paired experiments bind randomness to the request
    index instead of consuming one topology-dependent sequential stream.
    """

    _validate_initial_state(initial_state)
    request_trace = _validated_request_trace(requests)
    if isinstance(request_rngs, (str, bytes)):
        raise SimulationError("request_rngs must be an iterable of random.Random objects")
    try:
        rng_iterator = iter(request_rngs)
    except TypeError as exc:
        raise SimulationError(
            "request_rngs must be an iterable of random.Random objects"
        ) from exc
    return _run_validated_trace(initial_state, request_trace, rng_iterator)


def _run_validated_trace(
    initial_state: HypergraphState,
    request_trace: tuple[PaymentRequest, ...],
    request_rngs: Iterable[random.Random],
) -> CoreSimulationResult:

    state = initial_state
    first_depletion = 0 if _has_zero_balance(state) else None
    first_no_path: int | None = None
    first_rejection: int | None = None
    outcomes: list[CoreRequestOutcome] = []
    rng_iterator = iter(request_rngs)
    for request_index, request in enumerate(request_trace, start=1):
        try:
            request_rng = next(rng_iterator)
        except StopIteration as exc:
            raise SimulationError(
                "request_rngs must contain exactly one RNG per request"
            ) from exc
        if not isinstance(request_rng, random.Random):
            raise SimulationError("every request RNG must be a random.Random instance")
        search_result = find_feasible_route(state, request, request_rng)
        if search_result.route is None:
            if first_no_path is None:
                first_no_path = request_index
            if first_rejection is None:
                first_rejection = request_index
            depleted_coordinates: tuple[BalanceCoordinate, ...] = ()
        else:
            transition = apply_atomic_payment(state, request, search_result.route)
            if not transition.accepted:
                raise SimulationError(
                    "full feasible router returned a route rejected by state engine"
                )
            depleted_coordinates = transition.depleted_coordinates
            if first_depletion is None and depleted_coordinates:
                first_depletion = request_index
            state = transition.state
        outcomes.append(
            CoreRequestOutcome(
                request_index=request_index,
                request=request,
                search_result=search_result,
                depleted_coordinates=depleted_coordinates,
            )
        )

    try:
        next(rng_iterator)
    except StopIteration:
        pass
    else:
        raise SimulationError("request_rngs must contain exactly one RNG per request")

    horizon = len(outcomes)
    return CoreSimulationResult(
        initial_state=initial_state,
        final_state=state,
        outcomes=tuple(outcomes),
        tau_dep=_event_or_censor(first_depletion, horizon),
        tau_nopath=_event_or_censor(first_no_path, horizon),
        tau_rej=_event_or_censor(first_rejection, horizon),
    )


def _validate_initial_state(initial_state: object) -> None:
    if not isinstance(initial_state, HypergraphState):
        raise SimulationError("initial_state must be a HypergraphState")


def _validated_request_trace(
    requests: Iterable[PaymentRequest],
) -> tuple[PaymentRequest, ...]:
    if isinstance(requests, (str, bytes)):
        raise SimulationError("requests must be an iterable of PaymentRequest objects")
    try:
        request_trace = tuple(requests)
    except TypeError as exc:
        raise SimulationError(
            "requests must be an iterable of PaymentRequest objects"
        ) from exc
    if any(not isinstance(request, PaymentRequest) for request in request_trace):
        raise SimulationError("every request must be a PaymentRequest")
    return request_trace


def _has_zero_balance(state: HypergraphState) -> bool:
    return any(
        balance == 0
        for edge in state.hyperedges
        for _, balance in edge.balances
    )


def _route_bottleneck(
    state: HypergraphState,
    request: PaymentRequest,
    route: Route,
) -> Fraction:
    return min(
        Fraction(
            state.edge(step.hyperedge_id).balance_of(step.payer) - request.amount,
            state.edge(step.hyperedge_id).total_balance,
        )
        for step in route.steps
    )


def _event_or_censor(
    event_request: int | None,
    horizon: int,
) -> EventObservation:
    if event_request is None:
        return EventObservation.censored_at(horizon)
    return EventObservation.observed_at(event_request)


__all__ = [
    "CoreRequestOutcome",
    "CoreSimulationResult",
    "EventObservation",
    "FailureEpisode",
    "RecoveryObservation",
    "SimulationError",
    "run_core_trace",
    "run_core_trace_with_request_rngs",
]
