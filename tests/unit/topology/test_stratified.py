"""Tests for deterministic Lightning structural strata and subgraphs."""

from __future__ import annotations

from dataclasses import replace
import random
import unittest

from secondaryexploration.topology import (
    ParentGraph,
    StratifiedSamplingError,
    largest_connected_parent,
    parent_graph_fingerprint,
    sample_lightning_subgraph,
    stratify_lightning_parent,
    validate_lightning_strata_record,
    validate_lightning_subgraph_sample,
)
from secondaryexploration.topology.stratified import (
    _articulation_metrics,
    _core_numbers,
)


def _layered_parent() -> ParentGraph:
    nodes = [f"v{index:02d}" for index in range(40)]
    edges: list[tuple[str, str]] = []
    for left in range(10):
        for right in range(left + 1, 10):
            edges.append((nodes[left], nodes[right]))
    edges.extend(
        (
            ("v00", "v10"),
            ("v01", "v11"),
            ("v02", "v12"),
            ("v10", "v13"),
            ("v11", "v14"),
            ("v12", "v15"),
            ("v13", "v16"),
            ("v14", "v17"),
            ("v15", "v18"),
            ("v16", "v19"),
            ("v17", "v20"),
            ("v18", "v21"),
            ("v19", "v22"),
            ("v20", "v23"),
            ("v21", "v24"),
        )
    )
    for offset, leaf in enumerate(range(25, 40)):
        edges.append((f"v{16 + offset % 9:02d}", f"v{leaf:02d}"))
    return ParentGraph.from_edges(nodes, edges)


def _brute_core_numbers(parent: ParentGraph) -> dict[str, int]:
    result = {node_id: 0 for node_id in parent.nodes}
    for threshold in range(1, len(parent.nodes)):
        retained = set(parent.nodes)
        while True:
            remove = {
                node_id
                for node_id in retained
                if sum(neighbor in retained for neighbor in parent.neighbors(node_id))
                < threshold
            }
            if not remove:
                break
            retained -= remove
        for node_id in retained:
            result[node_id] = threshold
    return result


def _brute_bridge_metrics(parent: ParentGraph) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for removed in parent.nodes:
        remaining = set(parent.nodes) - {removed}
        sizes: list[int] = []
        while remaining:
            start = min(remaining)
            remaining.remove(start)
            visited = {start}
            frontier = [start]
            while frontier:
                current = frontier.pop()
                for neighbor in parent.neighbors(current):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        visited.add(neighbor)
                        frontier.append(neighbor)
            sizes.append(len(visited))
        if len(sizes) >= 2:
            result[removed] = (len(sizes), len(parent.nodes) - 1 - max(sizes))
    return result


class LargestConnectedParentTests(unittest.TestCase):
    def test_component_tie_uses_lexicographically_smallest_node_tuple(self) -> None:
        parent = ParentGraph.from_edges(
            ("a", "b", "c", "x", "y", "z"),
            (("a", "b"), ("b", "c"), ("c", "a"), ("x", "y"), ("y", "z"), ("z", "x")),
        )

        lcc = largest_connected_parent(parent)

        self.assertEqual(lcc.nodes, ("a", "b", "c"))
        self.assertEqual(lcc.edge_count, 3)


class LightningStrataTests(unittest.TestCase):
    def test_rank_tails_and_articulation_pool_are_exact_and_disjoint(self) -> None:
        parent = _layered_parent()

        record = stratify_lightning_parent(parent)
        core = dict(record.core_numbers)

        self.assertEqual(record.pool_width, 8)
        self.assertEqual(len(record.core_candidates), 8)
        self.assertEqual(len(record.peripheral_candidates), 8)
        self.assertTrue(record.bridge_candidates)
        self.assertTrue(set(record.core_candidates).issubset({f"v{i:02d}" for i in range(10)}))
        self.assertTrue(all(core[f"v{i:02d}"] == 9 for i in range(10)))
        self.assertTrue(all(core[f"v{i:02d}"] == 1 for i in range(10, 40)))
        self.assertIn("v10", {metric.node_id for metric in record.bridge_metrics})
        pools = [
            set(record.core_candidates),
            set(record.bridge_candidates),
            set(record.peripheral_candidates),
        ]
        self.assertFalse(pools[0] & pools[1])
        self.assertFalse(pools[0] & pools[2])
        self.assertFalse(pools[1] & pools[2])

    def test_graph_without_articulation_candidates_fails_closed(self) -> None:
        nodes = tuple(f"n{i}" for i in range(10))
        clique = ParentGraph.from_edges(
            nodes,
            ((nodes[i], nodes[j]) for i in range(10) for j in range(i + 1, 10)),
        )

        with self.assertRaisesRegex(StratifiedSamplingError, "no bridge candidates"):
            stratify_lightning_parent(clique)

    def test_integer_core_and_articulation_algorithms_match_brute_force(self) -> None:
        rng = random.Random(20260807)
        for case_index in range(20):
            size = 8 + case_index % 5
            nodes = tuple(f"c{case_index:02d}-{index:02d}" for index in range(size))
            edges = [(nodes[index - 1], nodes[index]) for index in range(1, size)]
            for left in range(size):
                for right in range(left + 2, size):
                    if rng.randrange(4) == 0:
                        edges.append((nodes[left], nodes[right]))
            parent = ParentGraph.from_edges(nodes, edges)
            expected_core = _brute_core_numbers(parent)
            expected_bridge = _brute_bridge_metrics(parent)
            observed_bridge = _articulation_metrics(parent)
            self.assertEqual(_core_numbers(parent), expected_core)
            self.assertEqual(
                {
                    metric.node_id: (
                        metric.component_count_after_removal,
                        metric.fragmentation_gain,
                    )
                    for metric in observed_bridge.values()
                },
                expected_bridge,
            )


