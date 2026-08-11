"""Tests for the pre-result formal inference artifact contract."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from types import SimpleNamespace
from pathlib import Path
import json
import shutil
import tempfile
import unittest
import weakref
from unittest.mock import patch

from secondaryexploration.experiments import (
    StudyManifestError,
    build_study_seed_ledger,
    load_study_design_manifest,
)
from secondaryexploration.experiments.artifacts import load_study_run_summary
from tools import formal_inference as target


_HEX64_A = "a" * 64
_HEX64_B = "b" * 64
_HEX40 = "c" * 40
_ROOT = Path(__file__).resolve().parents[3]


def _trace_row(index: int, scope: str, value: Fraction) -> dict[str, object]:
    return {
        "node_count": 30,
        "parent_model": "er_gnm",
        "parent_replicate": 0,
        "parent_graph_id": "n0030-r0000-er_gnm",
        "regime_id": f"regime-{index}",
        "scope": scope,
        "paired_manifest_fingerprint": f"{index + 1:064x}",
        "source_family": "demand-aware",
        "metric": "failure_risk",
        "horizon": 360,
        "binary_arm_count": 2,
        "binary_arm_events": [["binary-a", True], ["binary-b", index % 2 == 0]],
        "source_event": index == 0,
        "value": [value.numerator, value.denominator],
    }


def _interval(
    contrast_id: str,
    *,
    tier: str,
    direction: str,
    estimate: Fraction,
    lower: Fraction,
    upper: Fraction,
    gate: str,
) -> dict[str, object]:
    return {
        "contrast_id": contrast_id,
        "metric": "failure_risk",
        "node_count": 30,
        "tier": tier,
        "beneficial_direction": direction,
        "estimate": [estimate.numerator, estimate.denominator],
        "lower": [lower.numerator, lower.denominator],
        "upper": [upper.numerator, upper.denominator],
        "gate_state": gate,
    }


def _phase(phase: str, digest: str) -> dict[str, object]:
    families = []
    for spec in target._hierarchy_specs():
        intervals = []
        for registration in spec["registrations"]:
            positive = registration["beneficial_direction"] == "positive"
            item = _interval(
                registration["contrast_id"],
                tier=registration["tier"],
                direction=registration["beneficial_direction"],
                estimate=Fraction(1 if positive else -1, 10),
                lower=Fraction(1, 20) if positive else Fraction(-1, 5),
                upper=Fraction(1, 5) if positive else Fraction(-1, 20),
                gate="not_applicable" if registration["tier"] == "global" else "open",
            )
            item["metric"] = spec["metric"]
            item["node_count"] = spec["node_count"]
            intervals.append(item)
        families.append(
            {
                "family_id": spec["family_id"],
                "intervals": sorted(intervals, key=lambda item: item["contrast_id"]),
            }
        )
    evidence = {
        "schema_version": target.PHASE_EVIDENCE_SCHEMA,
        "status": "complete-strict-replay",
        "phase": phase,
        "study_id": f"synthetic-{phase}-v1",
        "source_fingerprints": {},
        "analysis_revision": _HEX40,
        "analysis_contract": {},
        "block_registry": [{} for _ in range(240)],
        "trace_contrasts": [],
        "parent_contrasts": [],
        "hierarchies": families,
        "event_coverage": [],
        "activity_sensitivity": [],
        "limitations": [],
    }
    evidence["evidence_fingerprint"] = target._mapping_fingerprint(evidence)
    return evidence


def _valid_hierarchies() -> list[dict[str, object]]:
    bootstrap = [[0, 1]] * 20_000
    output = []
    for spec in target._hierarchy_specs():
        intervals = []
        for registration in spec["registrations"]:
            global_tier = registration["tier"] == "global"
            intervals.append(
                {
                    "contrast_id": registration["contrast_id"],
                    "metric": spec["metric"],
                    "node_count": spec["node_count"],
                    "tier": registration["tier"],
                    "beneficial_direction": registration["beneficial_direction"],
                    "estimate": [0, 1],
                    "lower": [0, 1],
                    "upper": [0, 1],
                    "confidence_level": [159, 160],
                    "tail_probability": [1, 1600],
                    "parent_count": 60,
                    "stratum_parent_counts": [[model, 20] for model in target._MODELS],
                    "bootstrap_values": bootstrap,
                    "inference_status": "confirmatory" if global_tier else "descriptive",
                    "beneficial_effect_supported": False,
                    "gate_state": "not_applicable" if global_tier else "closed",
                }
            )
        output.append(
            {
                "family_id": spec["family_id"],
                "metric": spec["metric"],
                "node_count": spec["node_count"],
                "resamples": 20_000,
                "root_seed": 2026081003,
                "confidence_level": [159, 160],
                "adjusted_tail_probability": [1, 1600],
                "phase_family_scope": "one-of-eight-local-five-contrast-hierarchies",
                "intervals": intervals,
            }
        )
    return output


class FormalInferenceToolTests(unittest.TestCase):
    def test_stream_projection_build_is_exactly_legacy_phase_build(self) -> None:
        manifest = SimpleNamespace(
            phase=target.StudyPhase.FORMAL,
            fingerprint="1" * 64,
            study_id="formal-test",
        )
        ledger = SimpleNamespace(fingerprint="2" * 64)
        artifacts = []
        blocks = []
        for index in range(240):
            size = (30, 60, 120, 240)[index // 60]
            replicate = (index % 60) // 3
            model = target._MODELS[index % 3]
            key = f"n{size:04d}-r{replicate:04d}-{model}"
            artifacts.append(
                {
                    "block": {
                        "node_count": size,
                        "parent_replicate": replicate,
                        "parent_model": model,
                    },
                    "artifact_fingerprint": f"{index + 1:064x}",
                    "training": {
                        "demand_aware": {
                            "topology_fingerprint": "a" * 64,
                            "seed_topology_fingerprint": "a" * 64,
                        }
                    },
                }
            )
            blocks.append(
                {
                    "block_key": key,
                    "path": f"blocks/{key}.json",
                    "artifact_fingerprint": f"{index + 1:064x}",
                    "result_fingerprint": f"{index + 1000:064x}",
                }
            )
        summary = {
            "status": "complete",
            "completed_block_count": 240,
            "summary_fingerprint": "3" * 64,
            "blocks": sorted(blocks, key=lambda row: row["block_key"]),
        }
        calibration = {"evidence_fingerprint": "4" * 64}
        precision = {"precision_fingerprint": "5" * 64}
        trace_rows = [
            {"paired_manifest_fingerprint": "6" * 64, "synthetic": True}
        ]
        with patch.object(
            target, "_extract_trace_contrasts", return_value=trace_rows
        ), patch.object(
            target, "_aggregate_parent_contrasts", return_value=[]
        ), patch.object(
            target, "_build_hierarchies", return_value=[]
        ), patch.object(
            target, "_build_event_coverage", return_value=[]
        ), patch.object(
            target, "_build_activity_sensitivity_from_flags", return_value=[]
        ), patch.object(
            target, "validate_phase_evidence", return_value=None
        ):
            legacy = target.build_phase_evidence(
                manifest,
                ledger,
                summary,
                artifacts,
                calibration,
                precision,
                analysis_revision=_HEX40,
            )
            projection = {
                "stream_projection_version": 1,
                "trace_contrasts": trace_rows,
                "activity_flags": target._artifact_activity_flags(artifacts),
                "artifact_fingerprints": [
                    item["artifact_fingerprint"]
                    for item in sorted(artifacts, key=target._artifact_sort_key)
                ],
            }
            streamed = target.build_phase_evidence_from_projection(
                manifest,
                ledger,
                summary,
                projection,
                calibration,
                precision,
                analysis_revision=_HEX40,
            )
        self.assertEqual(streamed, legacy)

    def test_stream_summary_records_are_byte_semantic_equivalent_to_v1_builder(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/pilot/synthetic-calibration-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        summary = load_study_run_summary(
            _ROOT / "outputs/pilot/synthetic-calibration-v1/run-summary.json",
            manifest=manifest,
            ledger=ledger,
        )
        rebuilt = target._summary_from_stream_records(
            manifest,
            ledger,
            code_revision=summary["code_revision"],
            environment=summary["environment"],
            records=summary["blocks"],
        )
        self.assertEqual(rebuilt, summary)

    def test_streaming_summary_exactly_replays_complete_pilot(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/pilot/synthetic-calibration-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        output_root = _ROOT / "outputs/pilot/synthetic-calibration-v1"
        expected = load_study_run_summary(
            output_root / "run-summary.json",
            manifest=manifest,
            ledger=ledger,
        )
        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory)
            fixture_blocks = fixture_root / "blocks"
            (fixture_blocks / ".locks").mkdir(parents=True)
            for source in (output_root / "blocks").glob("*.json"):
                shutil.copy2(source, fixture_blocks / source.name)
            observed, registry = target.build_streaming_run_summary(
                manifest,
                ledger,
                output_root=fixture_root,
                code_revision=expected["code_revision"],
                environment=expected["environment"],
            )
        self.assertEqual(observed, expected)
        self.assertEqual(len(registry), expected["completed_block_count"])

    def test_streaming_summary_keeps_at_most_one_full_artifact_alive(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/formal/synthetic-formal-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        environment = {
            "python_implementation": "cpython",
            "python_version": "3.12.13",
            "platform_system": "Windows",
            "machine": "AMD64",
        }
        previous = None
        calls = 0

        class Artifact(dict):
            pass

        def loader(path, **expected):
            nonlocal previous, calls
            if previous is not None:
                self.assertIsNone(previous())
            calls += 1
            seed = expected["parent_seed"]
            model = expected["parent_model"]
            artifact = Artifact(
                block={
                    "node_count": seed.node_count,
                    "parent_replicate": seed.parent_replicate,
                    "parent_model": model,
                },
                timing_ns={"generation": calls, "exact_validation": calls + 1},
                artifact_fingerprint=f"{calls:064x}",
                result_fingerprint=f"{calls + 100:064x}",
            )
            previous = weakref.ref(artifact)
            return artifact

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            blocks = output / "blocks"
            (blocks / ".locks").mkdir(parents=True)
            for seed in ledger.parent_seeds:
                for model in target._MODELS:
                    key = (
                        f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}"
                    )
                    (blocks / f"{key}.json").write_bytes(b"{}")
            summary, registry = target.build_streaming_run_summary(
                manifest,
                ledger,
                output_root=output,
                code_revision="a" * 40,
                environment=environment,
                artifact_loader=loader,
            )
        self.assertEqual(calls, 240)
        self.assertEqual(len(registry), 240)
        self.assertEqual(summary["completed_block_count"], 240)

    def test_stream_registry_rejects_missing_foreign_and_active_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            blocks = output / "blocks"
            locks = blocks / ".locks"
            locks.mkdir(parents=True)
            key = "n0030-r0000-er_gnm"
            with self.assertRaisesRegex(StudyManifestError, "not complete"):
                target._exact_phase_block_paths(output, [key])
            (blocks / f"{key}.json").write_bytes(b"{}")
            (blocks / "foreign.json").write_bytes(b"{}")
            with self.assertRaisesRegex(StudyManifestError, "foreign"):
                target._exact_phase_block_paths(output, [key])
            (blocks / "foreign.json").unlink()
            (locks / f"{key}.lock").write_bytes(b"")
            with self.assertRaisesRegex(StudyManifestError, "lock root"):
                target._exact_phase_block_paths(output, [key])

    def test_streaming_summary_rejects_file_mutation_during_scan(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/pilot/synthetic-calibration-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        environment = {
            "python_implementation": "cpython",
            "python_version": "3.12.13",
            "platform_system": "Windows",
            "machine": "AMD64",
        }
        calls = 0

        def loader(path, **expected):
            nonlocal calls
            calls += 1
            seed = expected["parent_seed"]
            model = expected["parent_model"]
            if calls == 1:
                path.write_bytes(b"changed-after-first-hash")
            return {
                "block": {
                    "node_count": seed.node_count,
                    "parent_replicate": seed.parent_replicate,
                    "parent_model": model,
                },
                "timing_ns": {"generation": calls, "exact_validation": calls + 1},
                "artifact_fingerprint": f"{calls:064x}",
                "result_fingerprint": f"{calls + 100:064x}",
            }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            blocks = output / "blocks"
            (blocks / ".locks").mkdir(parents=True)
            for seed in ledger.parent_seeds:
                for model in target._MODELS:
                    key = (
                        f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}"
                    )
                    (blocks / f"{key}.json").write_bytes(b"{}")
            with self.assertRaisesRegex(StudyManifestError, "changed during"):
                target.build_streaming_run_summary(
                    manifest,
                    ledger,
                    output_root=output,
                    code_revision="a" * 40,
                    environment=environment,
                    artifact_loader=loader,
                )

    def test_phase_source_stream_keeps_at_most_one_full_artifact_alive(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/formal/synthetic-formal-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        environment = {
            "python_implementation": "cpython",
            "python_version": "3.12.13",
            "platform_system": "Windows",
            "machine": "AMD64",
        }
        records = []
        for index, (_key, seed, model) in enumerate(
            sorted(
                (
                    f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}",
                    seed,
                    model,
                )
                for seed in ledger.parent_seeds
                for model in target._MODELS
            ),
            start=1,
        ):
            key = f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}"
            records.append(
                {
                    "block_key": key,
                    "path": f"blocks/{key}.json",
                    "artifact_fingerprint": f"{index:064x}",
                    "result_fingerprint": f"{index + 1000:064x}",
                    "generation_ns": index,
                    "validation_ns": index + 1,
                }
            )
        summary = target._summary_from_stream_records(
            manifest,
            ledger,
            code_revision="a" * 40,
            environment=environment,
            records=records,
        )
        by_key = {record["block_key"]: record for record in records}
        previous = None
        calls = 0

        class Artifact(dict):
            pass

        def loader(path, **expected):
            nonlocal previous, calls
            if previous is not None:
                self.assertIsNone(previous())
            calls += 1
            seed = expected["parent_seed"]
            model = expected["parent_model"]
            key = f"n{seed.node_count:04d}-r{seed.parent_replicate:04d}-{model}"
            record = by_key[key]
            artifact = Artifact(
                block={
                    "node_count": seed.node_count,
                    "parent_replicate": seed.parent_replicate,
                    "parent_model": model,
                },
                timing_ns={
                    "generation": record["generation_ns"],
                    "exact_validation": record["validation_ns"],
                },
                artifact_fingerprint=record["artifact_fingerprint"],
                result_fingerprint=record["result_fingerprint"],
                training={
                    "demand_aware": {
                        "topology_fingerprint": "b" * 64,
                        "seed_topology_fingerprint": "b" * 64,
                    }
                },
            )
            previous = weakref.ref(artifact)
            return artifact

        def trace_projection(_manifest, artifacts):
            block = artifacts[0]["block"]
            return [
                {
                    "node_count": block["node_count"],
                    "parent_model": block["parent_model"],
                    "parent_replicate": block["parent_replicate"],
                    "regime_id": "fixture",
                    "source_family": "global",
                    "metric": "failure_risk",
                }
            ]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocks = root / "blocks"
            (blocks / ".locks").mkdir(parents=True)
            for record in records:
                (blocks / f"{record['block_key']}.json").write_bytes(b"{}")
            summary_path = root / "run-summary.json"
            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            with patch.object(
                target, "load_study_design_manifest", return_value=manifest
            ), patch.object(
                target, "load_audited_calibration_evidence", return_value={}
            ), patch.object(
                target, "load_formal_precision_evidence", return_value={}
            ), patch.object(
                target, "validate_frozen_execution_context", return_value=None
            ), patch.object(
                target, "load_synthetic_block_artifact", new=loader
            ), patch.object(
                target, "_extract_trace_contrasts", new=trace_projection
            ):
                sources = target.load_phase_sources(
                    Path("formal.json"),
                    summary_path,
                    Path("calibration-manifest.json"),
                    Path("calibration.json"),
                    Path("precision.json"),
                )
        self.assertEqual(calls, 240)
        self.assertEqual(len(sources[3]["trace_contrasts"]), 240)

    def test_each_source_uses_only_its_registered_resource_panel_bracket(self) -> None:
        regimes = tuple(
            SimpleNamespace(
                regime_id=f"regime-{index}",
                role=SimpleNamespace(value="test"),
                shift=SimpleNamespace(
                    value="same_distribution" if index < 4 else "shift"
                ),
            )
            for index in range(7)
        )
        manifest = SimpleNamespace(regimes=regimes, requests_per_node=1)

        def variant(variant_id, family, request_index):
            return {
                "variant_id": variant_id,
                "family": family,
                "horizon": 30,
                "tau_nopath": {"observed": True, "request_index": request_index},
            }

        variants = [
            variant("binary-low", "binary-matched", 10),
            variant("binary-high", "binary-matched", 28),
            variant("demand-aware", "demand-aware", 25),
            variant("fhs3", "fhs3", 16),
            variant("fhs5", "fhs5", 20),
            variant("nch", "nch", 22),
        ]
        artifact = {
            "block": {
                "node_count": 30,
                "parent_model": "er_gnm",
                "parent_replicate": 0,
            },
            "resource_panels": [
                {
                    "source_variant_id": source,
                    "binary_variant_ids": [binary],
                }
                for source, binary in (
                    ("demand-aware", "binary-low"),
                    ("fhs3", "binary-high"),
                    ("fhs5", "binary-low"),
                    ("nch", "binary-high"),
                )
            ],
            "held_out": [
                {
                    "paired_manifest_fingerprint": f"{index + 1:064x}",
                    "trace_seed": {"regime_id": f"regime-{index}"},
                    "variants": deepcopy(variants),
                }
                for index in range(7)
            ],
        }
        rows = target._extract_trace_contrasts(manifest, [artifact])
        demand = next(
            row
            for row in rows
            if row["regime_id"] == "regime-0"
            and row["source_family"] == "demand-aware"
            and row["metric"] == "normalized_restricted_tau_nopath"
        )
        fhs3 = next(
            row
            for row in rows
            if row["regime_id"] == "regime-0"
            and row["source_family"] == "fhs3"
            and row["metric"] == "normalized_restricted_tau_nopath"
        )
        self.assertEqual(demand["value"], [1, 2])
        self.assertEqual(fhs3["value"], [-2, 5])
        self.assertEqual(demand["binary_arm_count"], 1)
        self.assertEqual(demand["binary_arm_events"], [["binary-low", True]])

    def test_parent_scope_reconstruction_is_exact_four_to_three(self) -> None:
        rows = [
            _trace_row(index, "same_distribution", Fraction(index + 1, 10))
            for index in range(4)
        ] + [
            _trace_row(index + 4, "distribution_shift", Fraction(index + 5, 10))
            for index in range(3)
        ]
        observed = target._aggregate_parent_contrasts(rows)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["same_distribution_mean"], [1, 4])
        self.assertEqual(observed[0]["distribution_shift_mean"], [3, 5])
        self.assertEqual(observed[0]["combined_parent_value"], [2, 5])

    def test_q010_gate_is_parent_level_and_emits_no_quantile(self) -> None:
        rows = [
            _trace_row(index, "same_distribution", Fraction(0))
            for index in range(4)
        ]
        observed = target._build_event_coverage(rows)
        self.assertEqual(len(observed), 1)
        self.assertIsNone(observed[0]["quantile_estimate"])
        parent = observed[0]["parents"][0]
        self.assertEqual(parent["source_event_fraction"], [1, 4])
        self.assertTrue(parent["source_q0.10_identified"])
        self.assertTrue(parent["source_and_all_binary_q0.10_identified"])

    def test_censored_event_must_end_at_horizon(self) -> None:
        with self.assertRaisesRegex(StudyManifestError, "censored"):
            target._validate_event(
                {"observed": False, "request_index": 359},
                360,
            )

    def test_direction_and_zero_state_machine_is_exhaustive(self) -> None:
        beneficial = _interval(
            "x",
            tier="global",
            direction="negative",
            estimate=Fraction(-1, 10),
            lower=Fraction(-1, 5),
            upper=Fraction(-1, 20),
            gate="not_applicable",
        )
        harmful = deepcopy(beneficial)
        harmful.update(estimate=[1, 10], lower=[1, 20], upper=[1, 5])
        zero = deepcopy(beneficial)
        zero["estimate"] = [0, 1]
        self.assertEqual(target._interval_direction(beneficial), "beneficial")
        self.assertEqual(target._interval_direction(harmful), "harmful")
        self.assertEqual(target._point_sign_agreement(beneficial, harmful), "opposite")
        self.assertEqual(target._point_sign_agreement(beneficial, zero), "one_or_both_zero")
        self.assertEqual(target._replication_state(True, True), "independently_confirmed")
        self.assertEqual(target._replication_state(True, False), "formal_only")
        self.assertEqual(target._replication_state(False, True), "confirmation_only")
        self.assertEqual(target._replication_state(False, False), "neither")

    def test_cross_phase_builder_does_not_pool_and_applies_both_gates(self) -> None:
        formal = _phase("formal", _HEX64_A)
        confirmation = _phase("confirmation", _HEX64_B)
        observed = target._build_replication_from_validated_phases(
            formal, confirmation, analysis_revision=_HEX40
        )
        self.assertEqual(len(observed["contrast_results"]), 40)
        self.assertTrue(
            all(
                item["replication_state"] == "independently_confirmed"
                for item in observed["contrast_results"]
            )
        )
        family = confirmation["hierarchies"][0]
        global_interval = next(
            item for item in family["intervals"] if item["tier"] == "global"
        )
        global_interval["lower"] = [-1, 5]
        global_interval["upper"] = [1, 5]
        secondaries = [item for item in family["intervals"] if item["tier"] == "secondary"]
        for secondary in secondaries:
            secondary["gate_state"] = "closed"
        secondary = secondaries[0]
        confirmation["evidence_fingerprint"] = target._mapping_fingerprint(
            {key: value for key, value in confirmation.items() if key != "evidence_fingerprint"}
        )
        observed = target._build_replication_from_validated_phases(
            formal, confirmation, analysis_revision=_HEX40
        )
        item = next(
            value
            for value in observed["contrast_results"]
            if value["contrast_id"] == secondary["contrast_id"]
        )
        self.assertEqual(item["replication_state"], "formal_only")

    def test_replication_projection_drops_bootstrap_and_raw_phase_rows(self) -> None:
        phase = _phase("formal", _HEX64_A)
        projection = target._replication_phase_projection(phase)
        self.assertNotIn("trace_contrasts", projection)
        self.assertNotIn("parent_contrasts", projection)
        self.assertTrue(
            all(
                "bootstrap_values" not in interval
                for family in projection["hierarchies"]
                for interval in family["intervals"]
            )
        )

    def test_recomputed_outer_hash_cannot_defeat_strict_source_replay(self) -> None:
        expected = _phase("formal", _HEX64_A)
        altered = deepcopy(expected)
        altered["analysis_contract"] = {"tampered": True}
        altered["evidence_fingerprint"] = target._mapping_fingerprint(
            {key: value for key, value in altered.items() if key != "evidence_fingerprint"}
        )
        dummy_sources = (
            object(),
            object(),
            {"code_revision": "d" * 40},
            [],
            {},
            {},
            _HEX40,
        )
        with patch.object(target, "_validate_phase_nested", return_value=None), patch.object(
            target, "build_phase_evidence", return_value=expected
        ), patch.object(
            target, "_verify_analysis_snapshot", return_value=None
        ):
            with self.assertRaisesRegex(StudyManifestError, "complete replay"):
                target.validate_phase_evidence(altered, sources=dummy_sources)

    def test_rehashed_forged_nested_phase_is_rejected_before_replication(self) -> None:
        forged = _phase("formal", _HEX64_A)
        forged["source_fingerprints"] = {"forged": True}
        forged["evidence_fingerprint"] = target._mapping_fingerprint(
            {key: value for key, value in forged.items() if key != "evidence_fingerprint"}
        )
        with self.assertRaisesRegex(
            StudyManifestError, "analysis contract|source_fingerprints"
        ):
            target.validate_phase_evidence(forged)

    def test_public_replication_builder_requires_both_raw_source_chains(self) -> None:
        with self.assertRaises(TypeError):
            target.build_replication_evidence(  # type: ignore[call-arg]
                Path("formal.json"),
                Path("confirmation.json"),
                analysis_revision=_HEX40,
            )

    def test_public_replication_builder_streams_phases_before_private_build(self) -> None:
        formal = _phase("formal", _HEX64_A)
        confirmation = _phase("confirmation", _HEX64_B)
        loaded_formal = (object(), object(), {"code_revision": "d" * 40}, [], {}, {})
        loaded_confirmation = (
            object(),
            object(),
            {"code_revision": "d" * 40},
            [],
            {},
            {},
        )
        expected = {"strict": True}
        formal_projection = target._replication_phase_projection(formal)
        confirmation_projection = target._replication_phase_projection(confirmation)
        with patch.object(
            target,
            "load_phase_sources",
            side_effect=[loaded_formal, loaded_confirmation],
        ) as load_sources, patch.object(
            target,
            "load_phase_evidence",
            side_effect=[formal, confirmation],
        ) as load_evidence, patch.object(
            target, "_validate_cross_phase_sources", return_value=None
        ), patch.object(
            target,
            "_build_replication_from_validated_phases",
            return_value=expected,
        ) as private_build:
            observed = target.build_replication_evidence(
                Path("formal.json"),
                Path("confirmation.json"),
                formal_source_paths=(Path("fm"),) * 5,
                confirmation_source_paths=(Path("cm"),) * 5,
                analysis_revision=_HEX40,
            )
        self.assertIs(observed, expected)
        self.assertEqual(load_sources.call_count, 2)
        self.assertEqual(load_evidence.call_count, 2)
        private_build.assert_called_once_with(
            formal_projection,
            confirmation_projection,
            analysis_revision=_HEX40,
        )

    def test_replication_releases_formal_phase_before_confirmation_load(self) -> None:
        class Phase(dict):
            pass

        formal_holder = [Phase(_phase("formal", _HEX64_A))]
        formal_ref = weakref.ref(formal_holder[0])
        confirmation = Phase(_phase("confirmation", _HEX64_B))
        loaded_formal = (object(), object(), {"code_revision": "d" * 40}, {}, {}, {})
        loaded_confirmation = (
            object(),
            object(),
            {"code_revision": "d" * 40},
            {},
            {},
            {},
        )
        source_calls = 0
        evidence_calls = 0

        def source_loader(*_paths):
            nonlocal source_calls
            source_calls += 1
            if source_calls == 1:
                return loaded_formal
            self.assertIsNone(formal_ref())
            return loaded_confirmation

        def evidence_loader(_path, **_expected):
            nonlocal evidence_calls
            evidence_calls += 1
            return formal_holder.pop() if evidence_calls == 1 else confirmation

        with patch.object(
            target, "load_phase_sources", side_effect=source_loader
        ), patch.object(
            target, "load_phase_evidence", side_effect=evidence_loader
        ), patch.object(
            target, "_validate_cross_phase_sources", return_value=None
        ), patch.object(
            target,
            "_build_replication_from_validated_phases",
            return_value={"strict": True},
        ):
            target.build_replication_evidence(
                Path("formal.json"),
                Path("confirmation.json"),
                formal_source_paths=(Path("fm"),) * 5,
                confirmation_source_paths=(Path("cm"),) * 5,
                analysis_revision=_HEX40,
            )
        self.assertEqual(source_calls, 2)
        self.assertEqual(evidence_calls, 2)

    def test_replication_nested_state_is_recomputed_without_sources(self) -> None:
        evidence = target._build_replication_from_validated_phases(
            _phase("formal", _HEX64_A),
            _phase("confirmation", _HEX64_B),
            analysis_revision=_HEX40,
        )
        forged = deepcopy(evidence)
        forged["contrast_results"][0]["formal_interval_direction"] = "harmful"
        forged["replication_fingerprint"] = target._mapping_fingerprint(
            {key: value for key, value in forged.items() if key != "replication_fingerprint"}
        )
        with self.assertRaisesRegex(StudyManifestError, "phase success"):
            target.validate_replication_evidence(forged)

        forged = deepcopy(evidence)
        forged["contrast_results"][0]["point_sign_agreement"] = "opposite"
        forged["replication_fingerprint"] = target._mapping_fingerprint(
            {key: value for key, value in forged.items() if key != "replication_fingerprint"}
        )
        with self.assertRaisesRegex(StudyManifestError, "point-sign"):
            target.validate_replication_evidence(forged)

        forged = deepcopy(evidence)
        global_row = next(
            item for item in forged["contrast_results"] if item["tier"] == "global"
        )
        global_row["formal_gate_state"] = "open"
        forged["replication_fingerprint"] = target._mapping_fingerprint(
            {key: value for key, value in forged.items() if key != "replication_fingerprint"}
        )
        with self.assertRaisesRegex(StudyManifestError, "gate state differs"):
            target.validate_replication_evidence(forged)

        forged = deepcopy(evidence)
        secondary = next(
            item for item in forged["contrast_results"] if item["tier"] == "secondary"
        )
        secondary["formal_gate_state"] = "closed"
        secondary["formal_phase_success"] = False
        secondary["replication_state"] = "confirmation_only"
        forged["replication_fingerprint"] = target._mapping_fingerprint(
            {key: value for key, value in forged.items() if key != "replication_fingerprint"}
        )
        with self.assertRaisesRegex(StudyManifestError, "same-hierarchy global"):
            target.validate_replication_evidence(forged)

        forged = deepcopy(evidence)
        forged["contrast_results"][0]["contrast_id"] = "forged.contrast"
        forged["replication_fingerprint"] = target._mapping_fingerprint(
            {key: value for key, value in forged.items() if key != "replication_fingerprint"}
        )
        with self.assertRaisesRegex(StudyManifestError, "registry"):
            target.validate_replication_evidence(forged)

    def test_nested_hierarchy_validator_recomputes_intervals_and_gates(self) -> None:
        hierarchies = _valid_hierarchies()
        target._validate_hierarchies(hierarchies)

        reversed_interval = deepcopy(hierarchies)
        reversed_interval[0]["intervals"][0]["lower"] = [1, 1]
        with self.assertRaisesRegex(StudyManifestError, "reversed|replay"):
            target._validate_hierarchies(reversed_interval)

        forged_gate = deepcopy(hierarchies)
        global_interval = next(
            item
            for item in forged_gate[0]["intervals"]
            if item["tier"] == "global"
        )
        global_interval["gate_state"] = "open"
        with self.assertRaisesRegex(StudyManifestError, "global gate"):
            target._validate_hierarchies(forged_gate)

    def test_cross_phase_provenance_sets_must_be_disjoint(self) -> None:
        common = {
            "calibration_evidence": "1" * 64,
            "formal_precision": "2" * 64,
        }
        formal = {
            "analysis_revision": _HEX40,
            "analysis_contract": target._analysis_contract(),
            "evidence_fingerprint": "3" * 64,
            "source_fingerprints": {
                **common,
                "manifest": "4" * 64,
                "seed_ledger": "5" * 64,
                "run_summary": "6" * 64,
                "block_artifacts": ["7" * 64],
                "paired_manifests": ["8" * 64],
            },
        }
        confirmation = deepcopy(formal)
        confirmation["evidence_fingerprint"] = "9" * 64
        confirmation["source_fingerprints"].update(
            manifest="a" * 64,
            seed_ledger="b" * 64,
            run_summary="c" * 64,
            block_artifacts=["d" * 64],
            paired_manifests=["e" * 64],
        )
        target._validate_cross_phase_sources(formal, confirmation, _HEX40)
        confirmation["source_fingerprints"]["block_artifacts"] = ["7" * 64]
        with self.assertRaisesRegex(StudyManifestError, "overlap"):
            target._validate_cross_phase_sources(formal, confirmation, _HEX40)

        confirmation["source_fingerprints"]["block_artifacts"] = ["d" * 64]
        confirmation["source_fingerprints"]["run_summary"] = "4" * 64
        with self.assertRaisesRegex(StudyManifestError, "overlap"):
            target._validate_cross_phase_sources(formal, confirmation, _HEX40)

    def test_snapshot_rejects_untracked_execution_dependency(self) -> None:
        completed = [
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout="secondaryexploration/rogue.py\n"),
        ]
        with patch.object(target.subprocess, "run", side_effect=completed):
            with self.assertRaisesRegex(StudyManifestError, "untracked"):
                target._verify_analysis_snapshot(Path("."), _HEX40, "d" * 40)

    def test_evidence_output_is_confined_and_cannot_equal_an_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "manifest.json"
            with self.assertRaisesRegex(StudyManifestError, "results/inference"):
                target._evidence_target(root, "outside.json", [source])
            target_path = target._evidence_target(
                root, "results/inference/formal.json", [source]
            )
            self.assertEqual(target_path, root / "results/inference/formal.json")
            nested_input = root / "results" / "inference" / "same.json"
            with self.assertRaisesRegex(StudyManifestError, "overwrite"):
                target._evidence_target(root, nested_input, [nested_input])


if __name__ == "__main__":
    unittest.main()
