"""Contract tests for immutable balance-free hypergraph topologies."""

from __future__ import annotations

import unittest

from secondaryexploration.topology import (
    HyperedgeSpec,
    HypergraphTopology,
    TopologyError,
    TopologyResources,
)


class HyperedgeSpecTests(unittest.TestCase):
    def test_factory_canonicalizes_members_and_is_hashable(self) -> None:
        edge = HyperedgeSpec.from_members("edge-b", ("v2", "v0", "v1"))

        self.assertEqual(edge.members, ("v0", "v1", "v2"))
        self.assertEqual(edge.arity, 3)
        self.assertEqual({edge}, {edge})

    def test_direct_constructor_rejects_noncanonical_or_duplicate_members(self) -> None:
        invalid_members = (
            ("v1", "v0"),
            ("v0", "v0"),
            ("v0",),
        )
        for members in invalid_members:
            with self.subTest(members=members):
                with self.assertRaises(TopologyError):
                    HyperedgeSpec("edge", members)

    def test_identifiers_and_member_collections_are_validated(self) -> None:
        with self.assertRaises(TopologyError):
            HyperedgeSpec.from_members(" edge", ("v0", "v1"))
        with self.assertRaises(TopologyError):
            HyperedgeSpec.from_members("edge", "v0")
        with self.assertRaises(TopologyError):
            HyperedgeSpec.from_members("edge", ("v0", 1))  # type: ignore[arg-type]


class HypergraphTopologyTests(unittest.TestCase):
    def test_factory_canonicalizes_nodes_and_hyperedges(self) -> None:
        topology = HypergraphTopology.from_edges(
            nodes=("v2", "v0", "v1"),
            hyperedges={
                "edge-b": ("v2", "v1"),
                "edge-a": ("v1", "v0"),
            },
        )

        self.assertEqual(topology.nodes, ("v0", "v1", "v2"))
        self.assertEqual(
            tuple(edge.hyperedge_id for edge in topology.hyperedges),
            ("edge-a", "edge-b"),
        )
        self.assertTrue(topology.is_connected)
        self.assertEqual(topology.incidence_degree("v1"), 2)
        self.assertEqual(
            topology.node_incidence_degrees,
            (("v0", 1), ("v1", 2), ("v2", 1)),
        )
        self.assertEqual(
            topology.resources,
            TopologyResources(node_count=3, arities=(2, 2)),
        )

    def test_direct_constructor_requires_canonical_unique_tuples(self) -> None:
        edge_a = HyperedgeSpec.from_members("edge-a", ("v0", "v1"))
        edge_b = HyperedgeSpec.from_members("edge-b", ("v1", "v2"))
        invalid_cases = (
            (("v1", "v0", "v2"), (edge_a, edge_b)),
            (("v0", "v1", "v1"), (edge_a, edge_b)),
            (("v0", "v1", "v2"), (edge_b, edge_a)),
            (("v0", "v1", "v2"), (edge_a, edge_a)),
        )
        for nodes, edges in invalid_cases:
            with self.subTest(nodes=nodes, edges=edges):
                with self.assertRaises(TopologyError):
                    HypergraphTopology(nodes=nodes, hyperedges=edges)

    def test_unknown_members_and_unknown_degree_queries_are_rejected(self) -> None:
        with self.assertRaisesRegex(TopologyError, "unknown member"):
            HypergraphTopology.from_edges(
                nodes=("v0", "v1"),
                hyperedges={"edge": ("v0", "v2")},
            )

        topology = HypergraphTopology.from_edges(
            nodes=("v0", "v1"),
            hyperedges={"edge": ("v0", "v1")},
        )
        with self.assertRaisesRegex(TopologyError, "unknown node"):
            topology.incidence_degree("missing")

    def test_isolated_nodes_are_representable_and_detected(self) -> None:
        disconnected = HypergraphTopology.from_edges(
            nodes=("v0", "v1", "v2"),
            hyperedges={"edge": ("v0", "v1")},
        )
        singleton = HypergraphTopology.from_edges(nodes=("v0",), hyperedges={})

        self.assertFalse(disconnected.is_connected)
        self.assertEqual(disconnected.incidence_degree("v2"), 0)
        self.assertTrue(singleton.is_connected)
        self.assertEqual(
            singleton.resources,
            TopologyResources(node_count=1, arities=()),
        )

    def test_resource_value_requires_canonical_realizable_arity_witness(self) -> None:
        invalid = (
            dict(node_count=0, arities=()),
            dict(node_count=2, arities=(3,)),
            dict(node_count=3, arities=(3, 2)),
            dict(node_count=3, arities=(1,)),
            dict(node_count=3, arities=[2]),
        )
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(TopologyError):
                    TopologyResources(**values)  # type: ignore[arg-type]

    def test_pairwise_exposure_is_derived_and_cannot_be_forged(self) -> None:
        triad_resources = TopologyResources(node_count=3, arities=(3,))

        self.assertEqual(triad_resources.hyperedge_count, 1)
        self.assertEqual(triad_resources.incidence_count, 3)
        self.assertEqual(triad_resources.maximum_arity, 3)
        self.assertEqual(triad_resources.pairwise_member_exposure, 3)
        with self.assertRaises(TypeError):
            TopologyResources(  # type: ignore[call-arg]
                node_count=3,
                arities=(3,),
                pairwise_member_exposure=1,
            )


if __name__ == "__main__":
    unittest.main()
