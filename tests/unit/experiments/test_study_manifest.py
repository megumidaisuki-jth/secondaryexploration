"""Unit contract for study-design manifests and semantic seed ledgers."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from secondaryexploration.experiments import (
    StudyManifestError,
    StudyPhase,
    StudySeedLedger,
    TrafficRegimeRole,
    build_study_seed_ledger,
    generate_declared_request_trace,
    load_study_design_manifest,
    traffic_kernel_for,
    validate_study_seed_ledger,
)


_ROOT = Path(__file__).resolve().parents[3]
_PILOT = _ROOT / "configs" / "pilot" / "synthetic-pipeline-v1.json"


class StudyManifestUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_study_design_manifest(_PILOT)
        self.ledger = build_study_seed_ledger(self.manifest)

    def test_tracked_pilot_has_frozen_identity_and_complete_registry(self) -> None:
        self.assertEqual(
            self.manifest.fingerprint,
            "ffcdffe43e3d77b978e4a64cc2aaa368c302fe63cce92f4e6f16ad415625fb4c",
        )
        self.assertEqual(
            self.ledger.fingerprint,
            "284928d1a3f4679ac373f45984fb006622d88e085f0be95cb418fcf7a599988d",
        )
        self.assertEqual(tuple(cell.node_count for cell in self.manifest.size_cells), (30, 60))
        self.assertEqual(tuple(cell.target_edge_count for cell in self.manifest.size_cells), (81, 171))
        self.assertEqual(len(self.ledger.parent_seeds), 2)
        self.assertEqual(len(self.ledger.trace_seeds), 22)
        self.assertEqual(
            self.manifest.topology_families,
            ("demand-aware", "fhs3", "fhs5", "nch"),
        )
        self.assertEqual(self.manifest.demand_aware_seed_family, "fhs5")
        self.assertEqual(
            sum(regime.role is TrafficRegimeRole.TRAINING for regime in self.manifest.regimes),
            4,
        )

    def test_canonical_json_round_trip_preserves_identity(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "round-trip.json"
            path.write_text(
                json.dumps(
                    self.manifest.to_canonical_mapping(),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            reloaded = load_study_design_manifest(path)
        self.assertEqual(reloaded, self.manifest)
        self.assertEqual(reloaded.fingerprint, self.manifest.fingerprint)

    def test_loader_rejects_duplicate_missing_unknown_and_nested_unknown_fields(self) -> None:
        cases = []
        mapping = self.manifest.to_canonical_mapping()
        unknown = dict(mapping)
        unknown["result"] = "forbidden"
        cases.append(("unknown", json.dumps(unknown), "unknown keys"))
        missing = dict(mapping)
        del missing["base_seed"]
        cases.append(("missing", json.dumps(missing), "missing keys"))
        cases.append(
            (
                "duplicate",
                '{"schema_version":1,"schema_version":1}',
                "duplicate JSON key",
            )
        )
        nested = json.loads(json.dumps(mapping))
        nested["regimes"][0]["parameters"]["secret_result_weight"] = 1
        cases.append(("nested", json.dumps(nested), "parameters must be exactly"))

        with TemporaryDirectory() as directory:
            for name, payload, message in cases:
                with self.subTest(name=name):
                    path = Path(directory) / f"{name}.json"
                    path.write_text(payload, encoding="utf-8")
                    with self.assertRaisesRegex(StudyManifestError, message):
                        load_study_design_manifest(path)

    def test_pilot_cannot_be_relabeled_formal_without_freeze_evidence(self) -> None:
        with self.assertRaisesRegex(StudyManifestError, "basis_fingerprint"):
            replace(self.manifest, phase=StudyPhase.FORMAL)
        with self.assertRaisesRegex(StudyManifestError, "all primary sizes"):
            replace(
                self.manifest,
                phase=StudyPhase.FORMAL,
                basis_fingerprint="1" * 64,
                code_revision="2" * 40,
                environment_fingerprint="3" * 64,
            )

    def test_parent_attempt_ceiling_matches_the_generator_contract(self) -> None:
        self.assertEqual(
            replace(self.manifest, maximum_parent_attempts=10_000).maximum_parent_attempts,
            10_000,
        )
        with self.assertRaisesRegex(StudyManifestError, r"\[1, 10000\]"):
            replace(self.manifest, maximum_parent_attempts=10_001)

    def test_shift_contract_rejects_result_dependent_or_inexact_relations(self) -> None:
        regimes = list(self.manifest.regimes)
        index = next(
            i for i, item in enumerate(regimes) if item.regime_id == "test-direction-reversed"
        )
        altered_parameters = dict(regimes[index].parameters)
        altered_parameters["forward_weight"] = 2
        regimes[index] = replace(
            regimes[index],
            parameters=tuple(sorted(altered_parameters.items())),
        )
        with self.assertRaisesRegex(StudyManifestError, "exact swap"):
            replace(self.manifest, regimes=tuple(regimes))

        regimes = list(self.manifest.regimes)
        index = next(
            i for i, item in enumerate(regimes) if item.regime_id == "test-hotspot-relocated"
        )
        altered_parameters = dict(regimes[index].parameters)
        altered_parameters["hotspot_offset"] = 2
        regimes[index] = replace(
            regimes[index],
            parameters=tuple(sorted(altered_parameters.items())),
        )
        with self.assertRaisesRegex(StudyManifestError, "disjoint"):
            replace(self.manifest, regimes=tuple(regimes))

    def test_seed_ledger_is_unique_replayable_and_count_prefix_stable(self) -> None:
        validate_study_seed_ledger(self.ledger, self.manifest)
        all_seeds = tuple(
            seed
            for item in self.ledger.parent_seeds
            for seed in (
                item.ensemble_base_seed,
                item.capacity_search_seed,
                item.binary_matching_seed,
            )
        ) + tuple(
            seed
            for item in self.ledger.trace_seeds
            for seed in (item.trace_root_seed, item.routing_root_seed)
        )
        self.assertEqual(len(all_seeds), len(set(all_seeds)))

        expanded_manifest = replace(self.manifest, training_traces_per_regime=2)
        expanded = build_study_seed_ledger(expanded_manifest)
        earlier = {
            (
                item.node_count,
                item.parent_replicate,
                item.split,
                item.regime_id,
                item.trace_replicate,
            ): (item.trace_root_seed, item.routing_root_seed)
            for item in self.ledger.trace_seeds
        }
        later = {
            (
                item.node_count,
                item.parent_replicate,
                item.split,
                item.regime_id,
                item.trace_replicate,
            ): (item.trace_root_seed, item.routing_root_seed)
            for item in expanded.trace_seeds
        }
        self.assertTrue(all(later[key] == value for key, value in earlier.items()))

        forged_parent = replace(
            self.ledger.parent_seeds[0],
            ensemble_base_seed=self.ledger.parent_seeds[0].ensemble_base_seed ^ 1,
        )
        forged = StudySeedLedger(
            self.ledger.manifest_fingerprint,
            (forged_parent,) + self.ledger.parent_seeds[1:],
            self.ledger.trace_seeds,
        )
        with self.assertRaisesRegex(StudyManifestError, "complete regeneration"):
            validate_study_seed_ledger(forged, self.manifest)

    def test_declared_kernels_and_traces_are_topology_blind_and_split_separated(self) -> None:
        cell = self.manifest.size_cell(30)
        training_hotspot = self.manifest.regime("train-hotspot")
        relocated = self.manifest.regime("test-hotspot-relocated")
        train_kernel = traffic_kernel_for(cell, training_hotspot)
        shifted_kernel = traffic_kernel_for(cell, relocated)
        self.assertNotEqual(train_kernel.fingerprint, shifted_kernel.fingerprint)

        training_record = next(
            item
            for item in self.ledger.trace_seeds
            if item.node_count == 30 and item.regime_id == "train-uniform"
        )
        test_record = next(
            item
            for item in self.ledger.trace_seeds
            if item.node_count == 30 and item.regime_id == "test-uniform-id"
        )
        training_trace = generate_declared_request_trace(self.manifest, training_record)
        test_trace = generate_declared_request_trace(self.manifest, test_record)
        self.assertEqual(training_trace.kernel, test_trace.kernel)
        self.assertEqual(training_trace.length, 120)
        self.assertEqual(test_trace.length, 120)
        self.assertNotEqual(training_trace.root_seed, test_trace.root_seed)
        self.assertNotEqual(training_trace.requests, test_trace.requests)


if __name__ == "__main__":
    unittest.main()
