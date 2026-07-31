"""Exhaustively cross-check anchor formulas on small parameter cells."""

from __future__ import annotations

from math import comb
import unittest

from secondaryexploration.topology import (
    common_core_sunflower,
    uniform_overlap_chain,
)


class AnchorFormulaTests(unittest.TestCase):
    def test_all_small_anchor_cells_match_closed_form_resources_and_overlaps(
        self,
    ) -> None:
        checked_cells = 0
        for arity in range(2, 7):
            for overlap in range(1, arity):
                for edge_count in range(2, 7):
                    with self.subTest(
                        arity=arity,
                        overlap=overlap,
                        edge_count=edge_count,
                    ):
                        chain = uniform_overlap_chain(
                            arity,
                            overlap,
                            edge_count,
                        )
                        sunflower = common_core_sunflower(
                            arity,
                            overlap,
                            edge_count,
                        )
                        expected_nodes = overlap + edge_count * (arity - overlap)
                        expected_incidence = arity * edge_count
                        expected_pairwise = edge_count * comb(arity, 2)

                        self.assertTrue(chain.is_connected)
                        self.assertTrue(sunflower.is_connected)
                        self.assertEqual(chain.resources, sunflower.resources)
                        self.assertEqual(chain.resources.node_count, expected_nodes)
                        self.assertEqual(
                            chain.resources.hyperedge_count,
                            edge_count,
                        )
                        self.assertEqual(
                            chain.resources.incidence_count,
                            expected_incidence,
                        )
                        self.assertEqual(chain.resources.maximum_arity, arity)
                        self.assertEqual(
                            chain.resources.pairwise_member_exposure,
                            expected_pairwise,
                        )
                        self.assertEqual(
                            tuple(edge.arity for edge in chain.hyperedges),
                            (arity,) * edge_count,
                        )

                        chain_sets = tuple(
                            set(edge.members) for edge in chain.hyperedges
                        )
                        stride = arity - overlap
                        for left in range(edge_count):
                            for right in range(left + 1, edge_count):
                                separation = right - left
                                expected_intersection = max(
                                    0,
                                    arity - separation * stride,
                                )
                                self.assertEqual(
                                    len(chain_sets[left] & chain_sets[right]),
                                    expected_intersection,
                                )

                        sunflower_sets = tuple(
                            set(edge.members) for edge in sunflower.hyperedges
                        )
                        common_core = set.intersection(*sunflower_sets)
                        self.assertEqual(len(common_core), overlap)
                        for left in range(edge_count):
                            for right in range(left + 1, edge_count):
                                self.assertEqual(
                                    sunflower_sets[left] & sunflower_sets[right],
                                    common_core,
                                )
                        checked_cells += 1

        self.assertEqual(checked_cells, 75)


if __name__ == "__main__":
    unittest.main()
