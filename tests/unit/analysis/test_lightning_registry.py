"""Tests for the diagnostic-only Lightning sampling registry."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from secondaryexploration.analysis.lightning_registry import (
    LightningPanelInput,
    LightningRegistryError,
    build_lightning_sampling_registry,
    load_lightning_sampling_registry,
    validate_lightning_sampling_registry,
)
from secondaryexploration.topology import ParentGraph


def _panel_parent(prefix: str) -> ParentGraph:
    nodes = tuple(f"{prefix}{index:02d}" for index in range(40))
    edges: list[tuple[str, str]] = []
    for left in range(10):
        for right in range(left + 1, 10):
            edges.append((nodes[left], nodes[right]))
    edges.extend((nodes[index], nodes[index + 1]) for index in range(9, 39))
    edges.extend((nodes[0], nodes[index]) for index in range(10, 20))
    return ParentGraph.from_edges(nodes, edges)


class LightningRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.panels = (
            LightningPanelInput(
                2020,
                "fixture-2020",
                "a" * 64,
                "equal-node-only",
                _panel_parent("a"),
            ),
            LightningPanelInput(
                2026,
                "fixture-2026",
                "b" * 64,
                "equal-node-and-public-capacity-derived",
                _panel_parent("b"),
            ),
        )

    def test_registry_replays_and_discloses_diagnostic_limits(self) -> None:
        registry = build_lightning_sampling_registry(
            self.panels,
            base_seed=2026080702,
            replicate_count=2,
            requested_sizes=(8, 16),
        )

        validate_lightning_sampling_registry(registry, self.panels)
        self.assertEqual(registry["panel_years"], [2020, 2026])
        self.assertEqual(
            registry["status"], "diagnostic-only-not-formal-sample-size"
        )
        self.assertEqual(len(registry["panels"]), 2)
        self.assertEqual(len(registry["panels"][0]["samples"]), 12)
        self.assertEqual(
            len(registry["panels"][0]["overlap_diagnostics"]), 6
        )
        sensitivity = registry["panels"][0]["tie_break_sensitivity"]
        self.assertEqual(sensitivity["primary_policy"], "core-degree-node-id")
        self.assertEqual(
            sensitivity["alternative_policy"],
            "core-degree-source-bound-sha256",
        )
        for stratum in ("core", "bridge", "peripheral"):
            comparison = sensitivity["comparisons"][stratum]
            self.assertEqual(
                comparison["jaccard"],
                [comparison["intersection_count"], comparison["union_count"]],
            )
            if stratum != "bridge":
                self.assertEqual(
                    comparison["added_count"], comparison["removed_count"]
                )

    def test_content_or_source_tampering_is_rejected(self) -> None:
        registry = build_lightning_sampling_registry(
            self.panels,
            base_seed=2026080702,
            replicate_count=2,
            requested_sizes=(8,),
        )
        forged = deepcopy(registry)
        forged["panels"][0]["samples"][0]["edge_count"] += 1

        with self.assertRaisesRegex(LightningRegistryError, "fingerprint"):
            validate_lightning_sampling_registry(forged, self.panels)
        altered_panels = (
            self.panels[0],
            LightningPanelInput(
                2026,
                "fixture-2026",
                "c" * 64,
                "equal-node-and-public-capacity-derived",
                self.panels[1].parent,
            ),
        )
        with self.assertRaisesRegex(LightningRegistryError, "replay mismatch"):
            validate_lightning_sampling_registry(registry, altered_panels)

    def test_strict_loader_replays_and_rejects_duplicate_json_keys(self) -> None:
        registry = build_lightning_sampling_registry(
            self.panels,
            base_seed=2026080702,
            replicate_count=1,
            requested_sizes=(8,),
        )
        with tempfile.TemporaryDirectory() as directory:
            valid = Path(directory) / "valid.json"
            valid.write_text(json.dumps(registry), encoding="utf-8")
            self.assertEqual(
                load_lightning_sampling_registry(valid, self.panels),
                registry,
            )
            duplicate = Path(directory) / "duplicate.json"
            duplicate.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(LightningRegistryError, "duplicate JSON key"):
                load_lightning_sampling_registry(duplicate, self.panels)


if __name__ == "__main__":
    unittest.main()
