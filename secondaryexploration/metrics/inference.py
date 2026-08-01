"""Parent-level aggregation, cluster bootstrap, and hierarchy gating."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
import random
import re

from secondaryexploration.randomness import SeedError, derive_seed

from .errors import MetricError
from .paired import WithinBlockContrast


_MAX_UNSIGNED_64 = 2**64 - 1
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class InferenceError(MetricError):
    """Raised when hierarchical inference inputs are inconsistent."""


class ContrastMetric(str, Enum):
    """Registered scalar within-block contrast metrics."""

    NORMALIZED_RESTRICTED_TAU_NOPATH = "normalized_restricted_tau_nopath"
    FAILURE_RISK = "failure_risk"
    SUCCESS_RATE = "success_rate"
    ACCEPTED_VALUE = "accepted_value"


@dataclass(frozen=True, slots=True)
class BlockContrastObservation:
    """One treatment-minus-reference value from one paired trace block."""

    parent_graph_id: str
    trace_id: str
    analysis_cell_id: str
    manifest_fingerprint: str
    treatment_id: str
    reference_id: str
    metric: ContrastMetric
    horizon: int
    value: Fraction

    def __post_init__(self) -> None:
        for field, value in (
            ("parent_graph_id", self.parent_graph_id),
            ("trace_id", self.trace_id),
            ("analysis_cell_id", self.analysis_cell_id),
            ("treatment_id", self.treatment_id),
            ("reference_id", self.reference_id),
        ):
            _validate_identifier(value, field)
        if self.treatment_id == self.reference_id:
            raise InferenceError("treatment_id and reference_id must differ")
        if (
            not isinstance(self.manifest_fingerprint, str)
            or _SHA256_PATTERN.fullmatch(self.manifest_fingerprint) is None
        ):
            raise InferenceError("manifest_fingerprint must be lowercase SHA-256 hex")
        if not isinstance(self.metric, ContrastMetric):
            raise InferenceError("metric must be a ContrastMetric")
        if type(self.horizon) is not int or self.horizon < 1:
            raise InferenceError("horizon must be a positive integer")
        if not isinstance(self.value, Fraction):
            raise InferenceError("value must be an exact Fraction")


def block_contrast_observation(
    parent_graph_id: str,
    trace_id: str,
    analysis_cell_id: str,
    contrast: WithinBlockContrast,
    metric: ContrastMetric,
) -> BlockContrastObservation:
    """Extract one exact scalar from a manifest-attested paired contrast."""

    if not isinstance(contrast, WithinBlockContrast):
        raise InferenceError("contrast must be a WithinBlockContrast")
    if not isinstance(metric, ContrastMetric):
        raise InferenceError("metric must be a ContrastMetric")
    if metric is ContrastMetric.NORMALIZED_RESTRICTED_TAU_NOPATH:
        value = contrast.normalized_restricted_tau_nopath_difference
    elif metric is ContrastMetric.FAILURE_RISK:
        value = Fraction(contrast.failure_indicator_difference, 1)
    elif metric is ContrastMetric.SUCCESS_RATE:
        value = contrast.success_rate_difference
    else:
        value = Fraction(contrast.accepted_value_difference, 1)
    if value is None:
        raise InferenceError("the selected metric is undefined for this block")
    return BlockContrastObservation(
        parent_graph_id=parent_graph_id,
        trace_id=trace_id,
        analysis_cell_id=analysis_cell_id,
        manifest_fingerprint=contrast.manifest_fingerprint,
        treatment_id=contrast.treatment_id,
        reference_id=contrast.reference_id,
        metric=metric,
        horizon=contrast.treatment.horizon,
        value=value,
    )


@dataclass(frozen=True, slots=True)
class ParentContrastMean:
    """Equal-weight trace average within one parent graph."""

    parent_graph_id: str
    observations: tuple[BlockContrastObservation, ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.parent_graph_id, "parent_graph_id")
        if type(self.observations) is not tuple or not self.observations:
            raise InferenceError("observations must be a non-empty canonical tuple")
        if any(
            not isinstance(observation, BlockContrastObservation)
            for observation in self.observations
        ):
            raise InferenceError(
                "observations must contain BlockContrastObservation objects"
            )
        if any(
            observation.parent_graph_id != self.parent_graph_id
            for observation in self.observations
        ):
            raise InferenceError("all observations must match parent_graph_id")
        trace_ids = tuple(observation.trace_id for observation in self.observations)
        if len(set(trace_ids)) != len(trace_ids):
            raise InferenceError("trace identifiers must be unique within a parent")
        if tuple(sorted(trace_ids)) != trace_ids:
            raise InferenceError("observations must be in canonical trace_id order")
        fingerprints = tuple(
            observation.manifest_fingerprint for observation in self.observations
        )
        if len(set(fingerprints)) != len(fingerprints):
            raise InferenceError("manifest fingerprints must be unique within a parent")
        witness = _contrast_witness(self.observations[0])
        if any(
            _contrast_witness(observation) != witness
            for observation in self.observations[1:]
        ):
            raise InferenceError(
                "one parent mean cannot mix arms or contrast metrics"
            )

    @property
    def treatment_id(self) -> str:
        return self.observations[0].treatment_id

    @property
    def analysis_cell_id(self) -> str:
        return self.observations[0].analysis_cell_id

    @property
    def reference_id(self) -> str:
        return self.observations[0].reference_id

    @property
    def metric(self) -> ContrastMetric:
        return self.observations[0].metric

    @property
    def horizon(self) -> int:
        return self.observations[0].horizon

    @property
    def trace_count(self) -> int:
        return len(self.observations)

    @property
    def mean(self) -> Fraction:
        return sum(
            (observation.value for observation in self.observations),
            start=Fraction(0, 1),
        ) / self.trace_count


@dataclass(frozen=True, slots=True)
class HierarchicalContrastSample:
    """Canonical independent parent means for one registered contrast."""

    contrast_id: str
    parents: tuple[ParentContrastMean, ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.contrast_id, "contrast_id")
        if type(self.parents) is not tuple or len(self.parents) < 2:
            raise InferenceError("parents must contain at least two independent means")
        if any(not isinstance(parent, ParentContrastMean) for parent in self.parents):
            raise InferenceError("parents must contain ParentContrastMean objects")
        parent_ids = self.parent_ids
        if len(set(parent_ids)) != len(parent_ids):
            raise InferenceError("parent identifiers must be unique")
        if tuple(sorted(parent_ids)) != parent_ids:
            raise InferenceError("parents must be in canonical parent_graph_id order")
        witness = _parent_witness(self.parents[0])
        if any(_parent_witness(parent) != witness for parent in self.parents[1:]):
            raise InferenceError("one sample cannot mix arms or contrast metrics")
        fingerprints = tuple(
            observation.manifest_fingerprint
            for parent in self.parents
            for observation in parent.observations
        )
        if len(set(fingerprints)) != len(fingerprints):
            raise InferenceError("manifest fingerprints must be unique across a sample")

    @property
    def parent_ids(self) -> tuple[str, ...]:
        return tuple(parent.parent_graph_id for parent in self.parents)

    @property
    def treatment_id(self) -> str:
        return self.parents[0].treatment_id

    @property
    def analysis_cell_id(self) -> str:
        return self.parents[0].analysis_cell_id

    @property
    def reference_id(self) -> str:
        return self.parents[0].reference_id

    @property
    def metric(self) -> ContrastMetric:
        return self.parents[0].metric

    @property
    def horizon(self) -> int:
        return self.parents[0].horizon

    @property
    def estimate(self) -> Fraction:
        return sum(
            (parent.mean for parent in self.parents),
            start=Fraction(0, 1),
        ) / len(self.parents)


def group_parent_contrasts(
    observations: Iterable[BlockContrastObservation],
) -> tuple[ParentContrastMean, ...]:
    """Group trace contrasts without treating traces as independent parents."""

    observation_tuple = _validated_observations(observations)
    parent_ids = tuple(sorted({item.parent_graph_id for item in observation_tuple}))
    return tuple(
        ParentContrastMean(
            parent_graph_id,
            tuple(
                sorted(
                    (
                        observation
                        for observation in observation_tuple
                        if observation.parent_graph_id == parent_graph_id
                    ),
                    key=lambda observation: observation.trace_id,
                )
            ),
        )
        for parent_graph_id in parent_ids
    )


def hierarchical_contrast_sample(
    contrast_id: str,
    observations: Iterable[BlockContrastObservation],
) -> HierarchicalContrastSample:
    return HierarchicalContrastSample(
        contrast_id,
        group_parent_contrasts(observations),
    )


@dataclass(frozen=True, slots=True)
class BootstrapPlan:
    """Frozen parent-cluster bootstrap seed and precision envelope."""

    root_seed: int
    resamples: int
    confidence_level: Fraction

    def __post_init__(self) -> None:
        if type(self.root_seed) is not int or not 0 <= self.root_seed <= _MAX_UNSIGNED_64:
            raise InferenceError("root_seed must be an integer in [0, 2**64 - 1]")
        if type(self.resamples) is not int or self.resamples < 1:
            raise InferenceError("resamples must be a positive integer")
        if (
            not isinstance(self.confidence_level, Fraction)
            or not 0 < self.confidence_level < 1
        ):
            raise InferenceError("confidence_level must be a Fraction in (0, 1)")


def bootstrap_parent_indices(
    parent_count: int,
    plan: BootstrapPlan,
) -> tuple[tuple[int, ...], ...]:
    """Return independently seeded parent-index resamples."""

    if type(parent_count) is not int or parent_count < 2:
        raise InferenceError("parent_count must be an integer at least two")
    if not isinstance(plan, BootstrapPlan):
        raise InferenceError("plan must be a BootstrapPlan")
    replicates: list[tuple[int, ...]] = []
    for replicate_index in range(plan.resamples):
        try:
            seed = derive_seed(
                plan.root_seed,
                "statistics.parent_bootstrap",
                replicate_index,
            )
        except SeedError as exc:
            raise InferenceError("could not derive a bootstrap seed") from exc
        rng = random.Random(seed)
        replicates.append(
            tuple(_randbelow(rng, parent_count) for _ in range(parent_count))
        )
    return tuple(replicates)


def empirical_quantile(
    values: Iterable[Fraction],
    probability: Fraction,
) -> Fraction:
    """Return the left inverse of an exact finite empirical CDF."""

    if isinstance(values, (str, bytes)):
        raise InferenceError("values must be an iterable of Fraction objects")
    try:
        value_tuple = tuple(values)
    except TypeError as exc:
        raise InferenceError("values must be an iterable of Fraction objects") from exc
    if not value_tuple or any(not isinstance(value, Fraction) for value in value_tuple):
        raise InferenceError("values must be a non-empty Fraction collection")
    if not isinstance(probability, Fraction) or not 0 <= probability <= 1:
        raise InferenceError("probability must be a Fraction in [0, 1]")
    ordered = tuple(sorted(value_tuple))
    if probability == 0:
        return ordered[0]
    numerator = probability.numerator * len(ordered)
    index = (numerator + probability.denominator - 1) // probability.denominator - 1
    return ordered[index]


@dataclass(frozen=True, slots=True)
class ContrastInterval:
    """One parent-bootstrap percentile interval with explicit tail level."""

    contrast_id: str
    estimate: Fraction
    lower: Fraction
    upper: Fraction
    bootstrap_values: tuple[Fraction, ...]
    confidence_level: Fraction
    tail_probability: Fraction
    parent_count: int

    def __post_init__(self) -> None:
        _validate_identifier(self.contrast_id, "contrast_id")
        if any(
            not isinstance(value, Fraction)
            for value in (self.estimate, self.lower, self.upper)
        ):
            raise InferenceError("interval estimates and endpoints must be Fractions")
        if self.lower > self.upper:
            raise InferenceError("interval lower endpoint cannot exceed upper")
        if type(self.bootstrap_values) is not tuple or not self.bootstrap_values:
            raise InferenceError("bootstrap_values must be a non-empty tuple")
        if any(not isinstance(value, Fraction) for value in self.bootstrap_values):
            raise InferenceError("bootstrap_values must contain only Fractions")
        if (
            not isinstance(self.confidence_level, Fraction)
            or not 0 < self.confidence_level < 1
        ):
            raise InferenceError("confidence_level must be a Fraction in (0, 1)")
        if (
            not isinstance(self.tail_probability, Fraction)
            or not 0 < self.tail_probability < Fraction(1, 2)
        ):
            raise InferenceError("tail_probability must be a Fraction in (0, 1/2)")
        if type(self.parent_count) is not int or self.parent_count < 2:
            raise InferenceError("parent_count must be at least two")
        if self.lower != empirical_quantile(
            self.bootstrap_values,
            self.tail_probability,
        ) or self.upper != empirical_quantile(
            self.bootstrap_values,
            Fraction(1, 1) - self.tail_probability,
        ):
            raise InferenceError("interval endpoints do not match bootstrap quantiles")


@dataclass(frozen=True, slots=True)
class SimultaneousIntervalFamily:
    """Aligned common-resample intervals for one registered contrast family."""

    plan: BootstrapPlan
    samples: tuple[HierarchicalContrastSample, ...]
    parent_index_replicates: tuple[tuple[int, ...], ...]
    adjusted_contrast_ids: tuple[str, ...]
    intervals: tuple[ContrastInterval, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.plan, BootstrapPlan):
            raise InferenceError("plan must be a BootstrapPlan")
        _validate_aligned_samples(self.samples)
        sample_ids = tuple(sample.contrast_id for sample in self.samples)
        if (
            type(self.adjusted_contrast_ids) is not tuple
            or not self.adjusted_contrast_ids
            or len(set(self.adjusted_contrast_ids)) != len(self.adjusted_contrast_ids)
            or tuple(sorted(self.adjusted_contrast_ids)) != self.adjusted_contrast_ids
            or not set(self.adjusted_contrast_ids).issubset(sample_ids)
        ):
            raise InferenceError(
                "adjusted_contrast_ids must be a non-empty canonical sample subset"
            )
        expected_indices = bootstrap_parent_indices(
            len(self.samples[0].parents),
            self.plan,
        )
        if self.parent_index_replicates != expected_indices:
            raise InferenceError("parent_index_replicates do not replay from the plan")
        if type(self.intervals) is not tuple or not self.intervals:
            raise InferenceError("intervals must be a non-empty canonical tuple")
        if any(not isinstance(interval, ContrastInterval) for interval in self.intervals):
            raise InferenceError("intervals must contain ContrastInterval objects")
        contrast_ids = tuple(interval.contrast_id for interval in self.intervals)
        if len(set(contrast_ids)) != len(contrast_ids):
            raise InferenceError("interval contrast identifiers must be unique")
        if tuple(sorted(contrast_ids)) != contrast_ids:
            raise InferenceError("intervals must be in canonical contrast_id order")
        if contrast_ids != sample_ids:
            raise InferenceError("intervals must match the canonical sample IDs")
        expected_intervals = _intervals_for_samples(
            self.samples,
            self.plan,
            self.parent_index_replicates,
            self.adjusted_contrast_ids,
        )
        if self.intervals != expected_intervals:
            raise InferenceError("intervals do not replay from samples and shared indices")

    @property
    def family_size(self) -> int:
        return len(self.adjusted_contrast_ids)

    @property
    def tail_probability(self) -> Fraction:
        return (Fraction(1, 1) - self.plan.confidence_level) / (
            2 * self.family_size
        )


def simultaneous_percentile_intervals(
    samples: tuple[HierarchicalContrastSample, ...],
    plan: BootstrapPlan,
) -> SimultaneousIntervalFamily:
    """Compute aligned Bonferroni parent-bootstrap percentile intervals."""

    _validate_aligned_samples(samples)
    if not isinstance(plan, BootstrapPlan):
        raise InferenceError("plan must be a BootstrapPlan")
    return _build_interval_family(
        samples,
        plan,
        tuple(sample.contrast_id for sample in samples),
    )


def hierarchical_percentile_intervals(
    samples: tuple[HierarchicalContrastSample, ...],
    hierarchy: "ConfirmatoryHierarchy",
    plan: BootstrapPlan,
) -> SimultaneousIntervalFamily:
    """Adjust global/secondary intervals while leaving exploration nominal."""

    _validate_aligned_samples(samples)
    if not isinstance(hierarchy, ConfirmatoryHierarchy):
        raise InferenceError("hierarchy must be a ConfirmatoryHierarchy")
    sample_ids = {sample.contrast_id for sample in samples}
    registration_ids = {
        registration.contrast_id for registration in hierarchy.registrations
    }
    if sample_ids != registration_ids:
        raise InferenceError("hierarchy and samples must contain the same IDs")
    adjusted_ids = tuple(
        sorted(
            registration.contrast_id
            for registration in hierarchy.registrations
            if registration.tier is not InferenceTier.EXPLORATORY
        )
    )
    return _build_interval_family(samples, plan, adjusted_ids)


def _build_interval_family(
    samples: tuple[HierarchicalContrastSample, ...],
    plan: BootstrapPlan,
    adjusted_contrast_ids: tuple[str, ...],
) -> SimultaneousIntervalFamily:
    if not isinstance(plan, BootstrapPlan):
        raise InferenceError("plan must be a BootstrapPlan")
    adjusted_tail = (Fraction(1, 1) - plan.confidence_level) / (
        2 * len(adjusted_contrast_ids)
    )
    if plan.resamples * adjusted_tail < 1:
        raise InferenceError(
            "resamples are too few to resolve the adjusted empirical tail"
        )
    index_replicates = bootstrap_parent_indices(len(samples[0].parent_ids), plan)
    intervals = _intervals_for_samples(
        samples,
        plan,
        index_replicates,
        adjusted_contrast_ids,
    )
    return SimultaneousIntervalFamily(
        plan,
        samples,
        index_replicates,
        adjusted_contrast_ids,
        intervals,
    )


def _intervals_for_samples(
    samples: tuple[HierarchicalContrastSample, ...],
    plan: BootstrapPlan,
    index_replicates: tuple[tuple[int, ...], ...],
    adjusted_contrast_ids: tuple[str, ...],
) -> tuple[ContrastInterval, ...]:
    adjusted_tail = (Fraction(1, 1) - plan.confidence_level) / (
        2 * len(adjusted_contrast_ids)
    )
    nominal_tail = (Fraction(1, 1) - plan.confidence_level) / 2
    intervals: list[ContrastInterval] = []
    for sample in samples:
        tail_probability = (
            adjusted_tail
            if sample.contrast_id in set(adjusted_contrast_ids)
            else nominal_tail
        )
        parent_values = tuple(parent.mean for parent in sample.parents)
        bootstrap_values = tuple(
            sum(
                (parent_values[index] for index in indices),
                start=Fraction(0, 1),
            )
            / len(parent_values)
            for indices in index_replicates
        )
        intervals.append(
            ContrastInterval(
                contrast_id=sample.contrast_id,
                estimate=sample.estimate,
                lower=empirical_quantile(bootstrap_values, tail_probability),
                upper=empirical_quantile(
                    bootstrap_values,
                    Fraction(1, 1) - tail_probability,
                ),
                bootstrap_values=bootstrap_values,
                confidence_level=plan.confidence_level,
                tail_probability=tail_probability,
                parent_count=len(sample.parents),
            )
        )
    return tuple(intervals)


class InferenceTier(int, Enum):
    GLOBAL = 1
    SECONDARY = 2
    EXPLORATORY = 3


class BeneficialDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class InferenceStatus(str, Enum):
    CONFIRMATORY = "confirmatory"
    DESCRIPTIVE = "descriptive"
    EXPLORATORY = "exploratory"


@dataclass(frozen=True, slots=True)
class ContrastRegistration:
    contrast_id: str
    tier: InferenceTier
    beneficial_direction: BeneficialDirection

    def __post_init__(self) -> None:
        _validate_identifier(self.contrast_id, "contrast_id")
        if not isinstance(self.tier, InferenceTier):
            raise InferenceError("tier must be an InferenceTier")
        if not isinstance(self.beneficial_direction, BeneficialDirection):
            raise InferenceError(
                "beneficial_direction must be a BeneficialDirection"
            )


@dataclass(frozen=True, slots=True)
class ConfirmatoryHierarchy:
    registrations: tuple[ContrastRegistration, ...]

    def __post_init__(self) -> None:
        if type(self.registrations) is not tuple or not self.registrations:
            raise InferenceError("registrations must be a non-empty canonical tuple")
        if any(
            not isinstance(registration, ContrastRegistration)
            for registration in self.registrations
        ):
            raise InferenceError("registrations must contain ContrastRegistration")
        ids = tuple(registration.contrast_id for registration in self.registrations)
        if len(set(ids)) != len(ids):
            raise InferenceError("registration contrast identifiers must be unique")
        expected = tuple(
            sorted(
                self.registrations,
                key=lambda registration: (
                    registration.tier.value,
                    registration.contrast_id,
                ),
            )
        )
        if expected != self.registrations:
            raise InferenceError("registrations must be in canonical tier/id order")
        if sum(
            registration.tier is InferenceTier.GLOBAL
            for registration in self.registrations
        ) != 1:
            raise InferenceError("the hierarchy must contain exactly one global contrast")


@dataclass(frozen=True, slots=True)
class RegisteredInference:
    registration: ContrastRegistration
    interval: ContrastInterval
    status: InferenceStatus
    beneficial_effect_supported: bool

    def __post_init__(self) -> None:
        if not isinstance(self.registration, ContrastRegistration):
            raise InferenceError("registration must be a ContrastRegistration")
        if not isinstance(self.interval, ContrastInterval):
            raise InferenceError("interval must be a ContrastInterval")
        if self.registration.contrast_id != self.interval.contrast_id:
            raise InferenceError("registration and interval identifiers must match")
        if not isinstance(self.status, InferenceStatus):
            raise InferenceError("status must be an InferenceStatus")
        if type(self.beneficial_effect_supported) is not bool:
            raise InferenceError("beneficial_effect_supported must be boolean")


def apply_confirmatory_hierarchy(
    hierarchy: ConfirmatoryHierarchy,
    family: SimultaneousIntervalFamily,
) -> tuple[RegisteredInference, ...]:
    """Apply the global gate without suppressing any effect or interval."""

    if not isinstance(hierarchy, ConfirmatoryHierarchy):
        raise InferenceError("hierarchy must be a ConfirmatoryHierarchy")
    if not isinstance(family, SimultaneousIntervalFamily):
        raise InferenceError("family must be a SimultaneousIntervalFamily")
    interval_by_id = {
        interval.contrast_id: interval for interval in family.intervals
    }
    registration_ids = {
        registration.contrast_id for registration in hierarchy.registrations
    }
    if set(interval_by_id) != registration_ids:
        raise InferenceError("hierarchy and interval family must contain the same IDs")
    expected_adjusted_ids = tuple(
        sorted(
            registration.contrast_id
            for registration in hierarchy.registrations
            if registration.tier is not InferenceTier.EXPLORATORY
        )
    )
    if family.adjusted_contrast_ids != expected_adjusted_ids:
        raise InferenceError(
            "interval adjustment family must contain global and secondary IDs only"
        )
    global_registration = next(
        registration
        for registration in hierarchy.registrations
        if registration.tier is InferenceTier.GLOBAL
    )
    global_supported = _beneficial_support(
        global_registration,
        interval_by_id[global_registration.contrast_id],
    )
    decisions: list[RegisteredInference] = []
    for registration in hierarchy.registrations:
        interval = interval_by_id[registration.contrast_id]
        if registration.tier is InferenceTier.GLOBAL:
            status = InferenceStatus.CONFIRMATORY
        elif registration.tier is InferenceTier.SECONDARY:
            status = (
                InferenceStatus.CONFIRMATORY
                if global_supported
                else InferenceStatus.DESCRIPTIVE
            )
        else:
            status = InferenceStatus.EXPLORATORY
        decisions.append(
            RegisteredInference(
                registration,
                interval,
                status,
                _beneficial_support(registration, interval),
            )
        )
    return tuple(decisions)


def _beneficial_support(
    registration: ContrastRegistration,
    interval: ContrastInterval,
) -> bool:
    if registration.beneficial_direction is BeneficialDirection.POSITIVE:
        return interval.lower > 0
    return interval.upper < 0


def _validated_observations(
    observations: Iterable[BlockContrastObservation],
) -> tuple[BlockContrastObservation, ...]:
    if isinstance(observations, (str, bytes)):
        raise InferenceError("observations must be an iterable")
    try:
        values = tuple(observations)
    except TypeError as exc:
        raise InferenceError("observations must be an iterable") from exc
    if not values or any(
        not isinstance(value, BlockContrastObservation) for value in values
    ):
        raise InferenceError(
            "observations must be a non-empty BlockContrastObservation collection"
        )
    witness = _contrast_witness(values[0])
    if any(_contrast_witness(value) != witness for value in values[1:]):
        raise InferenceError("observations cannot mix arms or contrast metrics")
    return values


def _validate_aligned_samples(
    samples: object,
) -> None:
    if type(samples) is not tuple or not samples:
        raise InferenceError("samples must be a non-empty canonical tuple")
    if any(not isinstance(sample, HierarchicalContrastSample) for sample in samples):
        raise InferenceError("samples must contain HierarchicalContrastSample objects")
    contrast_ids = tuple(sample.contrast_id for sample in samples)
    if len(set(contrast_ids)) != len(contrast_ids):
        raise InferenceError("sample contrast identifiers must be unique")
    if tuple(sorted(contrast_ids)) != contrast_ids:
        raise InferenceError("samples must be in canonical contrast_id order")
    parent_ids = samples[0].parent_ids
    if any(sample.parent_ids != parent_ids for sample in samples[1:]):
        raise InferenceError("all simultaneous samples must use the same parent IDs")
    analysis_cell_id = samples[0].analysis_cell_id
    horizon = samples[0].horizon
    if any(
        sample.analysis_cell_id != analysis_cell_id or sample.horizon != horizon
        for sample in samples[1:]
    ):
        raise InferenceError(
            "all simultaneous samples must use the same analysis cell and horizon"
        )
    block_layout = _sample_block_layout(samples[0])
    if any(_sample_block_layout(sample) != block_layout for sample in samples[1:]):
        raise InferenceError(
            "all simultaneous samples must use the same parent-trace manifest layout"
        )


def _contrast_witness(
    observation: BlockContrastObservation,
) -> tuple[str, str, str, ContrastMetric, int]:
    return (
        observation.analysis_cell_id,
        observation.treatment_id,
        observation.reference_id,
        observation.metric,
        observation.horizon,
    )


def _sample_block_layout(
    sample: HierarchicalContrastSample,
) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    return tuple(
        (
            parent.parent_graph_id,
            tuple(
                (observation.trace_id, observation.manifest_fingerprint)
                for observation in parent.observations
            ),
        )
        for parent in sample.parents
    )


def _parent_witness(
    parent: ParentContrastMean,
) -> tuple[str, str, str, ContrastMetric, int]:
    return (
        parent.analysis_cell_id,
        parent.treatment_id,
        parent.reference_id,
        parent.metric,
        parent.horizon,
    )


def _randbelow(rng: random.Random, stop: int) -> int:
    bit_count = stop.bit_length()
    while True:
        candidate = rng.getrandbits(bit_count)
        if candidate < stop:
            return candidate


def _validate_identifier(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise InferenceError(f"{field} must be a string")
    if not value or value != value.strip():
        raise InferenceError(f"{field} must be non-empty and have no outer whitespace")
    if "\x00" in value:
        raise InferenceError(f"{field} must not contain NUL")


__all__ = [
    "BeneficialDirection",
    "BlockContrastObservation",
    "BootstrapPlan",
    "ConfirmatoryHierarchy",
    "ContrastInterval",
    "ContrastMetric",
    "ContrastRegistration",
    "HierarchicalContrastSample",
    "InferenceError",
    "InferenceStatus",
    "InferenceTier",
    "ParentContrastMean",
    "RegisteredInference",
    "SimultaneousIntervalFamily",
    "apply_confirmatory_hierarchy",
    "block_contrast_observation",
    "bootstrap_parent_indices",
    "empirical_quantile",
    "group_parent_contrasts",
    "hierarchical_contrast_sample",
    "hierarchical_percentile_intervals",
    "simultaneous_percentile_intervals",
]
