"""Tests for exact equal-per-node-capital initialization."""

from __future__ import annotations

import unittest

from secondaryexploration.topology import (
    HypergraphTopology,
    TopologyError,
    common_core_sunflower,
    equal_node_capital_state,
    node_budget_capital_state,
    node_capital_totals,
    uniform_overlap_chain,
)


class EqualNodeCapitalTests(unittest.TestCase):
    def test_chain_state_preserves_every_node_budget_and_membership(self) -> None:
        topology = uniform_overlap_chain(arity=3, overlap=1, edge_count=4)

        state = equal_node_capital_state(topology, per_node_capital=12)

        self.assertEqual(state.nodes, topology.nodes)
        self.assertEqual(state.total_balance, len(topology.nodes) * 12)
        self.assertEqual(
            node_capital_totals(state),
            tuple((node_id, 12) for node_id in topology.nodes),
        )
        for spec, edge in zip(topology.hyperedges, state.hyperedges):
            self.assertEqual(edge.hyperedge_id, spec.hyperedge_id)
            self.assertEqual(edge.members, spec.members)

    def test_sunflower_core_divides_budget_equally_across_channels(self) -> None:
        topology = common_core_sunflower(arity=3, overlap=1, edge_count=4)

        state = equal_node_capital_state(topology, per_node_capital=12)

        core_balances = tuple(
            edge.balance_of("v00000000") for edge in state.hyperedges
        )
        self.assertEqual(core_balances, (3, 3, 3, 3))
        for node_id, degree in topology.node_incidence_degrees:
            expected_local_balance = 12 // degree
            for edge in state.hyperedges:
                if node_id in edge.members:
                    self.assertEqual(
                        edge.balance_of(node_id),
                        expected_local_balance,
                    )

    def test_nondivisible_budget_is_rejected_without_identifier_bias(self) -> None:
        topology = common_core_sunflower(arity=3, overlap=1, edge_count=4)

        with self.assertRaisesRegex(TopologyError, "not divisible"):
            equal_node_capital_state(topology, per_node_capital=10)

    def test_isolated_node_cannot_receive_locked_capital(self) -> None:
        topology = HypergraphTopology.from_edges(
            nodes=("a", "b", "isolated"),
            hyperedges={"edge": ("a", "b")},
        )

        with self.assertRaisesRegex(TopologyError, "isolated"):
            equal_node_capital_state(topology, per_node_capital=10)

    def test_heterogeneous_budgets_are_preserved_with_bounded_rounding(self) -> None:
        topology = HypergraphTopology.from_edges(
            nodes=("a", "b", "c"),
            hyperedges={
                "edge-1": ("a", "b"),
                "edge-2": ("a", "c"),
                "edge-3": ("a", "b", "c"),
            },
        )

        state = node_budget_capital_state(
            topology,
            {"a": 8, "b": 5, "c": 4},
        )

        self.assertEqual(
            node_capital_totals(state),
            (("a", 8), ("b", 5), ("c", 4)),
        )
        a_allocations = tuple(
            edge.balance_of("a")
            for edge in state.hyperedges
            if "a" in edge.members
        )
        self.assertEqual(a_allocations, (3, 3, 2))

    def test_heterogeneous_budget_contract_rejects_bad_mappings(self) -> None:
        topology = HypergraphTopology.from_edges(
            nodes=("a", "b"),
            hyperedges={"edge": ("a", "b")},
        )

        for budgets in ({"a": 1}, {"a": 1, "b": 0}, {"a": 1, "b": 1.0}):
            with self.subTest(budgets=budgets):
                with self.assertRaises(TopologyError):
                    node_budget_capital_state(topology, budgets)  # type: ignore[arg-type]

    def test_capital_inputs_and_state_type_are_validated(self) -> None:
        topology = uniform_overlap_chain(2, 1, 2)
        for invalid in (0, -1, True, 1.0):
            with self.subTest(invalid=invalid):
                with self.assertRaises(TopologyError):
                    equal_node_capital_state(  # type: ignore[arg-type]
                        topology,
                        per_node_capital=invalid,
                    )

        with self.assertRaises(TopologyError):
            equal_node_capital_state(object(), 10)  # type: ignore[arg-type]
        with self.assertRaises(TopologyError):
            node_capital_totals(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
