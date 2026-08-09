"""Equal-stratum parent bootstrap for heterogeneous graph-model strata."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import random

from secondaryexploration.randomness import SeedError, derive_seed

from .inference import (
    BeneficialDirection,
    BootstrapPlan,
    ConfirmatoryHierarchy,
    ContrastInterval,
    HierarchicalContrastSample,
    InferenceError,
    InferenceStatus,
    InferenceTier,
    RegisteredInference,
    empirical_quantile,
)


@dataclass(frozen=True, slots=True)
class StratumContrastSample:
    """One independent-parent contrast sample within a declared stratum."""

    stratum_id: str
    sample: HierarchicalContrastSample

    def __post_init__(self) -> None:
        _validate_identifier(self.stratum_id, "stratum_id")
        if not isinstance(self.sample, HierarchicalContrastSample):
            raise InferenceError("stratum sample must be a HierarchicalContrastSample")

    @property
    def parent_count(self) -> int:
        return len(self.sample.parents)


@dataclass(frozen=True, slots=True)
class StratifiedContrastSample:
    """Equal-weight model-stratum means for one registered contrast."""

    contrast_id: str
    analysis_cell_id: str
    strata: tuple[StratumContrastSample, ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.contrast_id, "contrast_id")
        _validate_identifier(self.analysis_cell_id, "analysis_cell_id")
        if type(self.strata) is not tuple or len(self.strata) < 2:
            raise InferenceError("strata must contain at least two model strata")
        if any(not isinstance(item, StratumContrastSample) for item in self.strata):
            raise InferenceError("strata must contain StratumContrastSample objects")
        stratum_ids = self.stratum_ids
        if len(set(stratum_ids)) != len(stratum_ids):
            raise InferenceError("stratum identifiers must be unique")
        if tuple(sorted(stratum_ids)) != stratum_ids:
            raise InferenceError("strata must be in canonical stratum_id order")
        if any(item.sample.contrast_id != self.contrast_id for item in self.strata):
            raise InferenceError("every stratum sample must match contrast_id")
        stratum_cells = tuple(item.sample.analysis_cell_id for item in self.strata)
        if len(set(stratum_cells)) != len(stratum_cells):
            raise InferenceError("each stratum must retain a distinct analysis cell")
        witness = _sample_witness(self.strata[0].sample)
        if any(_sample_witness(item.sample) != witness for item in self.strata[1:]):
            raise InferenceError("strata cannot mix arms, metrics, or horizons")
        fingerprints = tuple(
            observation.manifest_fingerprint
            for item in self.strata
            for parent in item.sample.parents
            for observation in parent.observations
        )
        if len(set(fingerprints)) != len(fingerprints):
            raise InferenceError("manifest fingerprints must be unique across strata")

    @property
    def stratum_ids(self) -> tuple[str, ...]:
        return tuple(item.stratum_id for item in self.strata)

    @property
    def stratum_parent_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple((item.stratum_id, item.parent_count) for item in self.strata)

    @property
    def metric(self):
        return self.strata[0].sample.metric

    @property
    def horizon(self) -> int:
        return self.strata[0].sample.horizon

    @property
    def treatment_id(self) -> str:
        return self.strata[0].sample.treatment_id

    @property
    def reference_id(self) -> str:
        return self.strata[0].sample.reference_id

    @property
    def parent_count(self) -> int:
        return sum(item.parent_count for item in self.strata)

    @property
    def estimate(self) -> Fraction:
        return sum(
            (item.sample.estimate for item in self.strata),
            start=Fraction(0, 1),
        ) / len(self.strata)


StratifiedIndexReplicate = tuple[tuple[int, ...], ...]


def bootstrap_stratified_parent_indices(
    stratum_parent_counts: tuple[tuple[str, int], ...],
    plan: BootstrapPlan,
) -> tuple[StratifiedIndexReplicate, ...]:
    """Derive independent, prefix-stable parent resamples within each stratum."""

    if type(stratum_parent_counts) is not tuple or len(stratum_parent_counts) < 2:
        raise InferenceError("stratum_parent_counts must contain at least two strata")
    if not isinstance(plan, BootstrapPlan):
        raise InferenceError("plan must be a BootstrapPlan")
    if any(type(item) is not tuple or len(item) != 2 for item in stratum_parent_counts):
        raise InferenceError("each stratum count must be a (stratum_id, parent_count) pair")
    stratum_ids = tuple(item[0] for item in stratum_parent_counts)
    if (
        len(set(stratum_ids)) != len(stratum_ids)
        or tuple(sorted(stratum_ids)) != stratum_ids
    ):
        raise InferenceError("stratum_parent_counts must be canonical and unique")
    for item in stratum_parent_counts:
        if (
            type(item[0]) is not str
            or type(item[1]) is not int
            or item[1] < 2
        ):
            raise InferenceError("each stratum must declare at least two parents")
        _validate_identifier(item[0], "stratum_id")
    replicates = []
    for replicate_index in range(plan.resamples):
        stratum_replicates = []
        for stratum_id, parent_count in stratum_parent_counts:
            try:
                seed = derive_seed(
                    plan.root_seed,
                    f"statistics.stratified_parent_bootstrap.{stratum_id}",
                    replicate_index,
                )
            except SeedError as exc:
                raise InferenceError("could not derive a stratified bootstrap seed") from exc
            rng = random.Random(seed)
            stratum_replicates.append(
                tuple(_randbelow(rng, parent_count) for _ in range(parent_count))
            )
        replicates.append(tuple(stratum_replicates))
    return tuple(replicates)


@dataclass(frozen=True, slots=True)
class StratifiedSimultaneousIntervalFamily:
    """Aligned intervals from shared, within-stratum parent resamples."""

    plan: BootstrapPlan
    samples: tuple[StratifiedContrastSample, ...]
    stratum_index_replicates: tuple[StratifiedIndexReplicate, ...]
    adjusted_contrast_ids: tuple[str, ...]
    intervals: tuple[ContrastInterval, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.plan, BootstrapPlan):
            raise InferenceError("plan must be a BootstrapPlan")
        _validate_aligned_stratified_samples(self.samples)
        sample_ids = tuple(sample.contrast_id for sample in self.samples)
        if (
            type(self.adjusted_contrast_ids) is not tuple
            or not self.adjusted_contrast_ids
            or len(set(self.adjusted_contrast_ids)) != len(self.adjusted_contrast_ids)
            or tuple(sorted(self.adjusted_contrast_ids)) != self.adjusted_contrast_ids
            or not set(self.adjusted_contrast_ids).issubset(sample_ids)
        ):
            raise InferenceError("adjusted contrast IDs must be canonical sample IDs")
        expected_indices = bootstrap_stratified_parent_indices(
            self.samples[0].stratum_parent_counts,
            self.plan,
        )
        if self.stratum_index_replicates != expected_indices:
            raise InferenceError("stratified index replicates do not replay from plan")
        expected_intervals = _stratified_intervals(
            self.samples,
            self.plan,
            self.stratum_index_replicates,
            self.adjusted_contrast_ids,
        )
        if self.intervals != expected_intervals:
            raise InferenceError("stratified intervals do not replay from sources")

    @property
    def family_size(self) -> int:
        return len(self.adjusted_contrast_ids)


def stratified_simultaneous_percentile_intervals(
    samples: tuple[StratifiedContrastSample, ...],
    plan: BootstrapPlan,
) -> StratifiedSimultaneousIntervalFamily:
    """Apply simultaneous adjustment to every supplied stratified contrast."""

    _validate_aligned_stratified_samples(samples)
    return _build_stratified_family(
        samples,
        plan,
        tuple(sample.contrast_id for sample in samples),
    )


def stratified_hierarchical_percentile_intervals(
    samples: tuple[StratifiedContrastSample, ...],
    hierarchy: ConfirmatoryHierarchy,
    plan: BootstrapPlan,
) -> StratifiedSimultaneousIntervalFamily:
    """Apply global/secondary adjustment to stratified parent samples."""

    _validate_aligned_stratified_samples(samples)
    if not isinstance(hierarchy, ConfirmatoryHierarchy):
        raise InferenceError("hierarchy must be a ConfirmatoryHierarchy")
    sample_ids = {sample.contrast_id for sample in samples}
    registration_ids = {
        registration.contrast_id for registration in hierarchy.registrations
    }
    if sample_ids != registration_ids:
        raise InferenceError("hierarchy and stratified samples must contain the same IDs")
    adjusted_ids = tuple(
        sorted(
            registration.contrast_id
            for registration in hierarchy.registrations
            if registration.tier is not InferenceTier.EXPLORATORY
        )
    )
    return _build_stratified_family(samples, plan, adjusted_ids)


def _build_stratified_family(
    samples: tuple[StratifiedContrastSample, ...],
    plan: BootstrapPlan,
    adjusted_ids: tuple[str, ...],
) -> StratifiedSimultaneousIntervalFamily:
    if not isinstance(plan, BootstrapPlan):
        raise InferenceError("plan must be a BootstrapPlan")
    adjusted_tail = (Fraction(1, 1) - plan.confidence_level) / (
        2 * len(adjusted_ids)
    )
    if plan.resamples * adjusted_tail < 1:
        raise InferenceError("resamples are too few to resolve adjusted empirical tail")
    indices = bootstrap_stratified_parent_indices(
        samples[0].stratum_parent_counts,
        plan,
    )
    intervals = _stratified_intervals(samples, plan, indices, adjusted_ids)
    return StratifiedSimultaneousIntervalFamily(
        plan,
        samples,
        indices,
        adjusted_ids,
        intervals,
    )


def _stratified_intervals(
    samples: tuple[StratifiedContrastSample, ...],
    plan: BootstrapPlan,
    index_replicates: tuple[StratifiedIndexReplicate, ...],
    adjusted_ids: tuple[str, ...],
) -> tuple[ContrastInterval, ...]:
    adjusted_tail = (Fraction(1, 1) - plan.confidence_level) / (
        2 * len(adjusted_ids)
    )
    nominal_tail = (Fraction(1, 1) - plan.confidence_level) / 2
    intervals = []
    adjusted_set = set(adjusted_ids)
    for sample in samples:
        tail = adjusted_tail if sample.contrast_id in adjusted_set else nominal_tail
        bootstrap_values = []
        for replicate in index_replicates:
            stratum_means = []
            for stratum, indices in zip(sample.strata, replicate, strict=True):
                parent_values = tuple(parent.mean for parent in stratum.sample.parents)
                stratum_means.append(
                    sum(
                        (parent_values[index] for index in indices),
                        start=Fraction(0, 1),
                    )
                    / len(indices)
                )
            bootstrap_values.append(
                sum(stratum_means, start=Fraction(0, 1)) / len(stratum_means)
            )
        bootstrap_tuple = tuple(bootstrap_values)
        intervals.append(
            ContrastInterval(
                contrast_id=sample.contrast_id,
                estimate=sample.estimate,
                lower=empirical_quantile(bootstrap_tuple, tail),
                upper=empirical_quantile(bootstrap_tuple, Fraction(1, 1) - tail),
                bootstrap_values=bootstrap_tuple,
                confidence_level=plan.confidence_level,
                tail_probability=tail,
                parent_count=sample.parent_count,
            )
        )
    return tuple(intervals)


def apply_stratified_confirmatory_hierarchy(
    hierarchy: ConfirmatoryHierarchy,
    family: StratifiedSimultaneousIntervalFamily,
) -> tuple[RegisteredInference, ...]:
    """Apply the existing global gate to a stratified interval family."""

    if not isinstance(hierarchy, ConfirmatoryHierarchy):
        raise InferenceError("hierarchy must be a ConfirmatoryHierarchy")
    if not isinstance(family, StratifiedSimultaneousIntervalFamily):
        raise InferenceError("family must be a StratifiedSimultaneousIntervalFamily")
    interval_by_id = {item.contrast_id: item for item in family.intervals}
    registrations = {item.contrast_id: item for item in hierarchy.registrations}
    if set(interval_by_id) != set(registrations):
        raise InferenceError("hierarchy and interval family must contain the same IDs")
    expected_adjusted = tuple(
        sorted(
            item.contrast_id
            for item in hierarchy.registrations
            if item.tier is not InferenceTier.EXPLORATORY
        )
    )
    if family.adjusted_contrast_ids != expected_adjusted:
        raise InferenceError("stratified adjusted family differs from hierarchy")
    global_registration = next(
        item for item in hierarchy.registrations if item.tier is InferenceTier.GLOBAL
    )
    global_supported = _beneficial(
        global_registration.beneficial_direction,
        interval_by_id[global_registration.contrast_id],
    )
    results = []
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
        results.append(
            RegisteredInference(
                registration,
                interval,
                status,
                _beneficial(registration.beneficial_direction, interval),
            )
        )
    return tuple(results)


def _validate_aligned_stratified_samples(samples: object) -> None:
    if type(samples) is not tuple or not samples:
        raise InferenceError("samples must be a nonempty canonical tuple")
    if any(not isinstance(item, StratifiedContrastSample) for item in samples):
        raise InferenceError("samples must contain StratifiedContrastSample objects")
    contrast_ids = tuple(item.contrast_id for item in samples)
    if len(set(contrast_ids)) != len(contrast_ids) or tuple(sorted(contrast_ids)) != contrast_ids:
        raise InferenceError("stratified contrast IDs must be canonical and unique")
    first = samples[0]
    if any(
        item.analysis_cell_id != first.analysis_cell_id
        or item.horizon != first.horizon
        or item.stratum_parent_counts != first.stratum_parent_counts
        for item in samples[1:]
    ):
        raise InferenceError("simultaneous stratified samples have incompatible layouts")
    for stratum_index in range(len(first.strata)):
        reference = first.strata[stratum_index].sample
        reference_layout = _block_layout(reference)
        if any(
            item.strata[stratum_index].stratum_id
            != first.strata[stratum_index].stratum_id
            or item.strata[stratum_index].sample.analysis_cell_id
            != reference.analysis_cell_id
            or item.strata[stratum_index].sample.parent_ids != reference.parent_ids
            or _block_layout(item.strata[stratum_index].sample) != reference_layout
            for item in samples[1:]
        ):
            raise InferenceError("corresponding strata must share parent-trace layout")


def _block_layout(sample: HierarchicalContrastSample):
    return tuple(
        (
            parent.parent_graph_id,
            tuple(
                (item.trace_id, item.manifest_fingerprint)
                for item in parent.observations
            ),
        )
        for parent in sample.parents
    )


def _sample_witness(sample: HierarchicalContrastSample):
    return (
        sample.treatment_id,
        sample.reference_id,
        sample.metric,
        sample.horizon,
    )


def _beneficial(direction: BeneficialDirection, interval: ContrastInterval) -> bool:
    if direction is BeneficialDirection.POSITIVE:
        return interval.lower > 0
    return interval.upper < 0


def _randbelow(rng: random.Random, stop: int) -> int:
    bit_count = stop.bit_length()
    while True:
        candidate = rng.getrandbits(bit_count)
        if candidate < stop:
            return candidate


def _validate_identifier(value: object, field: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise InferenceError(f"{field} must be a nonempty canonical string")


__all__ = [
    "StratifiedContrastSample",
    "StratifiedSimultaneousIntervalFamily",
    "StratumContrastSample",
    "apply_stratified_confirmatory_hierarchy",
    "bootstrap_stratified_parent_indices",
    "stratified_hierarchical_percentile_intervals",
    "stratified_simultaneous_percentile_intervals",
]
