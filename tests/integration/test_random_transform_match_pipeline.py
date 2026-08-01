"""Primary-grid integration from parent draws through binary budget matches."""

from __future__ import annotations

import unittest

from secondaryexploration.randomness import derive_seed
from secondaryexploration.topology import (
    closed_neighborhood_nch,
    fixed_hyperedge_size,
    matched_synthetic_parent_graphs,
    match_binary_to_topology,
)


class RandomTransformMatchPipelineTests(unittest.TestCase):
    def test_primary_grid_has_declared_exact_and_bracketed_cells(self) -> None:
        exact_cells = 0
        bracketed_cells = 0
        checked = 0
        for replicate_index, node_count in enumerate((30, 60, 120, 240)):
            target_edges = 3 * (node_count - 3)
            ensemble = matched_synthetic_parent_graphs(
                node_count=node_count,
                attachment_count=3,
                block_count=4,
                sbm_within_edge_count=3 * target_edges // 4,
                base_seed=20260731,
                replicate_index=replicate_index,
                max_attempts=1_000,
            )
            root_seed = derive_seed(
                20260731,
                "binary.match",
                replicate_index,
            )
            for draw in ensemble.draws:
                transformed = (
                    closed_neighborhood_nch(draw.graph),
                    fixed_hyperedge_size(draw.graph, 3),
                    fixed_hyperedge_size(draw.graph, 5),
                )
                for source in transformed:
                    match = match_binary_to_topology(
                        draw.graph,
                        source,
                        root_seed=root_seed,
                    )
                    self.assertTrue(match.lower.is_connected)
                    self.assertTrue(match.upper.is_connected)
                    self.assertEqual(match.lower.nodes, source.nodes)
                    self.assertEqual(match.upper.nodes, source.nodes)
                    if match.is_exact:
                        exact_cells += 1
                    else:
                        bracketed_cells += 1
                    checked += 1

        self.assertEqual(checked, 36)
        self.assertEqual(exact_cells, 16)
        self.assertEqual(bracketed_cells, 20)


if __name__ == "__main__":
    unittest.main()
