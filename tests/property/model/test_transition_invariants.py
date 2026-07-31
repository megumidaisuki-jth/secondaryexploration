"""Finite exhaustive checks of atomic-transition invariants."""

from __future__ import annotations

import itertools
import unittest

from secondaryexploration.model import (
    BalanceCoordinate,
    HypergraphState,
    PaymentRequest,
    RejectionReason,
    Route,
    TransferStep,
    apply_atomic_payment,
)


class ExhaustiveTransitionInvariantTests(unittest.TestCase):
    def test_all_small_two_edge_states_preserve_atomic_contract(self) -> None:
        route = Route(
            steps=(
                TransferStep("edge-1", "a", "b"),
                TransferStep("edge-2", "b", "c"),
            )
        )
        checked_cases = 0

        for a_balance, b_in_edge_1, b_in_edge_2, c_balance in itertools.product(
            range(4),
            repeat=4,
        ):
            if a_balance + b_in_edge_1 == 0 or b_in_edge_2 + c_balance == 0:
                continue
            for amount in range(1, 4):
                with self.subTest(
                    balances=(
                        a_balance,
                        b_in_edge_1,
                        b_in_edge_2,
                        c_balance,
                    ),
                    amount=amount,
                ):
                    state = HypergraphState.from_balances(
                        nodes=("a", "b", "c"),
                        hyperedges={
                            "edge-1": {"a": a_balance, "b": b_in_edge_1},
                            "edge-2": {"b": b_in_edge_2, "c": c_balance},
                        },
                    )
                    original_hash = hash(state)
                    original_totals = tuple(
                        edge.total_balance for edge in state.hyperedges
                    )
                    feasible = a_balance >= amount and b_in_edge_2 >= amount

                    result = apply_atomic_payment(
                        state,
                        PaymentRequest("a", "c", amount),
                        route,
                    )

                    self.assertEqual(hash(state), original_hash)
                    self.assertEqual(
                        tuple(edge.total_balance for edge in state.hyperedges),
                        original_totals,
                    )
                    if not feasible:
                        self.assertFalse(result.accepted)
                        self.assertIs(result.state, state)
                        self.assertEqual(
                            result.rejection_reason,
                            RejectionReason.INSUFFICIENT_BALANCE,
                        )
                        self.assertEqual(result.depleted_coordinates, ())
                    else:
                        self.assertTrue(result.accepted)
                        self.assertIsNone(result.rejection_reason)
                        self.assertEqual(
                            tuple(
                                edge.total_balance for edge in result.state.hyperedges
                            ),
                            original_totals,
                        )
                        self.assertEqual(
                            result.state.edge("edge-1").balances,
                            (
                                ("a", a_balance - amount),
                                ("b", b_in_edge_1 + amount),
                            ),
                        )
                        self.assertEqual(
                            result.state.edge("edge-2").balances,
                            (
                                ("b", b_in_edge_2 - amount),
                                ("c", c_balance + amount),
                            ),
                        )
                        self.assertTrue(
                            all(
                                balance >= 0
                                for edge in result.state.hyperedges
                                for _, balance in edge.balances
                            )
                        )
                        expected_depletions = tuple(
                            sorted(
                                coordinate
                                for condition, coordinate in (
                                    (
                                        a_balance == amount,
                                        BalanceCoordinate("edge-1", "a"),
                                    ),
                                    (
                                        b_in_edge_2 == amount,
                                        BalanceCoordinate("edge-2", "b"),
                                    ),
                                )
                                if condition
                            )
                        )
                        self.assertEqual(
                            result.depleted_coordinates,
                            expected_depletions,
                        )
                    checked_cases += 1

        self.assertEqual(checked_cases, 675)


if __name__ == "__main__":
    unittest.main()
