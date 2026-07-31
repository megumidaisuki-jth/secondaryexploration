"""Exhaustive invariants for NCH and FHS on small connected graphs."""

from __future__ import annotations

from itertools import combinations
import unittest

from secondaryexploration.topology import (
    HyperedgeSpec,
    ParentGraph,
    binary_topology,
    canonical_local_ratio_vertex_cover,
    closed_neighborhood_nch,
    fixed_hyperedge_size,
    uncovered_parent_edges,
)


def connected_within_parent(parent: ParentGraph, edge: HyperedgeSpec) -> bool:
    allowed = set(edge.members)
    visited = {edge.members[0]}
    frontier = [edge.members[0]]
    while frontier:
        current = frontier.pop()
        for neighbor in parent.neighbors(current):
            if neighbor in allowed and neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return visited == allowed


class TransformationInvariantTests(unittest.TestCase):
    def test_all_connected_labeled_graphs_through_five_nodes_preserve_edges(
        self,
    ) -> None:
        labels = ("a", "b", "c", "d", "e")
        checked_parents = 0
        checked_fhs_outputs = 0
        for node_count in range(2, 6):
            nodes = labels[:node_count]
            possible_edges = tuple(combinations(nodes, 2))
            for mask in range(1 << len(possible_edges)):
                selected_edges = tuple(
                    edge
                    for edge_index, edge in enumerate(possible_edges)
                    if mask & (1 << edge_index)
                )
                parent = ParentGraph.from_edges(nodes, selected_edges)
                if not parent.is_connected:
                    continue

                with self.subTest(node_count=node_count, mask=mask, family="nch"):
                    nch = closed_neighborhood_nch(parent)
                    cover = canonical_local_ratio_vertex_cover(parent)
                    expected_memberships = tuple(
                        tuple(sorted((cover_node,) + parent.neighbors(cover_node)))
                        for cover_node in cover
                    )
                    self.assertEqual(
                        tuple(edge.members for edge in nch.hyperedges),
                        expected_memberships,
                    )
                    self.assertEqual(uncovered_parent_edges(parent, nch), ())
                    self.assertTrue(nch.is_connected)
                    self.assertTrue(
                        all(degree > 0 for _, degree in nch.node_incidence_degrees)
                    )
                    self.assertTrue(
                        all(connected_within_parent(parent, edge) for edge in nch.hyperedges)
                    )

                for maximum_arity in range(2, node_count + 1):
                    with self.subTest(
                        node_count=node_count,
                        mask=mask,
                        family="fhs",
                        maximum_arity=maximum_arity,
                    ):
                        fhs = fixed_hyperedge_size(parent, maximum_arity)
                        self.assertEqual(uncovered_parent_edges(parent, fhs), ())
                        self.assertTrue(fhs.is_connected)
                        self.assertTrue(
                            all(
                                2 <= edge.arity <= maximum_arity
                                for edge in fhs.hyperedges
                            )
                        )
                        self.assertTrue(
                            all(
                                degree > 0
                                for _, degree in fhs.node_incidence_degrees
                            )
                        )
                        self.assertTrue(
                            all(
                                connected_within_parent(parent, edge)
                                for edge in fhs.hyperedges
                            )
                        )
                        self.assertEqual(
                            fhs,
                            fixed_hyperedge_size(parent, maximum_arity),
                        )
                        if maximum_arity == 2:
                            self.assertEqual(
                                sorted(edge.members for edge in fhs.hyperedges),
                                sorted(
                                    edge.members
                                    for edge in binary_topology(parent).hyperedges
                                ),
                            )
                        checked_fhs_outputs += 1
                checked_parents += 1

        self.assertEqual(checked_parents, 771)
        self.assertEqual(checked_fhs_outputs, 3_035)


if __name__ == "__main__":
    unittest.main()
