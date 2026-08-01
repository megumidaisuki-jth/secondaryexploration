"""Exact Kaplan-Meier summaries on the discrete request clock."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from secondaryexploration.simulation import EventObservation

from .errors import MetricError


class SurvivalError(MetricError):
    """Raised when a survival sample or requested estimand is invalid."""


@dataclass(frozen=True, slots=True)
class SurvivalPoint:
    """Kaplan-Meier state after all events at one request time."""

    time: int
    at_risk: int
    events: int
    censored: int
    survival: Fraction

    def __post_init__(self) -> None:
        if type(self.time) is not int or self.time < 0:
            raise SurvivalError("survival-point time must be non-negative")
        for name, value in (
            ("at_risk", self.at_risk),
            ("events", self.events),
            ("censored", self.censored),
        ):
            if type(value) is not int or value < 0:
                raise SurvivalError(f"{name} must be a non-negative integer")
        if self.at_risk < self.events + self.censored:
            raise SurvivalError("events and censoring cannot exceed the risk set")
        if not isinstance(self.survival, Fraction) or not 0 <= self.survival <= 1:
            raise SurvivalError("survival must be a Fraction in [0, 1]")


@dataclass(frozen=True, slots=True)
class KaplanMeierEstimate:
    """Validated exact survival curve for a non-empty canonical sample."""

    observations: tuple[EventObservation, ...]
    points: tuple[SurvivalPoint, ...]

    def __post_init__(self) -> None:
        if type(self.observations) is not tuple or not self.observations:
            raise SurvivalError("observations must be a non-empty canonical tuple")
        if any(
            not isinstance(observation, EventObservation)
            for observation in self.observations
        ):
            raise SurvivalError("observations must contain EventObservation objects")
        if tuple(sorted(self.observations, key=_observation_key)) != self.observations:
            raise SurvivalError("observations must be in canonical time/status order")
        if type(self.points) is not tuple or any(
            not isinstance(point, SurvivalPoint) for point in self.points
        ):
            raise SurvivalError("points must be a SurvivalPoint tuple")
        expected = _estimate_points(self.observations)
        if self.points != expected:
            raise SurvivalError("points do not match the observation sample")

    @property
    def maximum_follow_up(self) -> int:
        return self.observations[-1].request_index

    def survival_at(self, time: int) -> Fraction:
        _validate_evaluation_time(
            time,
            self.maximum_follow_up,
            self.points[-1].survival == 0,
            "time",
        )
        survival = Fraction(1, 1)
        for point in self.points:
            if point.time > time:
                break
            survival = point.survival
        return survival

    def failure_risk_at(self, time: int) -> Fraction:
        return Fraction(1, 1) - self.survival_at(time)

    def restricted_mean(self, horizon: int) -> Fraction:
        _validate_evaluation_time(
            horizon,
            self.maximum_follow_up,
            self.points[-1].survival == 0,
            "horizon",
        )
        total = Fraction(0, 1)
        previous_time = 0
        survival = Fraction(1, 1)
        for point in self.points:
            if point.time >= horizon:
                break
            total += (point.time - previous_time) * survival
            previous_time = point.time
            survival = point.survival
        total += (horizon - previous_time) * survival
        return total

    def quantile(self, probability: Fraction) -> int | None:
        if (
            not isinstance(probability, Fraction)
            or not 0 < probability <= Fraction(1, 1)
        ):
            raise SurvivalError("probability must be a Fraction in (0, 1]")
        threshold = Fraction(1, 1) - probability
        for point in self.points:
            if point.events and point.survival <= threshold:
                return point.time
        return None


def kaplan_meier(
    observations: Iterable[EventObservation],
) -> KaplanMeierEstimate:
    """Build an exact discrete-time Kaplan-Meier estimate."""

    if isinstance(observations, (str, bytes)):
        raise SurvivalError("observations must be an iterable of EventObservation")
    try:
        observation_tuple = tuple(observations)
    except TypeError as exc:
        raise SurvivalError(
            "observations must be an iterable of EventObservation"
        ) from exc
    if not observation_tuple:
        raise SurvivalError("survival estimation requires at least one observation")
    if any(
        not isinstance(observation, EventObservation)
        for observation in observation_tuple
    ):
        raise SurvivalError("every observation must be an EventObservation")
    canonical = tuple(sorted(observation_tuple, key=_observation_key))
    return KaplanMeierEstimate(canonical, _estimate_points(canonical))


def _estimate_points(
    observations: tuple[EventObservation, ...],
) -> tuple[SurvivalPoint, ...]:
    times = tuple(sorted({observation.request_index for observation in observations}))
    survival = Fraction(1, 1)
    points: list[SurvivalPoint] = []
    for time in times:
        at_risk = sum(
            observation.request_index >= time for observation in observations
        )
        events = sum(
            observation.observed and observation.request_index == time
            for observation in observations
        )
        censored = sum(
            not observation.observed and observation.request_index == time
            for observation in observations
        )
        survival *= Fraction(at_risk - events, at_risk)
        points.append(
            SurvivalPoint(time, at_risk, events, censored, survival)
        )
    return tuple(points)


def _observation_key(observation: EventObservation) -> tuple[int, bool]:
    return (observation.request_index, not observation.observed)


def _validate_evaluation_time(
    value: object,
    maximum: int,
    zero_survival_tail: bool,
    field: str,
) -> None:
    if type(value) is not int or value < 0:
        raise SurvivalError(f"{field} must be a non-negative integer")
    if value > maximum and not zero_survival_tail:
        raise SurvivalError(
            f"{field} exceeds maximum follow-up {maximum} with a nonzero tail"
        )


__all__ = [
    "KaplanMeierEstimate",
    "SurvivalError",
    "SurvivalPoint",
    "kaplan_meier",
]
