"""Contract tests for all-or-nothing hypergraph payment transitions."""

from __future__ import annotations

import unittest

from secondaryexploration.model import (
    BalanceCoordinate,
    HypergraphState,
    ModelError,
    PaymentRequest,
    Route,
    TransferStep,
)
from secondaryexploration.model.transition import (
    PaymentTransition,
    RejectionReason,
    apply_atomic_payment,
    is_route_feasible,
)


def two_edge_state(*, second_payer_balance: int = 3) -> HypergraphState:
    return HypergraphState.from_balances(
        nodes=("a", "b", "c", "d"),
        hyperedges={
            "edge-1": {"a": 5, "b": 1, "c": 0},
            "edge-2": {
                "b": second_payer_balance,
                "c": 5 - second_payer_balance,
                "d": 0,
            },
        },
    )


def two_hop_route() -> Route:
    return Route(
        steps=(
            TransferStep("edge-1", "a", "b"),
            TransferStep("edge-2", "b", "d"),
        )
    )


class RouteFeasibilityTests(unittest.TestCase):
    def test_route_is_feasible_when_every_payer_coordinate_can_pay(self) -> None:
        self.assertTrue(
            is_route_feasible(
                two_edge_state(second_payer_balance=3),
                PaymentRequest("a", "d", 3),
                two_hop_route(),
            )
        )

    def test_route_is_infeasible_when_any_later_coordinate_cannot_pay(self) -> None:
        self.assertFalse(
            is_route_feasible(
                two_edge_state(second_payer_balance=2),
                PaymentRequest("a", "d", 3),
                two_hop_route(),
            )
        )

    def test_receipt_on_one_edge_cannot_fund_another_edge_in_same_payment(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "b", "d"),
            hyperedges={
                "edge-1": {"a": 2, "b": 1},
                "edge-2": {"b": 0, "d": 3},
            },
        )

        self.assertFalse(
            is_route_feasible(
                state,
                PaymentRequest("a", "d", 1),
                two_hop_route(),
            )
        )

    def test_request_and_route_endpoints_must_match(self) -> None:
        with self.assertRaisesRegex(ModelError, "endpoint"):
            is_route_feasible(
                two_edge_state(),
                PaymentRequest("a", "c", 1),
                two_hop_route(),
            )

    def test_request_endpoints_must_exist_in_the_network(self) -> None:
        route = Route(steps=(TransferStep("edge-1", "outside", "a"),))

        with self.assertRaisesRegex(ModelError, "source.*node set"):
            is_route_feasible(
                two_edge_state(),
                PaymentRequest("outside", "a", 1),
                route,
            )

    def test_every_step_must_reference_an_existing_edge(self) -> None:
        route = Route(steps=(TransferStep("missing", "a", "d"),))

        with self.assertRaisesRegex(ModelError, "hyperedge.*missing"):
            is_route_feasible(
                two_edge_state(),
                PaymentRequest("a", "d", 1),
                route,
            )

    def test_step_endpoints_must_be_members_of_the_hyperedge(self) -> None:
        route = Route(steps=(TransferStep("edge-1", "a", "d"),))

        with self.assertRaisesRegex(ModelError, "payee.*d.*edge-1"):
            is_route_feasible(
                two_edge_state(),
                PaymentRequest("a", "d", 1),
                route,
            )

    def test_step_payer_must_be_a_member_of_the_hyperedge(self) -> None:
        route = Route(steps=(TransferStep("edge-1", "d", "a"),))

        with self.assertRaisesRegex(ModelError, "payer.*d.*edge-1"):
            is_route_feasible(
                two_edge_state(),
                PaymentRequest("d", "a", 1),
                route,
            )


