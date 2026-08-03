"""Registered train-once and held-out execution for one synthetic parent block."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from secondaryexploration.experiments import (
    StudyManifestError,
    TrafficRegimeRole,
    build_study_seed_ledger,
    generate_declared_request_trace,
    load_study_design_manifest,
)
from secondaryexploration.experiments.pipeline import run_synthetic_parent_block
from secondaryexploration.experiments.artifacts import (
    atomic_write_json,
    build_study_run_summary,
    build_synthetic_block_artifact,
    load_synthetic_block_artifact,
    validate_synthetic_block_artifact,
)
from secondaryexploration.experiments.runner import execute_synthetic_study
from secondaryexploration.optimization import DirectedDemandMatrix
from secondaryexploration.topology import (
    HypergraphTopology,
    ParentGraphModel,
    node_capital_totals,
)


_ROOT = Path(__file__).resolve().parents[2]
_PILOT = _ROOT / "configs" / "pilot" / "synthetic-pipeline-v1.json"


class SyntheticParentBlockPipelineTests(unittest.TestCase):
    def test_small_registered_er_block_trains_once_and_evaluates_only_test_traces(self) -> None:
        tracked = load_study_design_manifest(_PILOT)
        manifest = replace(
            tracked,
            study_id="synthetic-pipeline-integration",
            output_root="outputs/tests/synthetic-pipeline-integration",
            size_cells=(tracked.size_cells[0],),
            requests_per_node=1,
            topology_search=replace(
                tracked.topology_search,
                proposal_budget=12,
                maximum_rounds=1,
            ),
            capacity_search=replace(
                tracked.capacity_search,
                evaluation_budget=2,
            ),
        )
        ledger = build_study_seed_ledger(manifest)
        parent_seed = ledger.parent_seeds[0]

        result = run_synthetic_parent_block(
            manifest,
            parent_seed,
            ParentGraphModel.ER_GNM,
        )

        training_records = tuple(
            item
            for item in ledger.trace_seeds
            if item.split == "training" and item.node_count == 30
        )
        independently_aggregated = DirectedDemandMatrix.from_requests(
            result.parent_draw.graph.nodes,
            tuple(
                request
                for record in training_records
                for request in generate_declared_request_trace(manifest, record).requests
            ),
        )
        self.assertEqual(result.training_demand, independently_aggregated)
        self.assertEqual(len(result.training_trace_seeds), 4)
        self.assertEqual(len(result.panels), 4)
        self.assertEqual(len(result.clique_cost_references), 4)
        self.assertEqual(len(result.held_out_runs), 7)
        self.assertEqual(
            tuple(item.trace_seed.regime_id for item in result.held_out_runs),
            tuple(
                item.regime_id
                for item in manifest.regimes
                if item.role is TrafficRegimeRole.TEST
            ),
        )

        variant_ids = tuple(item.variant_id for item in result.variants)
        self.assertEqual(len(variant_ids), len(set(variant_ids)))
        demand_panel = next(item for item in result.panels if item.panel_id == "panel-demand-aware")
        fhs5_panel = next(item for item in result.panels if item.panel_id == "panel-fhs5")
        self.assertEqual(demand_panel.binary_variant_ids, fhs5_panel.binary_variant_ids)
        self.assertEqual(len(result.variants), 10)

        for variant in result.variants:
            with self.subTest(variant=variant.variant_id):
                self.assertEqual(variant.capacity_result.evaluation_count, 2)
                self.assertEqual(
                    node_capital_totals(variant.initial_state),
                    tuple((node_id, 120) for node_id in variant.topology.nodes),
                )
        for held_out in result.held_out_runs:
            self.assertEqual(held_out.result.horizon, 30)
            self.assertEqual(
                tuple(item.variant_id for item in held_out.result.variant_results),
                variant_ids,
            )
        self.assertEqual(
            result.fingerprint,
            "d5dac2b4ece91f38b87d64e4f58bdc37091bbe2bb8e4c2f7be34d3d813d7171e",
        )

        altered_parent_seed = replace(
            result.parent_seed,
            capacity_search_seed=result.parent_seed.capacity_search_seed ^ 1,
        )
        self.assertNotEqual(
            replace(result, parent_seed=altered_parent_seed).fingerprint,
            result.fingerprint,
        )

        altered_score = replace(
            result.demand_aware_result.score,
            captured_bidirectional=(
                result.demand_aware_result.score.captured_bidirectional + 1
            ),
        )
        altered_demand_result = replace(
            result.demand_aware_result,
            score=altered_score,
        )
        altered_result = replace(
            result,
            demand_aware_result=altered_demand_result,
        )
        self.assertNotEqual(altered_result.fingerprint, result.fingerprint)

        reference = result.clique_cost_references[0]
        isolated_topology = HypergraphTopology(
            nodes=tuple(sorted(reference.topology.nodes + ("isolated-audit-node",))),
            hyperedges=reference.topology.hyperedges,
        )
        altered_reference = replace(reference, topology=isolated_topology)
        with self.assertRaisesRegex(StudyManifestError, "exact source clique expansion"):
            replace(
                result,
                clique_cost_references=(altered_reference,)
                + result.clique_cost_references[1:],
            )

        environment = {
            "python_implementation": "cpython",
            "python_version": "3.12.0",
            "platform_system": "test-platform",
            "machine": "test-machine",
        }
        artifact = build_synthetic_block_artifact(
            result,
            code_revision="a" * 40,
            environment=environment,
            generation_ns=123,
            validation_ns=456,
        )
        self.assertEqual(artifact["result_fingerprint"], result.fingerprint)
        self.assertEqual(len(artifact["variants"]), 10)
        self.assertEqual(len(artifact["held_out"]), 7)
        validate_synthetic_block_artifact(
            artifact,
            manifest=manifest,
            ledger=ledger,
            parent_seed=parent_seed,
            parent_model=ParentGraphModel.ER_GNM.value,
            code_revision="a" * 40,
            environment=environment,
        )

        with TemporaryDirectory() as directory:
            artifact_path = Path(directory) / "block.json"
            atomic_write_json(artifact_path, artifact)
            loaded = load_synthetic_block_artifact(
                artifact_path,
                manifest=manifest,
                ledger=ledger,
                parent_seed=parent_seed,
                parent_model=ParentGraphModel.ER_GNM.value,
                code_revision="a" * 40,
                environment=environment,
            )
            self.assertTrue(loaded == json.loads(json.dumps(artifact)))

            summary = build_study_run_summary(
                manifest,
                ledger,
                code_revision="a" * 40,
                environment=environment,
                block_artifacts=[artifact],
            )
            self.assertEqual(summary["status"], "in_progress")
            self.assertEqual(summary["expected_block_count"], 3)
            self.assertEqual(summary["total_generation_ns"], 123)

        tampered = json.loads(json.dumps(artifact))
        tampered["variants"][0]["unknown_result"] = 1
        _refingerprint(tampered)
        with self.assertRaises(StudyManifestError):
            validate_synthetic_block_artifact(tampered)

        attacks = []
        fake_result = json.loads(json.dumps(artifact))
        fake_result["result_fingerprint"] = "f" * 64
        attacks.append(("result", fake_result, {}))
        false_science = json.loads(json.dumps(artifact))
        false_science["held_out"][0]["variants"][0]["accepted_request_count"] = -999
        attacks.append(("summary", false_science, {}))
        plausible_science = json.loads(json.dumps(artifact))
        plausible_variant = plausible_science["held_out"][0]["variants"][0]
        changed_count = (
            plausible_variant["accepted_request_count"] - 1
            if plausible_variant["accepted_request_count"] > 0
            else 1
        )
        plausible_variant["accepted_request_count"] = changed_count
        plausible_variant["accepted_value"] = changed_count
        plausible_variant["success_rate"] = [changed_count, plausible_variant["horizon"]]
        attacks.append(("plausible-summary", plausible_science, {}))
        wrong_family = json.loads(json.dumps(artifact))
        wrong_family["held_out"][0]["variants"][0]["family"] = "wrong-family"
        attacks.append(("held-out-family", wrong_family, {}))
        coordinated_demand = json.loads(json.dumps(artifact))
        coordinated_demand["training"]["demand_fingerprint"] = "f" * 64
        coordinated_demand["result_witness"]["training_demand"] = "f" * 64
        coordinated_demand["result_fingerprint"] = _fingerprint_json(
            coordinated_demand["result_witness"]
        )
        attacks.append(("coordinated-demand", coordinated_demand, {"context": True}))
        fake_draw = json.loads(json.dumps(artifact))
        fake_draw["block"]["draw_seed"] = 0
        attacks.append(("draw", fake_draw, {"context": True}))
        mixed_training = json.loads(json.dumps(artifact))
        mixed_training["training"]["trace_seeds"][0]["split"] = "test"
        attacks.append(("training", mixed_training, {"context": True}))
        mixed_held_out = json.loads(json.dumps(artifact))
        mixed_held_out["held_out"][0]["trace_seed"]["parent_replicate"] = 999
        attacks.append(("held-out", mixed_held_out, {"context": True}))
        bad_resources = json.loads(json.dumps(artifact))
        bad_resources["variants"][0]["resources"]["incidence_count"] = 0
        attacks.append(("resources", bad_resources, {"context": True}))
        for name, attack, options in attacks:
            with self.subTest(artifact_attack=name):
                _refingerprint(attack)
                expected = (
                    {
                        "manifest": manifest,
                        "ledger": ledger,
                        "parent_seed": parent_seed,
                        "parent_model": ParentGraphModel.ER_GNM.value,
                        "code_revision": "a" * 40,
                        "environment": environment,
                    }
                    if options
                    else {}
                )
                with self.assertRaises(StudyManifestError):
                    validate_synthetic_block_artifact(attack, **expected)

        with self.assertRaisesRegex(StudyManifestError, "complete regeneration"):
            build_study_run_summary(
                replace(manifest, study_id="mixed-manifest"),
                ledger,
                code_revision="a" * 40,
                environment=environment,
                block_artifacts=[artifact],
            )

        with TemporaryDirectory() as directory:
            nonfinite_path = Path(directory) / "nonfinite.json"
            with self.assertRaisesRegex(StudyManifestError, "strict canonical JSON"):
                atomic_write_json(nonfinite_path, {"value": float("nan")})
            self.assertFalse(nonfinite_path.exists())
            with self.assertRaisesRegex(StudyManifestError, "full lowercase Git SHA-1"):
                execute_synthetic_study(
                    _PILOT,
                    workspace_root=directory,
                    code_revision="bad",
                )


def _refingerprint(artifact: dict[str, object]) -> None:
    artifact.pop("artifact_fingerprint", None)
    artifact["artifact_fingerprint"] = _fingerprint_json(artifact)


def _fingerprint_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    unittest.main()
