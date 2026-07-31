"""Integration test for the tracked scaffold pilot configuration."""

from __future__ import annotations

from pathlib import Path
import unittest

from secondaryexploration import ExperimentConfig, load_experiment_config


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PILOT_CONFIG = REPOSITORY_ROOT / "configs" / "pilot" / "scaffold-smoke.json"
EXPECTED_FINGERPRINT = (
    "2eae8983105262dd1e3fdc82629bab067c2e1364e171ee3bee3c74b534d3e575"
)


class PilotConfigTests(unittest.TestCase):
    def test_tracked_pilot_config_has_expected_identity(self) -> None:
        config = load_experiment_config(PILOT_CONFIG)

        self.assertEqual(config.schema_version, 1)
        self.assertEqual(config.experiment_id, "scaffold-smoke")
        self.assertEqual(config.base_seed, 20260731)
        self.assertEqual(config.replicate_count, 4)
        self.assertEqual(config.output_root, "outputs/scaffold-smoke")
        self.assertEqual(config.fingerprint(), EXPECTED_FINGERPRINT)

    def test_scientifically_relevant_change_changes_identity(self) -> None:
        config = load_experiment_config(PILOT_CONFIG)
        changed_mapping = config.to_canonical_mapping()
        changed_mapping["replicate_count"] = 5
        changed = ExperimentConfig.from_mapping(changed_mapping)

        self.assertNotEqual(config.fingerprint(), changed.fingerprint())


if __name__ == "__main__":
    unittest.main()
