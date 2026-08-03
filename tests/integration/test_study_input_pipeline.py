"""End-to-end generation of all parent and trace inputs in the pilot manifest."""

from __future__ import annotations

from pathlib import Path
import unittest

from secondaryexploration.experiments import (
    build_study_seed_ledger,
    generate_declared_parent_ensemble,
    generate_declared_request_trace,
    load_study_design_manifest,
)


_ROOT = Path(__file__).resolve().parents[2]
_PILOT = _ROOT / "configs" / "pilot" / "synthetic-pipeline-v1.json"


class StudyInputPipelineIntegrationTests(unittest.TestCase):
    def test_every_registered_parent_and_trace_replays_from_the_ledger(self) -> None:
        manifest = load_study_design_manifest(_PILOT)
        ledger = build_study_seed_ledger(manifest)

        for record in ledger.parent_seeds:
            with self.subTest(parent_size=record.node_count):
                ensemble = generate_declared_parent_ensemble(manifest, record)
                cell = manifest.size_cell(record.node_count)
                self.assertEqual(
                    tuple(draw.graph.edge_count for draw in ensemble.draws),
                    (cell.target_edge_count,) * 3,
                )
                self.assertEqual(
                    tuple(draw.graph.nodes for draw in ensemble.draws),
                    (ensemble.er.graph.nodes,) * 3,
                )
                self.assertEqual(
                    ensemble,
                    generate_declared_parent_ensemble(manifest, record),
                )

        for record in ledger.trace_seeds:
            with self.subTest(
                trace_size=record.node_count,
                split=record.split,
                regime=record.regime_id,
            ):
                trace = generate_declared_request_trace(manifest, record)
                self.assertEqual(
                    trace.length,
                    record.node_count * manifest.requests_per_node,
                )
                self.assertEqual(trace.root_seed, record.trace_root_seed)
                self.assertEqual(
                    trace,
                    generate_declared_request_trace(manifest, record),
                )


if __name__ == "__main__":
    unittest.main()