class LightningSubgraphSampleTests(unittest.TestCase):
    def test_forged_cached_strata_are_rejected_before_sampling(self) -> None:
        parent = _layered_parent()
        canonical = stratify_lightning_parent(parent)
        forged_core = set(canonical.core_candidates)
        forged_peripheral = set(canonical.peripheral_candidates)
        core_node = canonical.core_candidates[0]
        peripheral_node = canonical.peripheral_candidates[0]
        forged_core.remove(core_node)
        forged_core.add(peripheral_node)
        forged_peripheral.remove(peripheral_node)
        forged_peripheral.add(core_node)
        forged = replace(
            canonical,
            core_candidates=tuple(sorted(forged_core)),
            peripheral_candidates=tuple(sorted(forged_peripheral)),
        )

        with self.assertRaisesRegex(StratifiedSamplingError, "strata replay mismatch"):
            validate_lightning_strata_record(parent, forged)
        with self.assertRaisesRegex(StratifiedSamplingError, "strata replay mismatch"):
            sample_lightning_subgraph(
                parent,
                "f" * 64,
                2026,
                "core",
                0,
                8,
                20260807,
                strata=forged,
            )

    def test_samples_are_exact_connected_induced_and_size_nested(self) -> None:
        parent = _layered_parent()
        strata = stratify_lightning_parent(parent)
        source = "a" * 64

        small = sample_lightning_subgraph(
            parent, source, 2026, "bridge", 0, 8, 20260807, strata=strata
        )
        large = sample_lightning_subgraph(
            parent, source, 2026, "bridge", 0, 16, 20260807, strata=strata
        )

        self.assertEqual(small.semantic_seed, large.semantic_seed)
        self.assertEqual(large.discovery_order[:8], small.discovery_order)
        self.assertTrue(small.subgraph.is_connected)
        self.assertEqual(len(small.subgraph.nodes), 8)
        selected = set(small.discovery_order)
        expected_edges = tuple(
            edge for edge in strata.lcc.edges if edge.left in selected and edge.right in selected
        )
        self.assertEqual(small.subgraph.edges, expected_edges)

    def test_replicates_use_distinct_anchors_and_replay_exactly(self) -> None:
        parent = _layered_parent()
        source = "b" * 64
        for stratum in ("core", "bridge", "peripheral"):
            first = sample_lightning_subgraph(
                parent, source, 2023, stratum, 0, 10, 20260807
            )
            second = sample_lightning_subgraph(
                parent, source, 2023, stratum, 1, 10, 20260807
            )
            self.assertNotEqual(first.anchor, second.anchor)
            validate_lightning_subgraph_sample(parent, source, 20260807, first)
            validate_lightning_subgraph_sample(parent, source, 20260807, second)

    def test_wrong_source_seed_or_parent_is_rejected(self) -> None:
        parent = _layered_parent()
        source = "c" * 64
        sample = sample_lightning_subgraph(
            parent, source, 2022, "core", 0, 12, 20260807
        )

        with self.assertRaisesRegex(StratifiedSamplingError, "source fingerprint mismatch"):
            validate_lightning_subgraph_sample(parent, "d" * 64, 20260807, sample)
        with self.assertRaisesRegex(StratifiedSamplingError, "replay mismatch"):
            validate_lightning_subgraph_sample(parent, source, 20260808, sample)
        forged = replace(sample, source_fingerprint="e" * 64)
        with self.assertRaisesRegex(StratifiedSamplingError, "source fingerprint mismatch"):
            validate_lightning_subgraph_sample(parent, source, 20260807, forged)

    def test_parent_fingerprint_is_canonical_and_structure_sensitive(self) -> None:
        parent = _layered_parent()
        rebuilt = ParentGraph.from_edges(
            reversed(parent.nodes),
            (reversed(edge.endpoints) for edge in reversed(parent.edges)),
        )
        removed = ParentGraph.from_edges(
            parent.nodes,
            (edge.endpoints for edge in parent.edges[:-1]),
        )

        self.assertEqual(parent_graph_fingerprint(parent), parent_graph_fingerprint(rebuilt))
        self.assertNotEqual(parent_graph_fingerprint(parent), parent_graph_fingerprint(removed))


if __name__ == "__main__":
    unittest.main()
