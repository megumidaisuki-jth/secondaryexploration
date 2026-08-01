"""Exact within-block service summaries and paired contrasts."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from secondaryexploration.experiments import PairedRunResult

from .errors import MetricError


@dataclass(frozen=True, slots=True)
class VariantServiceSummary:
    """One manifest-attested variant's service outcomes."""

    paired_result: PairedRunResult
    variant_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.paired_result, PairedRunResult):
            raise MetricError("paired_result must be a PairedRunResult")
        if not isinstance(self.variant_id, str):
            raise MetricError("variant_id must be a string")
        if self.variant_id not in self.variant_ids:
            raise MetricError(f"unknown variant {self.variant_id!r}")

    @property
    def variant_ids(self) -> tuple[str, ...]:
        return tuple(item.variant_id for item in self.paired_result.variant_results)

    @property
    def simulation(self):
        return next(
            item.simulation
            for item in self.paired_result.variant_results
            if item.variant_id == self.variant_id
        )

    @property
    def block_id(self) -> str:
        return self.paired_result.manifest.block_id

    @property
    def manifest_fingerprint(self) -> str:
        return self.paired_result.manifest_fingerprint

    @property
    def horizon(self) -> int:
        return self.paired_result.horizon

    @property
    def restricted_tau_nopath(self) -> int:
        return self.simulation.tau_nopath.request_index

    @property
    def failed_by_horizon(self) -> bool:
        return self.simulation.tau_nopath.observed

    @property
    def normalized_restricted_tau_nopath(self) -> Fraction | None:
        if self.horizon == 0:
            return None
        return Fraction(self.restricted_tau_nopath, self.horizon)

    @property
    def success_rate(self) -> Fraction | None:
        return self.simulation.success_rate

    @property
    def accepted_value(self) -> int:
        return sum(
            outcome.request.amount
            for outcome in self.simulation.outcomes
            if outcome.accepted
        )


@dataclass(frozen=True, slots=True)
class WithinBlockContrast:
    """Treatment-minus-reference contrast within one exact pairing block."""

    treatment: VariantServiceSummary
    reference: VariantServiceSummary

    def __post_init__(self) -> None:
        if not isinstance(self.treatment, VariantServiceSummary) or not isinstance(
            self.reference, VariantServiceSummary
        ):
            raise MetricError("contrast inputs must be VariantServiceSummary objects")
        if self.treatment.manifest_fingerprint != self.reference.manifest_fingerprint:
            raise MetricError("paired summaries must come from the same manifest")
        if self.treatment.horizon != self.reference.horizon:
            raise MetricError("paired summaries must use the same horizon")
        if self.treatment.variant_id == self.reference.variant_id:
            raise MetricError("treatment and reference variants must differ")

    @property
    def block_id(self) -> str:
        return self.treatment.block_id

    @property
    def manifest_fingerprint(self) -> str:
        return self.treatment.manifest_fingerprint

    @property
    def treatment_id(self) -> str:
        return self.treatment.variant_id

    @property
    def reference_id(self) -> str:
        return self.reference.variant_id

    @property
    def restricted_tau_nopath_difference(self) -> int:
        return (
            self.treatment.restricted_tau_nopath
            - self.reference.restricted_tau_nopath
        )

    @property
    def failure_indicator_difference(self) -> int:
        return int(self.treatment.failed_by_horizon) - int(
            self.reference.failed_by_horizon
        )

    @property
    def normalized_restricted_tau_nopath_difference(self) -> Fraction | None:
        if (
            self.treatment.normalized_restricted_tau_nopath is None
            or self.reference.normalized_restricted_tau_nopath is None
        ):
            return None
        return (
            self.treatment.normalized_restricted_tau_nopath
            - self.reference.normalized_restricted_tau_nopath
        )

    @property
    def success_rate_difference(self) -> Fraction | None:
        if self.treatment.success_rate is None or self.reference.success_rate is None:
            return None
        return self.treatment.success_rate - self.reference.success_rate

    @property
    def accepted_value_difference(self) -> int:
        return self.treatment.accepted_value - self.reference.accepted_value


def service_summary(
    paired_result: PairedRunResult,
    variant_id: str,
) -> VariantServiceSummary:
    return VariantServiceSummary(paired_result, variant_id)


def within_block_contrast(
    treatment: VariantServiceSummary,
    reference: VariantServiceSummary,
) -> WithinBlockContrast:
    return WithinBlockContrast(treatment, reference)


__all__ = [
    "VariantServiceSummary",
    "WithinBlockContrast",
    "service_summary",
    "within_block_contrast",
]
