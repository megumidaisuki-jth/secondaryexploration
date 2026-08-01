"""Unit contracts for seeded random parent-graph families."""

from __future__ import annotations

import unittest

from secondaryexploration.topology import (
    MatchedParentEnsemble,
    ParentGraph,
    ParentGraphDraw,
    ParentGraphModel,
    TopologyError,
    TopologyGenerationError,
    barabasi_albert_parent_graph,
    connected_gnm_parent_graph,
    connected_sbm_parent_graph,
    matched_synthetic_parent_graphs,
)


class ParentGraphDrawTests(unittest.TestCase):
    def test_connected_gnm_replays_graph_attempt_and_draw_seed(self) -> None:
        first = connected_gnm_parent_graph(8, 9, root_seed=17, max_attempts=50)
        second = connected_gnm_parent_graph(8, 9, root_seed=17, max_attempts=50)

        self.assertEqual(first, second)
        self.assertEqual(first.model, ParentGraphModel.ER_GNM)
        self.assertEqual(first.graph.edge_count, 9)
        self.assertTrue(first.graph.is_connected)
        self.assertEqual(first.accepted_attempt, 0)
        self.assertEqual(first.draw_seed, 36554340086133148)
        self.assertEqual(
            tuple(edge.endpoints for edge in first.graph.edges),
            (
                ("v00000000", "v00000001"),
                ("v00000000", "v00000002"),
                ("v00000000", "v00000006"),
                ("v00000001", "v00000006"),
                ("v00000001", "v00000007"),
                ("v00000002", "v00000005"),
                ("v00000003", "v00000004"),
                ("v00000003", "v00000007"),
                ("v00000004", "v00000005"),
            ),
        )

    def test_barabasi_albert_known_seeded_vector_and_exact_edge_formula(self) -> None:
        draw = barabasi_albert_parent_graph(8, 2, root_seed=23)

        self.assertEqual(draw.model, ParentGraphModel.BARABASI_ALBERT)
        self.assertEqual(draw.accepted_attempt, 0)
        self.assertEqual(draw.graph.edge_count, 12)
        self.assertEqual(
            tuple(edge.endpoints for edge in draw.graph.edges),
            (
                ("v00000000", "v00000001"),
                ("v00000000", "v00000002"),
                ("v00000000", "v00000003"),
                ("v00000000", "v00000005"),
                ("v00000002", "v00000003"),
                ("v00000002", "v00000004"),
                ("v00000002", "v00000005"),
                ("v00000002", "v00000007"),
                ("v00000003", "v00000004"),
                ("v00000003", "v00000006"),
                ("v00000005", "v00000006"),
                ("v00000005", "v00000007"),
            ),
        )

    def test_fixed_count_sbm_preserves_declared_pair_counts(self) -> None:
        blocks = (4, 4)
        draw = connected_sbm_parent_graph(
            blocks,
            edge_count=10,
            within_edge_count=6,
            root_seed=29,
            max_attempts=50,
        )

        block_by_node = {
            node: block_index
            for block_index, block in enumerate(draw.blocks)
            for node in block
        }
        within = sum(
            block_by_node[edge.left] == block_by_node[edge.right]
            for edge in draw.graph.edges
        )
        self.assertEqual(draw.model, ParentGraphModel.SBM_FIXED_COUNT)
        self.assertEqual(draw.graph.edge_count, 10)
        self.assertEqual(within, 6)
        self.assertEqual(len(draw.blocks), 2)
        self.assertEqual(draw.accepted_attempt, 1)
        self.assertEqual(draw.draw_seed, 8833761872156385723)
        self.assertEqual(
            tuple(edge.endpoints for edge in draw.graph.edges),
            (
                ("v00000000", "v00000002"),
                ("v00000000", "v00000003"),
                ("v00000000", "v00000006"),
                ("v00000001", "v00000003"),
                ("v00000001", "v00000007"),
                ("v00000002", "v00000005"),
                ("v00000003", "v00000005"),
                ("v00000004", "v00000005"),
                ("v00000004", "v00000006"),
                ("v00000006", "v00000007"),
            ),
        )

    def test_invalid_and_impossible_inputs_fail_closed(self) -> None:
        invalid_calls = (
            lambda: connected_gnm_parent_graph(True, 1, root_seed=0),
            lambda: connected_gnm_parent_graph(5, 3, root_seed=0),
            lambda: connected_gnm_parent_graph(5, 11, root_seed=0),
            lambda: connected_gnm_parent_graph(5, 4, root_seed=-1),
            lambda: connected_gnm_parent_graph(5, 4, root_seed=0, max_attempts=0),
            lambda: barabasi_albert_parent_graph(5, 0, root_seed=0),
            lambda: barabasi_albert_parent_graph(5, 5, root_seed=0),
            lambda: connected_sbm_parent_graph(
                (3, 0), 4, 2, root_seed=0
            ),
            lambda: connected_sbm_parent_graph(
                (3, 3), 5, 5, root_seed=0
            ),
            lambda: connected_sbm_parent_graph(
                (2, 2, 2), 5, 4, root_seed=0
            ),
        )
        for call in invalid_calls:
            with self.subTest(call=call):
                with self.assertRaises(TopologyError):
                    call()

    def test_exhausted_connected_resampling_is_explicit(self) -> None:
        with self.assertRaisesRegex(TopologyGenerationError, "1 attempts"):
            connected_gnm_parent_graph(6, 5, root_seed=1, max_attempts=1)

    def test_public_draw_record_rejects_unreplayable_or_forged_metadata(self) -> None:
        er = connected_gnm_parent_graph(4, 3, root_seed=0, max_attempts=50)
        ba = barabasi_albert_parent_graph(4, 1, root_seed=0)
        alternate_graphs = (
            ParentGraph.from_edges(
                er.graph.nodes,
                (("v00000000", "v00000001"),
                 ("v00000000", "v00000002"),
                 ("v00000000", "v00000003")),
            ),
            ParentGraph.from_edges(
                er.graph.nodes,
                (("v00000000", "v00000001"),
                 ("v00000001", "v00000002"),
                 ("v00000002", "v00000003")),
            ),
        )
        forged_graph = next(graph for graph in alternate_graphs if graph != er.graph)

        invalid_records = (
            lambda: ParentGraphDraw(
                ParentGraphModel.ER_GNM,
                er.graph,
                root_seed=0,
                accepted_attempt=2**64,
            ),
            lambda: ParentGraphDraw(
                ParentGraphModel.BARABASI_ALBERT,
                ba.graph,
                root_seed=0,
                accepted_attempt=1,
                attachment_count=1,
            ),
            lambda: ParentGraphDraw(
                ParentGraphModel.ER_GNM,
                ParentGraph.from_edges(("a", "b"), (("a", "b"),)),
                root_seed=0,
                accepted_attempt=0,
            ),
            lambda: ParentGraphDraw(
                ParentGraphModel.ER_GNM,
                forged_graph,
                root_seed=er.root_seed,
                accepted_attempt=er.accepted_attempt,
            ),
        )
        for construct in invalid_records:
            with self.subTest(construct=construct):
                with self.assertRaises(TopologyError):
                    construct()

    def test_matched_record_rejects_forged_seed_provenance(self) -> None:
        ensemble = matched_synthetic_parent_graphs(
            node_count=12,
            attachment_count=2,
            block_count=3,
            sbm_within_edge_count=12,
            base_seed=71,
            replicate_index=4,
            max_attempts=500,
        )

        with self.assertRaisesRegex(TopologyError, "declared base seed"):
            MatchedParentEnsemble(
                base_seed=72,
                replicate_index=4,
                er=ensemble.er,
                ba=ensemble.ba,
                sbm=ensemble.sbm,
            )


if __name__ == "__main__":
    unittest.main()
