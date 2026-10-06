import copy
from fractions import Fraction
import json
import unittest

from tools import supplement_da_fhs5 as s


class SupplementTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(s.DEFAULT_CONFIG.read_bytes())
        self.row = dict(node_count=30, parent_model="er_gnm", parent_replicate=0,
                        parent_graph_id="p", regime_id="r", scope="same_distribution",
                        horizon=360, paired_manifest_fingerprint="paired", binary_arm_count=2,
                        binary_arm_events=[["lo", False], ["hi", True]], value=[1, 2])

    def test_shared_bracket_cancels_exactly(self):
        a, b = copy.deepcopy(self.row), copy.deepcopy(self.row)
        b["value"] = [-1, 2]
        self.assertEqual(s.pair_delta(a, b, "failure_risk"), 1)
        a["value"], b["value"] = [101, 720], [99, 720]
        self.assertEqual(s.pair_delta(a, b, "normalized_restricted_tau_nopath"), 1)

    def test_reject_different_reference(self):
        b = copy.deepcopy(self.row)
        b["binary_arm_events"][0][0] = "other"
        with self.assertRaises(ValueError):
            s.pair_delta(self.row, b, "failure_risk")

    def test_reject_unpaired_ticket_manifest(self):
        b = copy.deepcopy(self.row); b["paired_manifest_fingerprint"] = "wrong"
        with self.assertRaises(ValueError):
            s.pair_delta(self.row, b, "failure_risk")

    def test_reject_noninteger_after_cancellation(self):
        b = copy.deepcopy(self.row); b["value"] = [0, 1]
        with self.assertRaises(ValueError):
            s.pair_delta(self.row, b, "failure_risk")

    def test_exact_order_statistic(self):
        arr = list(range(1, 20001))
        self.assertEqual(s.qrank(arr, Fraction(1, 640)), 32)
        self.assertEqual(s.qrank(arr, Fraction(639, 640)), 19969)
        self.assertEqual(s.qrank(arr, Fraction(1, 40)), 500)
        self.assertEqual(s.qrank(arr, Fraction(39, 40)), 19500)

    def test_repeatable_and_stratum_separated_indices(self):
        args = (self.config, "formal", 30, 5)
        a = s.indices(*args, "er_gnm")
        self.assertEqual(a, s.indices(*args, "er_gnm"))
        self.assertNotEqual(a, s.indices(*args, "barabasi_albert"))
        self.assertTrue(all(0 <= i < 20 for i in a))

    def test_chunk_boundary_invariant_and_paired_metrics(self):
        strata = {m: [[i, -i] for i in range(20)] for m in self.config["models"]}
        entire = s.bootstrap_chunk(self.config, "formal", 30, strata, 0, 20)
        split = s.bootstrap_chunk(self.config, "formal", 30, strata, 0, 7) + s.bootstrap_chunk(self.config, "formal", 30, strata, 7, 20)
        self.assertEqual(entire, split)
        self.assertTrue(all(a == -b for a, b in entire))

    def test_constant_parent_strata_equal_weight(self):
        strata = {m: [[j * 7, -j * 7] for _ in range(20)] for j, m in enumerate(self.config["models"])}
        draws = s.bootstrap_chunk(self.config, "formal", 30, strata, 0, 5)
        self.assertEqual(draws, [[420, -420]] * 5)

    def test_zero_empirical_distribution_not_favorable(self):
        parents = [{"integer_totals": [0, 0]} for _ in range(60)]
        results = s.summary(self.config, "formal", 30, parents, [[0, 0]] * 20000)
        self.assertTrue(all(r["adjusted_interval_direction"] == "includes_zero" and r["degenerate_empirical_bootstrap"] for r in results))


if __name__ == "__main__":
    unittest.main()
