"""Registered train-once and held-out execution for one synthetic parent block."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from secondaryexploration.experiments import (
    StudyManifestError,
    TrafficRegimeRole,
    build_study_seed_ledger,
    generate_declared_request_trace,
    load_study_design_manifest,
)
from secondaryexploration.experiments.pipeline import run_synthetic_parent_block
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


if __name__ == "__main__":
    unittest.main()
