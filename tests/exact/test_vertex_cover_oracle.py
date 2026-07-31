"""Exact small-graph audit of the canonical local-ratio vertex cover."""

from __future__ import annotations

from itertools import combinations
import unittest

from secondaryexploration.topology import (
    ParentGraph,
    canonical_local_ratio_vertex_cover,
)


def exact_minimum_cover_size(graph: ParentGraph) -> int:
    for size in range(len(graph.nodes) + 1):
        for candidate in combinations(graph.nodes, size):
            selected = set(candidate)
            if all(
                edge.left in selected or edge.right in selected
                for edge in graph.edges
            ):
                return size
    raise AssertionError("finite graph must have a vertex cover")


class LocalRatioVertexCoverTests(unittest.TestCase):
    def test_known_canonical_path_output_matches_frozen_algorithm(self) -> None:
        graph = ParentGraph.from_edges(
            nodes=("a", "b", "c", "d"),
            edges=(("a", "b"), ("b", "c"), ("c", "d")),
        )

        self.assertEqual(
            canonical_local_ratio_vertex_cover(graph),
            ("a", "b", "c"),
        )

    def test_all_labeled_graphs_through_five_nodes_are_covered_within_two_opt(
        self,
    ) -> None:
        checked_graphs = 0
        labels = ("a", "b", "c", "d", "e")
        for node_count in range(1, 6):
            nodes = labels[:node_count]
            possible_edges = tuple(combinations(nodes, 2))
            for mask in range(1 << len(possible_edges)):
                selected_edges = tuple(
                    edge
                    for index, edge in enumerate(possible_edges)
                    if mask & (1 << index)
                )
                graph = ParentGraph.from_edges(nodes, selected_edges)
                cover = canonical_local_ratio_vertex_cover(graph)
                cover_set = set(cover)
                optimum = exact_minimum_cover_size(graph)

                self.assertEqual(tuple(sorted(cover)), cover)
                self.assertTrue(
                    all(
                        edge.left in cover_set or edge.right in cover_set
                        for edge in graph.edges
                    )
                )
                self.assertLessEqual(len(cover), 2 * optimum)
                self.assertEqual(
                    cover,
                    canonical_local_ratio_vertex_cover(graph),
                )
                checked_graphs += 1

        self.assertEqual(checked_graphs, 1_099)


if __name__ == "__main__":
    unittest.main()
