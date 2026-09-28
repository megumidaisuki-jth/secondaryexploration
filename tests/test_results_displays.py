"""Small synthetic test fixtures only; never used as manuscript observations."""
import copy
import unittest

from tools import build_results_displays as displays


def fixture():
    phases = {}
    records = []
    for phase in ("formal", "confirmation"):
        rows = []
        for cid in displays.IDS:
            metric, size, family = cid.split(".")
            negative = metric == "failure_risk"
            rows.append({"contrast_id": cid, "phase": phase, "metric": metric,
                "node_count": int(size[1:]), "tier": "global" if family == "global" else "secondary",
                "beneficial_direction": "negative" if negative else "positive",
                "estimate": [-2 if negative else 2, 10],
                "lower": [-3 if negative else 1, 10], "upper": [-1 if negative else 3, 10],
                "gate_state": "not_applicable" if family == "global" else "open",
                "beneficial_effect_supported": True, "parent_count": 60,
                "stratum_parent_counts": [["barabasi_albert",20],["er_gnm",20],["sbm_fixed_count",20]],
                "resamples": 20000, "confidence_level": [159,160],
                "tail_probability": [1,1600], "adjusted_tail_probability": [1,1600]})
        phases[phase] = {"registered_intervals": rows}
    for row in phases["formal"]["registered_intervals"]:
        records.append({k: row[k] for k in ("contrast_id", "metric", "node_count", "tier", "beneficial_direction")})
        for phase in ("formal", "confirmation"):
            records[-1].update({f"{phase}_interval_direction": "beneficial", f"{phase}_gate_state": row["gate_state"],
                f"{phase}_phase_success": True, f"{phase}_point_direction": "beneficial"})
        records[-1].update(replication_state="independently_confirmed", point_sign_agreement="same_beneficial")
    return {"phase_data": phases, "cross_phase_replication_records": records}


class DisplayChecks(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def test_complete_registry(self):
        self.assertEqual(len(displays.check_registry(self.data)["formal"]), 40)

    def test_missing_row(self):
        self.data["phase_data"]["formal"]["registered_intervals"].pop()
        with self.assertRaisesRegex(ValueError, "registry"):
            displays.check_registry(self.data)

    def test_duplicate_or_reordered_row(self):
        rows = self.data["phase_data"]["formal"]["registered_intervals"]
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaisesRegex(ValueError, "registry"):
            displays.check_registry(self.data)

    def test_false_replication_state(self):
        self.data["cross_phase_replication_records"][0]["replication_state"] = "neither"
        with self.assertRaisesRegex(ValueError, "state"):
            displays.check_registry(self.data)

    def test_wrong_gate(self):
        self.data["phase_data"]["formal"]["registered_intervals"][0]["gate_state"] = "closed"
        with self.assertRaisesRegex(ValueError, "gate"):
            displays.check_registry(self.data)

    def test_wrong_direction(self):
        self.data["cross_phase_replication_records"][0]["formal_interval_direction"] = "harmful"
        with self.assertRaisesRegex(ValueError, "direction"):
            displays.check_registry(self.data)

    def test_wrong_n(self):
        self.data["phase_data"]["formal"]["registered_intervals"][0]["parent_count"] = 420
        with self.assertRaisesRegex(ValueError, "n differs"):
            displays.check_registry(self.data)

    def test_all_replication_states(self):
        for formal_success, confirmation_success, expected in [
            (True, True, "independently_confirmed"), (True, False, "formal_only"),
            (False, True, "confirmation_only"), (False, False, "neither")]:
            data = fixture()
            rep = data["cross_phase_replication_records"][0]
            for phase, success in zip(("formal", "confirmation"), (formal_success, confirmation_success)):
                if not success:
                    row = data["phase_data"][phase]["registered_intervals"][0]
                    row.update(estimate=[1,10], lower=[0,1], upper=[2,10], beneficial_effect_supported=False)
                    rep.update({f"{phase}_interval_direction": "inconclusive", f"{phase}_point_direction": "harmful", f"{phase}_phase_success": False})
            rep["replication_state"] = expected
            rep["point_sign_agreement"] = "same_beneficial" if formal_success and confirmation_success else "same_harmful" if not formal_success and not confirmation_success else "opposite"
            displays.check_registry(data)

    def test_closed_global_gate_propagation(self):
        data = fixture()
        rows = data["phase_data"]["formal"]["registered_intervals"]
        rows[3].update(lower=[-1,10], upper=[0,1], beneficial_effect_supported=False)
        for i in range(5):
            rows[i]["beneficial_effect_supported"] = False
            if i != 3:
                rows[i]["gate_state"] = "closed"
            rep = data["cross_phase_replication_records"][i]
            rep.update(formal_gate_state=rows[i]["gate_state"], formal_phase_success=False,
                       formal_interval_direction="inconclusive" if i == 3 else "beneficial",
                       replication_state="confirmation_only")
        displays.check_registry(data)

    def test_exact_rounding(self):
        for value, expected in [([1,3], "0.333"), ([-1,100000], "0.000"),
                                ([0,1], "0.000"), ([1,2000], "0.000"), ([3,2000], "0.002")]:
            self.assertEqual(displays.decimal(value), expected)

    def test_rounded_zero_does_not_change_direction(self):
        row = copy.copy(self.data["phase_data"]["formal"]["registered_intervals"][0])
        row.update(lower=[-2,100000], upper=[-1,100000])
        self.assertEqual(displays.decimal(row["upper"]), "0.000")
        self.assertEqual(displays.interval_direction(row), "beneficial")

    def test_zero_boundary_is_inconclusive(self):
        row = copy.copy(self.data["phase_data"]["formal"]["registered_intervals"][0])
        row["upper"] = [0,1]
        self.assertEqual(displays.interval_direction(row), "inconclusive")

    def test_invalid_fraction(self):
        with self.assertRaises(ValueError):
            displays.frac([1,0])
        with self.assertRaises(ValueError):
            displays.frac([True,1])


if __name__ == "__main__":
    unittest.main()
