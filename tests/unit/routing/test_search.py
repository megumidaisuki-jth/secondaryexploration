"""Contract tests for complete balance-aware feasible-path search."""

from __future__ import annotations

from fractions import Fraction
import random
import unittest

from secondaryexploration.model import (
    HypergraphState,
    PaymentRequest,
    Route,
)
from secondaryexploration.routing.search import (
    RouteSearchResult,
    RoutingError,
    find_feasible_route,
)


class NoDrawRandom(random.Random):
    def randrange(self, stop: int) -> int:
        raise AssertionError(f"unexpected random draw with stop={stop}")


class TicketRandom(random.Random):
    def __init__(self, ticket: int) -> None:
        super().__init__(0)
        self.ticket = ticket
        self.calls: list[int] = []

    def randrange(self, stop: int) -> int:
        self.calls.append(stop)
        if not 0 <= self.ticket < stop:
            raise AssertionError(f"ticket {self.ticket} is outside [0, {stop})")
        return self.ticket


def route_signature(route: Route | None) -> tuple[tuple[str, str, str], ...] | None:
    if route is None:
        return None
    return tuple(
        (step.hyperedge_id, step.payer, step.payee) for step in route.steps
    )


class FullFeasibleSearchTests(unittest.TestCase):
    def test_direct_high_arity_hyperedge_costs_one_hop(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "s", "t"),
            hyperedges={"high-order": {"a": 2, "s": 5, "t": 0}},
        )

        result = find_feasible_route(
            state,
            PaymentRequest("s", "t", 3),
            NoDrawRandom(),
        )

        self.assertEqual(
            route_signature(result.route),
            (("high-order", "s", "t"),),
        )
        self.assertEqual(result.shortest_hops, 1)
        self.assertEqual(result.bottleneck, Fraction(2, 7))
        self.assertEqual(result.tied_route_count, 1)

    def test_directional_payer_balance_controls_residual_arc(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("s", "t"),
            hyperedges={"edge": {"s": 0, "t": 5}},
        )

        forward = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            NoDrawRandom(),
        )
        reverse = find_feasible_route(
            state,
            PaymentRequest("t", "s", 1),
            NoDrawRandom(),
        )

        self.assertEqual(forward, RouteSearchResult.no_path())
        self.assertEqual(
            route_signature(reverse.route),
            (("edge", "t", "s"),),
        )
        self.assertEqual(reverse.bottleneck, Fraction(4, 5))

    def test_shorter_route_beats_longer_route_with_larger_margin(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "s", "t"),
            hyperedges={
                "direct": {"s": 1, "t": 9},
                "first": {"a": 0, "s": 10},
                "second": {"a": 10, "t": 0},
            },
        )

        result = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            NoDrawRandom(),
        )

        self.assertEqual(route_signature(result.route), (("direct", "s", "t"),))
        self.assertEqual(result.shortest_hops, 1)
        self.assertEqual(result.bottleneck, Fraction(0, 1))

    def test_normalized_not_raw_residual_balance_selects_equal_hop_winner(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first-big": {"a": 90, "s": 10},
                "a-second-big": {"a": 10, "t": 90},
                "b-first-small": {"b": 5, "s": 5},
                "b-second-small": {"b": 5, "t": 5},
            },
        )

        result = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            NoDrawRandom(),
        )

        self.assertEqual(result.route.nodes, ("s", "b", "t"))
        self.assertEqual(result.shortest_hops, 2)
        self.assertEqual(result.bottleneck, Fraction(2, 5))
        self.assertEqual(result.tied_route_count, 1)

    def test_parallel_hyperedges_are_distinct_uniformly_tied_routes(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("s", "t"),
            hyperedges={
                "edge-1": {"s": 2, "t": 0},
                "edge-2": {"s": 2, "t": 0},
            },
        )
        first_rng = TicketRandom(0)
        second_rng = TicketRandom(1)

        first = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            first_rng,
        )
        second = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            second_rng,
        )

        self.assertEqual(first.tied_route_count, 2)
        self.assertEqual(second.tied_route_count, 2)
        self.assertEqual(first_rng.calls, [2])
        self.assertEqual(second_rng.calls, [2])
        self.assertEqual(
            {route_signature(first.route), route_signature(second.route)},
            {
                (("edge-1", "s", "t"),),
                (("edge-2", "s", "t"),),
            },
        )

    def test_diamond_ticket_counts_complete_optimal_routes(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first": {"a": 0, "s": 2},
                "a-second": {"a": 2, "t": 0},
                "b-first": {"b": 0, "s": 2},
                "b-second": {"b": 2, "t": 0},
            },
        )

        first = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            TicketRandom(0),
        )
        second = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            TicketRandom(1),
        )

        self.assertEqual(first.tied_route_count, 2)
        self.assertEqual(first.bottleneck, Fraction(1, 2))
        self.assertEqual(first.route.nodes, ("s", "a", "t"))
        self.assertEqual(second.route.nodes, ("s", "b", "t"))

    def test_exponentially_many_ties_are_counted_without_route_materialization(self) -> None:
        layer_count = 15
        layers = tuple(
            (f"layer-{index:02d}-a", f"layer-{index:02d}-b")
            for index in range(layer_count)
        )
        nodes = ("source", "target") + tuple(
            node for layer in layers for node in layer
        )
        hyperedges: dict[str, dict[str, int]] = {}
        for next_node in layers[0]:
            hyperedges[f"source-to-{next_node}"] = {"source": 2, next_node: 0}
        for layer_index, (current_layer, next_layer) in enumerate(
            zip(layers, layers[1:])
        ):
            for payer in current_layer:
                for payee in next_layer:
                    hyperedges[
                        f"layer-{layer_index:02d}-{payer}-to-{payee}"
                    ] = {payer: 2, payee: 0}
        for payer in layers[-1]:
            hyperedges[f"{payer}-to-target"] = {payer: 2, "target": 0}
        state = HypergraphState.from_balances(nodes=nodes, hyperedges=hyperedges)
        last_ticket = 2**layer_count - 1
        rng = TicketRandom(last_ticket)

        result = find_feasible_route(
            state,
            PaymentRequest("source", "target", 1),
            rng,
        )

        self.assertEqual(result.shortest_hops, layer_count + 1)
        self.assertEqual(result.bottleneck, Fraction(1, 2))
        self.assertEqual(result.tied_route_count, 2**layer_count)
        self.assertEqual(rng.calls, [2**layer_count])
        self.assertEqual(result.route.nodes[0], "source")
        self.assertEqual(result.route.nodes[-1], "target")

    def test_unique_optimum_consumes_no_random_draw(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first": {"a": 1, "s": 3},
                "a-second": {"a": 3, "t": 1},
                "b-first": {"b": 2, "s": 2},
                "b-second": {"b": 2, "t": 2},
            },
        )

        result = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            NoDrawRandom(),
        )

        self.assertEqual(result.route.nodes, ("s", "a", "t"))
        self.assertEqual(result.tied_route_count, 1)

    def test_no_path_is_explicit_and_consumes_no_random_draw(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("isolated", "s", "t"),
            hyperedges={"edge": {"s": 1, "t": 0}},
        )

        result = find_feasible_route(
            state,
            PaymentRequest("s", "isolated", 1),
            NoDrawRandom(),
        )

        self.assertEqual(result, RouteSearchResult.no_path())
        self.assertIsNone(result.route)
        self.assertIsNone(result.shortest_hops)
        self.assertIsNone(result.bottleneck)
        self.assertEqual(result.tied_route_count, 0)

    def test_request_endpoints_and_rng_are_validated(self) -> None:
        state = HypergraphState.from_balances(nodes=("s", "t"), hyperedges={})

        with self.assertRaisesRegex(RoutingError, "source.*node set"):
            find_feasible_route(
                state,
                PaymentRequest("outside", "t", 1),
                NoDrawRandom(),
            )
        with self.assertRaisesRegex(RoutingError, "rng"):
            find_feasible_route(  # type: ignore[arg-type]
                state,
                PaymentRequest("s", "t", 1),
                object(),
            )


