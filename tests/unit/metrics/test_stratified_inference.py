"""Tests for equal-model-stratum parent bootstrap inference."""

from __future__ import annotations

from fractions import Fraction
import hashlib
import random
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
    StratifiedContrastSample,
    StratumContrastSample,
    apply_stratified_confirmatory_hierarchy,
    bootstrap_stratified_parent_indices,
    stratified_hierarchical_percentile_intervals,
    stratified_simultaneous_percentile_intervals,
)
from secondaryexploration.randomness import derive_seed


def _fingerprint(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _stratum(
    contrast_id: str,
    stratum_id: str,
    values: tuple[int, ...],
    *,
    treatment_id: str = "hypergraph",
    parent_prefix: str | None = None,
    analysis_cell_prefix: str = "size-60",
) -> StratumContrastSample:
    prefix = stratum_id if parent_prefix is None else parent_prefix
    parents = []
    for index, value in enumerate(values):
        parent_id = f"{prefix}-p{index}"
        observation = BlockContrastObservation(
            parent_graph_id=parent_id,
            trace_id="trace-0",
            analysis_cell_id=f"{analysis_cell_prefix}-{stratum_id}",
            manifest_fingerprint=_fingerprint(f"{stratum_id}-{index}-trace-0"),
            treatment_id=treatment_id,
            reference_id="binary",
            metric=ContrastMetric.NORMALIZED_RESTRICTED_TAU_NOPATH,
            horizon=720,
            value=Fraction(value, 1),
        )
        parents.append(ParentContrastMean(parent_id, (observation,)))
    return StratumContrastSample(
        stratum_id,
        HierarchicalContrastSample(contrast_id, tuple(parents)),
    )


def _sample(
    contrast_id: str,
    first: tuple[int, ...],
    second: tuple[int, ...],
    *,
    treatment_id: str = "hypergraph",
    second_prefix: str | None = None,
    second_analysis_cell_prefix: str = "size-60",
) -> StratifiedContrastSample:
    return StratifiedContrastSample(
        contrast_id,
        "size-60-global",
        (
            _stratum(
                contrast_id,
                "barabasi-albert",
                first,
                treatment_id=treatment_id,
            ),
            _stratum(
                contrast_id,
                "er-gnm",
                second,
                treatment_id=treatment_id,
                parent_prefix=second_prefix,
                analysis_cell_prefix=second_analysis_cell_prefix,
            ),
        ),
    )


def _oracle_randbelow(rng: random.Random, stop: int) -> int:
    bits = stop.bit_length()
    while True:
        value = rng.getrandbits(bits)
        if value < stop:
            return value


class StratifiedParentBootstrapTests(unittest.TestCase):
    def test_estimate_weights_strata_equally_not_parents(self) -> None:
        sample = _sample("global", (0, 2), (10, 12, 14, 16))

        pooled_parent_mean = Fraction(sum((0, 2, 10, 12, 14, 16)), 6)

        self.assertEqual(sample.estimate, Fraction(7, 1))
        self.assertEqual(pooled_parent_mean, Fraction(9, 1))
        self.assertEqual(sample.stratum_parent_counts, (("barabasi-albert", 2), ("er-gnm", 4)))

    def test_index_vectors_are_independent_by_stratum_and_prefix_stable(self) -> None:
        short = BootstrapPlan(20260809, 5, Fraction(9, 10))
        long = BootstrapPlan(20260809, 10, Fraction(9, 10))
        counts = (("barabasi-albert", 2), ("er-gnm", 4))

        observed = bootstrap_stratified_parent_indices(counts, short)

        expected_first = []
        for stratum_id, count in counts:
            seed = derive_seed(
                short.root_seed,
                f"statistics.stratified_parent_bootstrap.{stratum_id}",
                0,
            )
            rng = random.Random(seed)
            expected_first.append(
                tuple(_oracle_randbelow(rng, count) for _ in range(count))
            )
        self.assertEqual(observed[0], tuple(expected_first))
        self.assertEqual(
            bootstrap_stratified_parent_indices(counts, long)[:5],
            observed,
        )
        with self.assertRaisesRegex(InferenceError, "pair"):
            bootstrap_stratified_parent_indices(("bad", ("er-gnm", 2)), short)

        equal_counts = (("barabasi-albert", 2), ("er-gnm", 2))
        equal_count_replicates = bootstrap_stratified_parent_indices(
            equal_counts,
            short,
        )
        self.assertNotEqual(
            tuple(item[0] for item in equal_count_replicates),
            tuple(item[1] for item in equal_count_replicates),
        )

    def test_simultaneous_family_uses_shared_within_stratum_resamples(self) -> None:
        first = _sample("a-global", (1, 2), (3, 4, 5, 6), treatment_id="hypergraph-a")
        second = _sample("b-secondary", (10, 20), (30, 40, 50, 60), treatment_id="hypergraph-b")
        plan = BootstrapPlan(1234, 200, Fraction(9, 10))

        family = stratified_simultaneous_percentile_intervals(
            (first, second),
            plan,
        )

        self.assertEqual(family.samples, (first, second))
        self.assertEqual(family.intervals[0].estimate, first.estimate)
        self.assertEqual(family.intervals[1].estimate, second.estimate)
        self.assertEqual(
            family.intervals[1].bootstrap_values,
            tuple(value * 10 for value in family.intervals[0].bootstrap_values),
        )

    def test_hierarchy_gate_and_misaligned_strata_fail_closed(self) -> None:
        global_sample = _sample("global", (1, 2), (3, 4), treatment_id="global-h")
        secondary_sample = _sample(
            "secondary",
            (2, 4),
            (6, 8),
            treatment_id="secondary-h",
        )
        hierarchy = ConfirmatoryHierarchy(
            (
                ContrastRegistration(
                    "global",
                    InferenceTier.GLOBAL,
                    BeneficialDirection.POSITIVE,
                ),
                ContrastRegistration(
                    "secondary",
                    InferenceTier.SECONDARY,
                    BeneficialDirection.POSITIVE,
                ),
            )
        )
        family = stratified_hierarchical_percentile_intervals(
            (global_sample, secondary_sample),
            hierarchy,
            BootstrapPlan(99, 400, Fraction(19, 20)),
        )

        decisions = apply_stratified_confirmatory_hierarchy(hierarchy, family)

        self.assertTrue(decisions[0].beneficial_effect_supported)
        self.assertEqual(decisions[1].status, InferenceStatus.CONFIRMATORY)
        misaligned = _sample(
            "secondary",
            (2, 4),
            (6, 8),
            treatment_id="secondary-h",
            second_prefix="different",
        )
        with self.assertRaisesRegex(InferenceError, "parent-trace layout"):
            stratified_hierarchical_percentile_intervals(
                (global_sample, misaligned),
                hierarchy,
                BootstrapPlan(99, 400, Fraction(19, 20)),
            )
        wrong_cell = _sample(
            "secondary",
            (2, 4),
            (6, 8),
            treatment_id="secondary-h",
            second_analysis_cell_prefix="size-120",
        )
        with self.assertRaisesRegex(InferenceError, "parent-trace layout"):
            stratified_hierarchical_percentile_intervals(
                (global_sample, wrong_cell),
                hierarchy,
                BootstrapPlan(99, 400, Fraction(19, 20)),
            )

    def test_negative_direction_gate_closed_and_tail_levels_are_explicit(self) -> None:
        global_sample = _sample(
            "a-global",
            (-2, 2),
            (-2, 2),
            treatment_id="global-negative",
        )
        secondary_sample = _sample(
            "b-secondary",
            (-4, -4),
            (-4, -4),
            treatment_id="secondary-negative",
        )
        exploratory_sample = _sample(
            "c-exploratory",
            (-2, -2),
            (-2, -2),
            treatment_id="exploratory-negative",
        )
        hierarchy = ConfirmatoryHierarchy(
            (
                ContrastRegistration(
                    "a-global",
                    InferenceTier.GLOBAL,
                    BeneficialDirection.NEGATIVE,
                ),
                ContrastRegistration(
                    "b-secondary",
                    InferenceTier.SECONDARY,
                    BeneficialDirection.NEGATIVE,
                ),
                ContrastRegistration(
                    "c-exploratory",
                    InferenceTier.EXPLORATORY,
                    BeneficialDirection.NEGATIVE,
                ),
            )
        )
        family = stratified_hierarchical_percentile_intervals(
            (global_sample, secondary_sample, exploratory_sample),
            hierarchy,
            BootstrapPlan(101, 400, Fraction(19, 20)),
        )

        self.assertEqual(family.family_size, 2)
        self.assertEqual(family.intervals[0].tail_probability, Fraction(1, 80))
        self.assertEqual(family.intervals[1].tail_probability, Fraction(1, 80))
        self.assertEqual(family.intervals[2].tail_probability, Fraction(1, 40))
        decisions = apply_stratified_confirmatory_hierarchy(hierarchy, family)
        self.assertFalse(decisions[0].beneficial_effect_supported)
        self.assertEqual(decisions[1].status, InferenceStatus.DESCRIPTIVE)
        self.assertTrue(decisions[1].beneficial_effect_supported)
        self.assertEqual(decisions[2].status, InferenceStatus.EXPLORATORY)
        self.assertTrue(decisions[2].beneficial_effect_supported)

    def test_too_few_resamples_for_adjusted_tail_fail_closed(self) -> None:
        first = _sample("a-global", (1, 2), (3, 4), treatment_id="hypergraph-a")
        second = _sample("b-secondary", (2, 4), (6, 8), treatment_id="hypergraph-b")

        with self.assertRaisesRegex(InferenceError, "too few"):
            stratified_simultaneous_percentile_intervals(
                (first, second),
                BootstrapPlan(7, 20, Fraction(19, 20)),
            )


if __name__ == "__main__":
    unittest.main()
