"""Contract tests for immutable hypergraph payment-network entities."""

from __future__ import annotations

import unittest

from secondaryexploration.model.entities import (
    BalanceCoordinate,
    HyperedgeState,
    HypergraphState,
    ModelError,
    PaymentRequest,
    Route,
    TransferStep,
)


class HyperedgeStateTests(unittest.TestCase):
    def test_factory_canonicalizes_balances_and_state_is_hashable(self) -> None:
        edge = HyperedgeState.from_balances(
            "edge-1",
            {"carol": 0, "alice": 5, "bob": 3},
        )

        self.assertEqual(
            edge.balances,
            (("alice", 5), ("bob", 3), ("carol", 0)),
        )
        self.assertEqual(edge.members, ("alice", "bob", "carol"))
        self.assertEqual(edge.total_balance, 8)
        self.assertEqual(edge.balance_of("bob"), 3)
        self.assertIsInstance(hash(edge), int)

    def test_unknown_member_lookup_is_rejected(self) -> None:
        edge = HyperedgeState.from_balances("edge-1", {"alice": 1, "bob": 1})

        with self.assertRaisesRegex(ModelError, "member.*carol"):
            edge.balance_of("carol")

    def test_invalid_identifiers_are_rejected(self) -> None:
        invalid_identifiers: tuple[object, ...] = (4, "", " ", " edge", "edge ", "e\x00dge")
        for invalid_value in invalid_identifiers:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(ModelError, "hyperedge_id"):
                    HyperedgeState.from_balances(  # type: ignore[arg-type]
                        invalid_value,
                        {"alice": 1, "bob": 1},
                    )

    def test_invalid_balance_collections_are_rejected(self) -> None:
        invalid_balances: list[dict[str, object]] = [
            {},
            {"alice": 1},
            {"alice": 0, "bob": 0},
            {"alice": True, "bob": 1},
            {"alice": -1, "bob": 2},
            {"alice": 1.0, "bob": 1},
            {"": 1, "bob": 1},
            {" alice": 1, "bob": 1},
        ]
        for invalid_value in invalid_balances:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ModelError):
                    HyperedgeState.from_balances(  # type: ignore[arg-type]
                        "edge-1",
                        invalid_value,
                    )

    def test_direct_constructor_requires_canonical_unique_tuple(self) -> None:
        invalid_tuples = [
            (("bob", 1), ("alice", 1)),
            (("alice", 1), ("alice", 2)),
        ]
        for invalid_value in invalid_tuples:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(ModelError, "canonical|unique"):
                    HyperedgeState("edge-1", invalid_value)

        with self.assertRaisesRegex(ModelError, "tuple"):
            HyperedgeState(  # type: ignore[arg-type]
                "edge-1",
                [["alice", 1], ["bob", 1]],
            )


class HypergraphStateTests(unittest.TestCase):
    def test_factory_canonicalizes_edges_and_preserves_isolated_nodes(self) -> None:
        state = HypergraphState.from_balances(
            nodes=["d", "c", "b", "a"],
            hyperedges={
                "edge-2": {"b": 2, "c": 2},
                "edge-1": {"a": 3, "b": 1},
            },
        )

        self.assertEqual(state.nodes, ("a", "b", "c", "d"))
        self.assertEqual(
            tuple(edge.hyperedge_id for edge in state.hyperedges),
            ("edge-1", "edge-2"),
        )
        self.assertEqual(state.edge("edge-1").balance_of("a"), 3)
        self.assertEqual(state.total_balance, 8)
        self.assertIsInstance(hash(state), int)

    def test_empty_edge_collection_is_representable(self) -> None:
        state = HypergraphState.from_balances(nodes=["alice"], hyperedges={})

        self.assertEqual(state.nodes, ("alice",))
        self.assertEqual(state.hyperedges, ())
        self.assertEqual(state.total_balance, 0)

    def test_unknown_edge_lookup_is_rejected(self) -> None:
        state = HypergraphState.from_balances(nodes=["alice"], hyperedges={})

        with self.assertRaisesRegex(ModelError, "hyperedge.*missing"):
            state.edge("missing")

    def test_unknown_hyperedge_member_is_rejected(self) -> None:
        with self.assertRaisesRegex(ModelError, "carol.*node set"):
            HypergraphState.from_balances(
                nodes=["alice", "bob"],
                hyperedges={"edge-1": {"alice": 1, "carol": 1}},
            )

    def test_invalid_node_collections_are_rejected(self) -> None:
        invalid_nodes: list[object] = [
            [],
            ["alice", "alice"],
            ["alice", " bob"],
            ["alice", 4],
        ]
        for invalid_value in invalid_nodes:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(ModelError, "nodes|node"):
                    HypergraphState.from_balances(  # type: ignore[arg-type]
                        nodes=invalid_value,
                        hyperedges={},
                    )

    def test_direct_constructor_requires_canonical_unique_tuples(self) -> None:
        edge = HyperedgeState.from_balances("edge-1", {"alice": 1, "bob": 1})

        with self.assertRaisesRegex(ModelError, "nodes.*canonical"):
            HypergraphState(nodes=("bob", "alice"), hyperedges=(edge,))
        with self.assertRaisesRegex(ModelError, "hyperedges.*unique"):
            HypergraphState(
                nodes=("alice", "bob"),
                hyperedges=(edge, edge),
            )


