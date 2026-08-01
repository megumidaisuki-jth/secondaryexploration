"""Contract tests for Gate-V1 public-source reconstruction."""

from __future__ import annotations

import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from secondaryexploration.experiments import (
    PriorPaperError,
    PriorPaperInputManifest,
    componentwise_closed_neighborhood_nch,
    componentwise_fixed_hyperedge_size,
    describe_prior_paper_topology,
    load_prior_paper_dataset,
    prior_paper_binary_state,
    prior_paper_transformed_state,
    published_order_closed_neighborhood_nch,
)
from secondaryexploration.topology import binary_topology, node_capital_totals


def _write_fixture(root: Path) -> tuple[Path, Path, PriorPaperInputManifest]:
    topology = root / "topology.zip"
    trace = root / "trace.csv"
    payload = {
        "nodes": [],
        "edges": [
            {
                "node1_pub": "a",
                "node2_pub": "b",
                "capacity": "10",
                "node1_policy": {"disabled": False},
                "node2_policy": None,
            },
            {
                "node1_pub": "b",
                "node2_pub": "a",
                "capacity": "6",
                "node1_policy": {"disabled": False},
                "node2_policy": {"disabled": True},
            },
            {
                "node1_pub": "b",
                "node2_pub": "c",
                "capacity": "8",
                "node1_policy": {"disabled": True},
                "node2_policy": {"disabled": False},
            },
            {
                "node1_pub": "d",
                "node2_pub": "e",
                "capacity": "4",
                "node1_policy": {"disabled": False},
                "node2_policy": {"disabled": False},
            },
            {
                "node1_pub": "c",
                "node2_pub": "inactive",
                "capacity": "999",
                "node1_policy": {"disabled": True},
                "node2_policy": None,
            },
        ],
    }
    with zipfile.ZipFile(topology, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("snapshot.json", json.dumps(payload))
    with trace.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("transaction_id", "source", "target", "amount_SAT"),
        )
        writer.writeheader()
        writer.writerow(
            {"transaction_id": "0", "source": "a", "target": "c", "amount_SAT": 2}
        )
        writer.writerow(
            {"transaction_id": "1", "source": "d", "target": "e", "amount_SAT": 3}
        )
    manifest = PriorPaperInputManifest(
        upstream_commit="a" * 40,
        topology_sha256=hashlib.sha256(topology.read_bytes()).hexdigest(),
        trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
    )
    return topology, trace, manifest


class PriorPaperSourceTests(unittest.TestCase):
    def test_loader_recovers_active_simple_graph_capacities_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            topology, trace, manifest = _write_fixture(Path(directory))

            dataset = load_prior_paper_dataset(topology, trace, manifest)

        self.assertEqual(dataset.parent.nodes, ("a", "b", "c", "d", "e"))
        self.assertEqual(
            tuple((edge.endpoints, capacity) for edge, capacity in dataset.edge_capacities),
            ((('a', 'b'), 16), (('b', 'c'), 8), (('d', 'e'), 4)),
        )
        self.assertEqual(dataset.scaled_node_budgets, {"a": 16, "b": 24, "c": 8, "d": 4, "e": 4})
        self.assertEqual(
            dataset.networkx_edge_order,
            (("a", "b"), ("b", "c"), ("d", "e")),
        )
        self.assertEqual(tuple(request.amount for request in dataset.requests), (2, 3))
        self.assertEqual(tuple(request.amount for request in dataset.scaled_requests), (4, 6))

    def test_hash_mismatch_blocks_source_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            topology, trace, manifest = _write_fixture(Path(directory))
            bad_manifest = PriorPaperInputManifest(
                upstream_commit=manifest.upstream_commit,
                topology_sha256="0" * 64,
                trace_sha256=manifest.trace_sha256,
            )

            with self.assertRaisesRegex(PriorPaperError, "SHA-256 mismatch"):
                load_prior_paper_dataset(topology, trace, bad_manifest)

    def test_componentwise_transforms_preserve_disconnected_source_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            topology, trace, manifest = _write_fixture(Path(directory))
            dataset = load_prior_paper_dataset(topology, trace, manifest)

        nch = componentwise_closed_neighborhood_nch(dataset.parent)
        fhs = componentwise_fixed_hyperedge_size(dataset.parent, 3)

        self.assertEqual(nch.nodes, dataset.parent.nodes)
        self.assertEqual(fhs.nodes, dataset.parent.nodes)
        self.assertFalse(nch.is_connected)
        self.assertFalse(fhs.is_connected)
        self.assertTrue(all(degree > 0 for _, degree in nch.node_incidence_degrees))
        self.assertEqual(tuple(edge.members for edge in fhs.hyperedges), (("a", "b", "c"), ("d", "e")))

    def test_published_nch_isolates_networkx_insertion_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            topology, trace, manifest = _write_fixture(Path(directory))
            dataset = load_prior_paper_dataset(topology, trace, manifest)
        source_ordered = replace(
            dataset,
            networkx_edge_order=(("b", "a"), ("b", "c"), ("d", "e")),
        )

        canonical = componentwise_closed_neighborhood_nch(dataset.parent)
        published = published_order_closed_neighborhood_nch(source_ordered)

        self.assertNotEqual(
            tuple(edge.members for edge in canonical.hyperedges),
            tuple(edge.members for edge in published.hyperedges),
        )
        self.assertIn(("a", "b", "c"), tuple(edge.members for edge in published.hyperedges))

    def test_states_preserve_published_channel_and_node_capital_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            topology, trace, manifest = _write_fixture(Path(directory))
            dataset = load_prior_paper_dataset(topology, trace, manifest)

        binary = binary_topology(dataset.parent)
        binary_state = prior_paper_binary_state(dataset)
        nch = componentwise_closed_neighborhood_nch(dataset.parent)
        nch_state = prior_paper_transformed_state(dataset, nch)

        self.assertEqual(binary_state.nodes, binary.nodes)
        self.assertEqual(binary_state.edge("binary-00000000").balances, (("a", 16), ("b", 16)))
        expected_totals = tuple(sorted(dataset.scaled_node_budgets.items()))
        self.assertEqual(node_capital_totals(binary_state), expected_totals)
        self.assertEqual(node_capital_totals(nch_state), expected_totals)
        self.assertEqual(binary_state.total_balance, nch_state.total_balance)

    def test_topology_descriptor_uses_paper_degree_convention(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            topology, trace, manifest = _write_fixture(Path(directory))
            dataset = load_prior_paper_dataset(topology, trace, manifest)

        descriptor = describe_prior_paper_topology(binary_topology(dataset.parent))

        self.assertEqual(descriptor.node_count, 5)
        self.assertEqual(descriptor.hyperedge_count, 3)
        self.assertEqual(descriptor.incidence_count, 6)
        self.assertEqual(float(descriptor.mean_incidence_degree), 1.2)
        self.assertEqual(descriptor.maximum_arity, 2)


if __name__ == "__main__":
    unittest.main()
