"""Contracts for immutable paired manifests and shared route tickets."""

from __future__ import annotations

from dataclasses import replace
import unittest

from secondaryexploration.experiments import (
    ExperimentError,
    PairedRunManifest,
    PairedRunResult,
    RouteChoiceRandom,
    TopologyVariant,
    VariantRunResult,
    route_choice_rng,
    route_choice_ticket,
    run_paired_experiment,
)
from secondaryexploration.model import HypergraphState, PaymentRequest
from secondaryexploration.simulation import run_core_trace_with_request_rngs
from secondaryexploration.topology import (
    HypergraphTopology,
    common_core_sunflower,
    equal_node_capital_state,
    uniform_overlap_chain,
)
from secondaryexploration.traffic import (
    AmountDistribution,
    DemandKernel,
    generate_request_trace,
    uniform_kernel,
)


def _manifest(length: int = 12) -> PairedRunManifest:
    chain = uniform_overlap_chain(arity=3, overlap=1, edge_count=3)
    sunflower = common_core_sunflower(arity=3, overlap=1, edge_count=3)
    trace = generate_request_trace(
        uniform_kernel(chain.nodes),
        AmountDistribution.from_weights(((1, 3), (2, 1))),
        length,
        root_seed=101,
    )
    return PairedRunManifest(
        block_id="parent-0007/trace-0003",
        trace=trace,
        routing_root_seed=20260801,
        variants=(
            TopologyVariant(
                variant_id="chain",
                family="anchor-chain",
                topology=chain,
                initial_state=equal_node_capital_state(chain, 12),
            ),
            TopologyVariant(
                variant_id="sunflower",
                family="anchor-sunflower",
                topology=sunflower,
                initial_state=equal_node_capital_state(sunflower, 12),
            ),
        ),
    )


