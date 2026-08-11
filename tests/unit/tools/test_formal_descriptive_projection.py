"""Tests for the result-blind descriptive mechanism projection."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import json
import tempfile
import unittest
import weakref

from secondaryexploration.experiments import (
    StudyManifestError,
    build_study_seed_ledger,
    load_study_design_manifest,
)
from secondaryexploration.experiments.artifacts import (
    load_study_run_summary,
    load_synthetic_block_artifact,
    validate_synthetic_block_artifact,
)
from secondaryexploration.experiments import artifacts as artifact_contract
from secondaryexploration.experiments.runner import runtime_environment
from tools import formal_descriptive_projection as target


_ROOT = Path(__file__).resolve().parents[3]
_HEX40 = "c" * 40


def _zero_parent_rows(manifest, artifact):
    block = artifact["block"]
    parent_id = target.primary._block_key(block)
    rows = []
    for source in target.primary._SOURCES:
        for metric in target._METRICS:
            dynamic = metric in target._DYNAMIC_METRICS
            rows.append(
                target._parent_row(
                    manifest.phase.value,
                    block["node_count"],
                    block["parent_model"],
                    block["parent_replicate"],
                    parent_id,
                    source,
                    metric,
                    Fraction(0) if dynamic else None,
                    Fraction(0) if dynamic else None,
                    Fraction(0),
                )
            )
    return sorted(rows, key=target._parent_sort_key)


class FormalDescriptiveProjectionTests(unittest.TestCase):
    def test_metric_primitives_are_exact(self) -> None:
        topology = [
            ["a", "b", "c"],
            [["e1", ["a", "b"]], ["e2", ["b", "c"]]],
        ]
        state = [
            ["e1", [["a", 6], ["b", 2]]],
            ["e2", [["b", 3], ["c", 0]]],
        ]
        self.assertEqual(
            target._topology_metrics(topology),
            {
                "topology_pair_coverage_fraction": Fraction(2, 3),
                "topology_mean_pair_multiplicity_covered": Fraction(1),
            },
        )
        self.assertEqual(
            target._state_metrics(state, topology),
            (Fraction(3, 8), Fraction(1, 4)),
        )
        final_state = [
            ["e1", [["a", 5], ["b", 3]]],
            ["e2", [["b", 2], ["c", 1]]],
        ]
        simulation = [
            state,
            [
                [
                    1,
                    ["a", "c", 1],
                    [["e1", "a", "b"], ["e2", "b", "c"]],
                    2,
                    [5, 8],
                    1,
                    [],
                ],
                [2, ["c", "a", 10], None, None, None, 0, []],
            ],
            final_state,
            [True, 0],
            [True, 2],
            [True, 2],
        ]
        costs = {
            "traversed_hyperedge_count": 2,
            "signaled_participant_slots": 4,
            "quadratic_coordination_exposure": 8,
            "unique_signaled_participants": 3,
            "route_arity_histogram": [[2, 2]],
        }
        initial, metrics = target._simulation_metrics(
            simulation,
            topology,
            costs,
            expected_horizon=2,
            routing_root_seed=123,
        )
        self.assertEqual(initial, state)
        self.assertEqual(metrics["final_coordinate_imbalance"], Fraction(7, 48))
        self.assertEqual(metrics["final_zero_coordinate_fraction"], Fraction(0))
        self.assertEqual(
            metrics["optimal_route_multiplicity_mass_per_attempt"], Fraction(1, 2)
        )
        self.assertEqual(
            metrics["multiple_optimal_route_fraction_per_attempt"], Fraction(0)
        )
        self.assertEqual(metrics["route_bottleneck_mass_per_attempt"], Fraction(5, 16))
        self.assertEqual(metrics["route_hop_mass_per_attempt"], Fraction(1))
        self.assertEqual(
            metrics["quadratic_coordination_exposure_per_attempt"], Fraction(4)
        )

    def test_real_pilot_block_projects_all_frozen_metrics(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/pilot/synthetic-calibration-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        seed = next(
            item
            for item in ledger.parent_seeds
            if item.node_count == 30 and item.parent_replicate == 0
        )
        artifact = load_synthetic_block_artifact(
            _ROOT
            / "outputs/pilot/synthetic-calibration-v1/blocks/"
            "n0030-r0000-er_gnm.json",
            manifest=manifest,
            ledger=ledger,
            parent_seed=seed,
            parent_model="er_gnm",
        )
        rows = target._project_block(manifest, artifact)
        self.assertEqual(len(rows), 4 * len(target._METRICS))
        self.assertEqual(
            {(row["source_family"], row["metric"]) for row in rows},
            {
                (source, metric)
                for source in target.primary._SOURCES
                for metric in target._METRICS
            },
        )
        for row in rows:
            if row["metric"] in target._STATIC_METRICS:
                self.assertIsNone(row["same_distribution_mean"])
                self.assertIsNone(row["distribution_shift_mean"])
            else:
                same = Fraction(*row["same_distribution_mean"])
                shifted = Fraction(*row["distribution_shift_mean"])
                self.assertEqual(
                    Fraction(*row["combined_parent_value"]),
                    Fraction(4, 7) * same + Fraction(3, 7) * shifted,
                )

    def test_exact_replay_rejects_rehashed_router_metadata_tamper(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/pilot/synthetic-calibration-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        seed = next(
            item
            for item in ledger.parent_seeds
            if item.node_count == 30 and item.parent_replicate == 0
        )
        artifact = load_synthetic_block_artifact(
            _ROOT
            / "outputs/pilot/synthetic-calibration-v1/blocks/"
            "n0030-r0000-er_gnm.json",
            manifest=manifest,
            ledger=ledger,
            parent_seed=seed,
            parent_model="er_gnm",
        )
        tampered = deepcopy(artifact)
        simulation = tampered["result_witness"]["held_out"][0][4][0][1]
        accepted = next(outcome for outcome in simulation[1] if outcome[2] is not None)
        accepted[5] += 1
        tampered["result_fingerprint"] = artifact_contract._json_fingerprint(
            tampered["result_witness"]
        )
        without_outer = dict(tampered)
        without_outer.pop("artifact_fingerprint")
        tampered["artifact_fingerprint"] = artifact_contract._mapping_fingerprint(
            without_outer
        )

        # This records the exact historical gap that the projection must close:
        # the base compact artifact contract does not consume tied_route_count.
        validate_synthetic_block_artifact(
            tampered,
            manifest=manifest,
            ledger=ledger,
            parent_seed=seed,
            parent_model="er_gnm",
        )
        with self.assertRaisesRegex(StudyManifestError, "exact paired route-choice"):
            target._project_block(manifest, tampered)

    def test_projection_rejects_rehashed_duplicate_binary_arm(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/pilot/synthetic-calibration-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        seed = next(
            item
            for item in ledger.parent_seeds
            if item.node_count == 30 and item.parent_replicate == 0
        )
        artifact = load_synthetic_block_artifact(
            _ROOT
            / "outputs/pilot/synthetic-calibration-v1/blocks/"
            "n0030-r0000-er_gnm.json",
            manifest=manifest,
            ledger=ledger,
            parent_seed=seed,
            parent_model="er_gnm",
        )
        tampered = deepcopy(artifact)
        panel = tampered["resource_panels"][0]
        panel["binary_variant_ids"].append(panel["binary_variant_ids"][0])
        panel["binary_incidence_deltas"].append(
            panel["binary_incidence_deltas"][0]
        )
        witness_panel = tampered["result_witness"]["panels"][0]
        witness_panel[2].append(witness_panel[2][0])
        witness_panel[4].append(witness_panel[4][0])
        tampered["result_fingerprint"] = artifact_contract._json_fingerprint(
            tampered["result_witness"]
        )
        without_outer = dict(tampered)
        without_outer.pop("artifact_fingerprint")
        tampered["artifact_fingerprint"] = artifact_contract._mapping_fingerprint(
            without_outer
        )
        validate_synthetic_block_artifact(
            tampered,
            manifest=manifest,
            ledger=ledger,
            parent_seed=seed,
            parent_model="er_gnm",
        )
        with self.assertRaisesRegex(StudyManifestError, "must be unique"):
            target._project_block(manifest, tampered)

    def test_exact_replay_rejects_rehashed_final_state_tamper(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/pilot/synthetic-calibration-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        seed = next(
            item
            for item in ledger.parent_seeds
            if item.node_count == 30 and item.parent_replicate == 0
        )
        artifact = load_synthetic_block_artifact(
            _ROOT
            / "outputs/pilot/synthetic-calibration-v1/blocks/"
            "n0030-r0000-er_gnm.json",
            manifest=manifest,
            ledger=ledger,
            parent_seed=seed,
            parent_model="er_gnm",
        )
        tampered = deepcopy(artifact)
        witnessed = tampered["result_witness"]["held_out"][0][4][0]
        variant_id, simulation = witnessed
        final_state = simulation[2]
        balances = next(
            edge[1]
            for edge in final_state
            if len(edge[1]) >= 2 and edge[1][0][1] > 0
        )
        balances[0][1] -= 1
        balances[1][1] += 1
        topology = next(
            item[2]
            for item in tampered["result_witness"]["variants"]
            if item[0] == variant_id
        )
        summary_variant = next(
            item
            for item in tampered["held_out"][0]["variants"]
            if item["variant_id"] == variant_id
        )
        summary_variant["final_state_fingerprint"] = (
            artifact_contract._json_fingerprint(
                {"nodes": topology[0], "hyperedges": final_state}
            )
        )
        tampered["result_fingerprint"] = artifact_contract._json_fingerprint(
            tampered["result_witness"]
        )
        without_outer = dict(tampered)
        without_outer.pop("artifact_fingerprint")
        tampered["artifact_fingerprint"] = artifact_contract._mapping_fingerprint(
            without_outer
        )
        validate_synthetic_block_artifact(
            tampered,
            manifest=manifest,
            ledger=ledger,
            parent_seed=seed,
            parent_model="er_gnm",
        )
        with self.assertRaisesRegex(StudyManifestError, "exact paired route-choice"):
            target._project_block(manifest, tampered)

    def test_complete_projection_streams_one_artifact_and_has_no_inference(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/formal/synthetic-formal-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        environment = runtime_environment()
        records = []
        for index, key in enumerate(target.primary._expected_block_keys(), start=1):
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
        summary = target.primary._summary_from_stream_records(
            manifest,
            ledger,
            code_revision=target.EXECUTION_REVISION,
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
            )
            previous = weakref.ref(artifact)
            return artifact

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            blocks = output / "blocks"
            (blocks / ".locks").mkdir(parents=True)
            for record in records:
                (blocks / f"{record['block_key']}.json").write_bytes(b"{}")
            evidence = target.build_phase_projection(
                manifest,
                ledger,
                summary,
                {"evidence_fingerprint": "d" * 64},
                {"precision_fingerprint": "e" * 64},
                output_root=output,
                projection_revision=_HEX40,
                artifact_loader=loader,
                block_projector=_zero_parent_rows,
            )
            evidence_path = output / "projection.json"
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            loaded = target.load_phase_projection(
                evidence_path,
                manifest=manifest,
                ledger=ledger,
                summary=summary,
                calibration={"evidence_fingerprint": "d" * 64},
                precision={"precision_fingerprint": "e" * 64},
                output_root=output,
                projection_revision=_HEX40,
                artifact_loader=loader,
                block_projector=_zero_parent_rows,
            )
            self.assertEqual(loaded, evidence)
            semantic_tamper = deepcopy(evidence)
            semantic_tamper["parent_contrasts"][0]["combined_parent_value"] = [1, 1]
            semantic_tamper["summaries"] = target._build_summaries(
                "formal", semantic_tamper["parent_contrasts"]
            )
            semantic_tamper["projection_fingerprint"] = (
                target.primary._mapping_fingerprint(
                    {
                        key: value
                        for key, value in semantic_tamper.items()
                        if key != "projection_fingerprint"
                    }
                )
            )
            target.validate_phase_projection(semantic_tamper)
            semantic_path = output / "semantic-tamper.json"
            semantic_path.write_text(
                json.dumps(
                    semantic_tamper, ensure_ascii=False, separators=(",", ":")
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                StudyManifestError, "complete replay mismatch"
            ):
                target.load_phase_projection(
                    semantic_path,
                    manifest=manifest,
                    ledger=ledger,
                    summary=summary,
                    calibration={"evidence_fingerprint": "d" * 64},
                    precision={"precision_fingerprint": "e" * 64},
                    output_root=output,
                    projection_revision=_HEX40,
                    artifact_loader=loader,
                    block_projector=_zero_parent_rows,
                )
        self.assertEqual(calls, 720)
        self.assertIsNone(previous())
        self.assertEqual(len(evidence["parent_contrasts"]), 12_480)
        self.assertEqual(len(evidence["summaries"]), 208)
        keys = set()

        def collect_keys(value):
            if isinstance(value, dict):
                keys.update(value)
                for item in value.values():
                    collect_keys(item)
            elif isinstance(value, list):
                for item in value:
                    collect_keys(item)

        collect_keys(evidence)
        self.assertNotIn("interval", keys)
        self.assertNotIn("p_value", keys)
        target.validate_phase_projection(evidence)

        tampered = deepcopy(evidence)
        tampered["parent_contrasts"][0]["p_value"] = [1, 2]
        tampered["projection_fingerprint"] = target.primary._mapping_fingerprint(
            {key: value for key, value in tampered.items() if key != "projection_fingerprint"}
        )
        with self.assertRaisesRegex(StudyManifestError, "fields differ"):
            target.validate_phase_projection(tampered)

    def test_projection_requires_complete_frozen_execution_summary(self) -> None:
        manifest = load_study_design_manifest(
            _ROOT / "configs/formal/synthetic-formal-v1.json"
        )
        ledger = build_study_seed_ledger(manifest)
        summary = {
            "status": "in_progress",
            "completed_block_count": 166,
        }
        with self.assertRaisesRegex(StudyManifestError, "complete 240"):
            target.build_phase_projection(
                manifest,
                ledger,
                summary,
                {},
                {},
                output_root=Path("unused"),
                projection_revision=_HEX40,
            )


if __name__ == "__main__":
    unittest.main()
