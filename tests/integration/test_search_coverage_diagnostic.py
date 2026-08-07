"""Source-bound replay of the frozen training-only search diagnostic."""

from __future__ import annotations

from pathlib import Path
import unittest

from secondaryexploration.analysis.search_coverage import (
    load_search_coverage_diagnostic,
)
from secondaryexploration.experiments import (
    build_study_seed_ledger,
    load_study_design_manifest,
)


_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _ROOT / "configs" / "pilot" / "synthetic-pipeline-v1.json"
_DIAGNOSTIC = (
    _ROOT / "results" / "pilot" / "synthetic-pipeline-v1" / "search-coverage.json"
)


class SearchCoverageDiagnosticTests(unittest.TestCase):
    def test_tracked_diagnostic_replays_from_training_inputs_only(self) -> None:
        manifest = load_study_design_manifest(_MANIFEST)
        ledger = build_study_seed_ledger(manifest)
        diagnostic = load_search_coverage_diagnostic(
            _DIAGNOSTIC,
            manifest=manifest,
            ledger=ledger,
            source_replay=True,
        )
        self.assertEqual(
            diagnostic["diagnostic_fingerprint"],
            "1baceb77d3f98afe9ee425f2e3b1fe9c3f111a9351abe886f5b7c96bcbf9c781",
        )
        self.assertFalse(diagnostic["held_out_accessed"])
        self.assertEqual(
            [item["changed_block_count"] for item in diagnostic["summaries"]],
            [1, 3, 4],
        )
        self.assertEqual(
            [item["proposal_budget"] for item in diagnostic["summaries"]],
            [120, 1_000, 5_000],
        )

if __name__ == "__main__":
    unittest.main()
