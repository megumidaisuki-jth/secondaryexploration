"""Within-block service-summary and contrast contracts."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import unittest

from secondaryexploration.experiments import (
    PairedRunManifest,
    TopologyVariant,
    run_paired_experiment,
)
from secondaryexploration.metrics import (
    MetricError,
    service_summary,
    within_block_contrast,
)
from secondaryexploration.topology import (
    common_core_sunflower,
    equal_node_capital_state,
    uniform_overlap_chain,
)
from secondaryexploration.traffic import (
    AmountDistribution,
    generate_request_trace,
    uniform_kernel,
)


def _result(block_id: str = "block-1"):
    chain = uniform_overlap_chain(3, 1, 3)
    sunflower = common_core_sunflower(3, 1, 3)
    trace = generate_request_trace(
        uniform_kernel(chain.nodes),
        AmountDistribution.from_weights(((1, 1), (2, 1))),
        20,
        root_seed=91,
    )
    manifest = PairedRunManifest(
        block_id=block_id,
        trace=trace,
        routing_root_seed=92,
        variants=(
            TopologyVariant("chain", "chain", chain, equal_node_capital_state(chain, 12)),
            TopologyVariant("sunflower", "sunflower", sunflower, equal_node_capital_state(sunflower, 12)),
        ),
    )
    return run_paired_experiment(manifest)


class PairedServiceMetricTests(unittest.TestCase):
    def test_summary_uses_restricted_event_time_and_exact_value(self) -> None:
        result = _result()
        summary = service_summary(result, "chain")
        simulation = result.variant_results[0].simulation

        self.assertEqual(summary.block_id, result.manifest.block_id)
        self.assertEqual(summary.manifest_fingerprint, result.manifest.fingerprint)
        self.assertEqual(summary.horizon, 20)
        self.assertEqual(summary.restricted_tau_nopath, simulation.tau_nopath.request_index)
        self.assertEqual(
            summary.normalized_restricted_tau_nopath,
            Fraction(simulation.tau_nopath.request_index, 20),
        )
        self.assertEqual(summary.failed_by_horizon, simulation.tau_nopath.observed)
        self.assertEqual(summary.success_rate, simulation.success_rate)
        self.assertEqual(
            summary.accepted_value,
            sum(
                outcome.request.amount
                for outcome in simulation.outcomes
                if outcome.accepted
            ),
        )

    def test_contrast_sign_is_treatment_minus_reference(self) -> None:
        result = _result()
        treatment = service_summary(result, "sunflower")
        reference = service_summary(result, "chain")

        contrast = within_block_contrast(treatment, reference)

        self.assertEqual(contrast.treatment_id, "sunflower")
        self.assertEqual(contrast.reference_id, "chain")
        self.assertEqual(
            contrast.restricted_tau_nopath_difference,
            treatment.restricted_tau_nopath - reference.restricted_tau_nopath,
        )
        self.assertEqual(
            contrast.failure_indicator_difference,
            int(treatment.failed_by_horizon) - int(reference.failed_by_horizon),
        )
        self.assertEqual(
            contrast.normalized_restricted_tau_nopath_difference,
            Fraction(contrast.restricted_tau_nopath_difference, 20),
        )
        self.assertEqual(
            contrast.success_rate_difference,
            treatment.success_rate - reference.success_rate,
        )
        self.assertEqual(
            contrast.accepted_value_difference,
            treatment.accepted_value - reference.accepted_value,
        )

    def test_cross_manifest_and_unknown_variant_fail_closed(self) -> None:
        first = _result("first")
        second = _result("second")
        with self.assertRaisesRegex(MetricError, "same manifest"):
            within_block_contrast(
                service_summary(first, "chain"),
                service_summary(second, "sunflower"),
            )
        with self.assertRaisesRegex(MetricError, "unknown variant"):
            service_summary(first, "missing")
        with self.assertRaises(MetricError):
            within_block_contrast(
                service_summary(first, "chain"),
                service_summary(first, "chain"),
            )

    def test_empty_trace_has_explicit_undefined_success_rate(self) -> None:
        result = _result()
        empty_trace = generate_request_trace(
            result.manifest.trace.kernel,
            result.manifest.trace.amount_distribution,
            0,
            root_seed=13,
        )
        empty = run_paired_experiment(replace(result.manifest, trace=empty_trace))

        summary = service_summary(empty, "chain")
        contrast = within_block_contrast(
            service_summary(empty, "sunflower"),
            summary,
        )

        self.assertEqual(summary.horizon, 0)
        self.assertIsNone(summary.normalized_restricted_tau_nopath)
        self.assertIsNone(summary.success_rate)
        self.assertEqual(summary.accepted_value, 0)
        self.assertIsNone(contrast.normalized_restricted_tau_nopath_difference)
        self.assertIsNone(contrast.success_rate_difference)


if __name__ == "__main__":
    unittest.main()
