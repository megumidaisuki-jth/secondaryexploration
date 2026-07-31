"""Contract tests for canonical simple undirected parent graphs."""

from __future__ import annotations

from fractions import Fraction
import unittest

from secondaryexploration.topology import GraphEdge, ParentGraph, TopologyError


class GraphEdgeTests(unittest.TestCase):
    def test_factory_canonicalizes_endpoints(self) -> None:
        edge = GraphEdge.from_endpoints("v2", "v0")

        self.assertEqual((edge.left, edge.right), ("v0", "v2"))
        self.assertEqual(edge.endpoints, ("v0", "v2"))

    def test_direct_constructor_rejects_loops_and_noncanonical_endpoints(self) -> None:
        with self.assertRaises(TopologyError):
            GraphEdge("v1", "v0")
        with self.assertRaises(TopologyError):
            GraphEdge("v0", "v0")


class ParentGraphTests(unittest.TestCase):
    def test_factory_canonicalizes_graph_and_exposes_exact_descriptors(self) -> None:
        graph = ParentGraph.from_edges(
            nodes=("d", "b", "a", "c"),
            edges=(("c", "d"), ("b", "a"), ("c", "b")),
        )

        self.assertEqual(graph.nodes, ("a", "b", "c", "d"))
        self.assertEqual(
            tuple(edge.endpoints for edge in graph.edges),
            (("a", "b"), ("b", "c"), ("c", "d")),
        )
        self.assertEqual(graph.edge_count, 3)
        self.assertEqual(graph.neighbors("b"), ("a", "c"))
        self.assertEqual(graph.degree("b"), 2)
        self.assertEqual(
            graph.node_degrees,
            (("a", 1), ("b", 2), ("c", 2), ("d", 1)),
        )
        self.assertEqual(graph.mean_degree, Fraction(3, 2))
        self.assertTrue(graph.is_connected)

    def test_direct_constructor_requires_canonical_unique_tuples(self) -> None:
        edge_ab = GraphEdge.from_endpoints("a", "b")
        edge_bc = GraphEdge.from_endpoints("b", "c")
        invalid_cases = (
            (("b", "a", "c"), (edge_ab, edge_bc)),
            (("a", "b", "b"), (edge_ab, edge_bc)),
            (("a", "b", "c"), (edge_bc, edge_ab)),
            (("a", "b", "c"), (edge_ab, edge_ab)),
        )
        for nodes, edges in invalid_cases:
            with self.subTest(nodes=nodes, edges=edges):
                with self.assertRaises(TopologyError):
                    ParentGraph(nodes=nodes, edges=edges)

    def test_factory_rejects_duplicate_unknown_and_malformed_edges(self) -> None:
        invalid_edge_sets = (
            (("a", "b"), ("b", "a")),
            (("a", "missing"),),
            (("a", "a"),),
            (("a",),),
        )
        for edges in invalid_edge_sets:
            with self.subTest(edges=edges):
                with self.assertRaises(TopologyError):
                    ParentGraph.from_edges(("a", "b"), edges)

    def test_disconnected_and_isolated_nodes_remain_representable(self) -> None:
        graph = ParentGraph.from_edges(
            nodes=("a", "b", "c", "d"),
            edges=(("a", "b"), ("c", "d")),
        )
        singleton = ParentGraph.from_edges(nodes=("only",), edges=())

        self.assertFalse(graph.is_connected)
        self.assertTrue(singleton.is_connected)
        self.assertEqual(singleton.mean_degree, Fraction(0, 1))
        with self.assertRaisesRegex(TopologyError, "unknown node"):
            graph.neighbors("missing")


if __name__ == "__main__":
    unittest.main()
