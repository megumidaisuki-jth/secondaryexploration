"""Exact discrete-time survival estimator contracts."""

from __future__ import annotations

from fractions import Fraction
import unittest

from secondaryexploration.metrics import (
    KaplanMeierEstimate,
    SurvivalError,
    kaplan_meier,
)
from secondaryexploration.simulation import EventObservation


class KaplanMeierTests(unittest.TestCase):
    def test_hand_calculated_events_and_censoring_at_same_time(self) -> None:
        estimate = kaplan_meier(
            (
                EventObservation.censored_at(4),
                EventObservation.observed_at(3),
                EventObservation.censored_at(3),
                EventObservation.observed_at(1),
            )
        )

        self.assertEqual(
            tuple(
                (point.time, point.at_risk, point.events, point.censored, point.survival)
                for point in estimate.points
            ),
            (
                (1, 4, 1, 0, Fraction(3, 4)),
                (3, 3, 1, 1, Fraction(1, 2)),
                (4, 1, 0, 1, Fraction(1, 2)),
            ),
        )
        self.assertEqual(estimate.survival_at(0), Fraction(1, 1))
        self.assertEqual(estimate.survival_at(2), Fraction(3, 4))
        self.assertEqual(estimate.failure_risk_at(3), Fraction(1, 2))
        self.assertEqual(estimate.restricted_mean(4), Fraction(3, 1))
        self.assertEqual(estimate.quantile(Fraction(1, 4)), 1)
        self.assertEqual(estimate.quantile(Fraction(1, 2)), 3)
        self.assertIsNone(estimate.quantile(Fraction(3, 4)))

    def test_time_zero_event_contributes_zero_restricted_time(self) -> None:
        estimate = kaplan_meier(
            (
                EventObservation.observed_at(0),
                EventObservation.censored_at(2),
            )
        )

        self.assertEqual(estimate.survival_at(0), Fraction(1, 2))
        self.assertEqual(estimate.restricted_mean(0), Fraction(0, 1))
        self.assertEqual(estimate.restricted_mean(2), Fraction(1, 1))
        self.assertEqual(estimate.quantile(Fraction(1, 2)), 0)

    def test_all_censored_quantile_is_not_imputed_as_horizon(self) -> None:
        estimate = kaplan_meier(
            tuple(EventObservation.censored_at(5) for _ in range(3))
        )

        self.assertEqual(estimate.restricted_mean(5), Fraction(5, 1))
        self.assertEqual(estimate.failure_risk_at(5), Fraction(0, 1))
        self.assertIsNone(estimate.quantile(Fraction(1, 4)))

    def test_zero_survival_tail_is_identified_beyond_last_event(self) -> None:
        estimate = kaplan_meier(
            (
                EventObservation.observed_at(1),
                EventObservation.observed_at(1),
            )
        )

        self.assertEqual(estimate.survival_at(100), Fraction(0, 1))
        self.assertEqual(estimate.restricted_mean(100), Fraction(1, 1))

    def test_public_estimate_rejects_tampered_points(self) -> None:
        valid = kaplan_meier(
            (
                EventObservation.observed_at(1),
                EventObservation.censored_at(2),
            )
        )

        with self.assertRaisesRegex(SurvivalError, "points"):
            KaplanMeierEstimate(valid.observations, valid.points[:-1])

    def test_invalid_samples_times_and_probabilities_fail_closed(self) -> None:
        with self.assertRaises(SurvivalError):
            kaplan_meier(())
        with self.assertRaises(SurvivalError):
            kaplan_meier("not observations")  # type: ignore[arg-type]
        estimate = kaplan_meier((EventObservation.censored_at(3),))
        for call in (
            lambda: estimate.survival_at(-1),
            lambda: estimate.survival_at(True),
            lambda: estimate.restricted_mean(4),
            lambda: estimate.quantile(Fraction(0, 1)),
            lambda: estimate.quantile(Fraction(2, 1)),
            lambda: estimate.quantile(0.5),  # type: ignore[arg-type]
        ):
            with self.subTest(call=call):
                with self.assertRaises(SurvivalError):
                    call()


if __name__ == "__main__":
    unittest.main()
