"""Integration checks for exactly matched synthetic parent ensembles."""

from __future__ import annotations

from fractions import Fraction
import unittest

from secondaryexploration.topology import matched_synthetic_parent_graphs


class MatchedParentEnsembleTests(unittest.TestCase):
    def test_primary_sizes_match_nodes_edges_and_mean_degree(self) -> None:
        for replicate_index, node_count in enumerate((30, 60, 120, 240)):
            attachment_count = 3
            target_edges = attachment_count * (node_count - attachment_count)
            within_edges = 3 * target_edges // 4
            with self.subTest(node_count=node_count):
                ensemble = matched_synthetic_parent_graphs(
                    node_count=node_count,
                    attachment_count=attachment_count,
                    block_count=4,
                    sbm_within_edge_count=within_edges,
                    base_seed=20260731,
                    replicate_index=replicate_index,
                    max_attempts=1_000,
                )

                graphs = tuple(draw.graph for draw in ensemble.draws)
                self.assertTrue(all(graph.is_connected for graph in graphs))
                self.assertEqual({graph.nodes for graph in graphs}, {graphs[0].nodes})
                self.assertEqual(
                    {graph.edge_count for graph in graphs},
                    {target_edges},
                )
                self.assertEqual(
                    {graph.mean_degree for graph in graphs},
                    {Fraction(2 * target_edges, node_count)},
                )
                self.assertEqual(
                    tuple(len(block) for block in ensemble.blocks),
                    tuple(
                        sorted(
                            tuple(len(block) for block in ensemble.blocks),
                            reverse=True,
                        )
                    ),
                )

    def test_builder_replays_and_namespaces_models(self) -> None:
        kwargs = dict(
            node_count=18,
            attachment_count=2,
            block_count=3,
            sbm_within_edge_count=20,
            base_seed=41,
            replicate_index=7,
            max_attempts=500,
        )
        first = matched_synthetic_parent_graphs(**kwargs)
        second = matched_synthetic_parent_graphs(**kwargs)

        self.assertEqual(first, second)
        self.assertEqual(len({draw.root_seed for draw in first.draws}), 3)
        self.assertEqual(first.target_edge_count, 32)


if __name__ == "__main__":
    unittest.main()
