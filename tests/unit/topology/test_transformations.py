"""Tests for binary, clique, NCH, and FHS topology transformations."""

from __future__ import annotations

import unittest

from secondaryexploration.topology import (
    HypergraphTopology,
    ParentGraph,
    TopologyError,
    binary_topology,
    clique_expansion,
    closed_neighborhood_nch,
    fixed_hyperedge_size,
    uncovered_parent_edges,
)


def path_graph(node_count: int) -> ParentGraph:
    nodes = tuple(chr(ord("a") + index) for index in range(node_count))
    return ParentGraph.from_edges(nodes, tuple(zip(nodes, nodes[1:])))


class BinaryReferenceTests(unittest.TestCase):
    def test_direct_binary_topology_preserves_every_parent_edge(self) -> None:
        parent = path_graph(4)

        topology = binary_topology(parent)

        self.assertEqual(topology.nodes, parent.nodes)
        self.assertEqual(
            tuple(edge.members for edge in topology.hyperedges),
            tuple(edge.endpoints for edge in parent.edges),
        )
        self.assertEqual(topology.resources.arities, (2, 2, 2))
        self.assertEqual(uncovered_parent_edges(parent, topology), ())

    def test_clique_expansion_preserves_channel_multiplicity(self) -> None:
        source = HypergraphTopology.from_edges(
            nodes=("a", "b", "c", "d"),
            hyperedges={
                "first": ("a", "b", "c"),
                "second": ("a", "b", "d"),
            },
        )

        expanded = clique_expansion(source)

        self.assertEqual(expanded.nodes, source.nodes)
        self.assertEqual(
            expanded.resources.hyperedge_count,
            source.resources.pairwise_member_exposure,
        )
        self.assertEqual(expanded.resources.incidence_count, 12)
        self.assertEqual(
            sum(edge.members == ("a", "b") for edge in expanded.hyperedges),
            2,
        )
        self.assertTrue(all(edge.arity == 2 for edge in expanded.hyperedges))


class NCHTransformationTests(unittest.TestCase):
    def test_closed_neighborhood_resolves_two_node_open_neighborhood_defect(
        self,
    ) -> None:
        parent = ParentGraph.from_edges(("a", "b"), (("a", "b"),))

        topology = closed_neighborhood_nch(parent)

        self.assertEqual(
            tuple(edge.members for edge in topology.hyperedges),
            (("a", "b"),),
        )
        self.assertEqual(uncovered_parent_edges(parent, topology), ())
        self.assertTrue(topology.is_connected)

    def test_path_nch_is_deterministic_connected_and_covers_parent_edges(self) -> None:
        parent = path_graph(4)

        first = closed_neighborhood_nch(parent)
        second = closed_neighborhood_nch(parent)

        self.assertEqual(first, second)
        self.assertEqual(
            tuple(edge.members for edge in first.hyperedges),
            (("a", "b"), ("a", "b", "c"), ("b", "c", "d")),
        )
        self.assertEqual(uncovered_parent_edges(parent, first), ())
        self.assertTrue(first.is_connected)
        self.assertTrue(
            all(degree > 0 for _, degree in first.node_incidence_degrees)
        )


class FHSTransformationTests(unittest.TestCase):
    def test_path_fhs_uses_canonical_degree_and_bfs_ties(self) -> None:
        parent = path_graph(5)

        topology = fixed_hyperedge_size(parent, maximum_arity=3)

        self.assertEqual(
            tuple(edge.members for edge in topology.hyperedges),
            (("a", "b", "c"), ("c", "d", "e")),
        )
        self.assertEqual(uncovered_parent_edges(parent, topology), ())
        self.assertTrue(topology.is_connected)

    def test_maximum_arity_two_recovers_every_binary_parent_edge(self) -> None:
        parent = ParentGraph.from_edges(
            nodes=("a", "b", "c", "d"),
            edges=(("a", "b"), ("a", "c"), ("b", "c"), ("c", "d")),
        )

        topology = fixed_hyperedge_size(parent, maximum_arity=2)

        self.assertEqual(
            sorted(edge.members for edge in topology.hyperedges),
            sorted(edge.endpoints for edge in parent.edges),
        )
        self.assertEqual(topology.resources.hyperedge_count, parent.edge_count)

    def test_full_size_bfs_collapses_connected_parent_to_one_hyperedge(self) -> None:
        parent = path_graph(5)

        topology = fixed_hyperedge_size(parent, maximum_arity=5)

        self.assertEqual(
            tuple(edge.members for edge in topology.hyperedges),
            (parent.nodes,),
        )

    def test_primary_transformations_reject_nonconnected_or_invalid_inputs(self) -> None:
        disconnected = ParentGraph.from_edges(
            nodes=("a", "b", "c", "d"),
            edges=(("a", "b"), ("c", "d")),
        )
        for transform in (
            lambda: closed_neighborhood_nch(disconnected),
            lambda: fixed_hyperedge_size(disconnected, 3),
        ):
            with self.assertRaisesRegex(TopologyError, "connected"):
                transform()

        parent = path_graph(3)
        for maximum_arity in (1, 4, True, 2.0):
            with self.subTest(maximum_arity=maximum_arity):
                with self.assertRaises(TopologyError):
                    fixed_hyperedge_size(  # type: ignore[arg-type]
                        parent,
                        maximum_arity,
                    )


if __name__ == "__main__":
    unittest.main()
