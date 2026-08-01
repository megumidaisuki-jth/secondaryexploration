"""Finite seeded grids for random parent-graph invariants."""

from __future__ import annotations

import unittest

from secondaryexploration.topology import (
    barabasi_albert_parent_graph,
    connected_gnm_parent_graph,
    connected_sbm_parent_graph,
)


class RandomGraphInvariantTests(unittest.TestCase):
    def test_seed_grid_preserves_exact_family_contracts(self) -> None:
        checked = 0
        for node_count in range(6, 13):
            edge_count = 2 * (node_count - 2)
            within_count = edge_count // 2
            for root_seed in range(12):
                with self.subTest(node_count=node_count, root_seed=root_seed):
                    er = connected_gnm_parent_graph(
                        node_count,
                        edge_count,
                        root_seed=root_seed,
                        max_attempts=2_000,
                    )
                    ba = barabasi_albert_parent_graph(
                        node_count,
                        2,
                        root_seed=root_seed,
                    )
                    sbm = connected_sbm_parent_graph(
                        (node_count // 2, node_count - node_count // 2),
                        edge_count,
                        within_count,
                        root_seed=root_seed,
                        max_attempts=2_000,
                    )

                    for draw in (er, ba, sbm):
                        self.assertTrue(draw.graph.is_connected)
                        self.assertEqual(draw.graph.edge_count, edge_count)
                        self.assertEqual(len(set(draw.graph.edges)), edge_count)
                    checked += 3

        self.assertEqual(checked, 252)


if __name__ == "__main__":
    unittest.main()