class RouteSearchResultTests(unittest.TestCase):
    def test_no_path_factory_is_internally_consistent(self) -> None:
        self.assertEqual(
            RouteSearchResult.no_path(),
            RouteSearchResult(
                route=None,
                shortest_hops=None,
                bottleneck=None,
                tied_route_count=0,
            ),
        )

    def test_inconsistent_no_path_metadata_is_rejected(self) -> None:
        with self.assertRaisesRegex(RoutingError, "no-path"):
            RouteSearchResult(
                route=None,
                shortest_hops=1,
                bottleneck=None,
                tied_route_count=0,
            )

    def test_inconsistent_found_path_metadata_is_rejected(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("s", "t"),
            hyperedges={"edge": {"s": 2, "t": 0}},
        )
        valid = find_feasible_route(
            state,
            PaymentRequest("s", "t", 1),
            NoDrawRandom(),
        )
        assert valid.route is not None

        invalid_cases = [
            (None, Fraction(1, 2), 1),
            (2, Fraction(1, 2), 1),
            (1, None, 1),
            (1, Fraction(-1, 2), 1),
            (1, Fraction(3, 2), 1),
            (1, Fraction(1, 2), 0),
        ]
        for hops, bottleneck, tied_count in invalid_cases:
            with self.subTest(
                hops=hops,
                bottleneck=bottleneck,
                tied_count=tied_count,
            ):
                with self.assertRaises(RoutingError):
                    RouteSearchResult(
                        route=valid.route,
                        shortest_hops=hops,
                        bottleneck=bottleneck,
                        tied_route_count=tied_count,
                    )


if __name__ == "__main__":
    unittest.main()
