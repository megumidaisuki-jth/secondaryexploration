"""Exhaustive small-graph invariants for binary incidence matching."""

from __future__ import annotations

from itertools import combinations
import unittest

from secondaryexploration.topology import ParentGraph, binary_incidence_match


def all_connected_labeled_graphs(node_count: int):
    nodes = tuple(f"v{index:08d}" for index in range(node_count))
    candidates = tuple(combinations(nodes, 2))
    for mask in range(1 << len(candidates)):
        edges = tuple(
            edge for index, edge in enumerate(candidates) if mask & (1 << index)
        )
        graph = ParentGraph.from_edges(nodes, edges)
        if graph.is_connected:
            yield graph


class BinaryMatchingInvariantTests(unittest.TestCase):
    def test_all_small_connected_graphs_and_feasible_budgets(self) -> None:
        checked = 0
        for node_count in range(2, 6):
            maximum_edges = node_count * (node_count - 1) // 2
            for parent in all_connected_labeled_graphs(node_count):
                parent_pairs = {edge.endpoints for edge in parent.edges}
                for incidence_budget in range(
                    2 * (node_count - 1),
                    2 * maximum_edges + 1,
                ):
                    with self.subTest(
                        nodes=node_count,
                        parent_edges=parent.edge_count,
                        incidence_budget=incidence_budget,
                    ):
                        match = binary_incidence_match(
                            parent,
                            incidence_budget,
                            root_seed=101,
                        )
                        lower_pairs = {
                            edge.members for edge in match.lower.hyperedges
                        }
                        upper_pairs = {
                            edge.members for edge in match.upper.hyperedges
                        }
                        lower_edges = incidence_budget // 2
                        upper_edges = (incidence_budget + 1) // 2

                        self.assertEqual(len(lower_pairs), lower_edges)
                        self.assertEqual(len(upper_pairs), upper_edges)
                        self.assertTrue(match.lower.is_connected)
                        self.assertTrue(match.upper.is_connected)
                        self.assertTrue(lower_pairs.issubset(upper_pairs))
                        self.assertEqual(
                            match.lower.resources.incidence_count,
                            2 * lower_edges,
                        )
                        self.assertEqual(
                            match.upper.resources.incidence_count,
                            2 * upper_edges,
                        )
                        if lower_edges <= parent.edge_count:
                            self.assertTrue(lower_pairs.issubset(parent_pairs))
                        else:
                            self.assertTrue(parent_pairs.issubset(lower_pairs))
                        if upper_edges <= parent.edge_count:
                            self.assertTrue(upper_pairs.issubset(parent_pairs))
                        else:
                            self.assertTrue(parent_pairs.issubset(upper_pairs))
                        checked += 1

        self.assertEqual(checked, 9_743)


if __name__ == "__main__":
    unittest.main()
