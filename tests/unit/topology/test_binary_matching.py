"""Unit contracts for incidence-budget-matched binary baselines."""

from __future__ import annotations

from itertools import combinations
import unittest

from secondaryexploration.topology import (
    BinaryIncidenceMatch,
    HypergraphTopology,
    ParentGraph,
    TopologyError,
    TopologyMatchingError,
    binary_incidence_match,
    match_binary_to_topology,
)


def path_parent(node_count: int) -> ParentGraph:
    nodes = tuple(f"v{index:08d}" for index in range(node_count))
    return ParentGraph.from_edges(nodes, zip(nodes, nodes[1:]))


class BinaryIncidenceMatchingTests(unittest.TestCase):
    def test_even_budget_exactly_reproduces_parent_at_parent_cost(self) -> None:
        parent = path_parent(4)

        match = binary_incidence_match(parent, 6, root_seed=17)

        self.assertTrue(match.is_exact)
        self.assertEqual(match.lower, match.upper)
        self.assertEqual(match.lower_incidence_delta, 0)
        self.assertEqual(match.upper_incidence_delta, 0)
        self.assertEqual(
            tuple(edge.members for edge in match.lower.hyperedges),
            tuple(edge.endpoints for edge in parent.edges),
        )
        self.assertEqual(
            tuple(edge.hyperedge_id for edge in match.lower.hyperedges),
            (
                "b00000000-00000001",
                "b00000001-00000002",
                "b00000002-00000003",
            ),
        )

    def test_odd_budget_returns_nested_adjacent_brackets(self) -> None:
        nodes = tuple(f"v{index:08d}" for index in range(5))
        parent = ParentGraph.from_edges(nodes, combinations(nodes, 2))

        match = binary_incidence_match(parent, 9, root_seed=23)

        self.assertFalse(match.is_exact)
        self.assertEqual(match.lower.resources.incidence_count, 8)
        self.assertEqual(match.upper.resources.incidence_count, 10)
        self.assertEqual(match.lower_incidence_delta, -1)
        self.assertEqual(match.upper_incidence_delta, 1)
        self.assertTrue(
            set(edge.members for edge in match.lower.hyperedges)
            < set(edge.members for edge in match.upper.hyperedges)
        )
        self.assertTrue(match.lower.is_connected)
        self.assertTrue(match.upper.is_connected)
        self.assertEqual(
            tuple(edge.members for edge in match.lower.hyperedges),
            (
                ("v00000000", "v00000001"),
                ("v00000000", "v00000004"),
                ("v00000001", "v00000002"),
                ("v00000001", "v00000003"),
            ),
        )
        self.assertEqual(
            tuple(edge.members for edge in match.upper.hyperedges),
            (
                ("v00000000", "v00000001"),
                ("v00000000", "v00000004"),
                ("v00000001", "v00000002"),
                ("v00000001", "v00000003"),
                ("v00000002", "v00000003"),
            ),
        )

    def test_parent_edges_are_preferred_before_nonparent_pairs(self) -> None:
        parent = path_parent(5)

        exact_parent = binary_incidence_match(parent, 8, root_seed=31).lower
        expanded = binary_incidence_match(parent, 12, root_seed=31).lower

        parent_pairs = {edge.endpoints for edge in parent.edges}
        self.assertEqual(
            {edge.members for edge in exact_parent.hyperedges},
            parent_pairs,
        )
        self.assertTrue(
            parent_pairs.issubset(
                {edge.members for edge in expanded.hyperedges}
            )
        )

    def test_topology_wrapper_rejects_node_mismatch(self) -> None:
        parent = path_parent(4)
        source = HypergraphTopology.from_edges(
            ("v00000000", "v00000001", "v00000002", "other"),
            {"h": ("v00000000", "v00000001", "v00000002", "other")},
        )

        with self.assertRaisesRegex(TopologyMatchingError, "same node set"):
            match_binary_to_topology(parent, source, root_seed=0)

    def test_infeasible_and_invalid_inputs_fail_closed(self) -> None:
        parent = path_parent(5)
        disconnected = ParentGraph.from_edges(
            parent.nodes,
            (("v00000000", "v00000001"), ("v00000002", "v00000003")),
        )
        calls = (
            lambda: binary_incidence_match(parent, 7, root_seed=0),
            lambda: binary_incidence_match(parent, 21, root_seed=0),
            lambda: binary_incidence_match(disconnected, 8, root_seed=0),
            lambda: binary_incidence_match(parent, True, root_seed=0),
            lambda: binary_incidence_match(parent, 8, root_seed=-1),
            lambda: binary_incidence_match(parent, 8, root_seed=2**64),
            lambda: binary_incidence_match(parent, 8, root_seed=True),
        )
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(TopologyError):
                    call()

    def test_public_match_record_rejects_altered_provenance(self) -> None:
        match = binary_incidence_match(path_parent(5), 9, root_seed=37)

        for values in (
            dict(source_incidence_count=8),
            dict(root_seed=38),
            dict(lower=match.upper),
            dict(upper=match.lower),
        ):
            kwargs = dict(
                parent=match.parent,
                source_incidence_count=match.source_incidence_count,
                root_seed=match.root_seed,
                lower=match.lower,
                upper=match.upper,
            )
            kwargs.update(values)
            with self.subTest(values=values):
                with self.assertRaises(TopologyMatchingError):
                    BinaryIncidenceMatch(**kwargs)


if __name__ == "__main__":
    unittest.main()
