"""Cross-check production feasible search against an independent DFS oracle."""

from __future__ import annotations

import inspect
import itertools
import random
import unittest

from secondaryexploration.model import (
    HypergraphState,
    PaymentRequest,
    apply_atomic_payment,
    is_route_feasible,
)
from secondaryexploration.routing import find_feasible_route
from tests.exact import reference_full_search
from tests.exact.reference_full_search import exhaustive_optimal_routes


def signature(route: object) -> tuple[tuple[str, str, str], ...]:
    steps = getattr(route, "steps")
    return tuple(
        (step.hyperedge_id, step.payer, step.payee) for step in steps
    )


class IndependentOracleTests(unittest.TestCase):
    def test_reference_implementation_does_not_import_production_routing(self) -> None:
        source = inspect.getsource(reference_full_search)

        self.assertNotIn("secondaryexploration.routing", source)
        self.assertNotIn("find_feasible_route", source)

    def test_weaker_prefix_is_counted_when_common_suffix_sets_bottleneck(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("s", "t", "u"),
            hyperedges={
                "high-prefix": {"s": 9, "u": 1},
                "low-prefix": {"s": 6, "u": 4},
                "shared-tail": {"t": 6, "u": 4},
            },
        )
        request = PaymentRequest("s", "t", 1)
        oracle = exhaustive_optimal_routes(state, request)

        production = find_feasible_route(state, request, random.Random(7))

        self.assertEqual(production.shortest_hops, 2)
        self.assertEqual(production.bottleneck, oracle.bottleneck)
        self.assertEqual(production.tied_route_count, 2)
        self.assertEqual(len(oracle.routes), 2)
        self.assertIn(
            signature(production.route),
            {signature(route) for route in oracle.routes},
        )

    def test_production_matches_oracle_across_small_balance_family(self) -> None:
        balance_patterns = (
            (2, 0, 0),
            (0, 2, 0),
            (0, 0, 2),
            (1, 1, 0),
            (1, 0, 1),
            (0, 1, 1),
            (1, 1, 1),
        )
        nodes = ("0", "1", "2", "3")
        requests = tuple(
            PaymentRequest(source, destination, amount)
            for source, destination in itertools.permutations(nodes, 2)
            for amount in (1, 2)
        )
        checked_cases = 0

        for first_pattern, second_pattern in itertools.product(
            balance_patterns,
            repeat=2,
        ):
            state = HypergraphState.from_balances(
                nodes=nodes,
                hyperedges={
                    "edge-1": dict(zip(("0", "1", "2"), first_pattern)),
                    "edge-2": dict(zip(("1", "2", "3"), second_pattern)),
                },
            )
            for request in requests:
                with self.subTest(
                    first_pattern=first_pattern,
                    second_pattern=second_pattern,
                    request=request,
                ):
                    oracle = exhaustive_optimal_routes(state, request)
                    production = find_feasible_route(
                        state,
                        request,
                        random.Random(20260731),
                    )

                    self.assertEqual(
                        production.shortest_hops,
                        oracle.shortest_hops,
                    )
                    self.assertEqual(production.bottleneck, oracle.bottleneck)
                    self.assertEqual(
                        production.tied_route_count,
                        len(oracle.routes),
                    )
                    if not oracle.routes:
                        self.assertIsNone(production.route)
                    else:
                        self.assertIsNotNone(production.route)
                        self.assertIn(
                            signature(production.route),
                            {signature(route) for route in oracle.routes},
                        )
                        assert production.route is not None
                        self.assertTrue(
                            is_route_feasible(state, request, production.route)
                        )
                        self.assertTrue(
                            apply_atomic_payment(
                                state,
                                request,
                                production.route,
                            ).accepted
                        )
                    checked_cases += 1

        self.assertEqual(checked_cases, 1_176)


if __name__ == "__main__":
    unittest.main()
