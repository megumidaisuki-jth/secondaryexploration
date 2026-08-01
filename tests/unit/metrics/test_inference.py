"""Parent-cluster bootstrap and confirmatory-hierarchy contracts."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import unittest

from secondaryexploration.metrics import (
    BeneficialDirection,
    BlockContrastObservation,
    BootstrapPlan,
    ConfirmatoryHierarchy,
    ContrastMetric,
    ContrastRegistration,
    HierarchicalContrastSample,
    InferenceError,
    InferenceStatus,
    InferenceTier,
    ParentContrastMean,
    apply_confirmatory_hierarchy,
    bootstrap_parent_indices,
    empirical_quantile,
    group_parent_contrasts,
    hierarchical_contrast_sample,
    hierarchical_percentile_intervals,
    simultaneous_percentile_intervals,
)


_FINGERPRINT = "1" * 64


def _observation(
    parent: str,
    trace: str,
    value: int | Fraction,
    *,
    treatment: str = "hypergraph",
    reference: str = "binary",
    metric: ContrastMetric = ContrastMetric.NORMALIZED_RESTRICTED_TAU_NOPATH,
    fingerprint: str = _FINGERPRINT,
    horizon: int = 100,
    analysis_cell: str = "er-n30-uniform",
) -> BlockContrastObservation:
    return BlockContrastObservation(
        parent_graph_id=parent,
        trace_id=trace,
        analysis_cell_id=analysis_cell,
        manifest_fingerprint=fingerprint,
        treatment_id=treatment,
        reference_id=reference,
        metric=metric,
        horizon=horizon,
        value=value if isinstance(value, Fraction) else Fraction(value, 1),
    )


def _sample(
    contrast_id: str = "global",
    scale: int = 1,
) -> HierarchicalContrastSample:
    observations = (
        _observation("parent-a", "trace-1", 1 * scale, fingerprint="1" * 64),
        _observation("parent-a", "trace-2", 3 * scale, fingerprint="2" * 64),
        _observation("parent-b", "trace-1", 5 * scale, fingerprint="3" * 64),
        _observation("parent-c", "trace-1", 9 * scale, fingerprint="4" * 64),
    )
    return hierarchical_contrast_sample(contrast_id, observations)


class ParentAggregationTests(unittest.TestCase):
    def test_parent_means_receive_equal_weight_despite_unequal_trace_counts(self) -> None:
        observations = (
            _observation("parent-a", "trace-1", 0, fingerprint="1" * 64),
            _observation("parent-a", "trace-2", 2, fingerprint="2" * 64),
            _observation("parent-b", "trace-1", 5, fingerprint="3" * 64),
        )

        parents = group_parent_contrasts(observations)
        sample = HierarchicalContrastSample("contrast", parents)

        self.assertEqual(tuple(parent.parent_graph_id for parent in parents), ("parent-a", "parent-b"))
        self.assertEqual(tuple(parent.mean for parent in parents), (Fraction(1), Fraction(5)))
        self.assertEqual(sample.estimate, Fraction(3))
        self.assertNotEqual(sample.estimate, Fraction(7, 3))

    def test_mixed_duplicate_and_noncanonical_records_fail_closed(self) -> None:
        valid = _sample()
        first_parent = valid.parents[0]
        invalid_calls = (
            lambda: ParentContrastMean(
                "parent-a",
                (first_parent.observations[0], first_parent.observations[0]),
            ),
            lambda: ParentContrastMean(
                "parent-a",
                tuple(reversed(first_parent.observations)),
            ),
            lambda: HierarchicalContrastSample("global", tuple(reversed(valid.parents))),
            lambda: HierarchicalContrastSample("global", (first_parent, first_parent)),
            lambda: group_parent_contrasts(
                (
                    _observation("parent-a", "trace-1", 1),
                    _observation(
                        "parent-a",
                        "trace-2",
                        2,
                        metric=ContrastMetric.FAILURE_RISK,
                    ),
                )
            ),
            lambda: group_parent_contrasts(
                (
                    _observation("parent-a", "trace-1", 1, fingerprint="8" * 64),
                    _observation(
                        "parent-a",
                        "trace-2",
                        2,
                        fingerprint="9" * 64,
                        analysis_cell="ba-n30-uniform",
                    ),
                )
            ),
            lambda: group_parent_contrasts(
                (
                    _observation("parent-a", "trace-1", 1, fingerprint="5" * 64),
                    _observation("parent-a", "trace-2", 2, fingerprint="5" * 64),
                )
            ),
            lambda: group_parent_contrasts(
                (
                    _observation("parent-a", "trace-1", 1, fingerprint="6" * 64),
                    _observation(
                        "parent-a",
                        "trace-2",
                        2,
                        fingerprint="7" * 64,
                        horizon=101,
                    ),
                )
            ),
            lambda: _observation("parent-a", "trace-1", 1, treatment="binary", reference="binary"),
        )
        for call in invalid_calls:
            with self.subTest(call=call):
                with self.assertRaises(InferenceError):
                    call()


class ClusterBootstrapTests(unittest.TestCase):
    def test_known_parent_index_vectors_and_prefix_stability(self) -> None:
        short = BootstrapPlan(
            root_seed=20260801,
            resamples=5,
            confidence_level=Fraction(9, 10),
        )
        long = replace(short, resamples=8)

        short_indices = bootstrap_parent_indices(3, short)
        long_indices = bootstrap_parent_indices(3, long)

        self.assertEqual(
            short_indices,
            (
                (2, 1, 1),
                (2, 1, 0),
                (0, 1, 1),
                (1, 1, 1),
                (0, 2, 0),
            ),
        )
        self.assertEqual(long_indices[:5], short_indices)

    def test_empirical_quantile_is_exact_left_inverse(self) -> None:
        values = (Fraction(5), Fraction(1), Fraction(3), Fraction(3))

        self.assertEqual(empirical_quantile(values, Fraction(0)), Fraction(1))
        self.assertEqual(empirical_quantile(values, Fraction(1, 4)), Fraction(1))
        self.assertEqual(empirical_quantile(values, Fraction(1, 2)), Fraction(3))
        self.assertEqual(empirical_quantile(values, Fraction(1)), Fraction(5))

    def test_simultaneous_family_shares_parent_resamples_and_bonferroni_tails(self) -> None:
        first = _sample("first", scale=1)
        second = _sample("second", scale=10)
        plan = BootstrapPlan(71, 40, Fraction(4, 5))

        result = simultaneous_percentile_intervals((first, second), plan)

        self.assertEqual(result.family_size, 2)
        self.assertEqual(result.tail_probability, Fraction(1, 20))
        self.assertEqual(
            result.intervals[1].bootstrap_values,
            tuple(value * 10 for value in result.intervals[0].bootstrap_values),
        )
        self.assertEqual(result.intervals[0].estimate, first.estimate)
        self.assertLessEqual(result.intervals[0].lower, first.estimate)
        self.assertGreaterEqual(result.intervals[0].upper, first.estimate)
        with self.assertRaisesRegex(InferenceError, "replay"):
            replace(
                result,
                parent_index_replicates=(
                    tuple(reversed(result.parent_index_replicates[0])),
                )
                + result.parent_index_replicates[1:],
            )
        with self.assertRaisesRegex(InferenceError, "replay"):
            replace(
                result,
                intervals=(
                    replace(
                        result.intervals[0],
                        estimate=result.intervals[0].estimate + 1,
                    ),
                    result.intervals[1],
                ),
            )

    def test_misaligned_parent_family_and_invalid_plan_fail_closed(self) -> None:
        first = _sample("first")
        second = HierarchicalContrastSample("second", first.parents[:-1])
        plan = BootstrapPlan(1, 10, Fraction(9, 10))

        with self.assertRaisesRegex(InferenceError, "same parent"):
            simultaneous_percentile_intervals((first, second), plan)
        missing_trace_parent = ParentContrastMean(
            first.parents[0].parent_graph_id,
            first.parents[0].observations[:1],
        )
        misaligned_blocks = HierarchicalContrastSample(
            "second",
            (missing_trace_parent,) + first.parents[1:],
        )
        with self.assertRaisesRegex(InferenceError, "manifest layout"):
            simultaneous_percentile_intervals(
                (first, misaligned_blocks),
                BootstrapPlan(1, 40, Fraction(4, 5)),
            )
        for call in (
            lambda: BootstrapPlan(-1, 10, Fraction(9, 10)),
            lambda: BootstrapPlan(1, 0, Fraction(9, 10)),
            lambda: BootstrapPlan(1, 10, Fraction(1)),
            lambda: bootstrap_parent_indices(1, plan),
            lambda: empirical_quantile((), Fraction(1, 2)),
            lambda: empirical_quantile((Fraction(1),), Fraction(2)),
            lambda: simultaneous_percentile_intervals(
                (_sample("a"), _sample("b")),
                BootstrapPlan(1, 10, Fraction(9, 10)),
            ),
        ):
            with self.subTest(call=call):
                with self.assertRaises(InferenceError):
                    call()


class ConfirmatoryHierarchyTests(unittest.TestCase):
    def _hierarchy(self) -> ConfirmatoryHierarchy:
        return ConfirmatoryHierarchy(
            registrations=(
                ContrastRegistration(
                    "global",
                    InferenceTier.GLOBAL,
                    BeneficialDirection.POSITIVE,
                ),
                ContrastRegistration(
                    "secondary-negative",
                    InferenceTier.SECONDARY,
                    BeneficialDirection.NEGATIVE,
                ),
                ContrastRegistration(
                    "exploratory",
                    InferenceTier.EXPLORATORY,
                    BeneficialDirection.POSITIVE,
                ),
            )
        )

    def test_global_success_unlocks_secondary_but_not_exploratory(self) -> None:
        samples = (
            _sample("exploratory", 1),
            _sample("global", 2),
            _sample("secondary-negative", -1),
        )
        hierarchy = self._hierarchy()
        intervals = hierarchical_percentile_intervals(
            tuple(sorted(samples, key=lambda sample: sample.contrast_id)),
            hierarchy,
            BootstrapPlan(3, 80, Fraction(4, 5)),
        )

        decisions = apply_confirmatory_hierarchy(hierarchy, intervals)
        by_id = {decision.registration.contrast_id: decision for decision in decisions}
        interval_by_id = {
            interval.contrast_id: interval for interval in intervals.intervals
        }

        self.assertTrue(by_id["global"].beneficial_effect_supported)
        self.assertEqual(by_id["global"].status, InferenceStatus.CONFIRMATORY)
        self.assertEqual(
            by_id["secondary-negative"].status,
            InferenceStatus.CONFIRMATORY,
        )
        self.assertTrue(by_id["secondary-negative"].beneficial_effect_supported)
        self.assertEqual(by_id["exploratory"].status, InferenceStatus.EXPLORATORY)
        self.assertEqual(interval_by_id["global"].tail_probability, Fraction(1, 20))
        self.assertEqual(
            interval_by_id["secondary-negative"].tail_probability,
            Fraction(1, 20),
        )
        self.assertEqual(
            interval_by_id["exploratory"].tail_probability,
            Fraction(1, 10),
        )

    def test_global_failure_keeps_secondary_descriptive(self) -> None:
        zero_global = hierarchical_contrast_sample(
            "global",
            (
                _observation("parent-a", "trace-1", -1, fingerprint="1" * 64),
                _observation("parent-a", "trace-2", 1, fingerprint="2" * 64),
                _observation("parent-b", "trace-1", 0, fingerprint="3" * 64),
                _observation("parent-c", "trace-1", 0, fingerprint="4" * 64),
            ),
        )
        samples = (
            _sample("exploratory", 1),
            zero_global,
            _sample("secondary-negative", -1),
        )
        hierarchy = self._hierarchy()
        intervals = hierarchical_percentile_intervals(
            tuple(sorted(samples, key=lambda sample: sample.contrast_id)),
            hierarchy,
            BootstrapPlan(3, 80, Fraction(4, 5)),
        )

        decisions = apply_confirmatory_hierarchy(hierarchy, intervals)
        by_id = {decision.registration.contrast_id: decision for decision in decisions}

        self.assertFalse(by_id["global"].beneficial_effect_supported)
        self.assertEqual(
            by_id["secondary-negative"].status,
            InferenceStatus.DESCRIPTIVE,
        )
        self.assertEqual(by_id["exploratory"].status, InferenceStatus.EXPLORATORY)

    def test_hierarchy_rejects_missing_duplicate_or_multiple_global_records(self) -> None:
        global_registration = ContrastRegistration(
            "global",
            InferenceTier.GLOBAL,
            BeneficialDirection.POSITIVE,
        )
        for registrations in (
            (),
            (global_registration, global_registration),
            (
                global_registration,
                ContrastRegistration(
                    "other-global",
                    InferenceTier.GLOBAL,
                    BeneficialDirection.NEGATIVE,
                ),
            ),
        ):
            with self.subTest(registrations=registrations):
                with self.assertRaises(InferenceError):
                    ConfirmatoryHierarchy(registrations)


if __name__ == "__main__":
    unittest.main()