class RouteChoiceTicketTests(unittest.TestCase):
    def test_known_ticket_vector_and_quantile_mapping(self) -> None:
        tickets = tuple(route_choice_ticket(20260801, index) for index in range(1, 5))

        self.assertEqual(
            tickets,
            (
                5609536081617205108,
                18119227559951936997,
                8391485650047947335,
                6003789568320102289,
            ),
        )
        denominator = 2**64
        for ticket in tickets:
            for tied_count in (1, 2, 3, 17):
                rng = route_choice_rng(20260801, tickets.index(ticket) + 1)
                self.assertEqual(rng.randrange(tied_count), ticket * tied_count // denominator)

        large_rng = route_choice_rng(20260801, 1)
        large_choice = large_rng.randrange(2**64 + 7)
        self.assertGreaterEqual(large_choice, 0)
        self.assertLess(large_choice, 2**64 + 7)
        self.assertGreaterEqual(large_rng.refinement_blocks_used, 1)

        boundary_rng = RouteChoiceRandom(2**64 // 3)
        self.assertIn(boundary_rng.randrange(3), (0, 1))
        self.assertGreaterEqual(boundary_rng.refinement_blocks_used, 1)

        high_rng = RouteChoiceRandom(2**64 - 1)
        self.assertGreaterEqual(high_rng.randrange(2**64 + 7), 2**64)

    def test_request_index_does_not_depend_on_prior_tie_consumption(self) -> None:
        skipped_first = route_choice_rng(91, 2).randrange(7)
        consumed_first = route_choice_rng(91, 1)
        consumed_first.randrange(19)
        second_after_consumption = route_choice_rng(91, 2).randrange(7)

        self.assertEqual(skipped_first, second_after_consumption)

    def test_ticket_api_fails_closed(self) -> None:
        invalid_calls = (
            lambda: route_choice_ticket(-1, 1),
            lambda: route_choice_ticket(0, 0),
            lambda: route_choice_rng(0, 1).randrange(0),
            lambda: route_choice_rng(0, 1).randrange(True),
            lambda: route_choice_rng(0, 1).randrange(1, 2),
            lambda: (lambda rng: (rng.randrange(2), rng.randrange(2)))(route_choice_rng(0, 1)),
        )
        for call in invalid_calls:
            with self.subTest(call=call):
                with self.assertRaises(ExperimentError):
                    call()


class ManifestTests(unittest.TestCase):
    def test_manifest_is_canonical_and_fingerprint_sensitive(self) -> None:
        manifest = _manifest()

        self.assertEqual(tuple(item.variant_id for item in manifest.variants), ("chain", "sunflower"))
        self.assertEqual(
            manifest.fingerprint,
            "b89c2ffd82c1d84337ba6a2d5ade180eac348128ae48961c1dbff31b0d609984",
        )
        self.assertEqual(manifest.fingerprint, manifest.fingerprint)
        self.assertNotEqual(
            manifest.fingerprint,
            replace(manifest, routing_root_seed=manifest.routing_root_seed + 1).fingerprint,
        )
        self.assertNotEqual(
            manifest.fingerprint,
            replace(manifest, block_id="parent-0007/trace-0004").fingerprint,
        )

    def test_manifest_rejects_noncanonical_duplicate_or_single_variants(self) -> None:
        manifest = _manifest()
        chain, sunflower = manifest.variants
        cases = (
            (sunflower, chain),
            (chain, chain),
            (chain,),
        )
        for variants in cases:
            with self.subTest(variants=variants):
                with self.assertRaises(ExperimentError):
                    replace(manifest, variants=variants)

    def test_manifest_rejects_trace_node_or_state_structure_mismatch(self) -> None:
        manifest = _manifest()
        chain, sunflower = manifest.variants
        foreign_trace = generate_request_trace(
            uniform_kernel(("a", "b")),
            AmountDistribution.from_weights(((1, 1),)),
            manifest.trace.length,
            root_seed=5,
        )
        bad_state = HypergraphState.from_balances(
            chain.topology.nodes,
            {"wrong-edge": {chain.topology.nodes[0]: 1, chain.topology.nodes[1]: 1}},
        )
        calls = (
            lambda: replace(manifest, trace=foreign_trace),
            lambda: replace(chain, initial_state=bad_state),
        )
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(ExperimentError):
                    call()

    def test_manifest_rejects_unequal_per_node_capital(self) -> None:
        manifest = _manifest()
        chain, sunflower = manifest.variants
        unequal = replace(
            sunflower,
            initial_state=equal_node_capital_state(sunflower.topology, 18),
        )

        with self.assertRaisesRegex(ExperimentError, "per-node capital"):
            replace(manifest, variants=(chain, unequal))


class PairedRunTests(unittest.TestCase):
    def test_end_to_end_result_reuses_trace_and_replays_exactly(self) -> None:
        manifest = _manifest(length=24)

        result = run_paired_experiment(manifest)

        self.assertEqual(result.manifest_fingerprint, manifest.fingerprint)
        self.assertEqual(result.horizon, manifest.trace.length)
        self.assertEqual(
            tuple(item.variant_id for item in result.variant_results),
            ("chain", "sunflower"),
        )
        for item in result.variant_results:
            self.assertEqual(item.simulation.horizon, manifest.trace.length)
            for request, outcome in zip(manifest.trace.requests, item.simulation.outcomes):
                self.assertIs(outcome.request, request)

    def test_result_rejects_sequential_rng_record_that_violates_common_tickets(self) -> None:
        nodes = ("a", "b", "s", "t")
        topology = HypergraphTopology.from_edges(
            nodes,
            {
                "a1": ("s", "a"),
                "a2": ("a", "t"),
                "b1": ("s", "b"),
                "b2": ("b", "t"),
            },
        )
        state = HypergraphState.from_balances(
            nodes,
            {
                edge.hyperedge_id: {member: 20 for member in edge.members}
                for edge in topology.hyperedges
            },
        )
        kernel = DemandKernel.from_weights(
            nodes,
            (
                (source, destination, 1_000_000 if (source, destination) == ("s", "t") else 1)
                for source in nodes
                for destination in nodes
                if source != destination
            ),
        )
        trace = generate_request_trace(
            kernel,
            AmountDistribution.from_weights(((1, 1),)),
            1,
            root_seed=0,
        )
        self.assertEqual(trace.requests, (PaymentRequest("s", "t", 1),))
        manifest = PairedRunManifest(
            block_id="two-path-counterexample",
            trace=trace,
            routing_root_seed=0,
            variants=(
                TopologyVariant("first", "two-path", topology, state),
                TopologyVariant("second", "two-path", topology, state),
            ),
        )
        valid = run_paired_experiment(manifest)
        variant = manifest.variants[0]
        wrong = run_core_trace_with_request_rngs(
            variant.initial_state,
            manifest.trace.requests,
            (route_choice_rng(1, 1),),
        )
        self.assertNotEqual(
            valid.variant_results[0].simulation.outcomes[0].search_result.route,
            wrong.outcomes[0].search_result.route,
        )
        forged = (
            VariantRunResult(variant.variant_id, wrong),
            valid.variant_results[1],
        )

        with self.assertRaisesRegex(ExperimentError, "common route-choice tickets"):
            PairedRunResult(manifest=manifest, variant_results=forged)

    def test_result_rejects_missing_or_mislabeled_variant(self) -> None:
        valid = run_paired_experiment(_manifest(length=4))
        with self.assertRaises(ExperimentError):
            replace(valid, variant_results=valid.variant_results[:1])
        with self.assertRaises(ExperimentError):
            replace(
                valid,
                variant_results=(
                    replace(valid.variant_results[0], variant_id="wrong"),
                    valid.variant_results[1],
                ),
            )


if __name__ == "__main__":
    unittest.main()
