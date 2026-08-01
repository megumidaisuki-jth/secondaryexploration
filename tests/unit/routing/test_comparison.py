"""Tests for isolated shortest-path comparison policies."""

from __future__ import annotations

from fractions import Fraction
import random
import unittest

from secondaryexploration.model import HypergraphState, PaymentRequest
from secondaryexploration.routing import (
    TopologyRouteSearchResult,
    find_balance_independent_uniform_shortest_route,
    find_uniform_shortest_available_route,
)
from secondaryexploration.topology import HypergraphTopology


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
            raise AssertionError("ticket outside route range")
        return self.ticket


class UniformShortestAvailableTests(unittest.TestCase):
    def test_lower_bottleneck_shortest_route_remains_in_uniform_tie(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first": {"a": 0, "s": 10},
                "a-second": {"a": 10, "t": 0},
                "b-first": {"b": 8, "s": 2},
                "b-second": {"b": 10, "t": 0},
            },
        )
        request = PaymentRequest("s", "t", 1)

        stronger = find_uniform_shortest_available_route(
            state, request, TicketRandom(0)
        )
        weaker = find_uniform_shortest_available_route(
            state, request, TicketRandom(1)
        )

        self.assertEqual(stronger.route.nodes, ("s", "a", "t"))
        self.assertEqual(weaker.route.nodes, ("s", "b", "t"))
        self.assertEqual(stronger.tied_route_count, 2)
        self.assertEqual(weaker.tied_route_count, 2)
        self.assertEqual(stronger.bottleneck, Fraction(9, 10))
        self.assertEqual(weaker.bottleneck, Fraction(1, 10))

    def test_parallel_hyperedges_are_distinct_shortest_routes(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("s", "t"),
            hyperedges={
                "edge-a": {"s": 2, "t": 0},
                "edge-b": {"s": 2, "t": 0},
            },
        )
        first_rng = TicketRandom(0)
        second_rng = TicketRandom(1)

        first = find_uniform_shortest_available_route(
            state, PaymentRequest("s", "t", 1), first_rng
        )
        second = find_uniform_shortest_available_route(
            state, PaymentRequest("s", "t", 1), second_rng
        )

        self.assertEqual(first_rng.calls, [2])
        self.assertEqual(second_rng.calls, [2])
        self.assertEqual(first.route.steps[0].hyperedge_id, "edge-a")
        self.assertEqual(second.route.steps[0].hyperedge_id, "edge-b")

    def test_no_available_path_is_explicit_without_draw(self) -> None:
        state = HypergraphState.from_balances(
            nodes=("s", "t"),
            hyperedges={"edge": {"s": 0, "t": 4}},
        )

        result = find_uniform_shortest_available_route(
            state, PaymentRequest("s", "t", 1), NoDrawRandom()
        )

        self.assertIsNone(result.route)
        self.assertEqual(result.tied_route_count, 0)


class BalanceIndependentShortestTests(unittest.TestCase):
    def test_route_exists_even_when_current_direction_is_depleted(self) -> None:
        topology = HypergraphTopology.from_edges(
            nodes=("s", "t"),
            hyperedges={"edge": ("s", "t")},
        )

        result = find_balance_independent_uniform_shortest_route(
            topology,
            PaymentRequest("s", "t", 5),
            NoDrawRandom(),
        )

        self.assertEqual(result.route.nodes, ("s", "t"))
        self.assertEqual(result.shortest_hops, 1)
        self.assertEqual(result.tied_route_count, 1)

    def test_diamond_routes_are_uniformly_ticketed(self) -> None:
        topology = HypergraphTopology.from_edges(
            nodes=("a", "b", "s", "t"),
            hyperedges={
                "a-first": ("a", "s"),
                "a-second": ("a", "t"),
                "b-first": ("b", "s"),
                "b-second": ("b", "t"),
            },
        )

        first = find_balance_independent_uniform_shortest_route(
            topology, PaymentRequest("s", "t", 1), TicketRandom(0)
        )
        second = find_balance_independent_uniform_shortest_route(
            topology, PaymentRequest("s", "t", 1), TicketRandom(1)
        )

        self.assertEqual(first.route.nodes, ("s", "a", "t"))
        self.assertEqual(second.route.nodes, ("s", "b", "t"))
        self.assertEqual(first.tied_route_count, 2)

    def test_disconnected_topology_returns_distinct_no_path_type(self) -> None:
        topology = HypergraphTopology.from_edges(
            nodes=("isolated", "s", "t"),
            hyperedges={"edge": ("s", "t")},
        )

        result = find_balance_independent_uniform_shortest_route(
            topology,
            PaymentRequest("s", "isolated", 1),
            NoDrawRandom(),
        )

        self.assertEqual(result, TopologyRouteSearchResult.no_path())


if __name__ == "__main__":
    unittest.main()
