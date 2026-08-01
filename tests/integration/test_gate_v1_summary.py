"""Integrity checks for the tracked Gate-V1 evidence summary."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from secondaryexploration.experiments.prior_paper import (
    PUBLISHED_TOPOLOGY_SHA256,
    PUBLISHED_TRACE_SHA256,
    UPSTREAM_COMMIT,
)


SUMMARY_PATH = (
    Path(__file__).resolve().parents[2]
    / "results"
    / "gate-v1-prior-paper"
    / "summary.json"
)


class GateV1SummaryTests(unittest.TestCase):
    def test_tracked_summary_has_consistent_sources_arithmetic_and_directions(self) -> None:
        payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["source"]["upstream_commit"], UPSTREAM_COMMIT)
        self.assertEqual(
            payload["source"]["topology_zip_sha256"],
            PUBLISHED_TOPOLOGY_SHA256,
        )
        self.assertEqual(
            payload["source"]["trace_csv_sha256"],
            PUBLISHED_TRACE_SHA256,
        )
        anchor = payload["input_anchor"]
        semantics = payload["source_semantics"]
        self.assertEqual(semantics["exact_unit_scale_per_sat"], 2)
        self.assertEqual(
            semantics["raw_amount_sat"] * semantics["exact_unit_scale_per_sat"],
            semantics["replay_request_amount_exact_units"],
        )
        self.assertEqual(
            2 * anchor["binary_incidence_count"] * 3,
            anchor["reconstructed_construction_cost"],
        )
        self.assertEqual(
            anchor["reconstructed_construction_cost"],
            anchor["paper_construction_cost"],
        )

        rows = {
            row["topology"]: row
            for row in payload["full_trace_reproduction"]
        }
        self.assertEqual(
            len({row["request_trace_sha256"] for row in rows.values()}),
            1,
        )
        for row in rows.values():
            for field in (
                "topology_sha256",
                "initial_state_sha256",
                "request_trace_sha256",
                "final_balance_sha256",
            ):
                self.assertRegex(row[field], r"^[0-9a-f]{64}$")
            self.assertEqual(
                row["accepted"]
                + row["no_path"]
                + row["unavailable_endpoint"],
                10_000,
            )
            self.assertAlmostEqual(
                row["success_rate"],
                row["accepted"] / 10_000,
            )
            self.assertAlmostEqual(
                row["average_successful_hops"],
                row["successful_hop_sum"] / row["accepted"],
            )
            self.assertAlmostEqual(
                row["absolute_hop_difference"],
                abs(
                    row["average_successful_hops"]
                    - row["paper_reported_average_hops"]
                ),
            )
            self.assertLessEqual(
                row["absolute_hop_difference"],
                payload["directional_checks"]["descriptive_absolute_hop_tolerance"],
            )
        self.assertGreaterEqual(
            rows["NCH-published-order"]["success_rate"],
            rows["LN"]["success_rate"],
        )
        self.assertGreaterEqual(
            rows["FHS-5"]["success_rate"],
            rows["LN"]["success_rate"],
        )
        self.assertGreaterEqual(
            rows["FHS-50"]["success_rate"],
            rows["LN"]["success_rate"],
        )
        self.assertLess(
            rows["NCH-published-order"]["average_successful_hops"],
            rows["LN"]["average_successful_hops"],
        )
        self.assertLess(
            rows["FHS-50"]["average_successful_hops"],
            rows["FHS-5"]["average_successful_hops"],
        )


if __name__ == "__main__":
    unittest.main()
