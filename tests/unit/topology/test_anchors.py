"""Tests for deterministic chain, sunflower, and binary anchors."""

from __future__ import annotations

import unittest

from secondaryexploration.topology import (
    TopologyError,
    common_core_sunflower,
    uniform_overlap_chain,
)


class DeterministicAnchorTests(unittest.TestCase):
    def test_binary_special_cases_are_path_and_star(self) -> None:
        chain = uniform_overlap_chain(arity=2, overlap=1, edge_count=4)
        star = common_core_sunflower(arity=2, overlap=1, edge_count=4)

        self.assertEqual(
            tuple(edge.members for edge in chain.hyperedges),
            (
                ("v00000000", "v00000001"),
                ("v00000001", "v00000002"),
                ("v00000002", "v00000003"),
                ("v00000003", "v00000004"),
            ),
        )
        self.assertEqual(chain.node_incidence_degrees[0][1], 1)
        self.assertEqual(chain.node_incidence_degrees[-1][1], 1)
        self.assertEqual(
            tuple(degree for _, degree in chain.node_incidence_degrees[1:-1]),
            (2, 2, 2),
        )
        self.assertEqual(star.incidence_degree("v00000000"), 4)
        self.assertEqual(
            tuple(degree for _, degree in star.node_incidence_degrees[1:]),
            (1, 1, 1, 1),
        )

    def test_triads_reproduce_paper_one_membership_patterns(self) -> None:
        chain = uniform_overlap_chain(arity=3, overlap=1, edge_count=3)
        star = common_core_sunflower(arity=3, overlap=1, edge_count=3)

        self.assertEqual(
            tuple(edge.members for edge in chain.hyperedges),
            (
                ("v00000000", "v00000001", "v00000002"),
                ("v00000002", "v00000003", "v00000004"),
                ("v00000004", "v00000005", "v00000006"),
            ),
        )
        self.assertEqual(
            tuple(edge.members for edge in star.hyperedges),
            (
                ("v00000000", "v00000001", "v00000002"),
                ("v00000000", "v00000003", "v00000004"),
                ("v00000000", "v00000005", "v00000006"),
            ),
        )

    def test_constructors_are_deterministic(self) -> None:
        self.assertEqual(
            uniform_overlap_chain(5, 3, 4),
            uniform_overlap_chain(5, 3, 4),
        )
        self.assertEqual(
            common_core_sunflower(5, 3, 4),
            common_core_sunflower(5, 3, 4),
        )

    def test_invalid_anchor_parameters_are_rejected(self) -> None:
        invalid_cases = (
            (1, 1, 2),
            (2, 0, 2),
            (2, 2, 2),
            (3, 1, 1),
            (True, 1, 2),
            (3, True, 2),
            (3, 1, True),
        )
        for arity, overlap, edge_count in invalid_cases:
            with self.subTest(
                arity=arity,
                overlap=overlap,
                edge_count=edge_count,
            ):
                with self.assertRaises(TopologyError):
                    uniform_overlap_chain(arity, overlap, edge_count)
                with self.assertRaises(TopologyError):
                    common_core_sunflower(arity, overlap, edge_count)


if __name__ == "__main__":
    unittest.main()