class AtomicPaymentTests(unittest.TestCase):
    def test_success_updates_all_edges_and_conserves_each_edge(self) -> None:
        state = two_edge_state(second_payer_balance=3)
        before_totals = {
            edge.hyperedge_id: edge.total_balance for edge in state.hyperedges
        }

        result = apply_atomic_payment(
            state,
            PaymentRequest("a", "d", 3),
            two_hop_route(),
        )

        self.assertTrue(result.accepted)
        self.assertIsNone(result.rejection_reason)
        self.assertIsNot(result.state, state)
        self.assertEqual(result.state.edge("edge-1").balance_of("a"), 2)
        self.assertEqual(result.state.edge("edge-1").balance_of("b"), 4)
        self.assertEqual(result.state.edge("edge-1").balance_of("c"), 0)
        self.assertEqual(result.state.edge("edge-2").balance_of("b"), 0)
        self.assertEqual(result.state.edge("edge-2").balance_of("c"), 2)
        self.assertEqual(result.state.edge("edge-2").balance_of("d"), 3)
        self.assertEqual(
            {
                edge.hyperedge_id: edge.total_balance
                for edge in result.state.hyperedges
            },
            before_totals,
        )
        self.assertEqual(
            result.depleted_coordinates,
            (BalanceCoordinate("edge-2", "b"),),
        )

        self.assertEqual(state.edge("edge-1").balance_of("a"), 5)
        self.assertEqual(state.edge("edge-2").balance_of("b"), 3)

    def test_rejection_is_atomic_and_returns_exact_original_state(self) -> None:
        state = two_edge_state(second_payer_balance=2)

        result = apply_atomic_payment(
            state,
            PaymentRequest("a", "d", 3),
            two_hop_route(),
        )

        self.assertFalse(result.accepted)
        self.assertEqual(
            result.rejection_reason,
            RejectionReason.INSUFFICIENT_BALANCE,
        )
        self.assertIs(result.state, state)
        self.assertEqual(result.depleted_coordinates, ())
        self.assertEqual(state.edge("edge-1").balance_of("a"), 5)
        self.assertEqual(state.edge("edge-1").balance_of("b"), 1)

    def test_exact_boundary_hit_is_accepted_and_reported(self) -> None:
        state = two_edge_state()
        route = Route(steps=(TransferStep("edge-1", "a", "b"),))

        result = apply_atomic_payment(
            state,
            PaymentRequest("a", "b", 5),
            route,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.state.edge("edge-1").balance_of("a"), 0)
        self.assertEqual(
            result.depleted_coordinates,
            (BalanceCoordinate("edge-1", "a"),),
        )

    def test_preexisting_zero_is_not_reported_as_new_depletion(self) -> None:
        state = two_edge_state()
        route = Route(steps=(TransferStep("edge-1", "a", "b"),))

        result = apply_atomic_payment(
            state,
            PaymentRequest("a", "b", 1),
            route,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.depleted_coordinates, ())
        self.assertEqual(result.state.edge("edge-1").balance_of("c"), 0)

    def test_multiple_payer_coordinates_can_deplete_in_one_atomic_step(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "b", "d"),
            hyperedges={
                "edge-1": {"a": 2, "b": 1},
                "edge-2": {"b": 2, "d": 1},
            },
        )

        result = apply_atomic_payment(
            state,
            PaymentRequest("a", "d", 2),
            two_hop_route(),
        )

        self.assertTrue(result.accepted)
        self.assertEqual(
            result.depleted_coordinates,
            (
                BalanceCoordinate("edge-1", "a"),
                BalanceCoordinate("edge-2", "b"),
            ),
        )

    def test_untraversed_hyperedge_is_strictly_unchanged(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "b", "c", "d"),
            hyperedges={
                "edge-1": {"a": 5, "b": 1},
                "edge-2": {"b": 3, "d": 2},
                "edge-3": {"a": 4, "c": 4},
            },
        )
        untouched = state.edge("edge-3")

        result = apply_atomic_payment(
            state,
            PaymentRequest("a", "d", 2),
            two_hop_route(),
        )

        self.assertTrue(result.accepted)
        self.assertIs(result.state.edge("edge-3"), untouched)
        self.assertEqual(result.state.edge("edge-3").balances, untouched.balances)

    def test_paper_one_unit_route_increment_is_reproduced(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("0", "1", "2", "3", "4"),
            hyperedges={
                "e1": {"0": 2, "1": 2, "2": 2},
                "e2": {"2": 2, "3": 2, "4": 2},
            },
        )
        route = Route(
            steps=(
                TransferStep("e1", "0", "2"),
                TransferStep("e2", "2", "3"),
            )
        )

        result = apply_atomic_payment(
            state,
            PaymentRequest("0", "3", 1),
            route,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(
            result.state.edge("e1").balances,
            (("0", 1), ("1", 2), ("2", 3)),
        )
        self.assertEqual(
            result.state.edge("e2").balances,
            (("2", 1), ("3", 3), ("4", 2)),
        )

    def test_transition_result_rejects_inconsistent_status_fields(self) -> None:
        state = two_edge_state()

        with self.assertRaisesRegex(ModelError, "accepted.*reason"):
            PaymentTransition(
                state=state,
                accepted=True,
                rejection_reason=RejectionReason.INSUFFICIENT_BALANCE,
                depleted_coordinates=(),
            )
        with self.assertRaisesRegex(ModelError, "rejected.*reason"):
            PaymentTransition(
                state=state,
                accepted=False,
                rejection_reason=None,
                depleted_coordinates=(),
            )
        with self.assertRaisesRegex(ModelError, "rejected.*depleted"):
            PaymentTransition(
                state=state,
                accepted=False,
                rejection_reason=RejectionReason.INSUFFICIENT_BALANCE,
                depleted_coordinates=(BalanceCoordinate("edge-1", "a"),),
            )

    def test_transition_result_rejects_ghost_depletion_coordinates(self) -> None:
        state = two_edge_state()

        with self.assertRaisesRegex(ModelError, "depleted.*zero"):
            PaymentTransition(
                state=state,
                accepted=True,
                rejection_reason=None,
                depleted_coordinates=(BalanceCoordinate("edge-1", "a"),),
            )
        with self.assertRaisesRegex(ModelError, "depleted.*state"):
            PaymentTransition(
                state=state,
                accepted=True,
                rejection_reason=None,
                depleted_coordinates=(BalanceCoordinate("missing", "a"),),
            )


if __name__ == "__main__":
    unittest.main()
