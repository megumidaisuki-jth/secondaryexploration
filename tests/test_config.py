"""Contract tests for experiment configuration loading and identity."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
import unittest

from secondaryexploration.config import (
    ConfigError,
    ExperimentConfig,
    load_experiment_config,
)


VALID_CONFIG: dict[str, object] = {
    "schema_version": 1,
    "experiment_id": "scaffold-smoke",
    "base_seed": 20260731,
    "replicate_count": 4,
    "output_root": "outputs/scaffold-smoke",
}


class ExperimentConfigTests(unittest.TestCase):
    def test_from_mapping_returns_typed_immutable_config(self) -> None:
        config = ExperimentConfig.from_mapping(VALID_CONFIG)

        self.assertEqual(config.schema_version, 1)
        self.assertEqual(config.experiment_id, "scaffold-smoke")
        self.assertEqual(config.base_seed, 20260731)
        self.assertEqual(config.replicate_count, 4)
        self.assertEqual(config.output_root, "outputs/scaffold-smoke")
        self.assertEqual(config.to_canonical_mapping(), VALID_CONFIG)
        self.assertEqual(
            list(config.to_canonical_mapping()),
            [
                "schema_version",
                "experiment_id",
                "base_seed",
                "replicate_count",
                "output_root",
            ],
        )

        with self.assertRaises(FrozenInstanceError):
            config.base_seed = 1  # type: ignore[misc]

    def test_fingerprint_does_not_depend_on_input_key_order(self) -> None:
        reversed_mapping = dict(reversed(list(VALID_CONFIG.items())))

        first = ExperimentConfig.from_mapping(VALID_CONFIG)
        second = ExperimentConfig.from_mapping(reversed_mapping)

        self.assertEqual(first.fingerprint(), second.fingerprint())
        self.assertEqual(len(first.fingerprint()), 64)

    def test_direct_construction_cannot_bypass_validation(self) -> None:
        with self.assertRaisesRegex(ConfigError, "replicate_count"):
            ExperimentConfig(
                schema_version=1,
                experiment_id="scaffold-smoke",
                base_seed=20260731,
                replicate_count=0,
                output_root="outputs/scaffold-smoke",
            )

    def test_missing_keys_are_rejected(self) -> None:
        raw = dict(VALID_CONFIG)
        del raw["output_root"]

        with self.assertRaisesRegex(ConfigError, "missing.*output_root"):
            ExperimentConfig.from_mapping(raw)

    def test_unknown_keys_are_rejected(self) -> None:
        raw = dict(VALID_CONFIG)
        raw["routing"] = "shortest"

        with self.assertRaisesRegex(ConfigError, "unknown.*routing"):
            ExperimentConfig.from_mapping(raw)

    def test_non_mapping_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "mapping"):
            ExperimentConfig.from_mapping([])  # type: ignore[arg-type]

    def test_invalid_field_values_are_rejected(self) -> None:
        invalid_cases: list[tuple[str, object]] = [
            ("schema_version", True),
            ("schema_version", "1"),
            ("schema_version", 2),
            ("experiment_id", 4),
            ("experiment_id", ""),
            ("experiment_id", " scaffold"),
            ("experiment_id", "scaffold "),
            ("experiment_id", "bad/id"),
            ("experiment_id", "éxperiment"),
            ("experiment_id", "a" * 65),
            ("base_seed", True),
            ("base_seed", "20260731"),
            ("base_seed", -1),
            ("base_seed", 2**64),
            ("replicate_count", True),
            ("replicate_count", 1.0),
            ("replicate_count", 0),
            ("replicate_count", 1_000_001),
            ("output_root", 4),
            ("output_root", ""),
            ("output_root", " outputs/run"),
            ("output_root", "/outputs/run"),
            ("output_root", "C:/outputs/run"),
            ("output_root", "C:outputs/run"),
            ("output_root", "outputs\\run"),
            ("output_root", "./outputs/run"),
            ("output_root", "outputs/../run"),
            ("output_root", "outputs//run"),
            ("output_root", "outputs/run/."),
        ]

        for field, invalid_value in invalid_cases:
            with self.subTest(field=field, invalid_value=invalid_value):
                raw = dict(VALID_CONFIG)
                raw[field] = invalid_value
                with self.assertRaisesRegex(ConfigError, field):
                    ExperimentConfig.from_mapping(raw)


class ConfigFileLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._temporary_directory.name)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _write_text(self, name: str, contents: str) -> Path:
        path = self.directory / name
        path.write_text(contents, encoding="utf-8")
        return path

    def test_loads_valid_json_object(self) -> None:
        path = self._write_text("valid.json", json.dumps(VALID_CONFIG))

        config = load_experiment_config(path)

        self.assertEqual(config, ExperimentConfig.from_mapping(VALID_CONFIG))

    def test_malformed_json_is_rejected(self) -> None:
        path = self._write_text("malformed.json", '{"schema_version": 1')

        with self.assertRaisesRegex(ConfigError, "malformed.json"):
            load_experiment_config(path)

    def test_non_object_top_level_is_rejected(self) -> None:
        path = self._write_text("list.json", "[]")

        with self.assertRaisesRegex(ConfigError, "mapping"):
            load_experiment_config(path)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        path = self._write_text(
            "duplicate.json",
            """{
                "schema_version": 1,
                "experiment_id": "first",
                "experiment_id": "second",
                "base_seed": 1,
                "replicate_count": 1,
                "output_root": "outputs/test"
            }""",
        )

        with self.assertRaisesRegex(ConfigError, "duplicate.*experiment_id"):
            load_experiment_config(path)

    def test_invalid_utf8_is_rejected(self) -> None:
        path = self.directory / "invalid-utf8.json"
        path.write_bytes(b"\xff\xfe")

        with self.assertRaisesRegex(ConfigError, "invalid-utf8.json"):
            load_experiment_config(path)

    def test_missing_file_is_reported_as_config_error(self) -> None:
        path = self.directory / "missing.json"

        with self.assertRaisesRegex(ConfigError, "missing.json"):
            load_experiment_config(path)


if __name__ == "__main__":
    unittest.main()