class RequestAndRouteTests(unittest.TestCase):
    def test_payment_request_accepts_positive_integer_amount(self) -> None:
        request = PaymentRequest("alice", "carol", 3)

        self.assertEqual(request.source, "alice")
        self.assertEqual(request.destination, "carol")
        self.assertEqual(request.amount, 3)
        self.assertIsInstance(hash(request), int)

    def test_invalid_payment_requests_are_rejected(self) -> None:
        invalid_cases: list[tuple[object, object, object]] = [
            ("alice", "alice", 1),
            ("", "bob", 1),
            ("alice", " bob", 1),
            (4, "bob", 1),
            ("alice", "bob", True),
            ("alice", "bob", 0),
            ("alice", "bob", -1),
            ("alice", "bob", 1.0),
        ]
        for source, destination, amount in invalid_cases:
            with self.subTest(source=source, destination=destination, amount=amount):
                with self.assertRaises(ModelError):
                    PaymentRequest(  # type: ignore[arg-type]
                        source,
                        destination,
                        amount,
                    )

    def test_route_exposes_continuous_node_path(self) -> None:
        route = Route(
            steps=(
                TransferStep("edge-1", "alice", "bob"),
                TransferStep("edge-2", "bob", "carol"),
            )
        )

        self.assertEqual(route.source, "alice")
        self.assertEqual(route.destination, "carol")
        self.assertEqual(route.hop_count, 2)
        self.assertEqual(route.nodes, ("alice", "bob", "carol"))
        self.assertIsInstance(hash(route), int)

    def test_invalid_transfer_steps_are_rejected(self) -> None:
        invalid_cases: list[tuple[object, object, object]] = [
            ("", "alice", "bob"),
            ("edge-1", "", "bob"),
            ("edge-1", "alice", " bob"),
            ("edge-1", "alice", "alice"),
        ]
        for edge, payer, payee in invalid_cases:
            with self.subTest(edge=edge, payer=payer, payee=payee):
                with self.assertRaises(ModelError):
                    TransferStep(edge, payer, payee)  # type: ignore[arg-type]

    def test_invalid_routes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ModelError, "non-empty"):
            Route(steps=())
        with self.assertRaisesRegex(ModelError, "tuple"):
            Route(  # type: ignore[arg-type]
                steps=[TransferStep("edge-1", "alice", "bob")],
            )
        with self.assertRaisesRegex(ModelError, "continuous"):
            Route(
                steps=(
                    TransferStep("edge-1", "alice", "bob"),
                    TransferStep("edge-2", "carol", "dave"),
                )
            )
        with self.assertRaisesRegex(ModelError, "repeat.*hyperedge"):
            Route(
                steps=(
                    TransferStep("edge-1", "alice", "bob"),
                    TransferStep("edge-1", "bob", "carol"),
                )
            )
        with self.assertRaisesRegex(ModelError, "repeat.*hyperedge"):
            Route(
                steps=(
                    TransferStep("edge-1", "alice", "bob"),
                    TransferStep("edge-2", "bob", "carol"),
                    TransferStep("edge-1", "carol", "dave"),
                )
            )
        with self.assertRaisesRegex(ModelError, "repeat.*node"):
            Route(
                steps=(
                    TransferStep("edge-1", "alice", "bob"),
                    TransferStep("edge-2", "bob", "alice"),
                )
            )

    def test_balance_coordinate_is_orderable_and_validated(self) -> None:
        coordinates = [
            BalanceCoordinate("edge-2", "alice"),
            BalanceCoordinate("edge-1", "bob"),
        ]

        self.assertEqual(
            sorted(coordinates),
            [
                BalanceCoordinate("edge-1", "bob"),
                BalanceCoordinate("edge-2", "alice"),
            ],
        )
        with self.assertRaisesRegex(ModelError, "node_id"):
            BalanceCoordinate("edge-1", "")


if __name__ == "__main__":
    unittest.main()
